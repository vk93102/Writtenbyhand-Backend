"""
Withdrawal Views - Manual UPI Payouts
Handles coin withdrawal requests for manual admin processing
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction as db_transaction
from django.utils import timezone
import logging

from ..models import UserCoins, CoinTransaction, CoinWithdrawal

logger = logging.getLogger(__name__)


@api_view(['POST'])
def withdraw_coins(request):
    """
    Withdraw coins as money via UPI (Manual Admin Processing)

    Endpoint: POST /api/wallet/withdraw/

    Business Rules:
    - Minimum withdrawal: 200 coins (₹20)
    - Conversion: 10 coins = ₹1
    - Method: UPI only
    - Coins deducted immediately, admin processes payout manually

    Request Body:
    {
        "upi_id": "user@paytm",
        "coins": 200,
        "user_id": "user_id"  // for unauthenticated testing
    }

    Response (Success):
    {
        "success": true,
        "withdrawal_id": "uuid",
        "coins_deducted": 200,
        "amount": 20.00,
        "upi_id": "user@paytm",
        "status": "pending",
        "message": "Withdrawal request submitted. Admin will process payment manually."
    }
    """
    try:
        logger.info(f"[WITHDRAW_COINS] Request received. Method: {request.method}, Content-Type: {request.content_type}")
        logger.info(f"[WITHDRAW_COINS] Raw body: {request.body}")
        logger.info(f"[WITHDRAW_COINS] Request data: {request.data}")
        
        # Extract user from token (assuming middleware sets request.user)
        user_id = str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else request.data.get('user_id')
        
        logger.info(f"[WITHDRAW_COINS] User ID: {user_id}, Authenticated: {hasattr(request, 'user') and request.user.is_authenticated}")
        
        if not user_id:
            logger.warning("[WITHDRAW_COINS] Missing user_id")
            return Response({
                'success': False,
                'error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Extract request data
        upi_id = request.data.get('upi_id', '').strip()
        coins = request.data.get('coins') or request.data.get('coins_amount')  # Support both parameters
        
        logger.info(f"[WITHDRAW_COINS] Extracted: upi_id={upi_id}, coins={coins}")
        
        # Validate required fields
        if not upi_id:
            logger.warning("[WITHDRAW_COINS] Missing UPI ID")
            return Response({
                'success': False,
                'error': 'UPI ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate UPI ID format (basic validation)
        if '@' not in upi_id or len(upi_id) < 5:
            logger.warning(f"[WITHDRAW_COINS] Invalid UPI format: {upi_id}")
            return Response({
                'success': False,
                'error': 'Invalid UPI ID format. Expected format: user@bank'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate coins amount
        try:
            coins = int(coins)
            logger.info(f"[WITHDRAW_COINS] Coins amount validated: {coins}")
            if coins < 200:
                logger.warning(f"[WITHDRAW_COINS] Coins below minimum: {coins} < 200")
                return Response({
                    'success': False,
                    'error': 'Minimum withdrawal is 200 coins (₹20)'
                }, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError) as e:
            logger.error(f"[WITHDRAW_COINS] Invalid coins amount: {coins}, error: {e}")
            return Response({
                'success': False,
                'error': 'Invalid coins amount'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get user's coin balance and validate withdrawal atomically
        logger.info(f"[WITHDRAW_COINS] Starting transaction to process withdrawal")
        with db_transaction.atomic():
            try:
                logger.info(f"[WITHDRAW_COINS] Fetching user coins for {user_id}")
                user_coins = UserCoins.objects.select_for_update().get(user_id=user_id)
                logger.info(f"[WITHDRAW_COINS] User coins found: total={user_coins.total_coins}, spent={user_coins.coins_spent}")
            except UserCoins.DoesNotExist:
                logger.error(f"[WITHDRAW_COINS] User coins not found for {user_id}")
                return Response({
                    'success': False,
                    'error': 'User has no coin balance'
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if user has enough coins
            if user_coins.total_coins < coins:
                logger.warning(f"[WITHDRAW_COINS] Insufficient balance: {user_coins.total_coins} < {coins}")
                return Response({
                    'success': False,
                    'error': f'Insufficient balance. Available: {user_coins.total_coins} coins, Requested: {coins} coins'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if balance after withdrawal is greater than 100
            remaining_balance = user_coins.total_coins - coins
            logger.info(f"[WITHDRAW_COINS] Balance check: remaining={remaining_balance}")
            if remaining_balance < 100:
                logger.warning(f"[WITHDRAW_COINS] Remaining balance too low: {remaining_balance} < 100")
                return Response({
                    'success': False,
                    'error': f'After withdrawal, your balance must be at least 100 coins. Current: {user_coins.total_coins}, Requested: {coins}, Remaining: {remaining_balance}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Calculate rupees amount (10 coins = ₹1)
            rupees_amount = coins / 10.0
            logger.info(f"[WITHDRAW_COINS] Processing withdrawal: {coins} coins = ₹{rupees_amount}")

            try:
                # Deduct coins and create withdrawal record
                user_coins.total_coins -= coins
                user_coins.coins_spent += coins
                user_coins.save()
                logger.info(f"[WITHDRAW_COINS] Coins deducted. New balance: total={user_coins.total_coins}, spent={user_coins.coins_spent}")

                withdrawal = CoinWithdrawal.objects.create(
                    user_id=user_id,
                    coins_amount=coins,
                    rupees_amount=rupees_amount,
                    upi_id=upi_id,
                    status='pending',  # Admin will review and process
                    razorpay_contact_id=None,
                    razorpay_fund_account_id=None,
                    razorpay_payout_id=None,
                    processed_at=None,
                    completed_at=None
                )
                logger.info(f"[WITHDRAW_COINS] Withdrawal record created: {withdrawal.id}")

                # Create transaction record
                CoinTransaction.objects.create(
                    user_coins=user_coins,
                    amount=coins,
                    transaction_type='withdrawal',
                    reason=f'UPI withdrawal to {upi_id} - ₹{rupees_amount} (PENDING ADMIN APPROVAL)'
                )
                logger.info(f"[WITHDRAW_COINS] Transaction record created")

                response_data = {
                    'success': True,
                    'withdrawal_id': str(withdrawal.id),
                    'coins_deducted': coins,
                    'amount': float(rupees_amount),
                    'upi_id': upi_id,
                    'remaining_balance': user_coins.total_coins,
                    'status': 'pending',
                    'message': 'Withdrawal request submitted successfully. Admin will review and process the payment manually.',
                    'conversion_rate': '10 coins = ₹1',
                    'note': 'Request is pending admin approval'
                }
                logger.info(f"[WITHDRAW_COINS] Success response: {response_data}")
                return Response(response_data, status=status.HTTP_201_CREATED)

            except Exception as e:
                # If anything fails, refund coins
                logger.error(f"[WITHDRAW_COINS] Failed to create withdrawal record: {str(e)}", exc_info=True)
                with db_transaction.atomic():
                    user_coins.total_coins += coins
                    user_coins.coins_spent -= coins
                    user_coins.save()
                    logger.info(f"[WITHDRAW_COINS] Refunded {coins} coins to user {user_id}")

                return Response({
                    'success': False,
                    'error': 'Failed to create withdrawal record',
                    'details': str(e),
                    'message': 'Coins have been refunded to your account'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.exception(f"[WITHDRAW_COINS] ERROR - Withdrawal request failed: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to process withdrawal request',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_withdrawal_history(request):
    """
    Get withdrawal history for authenticated user
    
    Endpoint: GET /api/wallet/withdrawals/
    
    Response:
    {
        "success": true,
        "withdrawals": [...],
        "total_withdrawn_coins": 1000,
        "total_withdrawn_rupees": 100.00
    }
    """
    try:
        user_id = str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else request.query_params.get('user_id')
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        withdrawals = CoinWithdrawal.objects.filter(user_id=user_id).order_by('-created_at')
        
        withdrawal_list = [{
            'withdrawal_id': str(w.id),
            'coins_amount': w.coins_amount,
            'rupees_amount': float(w.rupees_amount),
            'upi_id': w.upi_id,
            'status': w.status,
            'created_at': w.created_at,
            'completed_at': w.completed_at,
            'failure_reason': w.failure_reason
        } for w in withdrawals]
        
        total_coins = sum(w.coins_amount for w in withdrawals if w.status == 'completed')
        total_rupees = sum(float(w.rupees_amount) for w in withdrawals if w.status == 'completed')
        
        return Response({
            'success': True,
            'withdrawals': withdrawal_list,
            'count': len(withdrawal_list),
            'total_withdrawn_coins': total_coins,
            'total_withdrawn_rupees': total_rupees
        })
        
    except Exception as e:
        logger.error(f"Failed to get withdrawal history: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to get withdrawal history',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_withdrawal_status(request, withdrawal_id):
    """
    Get withdrawal status
    
    Endpoint: GET /api/wallet/withdrawal/<withdrawal_id>/
    
    Response:
    {
        "success": true,
        "withdrawal_id": "uuid",
        "status": "completed",
        "coins_amount": 500,
        "rupees_amount": 50.00
    }
    """
    try:
        withdrawal = CoinWithdrawal.objects.get(id=withdrawal_id)
        
        # Check if user has permission to view this withdrawal
        user_id = str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else request.query_params.get('user_id')
        if withdrawal.user_id != user_id and not request.user.is_staff:
            return Response({
                'success': False,
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return Response({
            'success': True,
            'withdrawal_id': str(withdrawal.id),
            'user_id': withdrawal.user_id,
            'coins_amount': withdrawal.coins_amount,
            'rupees_amount': float(withdrawal.rupees_amount),
            'upi_id': withdrawal.upi_id,
            'status': withdrawal.status,
            'created_at': withdrawal.created_at,
            'processed_at': withdrawal.processed_at,
            'completed_at': withdrawal.completed_at,
            'failure_reason': withdrawal.failure_reason,
            'razorpay_payout_id': withdrawal.razorpay_payout_id
        })
        
    except CoinWithdrawal.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Withdrawal not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Failed to get withdrawal status: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to get withdrawal status',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
