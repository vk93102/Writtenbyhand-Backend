"""
Razorpay Integration Views
Handles Razorpay payment orders, verification, and withdrawals
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import logging
import os
from django.contrib.auth.models import User
from django.conf import settings

from .models import Payment, UserCoins, CoinTransaction, CoinWithdrawal
from .services.payment_service import payment_service

logger = logging.getLogger(__name__)


def get_user_from_token(request):
    """
    Extract and validate JWT token from request header
    Returns User object or None if invalid/missing
    """
    try:
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]
        # IMPORTANT: Must use the same SECRET_KEY used for token encoding in simple_auth_views.py
        jwt_secret = getattr(settings, 'SECRET_KEY', 'your-secret-key-change-this')
        jwt_algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')

        # Decode token
        import jwt
        payload = jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm])

        # Get user
        user = User.objects.get(id=payload['user_id'])
        return user

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist):
        return None
    except Exception as e:
        logger.error(f"Error extracting user from token: {str(e)}")
        return None


@api_view(['POST'])
def create_razorpay_order(request):
    """
    Create a Razorpay order for one-time payments
    """
    try:
        # Get user from token
        user = get_user_from_token(request)
        if not user:
            return Response(
                {'error': 'Unauthorized', 'message': 'Invalid or missing token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get request data
        amount_rupees = request.data.get('amount')
        user_id = request.data.get('user_id')
        notes = request.data.get('notes', {})

        if not amount_rupees or not user_id:
            return Response(
                {'error': 'Missing required fields', 'message': 'amount and user_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create Razorpay order
        order_response = payment_service.create_order(
            amount=int(amount_rupees * 100),  # Convert to paise
            user_id=user_id,
            description=f"Payment by {user.username}",
            notes=notes
        )

        if not order_response['success']:
            logger.error(f"Failed to create order for user {user.id}: {order_response.get('error')}")
            return Response(
                {'error': 'Payment order creation failed', 'details': order_response.get('error')},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'success': True,
            'order_id': order_response['order_id'],
            'amount': amount_rupees,
            'currency': 'INR',
            'key_id': payment_service.get_key_id(),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error creating Razorpay order: {str(e)}")
        return Response(
            {'error': 'Internal server error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def verify_razorpay_payment(request):
    """
    Verify Razorpay payment signature
    """
    try:
        # Get user from token
        user = get_user_from_token(request)
        if not user:
            return Response(
                {'error': 'Unauthorized', 'message': 'Invalid or missing token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get verification data
        order_id = request.data.get('razorpay_order_id')
        payment_id = request.data.get('razorpay_payment_id')
        signature = request.data.get('razorpay_signature')

        if not all([order_id, payment_id, signature]):
            return Response(
                {'error': 'Missing required fields'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify payment
        verification_result = payment_service.verify_payment(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature
        )

        if verification_result['success']:
            return Response({
                'success': True,
                'message': 'Payment verified successfully'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': verification_result.get('error', 'Payment verification failed')
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_razorpay_key(request):
    """
    Get Razorpay public key for client-side checkout
    """
    try:
        key_data = payment_service.get_razorpay_key()
        return Response({
            'key_id': key_data['key_id']
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error getting Razorpay key: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_payment_status(request, order_id):
    """
    Get payment status by order ID
    """
    try:
        # Get user from token
        user = get_user_from_token(request)
        if not user:
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get payment status
        status_result = payment_service.get_order_status(order_id)

        return Response(status_result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_payment_history(request):
    """
    Get user's payment history
    """
    try:
        # Get user from token
        user = get_user_from_token(request)
        if not user:
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get payments for user
        payments = Payment.objects.filter(
            subscription__user_id=user.id
        ).order_by('-created_at')[:20]

        payment_data = [{
            'id': payment.id,
            'amount': payment.amount,
            'currency': payment.currency,
            'status': payment.status,
            'created_at': payment.created_at,
            'transaction_id': payment.transaction_id,
        } for payment in payments]

        return Response({
            'payments': payment_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting payment history: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def request_coin_withdrawal(request):
    """
    Request coin withdrawal - Convert coins to money

    Endpoint: POST /api/razorpay/withdraw/

    Conversion Rate: 10 coins = ₹1
    Minimum Withdrawal: 100 coins (₹10)

    Request Body:
    {
        "user_id": "user123",
        "coins_amount": 500,
        "payout_method": "upi",  // or "bank"
        "upi_id": "user@paytm",  // if payout_method is upi
        "account_holder_name": "John Doe",
        "account_number": "1234567890",  // if payout_method is bank
        "ifsc_code": "SBIN0001234"  // if payout_method is bank
    }

    Response (Success):
    {
        "success": true,
        "withdrawal_id": "uuid",
        "coins_deducted": 500,
        "amount": 50.00,
        "status": "pending",
    }
    """
    try:
        # Get user from token
        user = get_user_from_token(request)
        if not user:
            return Response(
                {'error': 'Unauthorized', 'message': 'Invalid or missing token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get request data
        user_id = request.data.get('user_id')
        coins_amount = request.data.get('coins_amount')
        payout_method = request.data.get('payout_method', 'upi')
        account_holder_name = request.data.get('account_holder_name', '')
        upi_id = request.data.get('upi_id')
        account_number = request.data.get('account_number')
        ifsc_code = request.data.get('ifsc_code')

        # Validate required fields
        if not user_id or not coins_amount:
            return Response(
                {'error': 'Missing required fields', 'message': 'user_id and coins_amount are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate coins amount
        try:
            coins_amount = int(coins_amount)
            if coins_amount < 100:
                return Response(
                    {'error': 'Invalid amount', 'message': 'Minimum withdrawal is 100 coins (₹10)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid coins amount'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate payout method
        if payout_method not in ['upi', 'bank']:
            return Response(
                {'error': 'Invalid payout method', 'message': 'Must be "upi" or "bank"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate payout details
        if payout_method == 'upi' and not upi_id:
            return Response(
                {'error': 'UPI ID required', 'message': 'UPI ID is required for UPI payouts'},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif payout_method == 'bank' and (not account_number or not ifsc_code):
            return Response(
                {'error': 'Bank details required', 'message': 'Account number and IFSC code are required for bank transfers'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get user's coin balance
        try:
            user_coins = UserCoins.objects.select_for_update().get(user_id=user_id)
        except UserCoins.DoesNotExist:
            return Response(
                {'error': 'No coin balance', 'message': 'User has no coin balance'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user has enough coins
        if user_coins.total_coins < coins_amount:
            return Response(
                {'error': 'Insufficient balance', 'message': f'Available: {user_coins.total_coins} coins'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check minimum balance after withdrawal
        remaining_balance = user_coins.total_coins - coins_amount
        if remaining_balance < 100:
            return Response(
                {'error': 'Invalid withdrawal', 'message': 'Must keep at least 100 coins after withdrawal'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate amount in rupees
        amount_rupees = coins_amount / 10.0

        # Create withdrawal record
        withdrawal = CoinWithdrawal.objects.create(
            user_id=user_id,
            coins_amount=coins_amount,
            rupees_amount=amount_rupees,
            upi_id=upi_id,
            status='pending'
        )

        # Deduct coins immediately
        user_coins.total_coins -= coins_amount
        user_coins.coins_spent += coins_amount
        user_coins.save()

        # Create transaction record
        CoinTransaction.objects.create(
            user_coins=user_coins,
            amount=-coins_amount,
            transaction_type='withdrawal',
            reason=f'Coin withdrawal - ₹{amount_rupees} via {payout_method.upper()}',
        )

        logger.info(f"Withdrawal created: {withdrawal.id} for user {user_id}, {coins_amount} coins")

        return Response({
            'success': True,
            'withdrawal_id': str(withdrawal.id),
            'coins_deducted': coins_amount,
            'amount': amount_rupees,
            'remaining_balance': user_coins.total_coins,
            'status': 'pending',
            'message': 'Withdrawal request submitted successfully. Payment will be processed within 24-48 hours.'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error processing withdrawal: {str(e)}")
        return Response(
            {'error': 'Internal server error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_withdrawal_history(request):
    """
    Get user's withdrawal history
    """
    try:
        # Get user from token
        user = get_user_from_token(request)
        if not user:
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {'error': 'User ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get withdrawals for user
        withdrawals = CoinWithdrawal.objects.filter(
            user_id=user_id
        ).order_by('-created_at')[:20]

        withdrawal_data = [{
            'id': str(w.id),
            'coins_amount': w.coins_amount,
            'amount_rupees': w.amount_rupees,

            'status': w.status,
            'created_at': w.created_at,
            'processed_at': w.processed_at,
        } for w in withdrawals]

        return Response({
            'withdrawals': withdrawal_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting withdrawal history: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_withdrawal_status(request, withdrawal_id):
    """
    Get withdrawal status by ID
    """
    try:
        # Get user from token
        user = get_user_from_token(request)
        if not user:
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            withdrawal = CoinWithdrawal.objects.get(id=withdrawal_id)
        except CoinWithdrawal.DoesNotExist:
            return Response(
                {'error': 'Withdrawal not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            'id': str(withdrawal.id),
            'coins_amount': withdrawal.coins_amount,
            'amount_rupees': withdrawal.amount_rupees,

            'status': withdrawal.status,
            'created_at': withdrawal.created_at,
            'processed_at': withdrawal.processed_at,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting withdrawal status: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def cancel_withdrawal(request, withdrawal_id):
    """
    Cancel pending withdrawal and refund coins
    """
    try:
        # Get user from token
        user = get_user_from_token(request)
        if not user:
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            withdrawal = CoinWithdrawal.objects.select_for_update().get(id=withdrawal_id)
        except CoinWithdrawal.DoesNotExist:
            return Response(
                {'error': 'Withdrawal not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if withdrawal can be cancelled
        if withdrawal.status != 'pending':
            return Response(
                {'error': 'Cannot cancel', 'message': f'Withdrawal is {withdrawal.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Refund coins
        try:
            user_coins = UserCoins.objects.select_for_update().get(user_id=withdrawal.user_id)
            user_coins.total_coins += withdrawal.coins_amount
            user_coins.coins_spent -= withdrawal.coins_amount
            user_coins.save()

            # Create refund transaction
            CoinTransaction.objects.create(
                user_coins=user_coins,
                amount=withdrawal.coins_amount,
                transaction_type='refund',
                reason=f'Withdrawal cancellation refund - ₹{withdrawal.rupees_amount}',
            )
        except UserCoins.DoesNotExist:
            return Response(
                {'error': 'User coins not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Update withdrawal status
        withdrawal.status = 'cancelled'
        withdrawal.save()

        return Response({
            'success': True,
            'message': f'Withdrawal cancelled. {withdrawal.coins_amount} coins refunded.',
            'refunded_coins': withdrawal.coins_amount
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error cancelling withdrawal: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def razorpay_webhook(request):
    """
    Handle Razorpay webhooks
    """
    try:
        # Webhook signature verification would go here
        # For now, just log the webhook data
        logger.info(f"Razorpay webhook received: {request.data}")

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error processing Razorpay webhook: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )