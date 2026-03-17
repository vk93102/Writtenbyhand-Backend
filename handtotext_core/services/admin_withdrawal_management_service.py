from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import logging

from ..models import CoinWithdrawal, UserCoins, CoinTransaction
from .withdrawal_service import WithdrawalService

logger = logging.getLogger(__name__)


class AdminWithdrawalService:
    @staticmethod
    def require_admin(request):
        try:
            if hasattr(request, 'user') and request.user.is_staff:
                return True
            admin_token = request.headers.get('X-Admin-Token')
            if admin_token:
                return True
        except Exception:
            pass
        return False

    @staticmethod
    @db_transaction.atomic
    def approve_withdrawal(withdrawal_id, admin_notes=""):
        logger.info(f"[ADMIN_WITHDRAWAL] Approving withdrawal {withdrawal_id}")

        try:
            withdrawal = CoinWithdrawal.objects.select_for_update().get(id=withdrawal_id)

            if withdrawal.status != 'pending':
                logger.warning(f"[ADMIN_WITHDRAWAL] Cannot approve {withdrawal.status} withdrawal")
                return {
                    'success': False,
                    'message': f'Withdrawal is already {withdrawal.status}.',
                    'withdrawal': None,
                    'error': f'Cannot approve {withdrawal.status} withdrawal.'
                }

            withdrawal.status = 'processing'
            withdrawal.processed_at = timezone.now()
            if admin_notes:
                withdrawal.admin_notes = admin_notes
            withdrawal.save()

            logger.info(f"[ADMIN_WITHDRAWAL] Withdrawal approved: {withdrawal_id}, status changed to processing")

            return {
                'success': True,
                'message': f'Withdrawal {withdrawal_id} approved and moved to processing.',
                'withdrawal': {
                    'withdrawal_id': str(withdrawal.id),
                    'user_id': withdrawal.user_id,
                    'coins_amount': withdrawal.coins_amount,
                    'rupees_amount': float(withdrawal.rupees_amount),
                    'upi_id': withdrawal.upi_id,
                    'status': withdrawal.status,
                    'processed_at': withdrawal.processed_at.isoformat() if withdrawal.processed_at else None,
                    'admin_notes': withdrawal.admin_notes
                },
                'error': None
            }

        except CoinWithdrawal.DoesNotExist:
            logger.error(f"[ADMIN_WITHDRAWAL] Withdrawal not found: {withdrawal_id}")
            return {
                'success': False,
                'message': 'Withdrawal not found.',
                'withdrawal': None,
                'error': 'Withdrawal ID does not exist.'
            }
        except Exception as e:
            logger.exception(f"[ADMIN_WITHDRAWAL] Error approving withdrawal: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to approve withdrawal.',
                'withdrawal': None,
                'error': str(e)
            }

    @staticmethod
    @db_transaction.atomic
    def reject_withdrawal(withdrawal_id, reason="", admin_notes=""):
        logger.info(f"[ADMIN_WITHDRAWAL] Rejecting withdrawal {withdrawal_id}, reason: {reason}")

        try:
            withdrawal = CoinWithdrawal.objects.select_for_update().get(id=withdrawal_id)

            # Can only reject pending or processing withdrawals
            if withdrawal.status not in ['pending', 'processing']:
                logger.warning(f"[ADMIN_WITHDRAWAL] Cannot reject {withdrawal.status} withdrawal")
                return {
                    'success': False,
                    'message': f'Withdrawal is {withdrawal.status}.',
                    'withdrawal': None,
                    'error': f'Cannot reject {withdrawal.status} withdrawal.'
                }

            # Get user coins
            user_coins = UserCoins.objects.select_for_update().get(user_id=withdrawal.user_id)

            # Refund coins
            original_balance = user_coins.total_coins
            user_coins.total_coins += withdrawal.coins_amount
            user_coins.coins_spent -= withdrawal.coins_amount
            user_coins.save()
            logger.info(f"[ADMIN_WITHDRAWAL] Refunded {withdrawal.coins_amount} coins to {withdrawal.user_id}")

            # Update withdrawal status
            withdrawal.status = 'rejected'
            withdrawal.failure_reason = reason or "Rejected by admin"
            withdrawal.processed_at = timezone.now()
            withdrawal.completed_at = timezone.now()
            if admin_notes:
                withdrawal.admin_notes = admin_notes
            withdrawal.save()

            # Create refund transaction
            CoinTransaction.objects.create(
                user_coins=user_coins,
                amount=withdrawal.coins_amount,
                transaction_type='refund',
                reason=f'Withdrawal rejected: {reason or "Admin rejection"}'
            )

            logger.info(f"[ADMIN_WITHDRAWAL] Withdrawal rejected: {withdrawal_id}, coins refunded")

            return {
                'success': True,
                'message': f'Withdrawal {withdrawal_id} rejected and {withdrawal.coins_amount} coins refunded to user.',
                'withdrawal': {
                    'withdrawal_id': str(withdrawal.id),
                    'user_id': withdrawal.user_id,
                    'coins_amount': withdrawal.coins_amount,
                    'rupees_amount': float(withdrawal.rupees_amount),
                    'upi_id': withdrawal.upi_id,
                    'status': withdrawal.status,
                    'failure_reason': withdrawal.failure_reason,
                    'completed_at': withdrawal.completed_at.isoformat() if withdrawal.completed_at else None,
                    'admin_notes': withdrawal.admin_notes
                },
                'error': None
            }

        except CoinWithdrawal.DoesNotExist:
            logger.error(f"[ADMIN_WITHDRAWAL] Withdrawal not found: {withdrawal_id}")
            return {
                'success': False,
                'message': 'Withdrawal not found.',
                'withdrawal': None,
                'error': 'Withdrawal ID does not exist.'
            }
        except UserCoins.DoesNotExist:
            logger.error(f"[ADMIN_WITHDRAWAL] User coins not found for withdrawal {withdrawal_id}")
            return {
                'success': False,
                'message': 'User coin balance not found.',
                'withdrawal': None,
                'error': 'Cannot refund coins to user.'
            }
        except Exception as e:
            logger.exception(f"[ADMIN_WITHDRAWAL] Error rejecting withdrawal: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to reject withdrawal.',
                'withdrawal': None,
                'error': str(e)
            }

    @staticmethod
    @db_transaction.atomic
    def delete_withdrawal(withdrawal_id):
        """
        Delete a withdrawal request (admin only)
        Refunds coins if withdrawal was pending
        
        Args:
            withdrawal_id (str): ID of withdrawal to delete
            
        Returns:
            dict: {
                'success': bool,
                'message': message,
                'error': error_message or None
            }
        """
        logger.info(f"[ADMIN_WITHDRAWAL] Deleting withdrawal {withdrawal_id}")

        try:
            withdrawal = CoinWithdrawal.objects.select_for_update().get(id=withdrawal_id)

            # Only pending or processing withdrawals should be deleted
            if withdrawal.status not in ['pending', 'processing']:
                logger.warning(f"[ADMIN_WITHDRAWAL] Cannot delete {withdrawal.status} withdrawal")
                return {
                    'success': False,
                    'message': f'Cannot delete {withdrawal.status} withdrawal.',
                    'error': f'Withdrawal is {withdrawal.status}.'
                }

            # Refund coins if withdrawal hasn't been completed
            if withdrawal.status in ['pending', 'processing']:
                try:
                    user_coins = UserCoins.objects.select_for_update().get(user_id=withdrawal.user_id)
                    user_coins.total_coins += withdrawal.coins_amount
                    user_coins.coins_spent -= withdrawal.coins_amount
                    user_coins.save()

                    CoinTransaction.objects.create(
                        user_coins=user_coins,
                        amount=withdrawal.coins_amount,
                        transaction_type='refund',
                        reason=f'Withdrawal deleted by admin: {withdrawal_id}'
                    )
                    logger.info(f"[ADMIN_WITHDRAWAL] Refunded {withdrawal.coins_amount} coins during deletion")
                except UserCoins.DoesNotExist:
                    logger.warning(f"[ADMIN_WITHDRAWAL] User coins not found during deletion, proceeding with deletion")

            # Delete withdrawal
            withdrawal.delete()
            logger.info(f"[ADMIN_WITHDRAWAL] Withdrawal deleted: {withdrawal_id}")

            return {
                'success': True,
                'message': f'Withdrawal {withdrawal_id} deleted successfully.',
                'error': None
            }

        except CoinWithdrawal.DoesNotExist:
            logger.warning(f"[ADMIN_WITHDRAWAL] Withdrawal not found: {withdrawal_id}")
            return {
                'success': False,
                'message': 'Withdrawal not found.',
                'error': 'Withdrawal ID does not exist.'
            }
        except Exception as e:
            logger.exception(f"[ADMIN_WITHDRAWAL] Error deleting withdrawal: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to delete withdrawal.',
                'error': str(e)
            }

    @staticmethod
    def mark_as_completed(withdrawal_id, admin_notes=""):
        """
        Mark withdrawal as completed (after payment processed)
        
        Args:
            withdrawal_id (str): ID of withdrawal to complete
            admin_notes (str): Optional notes about completion
            
        Returns:
            dict: success/error response
        """
        logger.info(f"[ADMIN_WITHDRAWAL] Marking withdrawal as completed: {withdrawal_id}")

        try:
            withdrawal = CoinWithdrawal.objects.select_for_update().get(id=withdrawal_id)

            if withdrawal.status == 'completed':
                return {
                    'success': False,
                    'message': 'Withdrawal is already completed.',
                    'error': 'Already completed'
                }

            withdrawal.status = 'completed'
            withdrawal.completed_at = timezone.now()
            if admin_notes:
                withdrawal.admin_notes = admin_notes
            withdrawal.save()

            logger.info(f"[ADMIN_WITHDRAWAL] Withdrawal marked as completed: {withdrawal_id}")

            return {
                'success': True,
                'message': f'Withdrawal {withdrawal_id} marked as completed.',
                'error': None
            }

        except CoinWithdrawal.DoesNotExist:
            logger.error(f"[ADMIN_WITHDRAWAL] Withdrawal not found: {withdrawal_id}")
            return {
                'success': False,
                'message': 'Withdrawal not found.',
                'error': 'ID does not exist'
            }
        except Exception as e:
            logger.exception(f"[ADMIN_WITHDRAWAL] Error completing withdrawal: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to complete withdrawal.',
                'error': str(e)
            }


# API Endpoints

@api_view(['POST'])
def api_approve_withdrawal(request, withdrawal_id):
    """
    Approve a withdrawal request
    
    Endpoint: POST /api/admin/withdrawal/approve/{withdrawal_id}/
    
    Request:
    {
        "admin_notes": "Payment details verified"
    }
    """
    try:
        if not AdminWithdrawalService.require_admin(request):
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)

        admin_notes = request.data.get('admin_notes', '')
        result = AdminWithdrawalService.approve_withdrawal(withdrawal_id, admin_notes)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception(f"[API] Error in approve_withdrawal: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def api_reject_withdrawal(request, withdrawal_id):
    """
    Reject a withdrawal request
    
    Endpoint: POST /api/admin/withdrawal/reject/{withdrawal_id}/
    
    Request:
    {
        "reason": "Invalid UPI ID",
        "admin_notes": "User requested cancellation"
    }
    """
    try:
        if not AdminWithdrawalService.require_admin(request):
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get('reason', '')
        admin_notes = request.data.get('admin_notes', '')
        result = AdminWithdrawalService.reject_withdrawal(withdrawal_id, reason, admin_notes)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception(f"[API] Error in reject_withdrawal: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
def api_delete_withdrawal(request, withdrawal_id):
    """
    Delete a withdrawal request (admin only)
    
    Endpoint: DELETE /api/admin/withdrawal/delete/{withdrawal_id}/
    """
    try:
        if not AdminWithdrawalService.require_admin(request):
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)

        result = AdminWithdrawalService.delete_withdrawal(withdrawal_id)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception(f"[API] Error in delete_withdrawal: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def api_complete_withdrawal(request, withdrawal_id):
    """
    Mark withdrawal as completed after payment
    
    Endpoint: POST /api/admin/withdrawal/complete/{withdrawal_id}/
    
    Request:
    {
        "admin_notes": "Payment processed via Razorpay"
    }
    """
    try:
        if not AdminWithdrawalService.require_admin(request):
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)

        admin_notes = request.data.get('admin_notes', '')
        result = AdminWithdrawalService.mark_as_completed(withdrawal_id, admin_notes)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception(f"[API] Error in complete_withdrawal: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
