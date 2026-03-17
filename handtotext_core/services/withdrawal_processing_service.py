"""
Withdrawal Service - Comprehensive Withdrawal Management
Handles coin withdrawal requests, processing, and admin operations
Production-ready code with atomic transactions and error handling
"""

from django.db import transaction as db_transaction
from django.utils import timezone
from django.db.models import Sum, F
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
import logging
import uuid

from ..models import UserCoins, CoinTransaction, CoinWithdrawal

logger = logging.getLogger(__name__)


class WithdrawalService:
    """
    Service class for handling all withdrawal operations
    Ensures atomic transactions and data consistency
    """

    # Constants
    CONVERSION_RATE = Decimal('10')  # 10 coins = ₹1
    MINIMUM_WITHDRAWAL = 200  # Minimum coins to withdraw
    MINIMUM_REMAINING_BALANCE = 100  # Minimum coins to keep after withdrawal

    @staticmethod
    def validate_withdrawal_amount(coins_amount):
        """
        Validate withdrawal amount
        Returns: (is_valid, error_message)
        """
        try:
            coins = int(coins_amount)
        except (ValueError, TypeError):
            return False, "Invalid coins amount. Must be an integer."

        if coins < WithdrawalService.MINIMUM_WITHDRAWAL:
            return False, f"Minimum withdrawal is {WithdrawalService.MINIMUM_WITHDRAWAL} coins (₹{WithdrawalService.MINIMUM_WITHDRAWAL / WithdrawalService.CONVERSION_RATE})"

        return True, None

    @staticmethod
    def validate_upi_id(upi_id):
        """
        Validate UPI ID format
        Returns: (is_valid, error_message)
        """
        if not upi_id or not isinstance(upi_id, str):
            return False, "UPI ID is required and must be a string."

        upi_id = upi_id.strip()

        # Basic UPI format validation
        if '@' not in upi_id or len(upi_id) < 5:
            return False, "Invalid UPI ID format (e.g., user@paytm, user@okhdfcbank)."

        return True, None

    @staticmethod
    @db_transaction.atomic
    def create_withdrawal_request(user_id, coins_amount, upi_id):
        """
        Create a withdrawal request with proper validation and coin deduction
        
        Args:
            user_id (str): User ID requesting withdrawal
            coins_amount (int): Number of coins to withdraw
            upi_id (str): UPI ID for payment
            
        Returns:
            dict: {
                'success': bool,
                'data': withdrawal_data or None,
                'error': error_message or None,
                'error_code': error_code or None
            }
        """
        logger.info(f"[WITHDRAWAL_SERVICE] Creating withdrawal: user={user_id}, coins={coins_amount}, upi={upi_id}")

        try:
            # Validate inputs
            valid, error = WithdrawalService.validate_withdrawal_amount(coins_amount)
            if not valid:
                logger.warning(f"[WITHDRAWAL_SERVICE] Invalid amount: {error}")
                return {
                    'success': False,
                    'data': None,
                    'error': error,
                    'error_code': 'INVALID_AMOUNT'
                }

            coins_amount = int(coins_amount)

            valid, error = WithdrawalService.validate_upi_id(upi_id)
            if not valid:
                logger.warning(f"[WITHDRAWAL_SERVICE] Invalid UPI: {error}")
                return {
                    'success': False,
                    'data': None,
                    'error': error,
                    'error_code': 'INVALID_UPI'
                }

            # Get user coins with lock
            try:
                user_coins = UserCoins.objects.select_for_update().get(user_id=str(user_id))
                logger.info(f"[WITHDRAWAL_SERVICE] User coins found: {user_coins.total_coins}")
            except UserCoins.DoesNotExist:
                logger.error(f"[WITHDRAWAL_SERVICE] No coin balance for user {user_id}")
                return {
                    'success': False,
                    'data': None,
                    'error': 'User has no coin balance record.',
                    'error_code': 'NO_BALANCE'
                }

            # Check sufficient balance
            if user_coins.total_coins < coins_amount:
                logger.warning(f"[WITHDRAWAL_SERVICE] Insufficient balance: {user_coins.total_coins} < {coins_amount}")
                return {
                    'success': False,
                    'data': None,
                    'error': f'Insufficient balance. Available: {user_coins.total_coins} coins.',
                    'error_code': 'INSUFFICIENT_BALANCE'
                }

            # Check minimum remaining balance
            remaining_balance = user_coins.total_coins - coins_amount
            if remaining_balance < WithdrawalService.MINIMUM_REMAINING_BALANCE:
                logger.warning(f"[WITHDRAWAL_SERVICE] Remaining balance too low: {remaining_balance}")
                return {
                    'success': False,
                    'data': None,
                    'error': f'After withdrawal, you must keep at least {WithdrawalService.MINIMUM_REMAINING_BALANCE} coins. Remaining would be: {remaining_balance}',
                    'error_code': 'BALANCE_TOO_LOW'
                }

            # Calculate rupees amount
            rupees_amount = Decimal(coins_amount) / WithdrawalService.CONVERSION_RATE

            # Deduct coins from user account
            user_coins.total_coins -= coins_amount
            user_coins.coins_spent += coins_amount
            user_coins.save()
            logger.info(f"[WITHDRAWAL_SERVICE] Coins deducted. New balance: {user_coins.total_coins}")

            # Create withdrawal record
            withdrawal = CoinWithdrawal.objects.create(
                id=uuid.uuid4(),
                user_id=str(user_id),
                coins_amount=coins_amount,
                rupees_amount=rupees_amount,
                upi_id=upi_id.strip(),
                status='pending',
                created_at=timezone.now()
            )
            logger.info(f"[WITHDRAWAL_SERVICE] Withdrawal created: {withdrawal.id}")

            # Create transaction record for audit trail
            CoinTransaction.objects.create(
                user_coins=user_coins,
                amount=coins_amount,
                transaction_type='withdrawal',
                reason=f'Coin withdrawal to {upi_id} - ₹{float(rupees_amount)} (Pending admin approval)'
            )
            logger.info(f"[WITHDRAWAL_SERVICE] Transaction record created")

            # Prepare response data
            response_data = {
                'withdrawal_id': str(withdrawal.id),
                'user_id': str(user_id),
                'coins_amount': coins_amount,
                'rupees_amount': float(rupees_amount),
                'upi_id': upi_id,
                'status': 'pending',
                'remaining_balance': user_coins.total_coins,
                'created_at': withdrawal.created_at.isoformat(),
                'conversion_rate': f'{int(WithdrawalService.CONVERSION_RATE)} coins = ₹1',
                'message': 'Withdrawal request submitted successfully. Admin will review and process within 24-48 hours.'
            }

            logger.info(f"[WITHDRAWAL_SERVICE] Withdrawal created successfully: {withdrawal.id}")
            return {
                'success': True,
                'data': response_data,
                'error': None,
                'error_code': None
            }

        except Exception as e:
            logger.exception(f"[WITHDRAWAL_SERVICE] CRITICAL ERROR creating withdrawal: {str(e)}")
            return {
                'success': False,
                'data': None,
                'error': 'Failed to process withdrawal request. Please try again.',
                'error_code': 'INTERNAL_ERROR'
            }

    @staticmethod
    def get_withdrawal_history(user_id, limit=50):
        """
        Get withdrawal history for a user
        
        Args:
            user_id (str): User ID
            limit (int): Max records to return
            
        Returns:
            dict: {
                'success': bool,
                'withdrawals': [],
                'total_withdrawn_coins': int,
                'total_withdrawn_rupees': float
            }
        """
        try:
            withdrawals = CoinWithdrawal.objects.filter(
                user_id=str(user_id)
            ).order_by('-created_at')[:limit]

            withdrawal_list = []
            for w in withdrawals:
                withdrawal_list.append({
                    'withdrawal_id': str(w.id),
                    'coins_amount': w.coins_amount,
                    'rupees_amount': float(w.rupees_amount),
                    'upi_id': w.upi_id,
                    'status': w.status,
                    'created_at': w.created_at.isoformat() if w.created_at else None,
                    'processed_at': w.processed_at.isoformat() if w.processed_at else None,
                    'completed_at': w.completed_at.isoformat() if w.completed_at else None,
                    'failure_reason': w.failure_reason
                })

            # Get totals
            stats = CoinWithdrawal.objects.filter(
                user_id=str(user_id),
                status='completed'
            ).aggregate(
                total_coins=Sum('coins_amount'),
                total_rupees=Sum('rupees_amount')
            )

            logger.info(f"[WITHDRAWAL_SERVICE] Retrieved {len(withdrawal_list)} withdrawals for user {user_id}")
            return {
                'success': True,
                'withdrawals': withdrawal_list,
                'total_withdrawn_coins': stats['total_coins'] or 0,
                'total_withdrawn_rupees': float(stats['total_rupees'] or 0)
            }

        except Exception as e:
            logger.exception(f"[WITHDRAWAL_SERVICE] Error getting withdrawal history: {str(e)}")
            return {
                'success': False,
                'withdrawals': [],
                'total_withdrawn_coins': 0,
                'total_withdrawn_rupees': 0
            }

    @staticmethod
    def get_withdrawal_status(withdrawal_id):
        """
        Get status of a specific withdrawal
        
        Args:
            withdrawal_id (str): Withdrawal ID
            
        Returns:
            dict: {
                'success': bool,
                'withdrawal': withdrawal_data or None,
                'error': error_message or None
            }
        """
        try:
            withdrawal = CoinWithdrawal.objects.get(id=withdrawal_id)
            logger.info(f"[WITHDRAWAL_SERVICE] Retrieved withdrawal {withdrawal_id}: status={withdrawal.status}")

            return {
                'success': True,
                'withdrawal': {
                    'withdrawal_id': str(withdrawal.id),
                    'user_id': withdrawal.user_id,
                    'coins_amount': withdrawal.coins_amount,
                    'rupees_amount': float(withdrawal.rupees_amount),
                    'upi_id': withdrawal.upi_id,
                    'status': withdrawal.status,
                    'created_at': withdrawal.created_at.isoformat() if withdrawal.created_at else None,
                    'processed_at': withdrawal.processed_at.isoformat() if withdrawal.processed_at else None,
                    'completed_at': withdrawal.completed_at.isoformat() if withdrawal.completed_at else None,
                    'failure_reason': withdrawal.failure_reason
                },
                'error': None
            }

        except CoinWithdrawal.DoesNotExist:
            logger.warning(f"[WITHDRAWAL_SERVICE] Withdrawal not found: {withdrawal_id}")
            return {
                'success': False,
                'withdrawal': None,
                'error': 'Withdrawal not found.'
            }
        except Exception as e:
            logger.exception(f"[WITHDRAWAL_SERVICE] Error getting withdrawal status: {str(e)}")
            return {
                'success': False,
                'withdrawal': None,
                'error': 'Failed to retrieve withdrawal status.'
            }

    @staticmethod
    @db_transaction.atomic
    def cancel_withdrawal(withdrawal_id):
        """
        Cancel a withdrawal and refund coins to user
        
        Args:
            withdrawal_id (str): Withdrawal ID to cancel
            
        Returns:
            dict: {
                'success': bool,
                'message': message,
                'error': error_message or None
            }
        """
        logger.info(f"[WITHDRAWAL_SERVICE] Attempting to cancel withdrawal {withdrawal_id}")

        try:
            withdrawal = CoinWithdrawal.objects.select_for_update().get(id=withdrawal_id)

            # Can only cancel pending or processing withdrawals
            if withdrawal.status not in ['pending', 'processing']:
                logger.warning(f"[WITHDRAWAL_SERVICE] Cannot cancel withdrawal with status: {withdrawal.status}")
                return {
                    'success': False,
                    'message': f'Cannot cancel {withdrawal.status} withdrawal.',
                    'error': f'Withdrawal is {withdrawal.status}.'
                }

            # Get user coins
            user_coins = UserCoins.objects.select_for_update().get(user_id=withdrawal.user_id)

            # Refund coins
            original_balance = user_coins.total_coins
            user_coins.total_coins += withdrawal.coins_amount
            user_coins.coins_spent -= withdrawal.coins_amount
            user_coins.save()
            logger.info(f"[WITHDRAWAL_SERVICE] Refunded {withdrawal.coins_amount} coins. Balance: {original_balance} → {user_coins.total_coins}")

            # Update withdrawal status
            withdrawal.status = 'cancelled'
            withdrawal.completed_at = timezone.now()
            withdrawal.save()

            # Create refund transaction
            CoinTransaction.objects.create(
                user_coins=user_coins,
                amount=withdrawal.coins_amount,
                transaction_type='refund',
                reason=f'Withdrawal cancelled: {withdrawal_id}'
            )

            logger.info(f"[WITHDRAWAL_SERVICE] Withdrawal cancelled successfully: {withdrawal_id}")
            return {
                'success': True,
                'message': f'Withdrawal cancelled. {withdrawal.coins_amount} coins refunded to user.',
                'error': None
            }

        except CoinWithdrawal.DoesNotExist:
            logger.error(f"[WITHDRAWAL_SERVICE] Withdrawal not found: {withdrawal_id}")
            return {
                'success': False,
                'message': 'Withdrawal not found.',
                'error': 'Withdrawal ID does not exist.'
            }
        except UserCoins.DoesNotExist:
            logger.error(f"[WITHDRAWAL_SERVICE] User coins not found for withdrawal {withdrawal_id}")
            return {
                'success': False,
                'message': 'User coin balance not found.',
                'error': 'Cannot refund coins.'
            }
        except Exception as e:
            logger.exception(f"[WITHDRAWAL_SERVICE] Error cancelling withdrawal: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to cancel withdrawal.',
                'error': str(e)
            }

    @staticmethod
    def get_pending_withdrawals(limit=100):
        """
        Get all pending withdrawals for admin review
        
        Args:
            limit (int): Max records to return
            
        Returns:
            dict: {
                'success': bool,
                'withdrawals': [],
                'count': int,
                'total_pending_amount': float
            }
        """
        try:
            withdrawals = CoinWithdrawal.objects.filter(
                status='pending'
            ).order_by('created_at')[:limit]

            withdrawal_list = []
            for w in withdrawals:
                withdrawal_list.append({
                    'withdrawal_id': str(w.id),
                    'user_id': w.user_id,
                    'coins_amount': w.coins_amount,
                    'rupees_amount': float(w.rupees_amount),
                    'upi_id': w.upi_id,
                    'created_at': w.created_at.isoformat() if w.created_at else None,
                    'status': w.status
                })

            # Get total pending amount
            total_stats = CoinWithdrawal.objects.filter(
                status='pending'
            ).aggregate(
                total_rupees=Sum('rupees_amount')
            )

            logger.info(f"[WITHDRAWAL_SERVICE] Retrieved {len(withdrawal_list)} pending withdrawals")
            return {
                'success': True,
                'withdrawals': withdrawal_list,
                'count': len(withdrawal_list),
                'total_pending_amount': float(total_stats['total_rupees'] or 0)
            }

        except Exception as e:
            logger.exception(f"[WITHDRAWAL_SERVICE] Error getting pending withdrawals: {str(e)}")
            return {
                'success': False,
                'withdrawals': [],
                'count': 0,
                'total_pending_amount': 0
            }

    @staticmethod
    def get_withdrawal_by_id(withdrawal_id):
        """Get withdrawal record by ID (for admin)"""
        try:
            return CoinWithdrawal.objects.get(id=withdrawal_id)
        except CoinWithdrawal.DoesNotExist:
            return None


# API Endpoints

@api_view(['POST'])
def api_create_withdrawal(request):
    """
    Create a withdrawal request
    
    Endpoint: POST /api/withdrawal/create/
    
    Request:
    {
        "user_id": "user123",
        "coins_amount": 500,
        "upi_id": "user@paytm"
    }
    """
    try:
        user_id = request.data.get('user_id')
        coins_amount = request.data.get('coins_amount')
        upi_id = request.data.get('upi_id')

        if not all([user_id, coins_amount, upi_id]):
            return Response({
                'success': False,
                'error': 'Missing required fields: user_id, coins_amount, upi_id'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = WithdrawalService.create_withdrawal_request(user_id, coins_amount, upi_id)

        if result['success']:
            return Response(result['data'], status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': result['error'],
                'error_code': result['error_code']
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception(f"[API] Error in create_withdrawal: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def api_get_withdrawal_history(request):
    """
    Get withdrawal history for a user
    
    Endpoint: GET /api/withdrawal/history/?user_id=user123&limit=50
    """
    try:
        user_id = request.query_params.get('user_id')
        limit = request.query_params.get('limit', 50)

        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            limit = int(limit)
        except ValueError:
            limit = 50

        result = WithdrawalService.get_withdrawal_history(user_id, limit)
        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(f"[API] Error in get_withdrawal_history: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def api_get_withdrawal_status(request, withdrawal_id):
    """
    Get status of a specific withdrawal
    
    Endpoint: GET /api/withdrawal/status/{withdrawal_id}/
    """
    try:
        result = WithdrawalService.get_withdrawal_status(withdrawal_id)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.exception(f"[API] Error in get_withdrawal_status: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def api_cancel_withdrawal(request, withdrawal_id):
    """
    Cancel a withdrawal and refund coins
    
    Endpoint: POST /api/withdrawal/cancel/{withdrawal_id}/
    """
    try:
        result = WithdrawalService.cancel_withdrawal(withdrawal_id)

        if result['success']:
            return Response({
                'success': True,
                'message': result['message']
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception(f"[API] Error in cancel_withdrawal: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def api_get_pending_withdrawals(request):
    """
    Get all pending withdrawals for admin
    
    Endpoint: GET /api/withdrawal/pending/?limit=100
    """
    try:
        # Check if user is admin (you can add authentication here)
        limit = request.query_params.get('limit', 100)

        try:
            limit = int(limit)
        except ValueError:
            limit = 100

        result = WithdrawalService.get_pending_withdrawals(limit)
        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(f"[API] Error in get_pending_withdrawals: {str(e)}")
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
