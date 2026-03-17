"""
Payment Views for Razorpay Integration
Handles payment order creation, verification, and processing
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging
import os
import jwt
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import Payment, UserSubscription
from .services.payment_service import payment_service

logger = logging.getLogger(__name__)


def get_user_from_token(request):
    """
    Extract and validate JWT token from request header
    Returns User object or None if invalid/missing
    Supports Bearer token format
    """
    try:
        auth_header = request.META.get('HTTP_AUTHORIZATION', '').strip()
        
        # Check if header exists
        if not auth_header:
            logger.warning("No Authorization header found in request")
            logger.warning(f"Available headers: {list(request.META.keys())}")
            return None
        
        logger.info(f"[TOKEN_DEBUG] Auth header found: {auth_header[:50]}...")
        
        # Extract token from Bearer format
        if not auth_header.startswith('Bearer '):
            logger.warning(f"Invalid auth header format: {auth_header[:20]}...")
            return None
        
        token = auth_header.split(' ')[1].strip()
        logger.info(f"[TOKEN_DEBUG] Token extracted, length: {len(token)}")
        
        if not token:
            logger.warning("Empty token in Authorization header")
            return None
        
        # Get JWT configuration from settings
        # IMPORTANT: Must use the same SECRET_KEY used for token encoding in simple_auth_views.py
        jwt_secret = getattr(settings, 'SECRET_KEY', 'your-secret-key-change-this')
        jwt_algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
        
        logger.info(f"[TOKEN_DEBUG] Using SECRET_KEY length: {len(jwt_secret)}")
        logger.info(f"[TOKEN_DEBUG] Using algorithm: {jwt_algorithm}")
        
        # Decode token
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm])
            logger.info(f"[TOKEN_DEBUG] JWT decoded successfully. Payload: {payload}")
        except jwt.InvalidAlgorithmError:
            # Try with HS256 if configured algorithm fails
            logger.warning(f"Algorithm {jwt_algorithm} failed, trying HS256")
            payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])
        except jwt.DecodeError as e:
            logger.error(f"JWT decode error: {str(e)}. Token length: {len(token)}, Secret length: {len(jwt_secret)}")
            raise
        
        # Extract user_id from payload (support different key names)
        user_id = payload.get('user_id') or payload.get('id') or payload.get('sub')
        
        if not user_id:
            logger.error(f"No user_id found in token payload: {list(payload.keys())}")
            return None
        
        # Get user
        user = User.objects.get(id=user_id)
        logger.info(f"User {user_id} authenticated successfully")
        return user
    
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {str(e)}")
        return None
    except User.DoesNotExist:
        logger.warning(f"User not found for token")
        return None
    except Exception as e:
        logger.error(f"Unexpected error extracting user from token: {str(e)}", exc_info=True)
        return None
        return None


class CreatePaymentOrderView(APIView):
    """
    Create a Razorpay payment order
    
    Request:
        POST /api/payment/create-order/
        {
            "plan": "premium",  # 'premium', 'annual'
            "auto_pay": true
        }
    
    Response:
        {
            "success": true,
            "order_id": "order_xxxxx",
            "amount": 199,
            "currency": "INR",
            "key_id": "rzp_live_xxxxx"
        }
    """
    
    def post(self, request):
        """Create Razorpay order - supports both authenticated users and guest users with user_id"""
        try:
            logger.info(f"[CREATE_PAYMENT_ORDER] Request received. Method: {request.method}")
            logger.info(f"[CREATE_PAYMENT_ORDER] Headers: Authorization present: {'HTTP_AUTHORIZATION' in request.META}")
            logger.info(f"[CREATE_PAYMENT_ORDER] Request data: {request.data}")
            
            # Get user from token OR user_id from request body (for guest users)
            user = get_user_from_token(request)
            user_id = None
            
            if user:
                user_id = str(user.id)
                logger.info(f"[CREATE_PAYMENT_ORDER] Authenticated user from token: {user_id}")
            else:
                # Try to get user_id from request body (for guest users)
                user_id = request.data.get('user_id')
                if user_id:
                    logger.info(f"[CREATE_PAYMENT_ORDER] Guest user from request body: {user_id}")
                else:
                    logger.error("[CREATE_PAYMENT_ORDER] No user authentication - neither token nor user_id provided")
                    return Response(
                        {'error': 'Unauthorized', 'message': 'Authentication required', 'details': 'Please provide either Bearer token or user_id in request body'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            
            logger.info(f"[CREATE_PAYMENT_ORDER] Creating payment order for user: {user_id}")
            
            # Get request data
            plan = request.data.get('plan', 'premium')
            auto_pay = request.data.get('auto_pay', False)
            
            logger.debug(f"[CREATE_PAYMENT_ORDER] Plan: {plan}, Auto-pay: {auto_pay}")
            
            # Define pricing
            pricing = {
                'premium': {'amount': 1, 'description': 'Premium Monthly Plan - ₹199/month'},
                'premium_annual': {'amount':199, 'description': 'Premium Annual Plan - ₹1990/year'},
            }
            
            if plan not in pricing:
                logger.warning(f"[CREATE_PAYMENT_ORDER] Invalid plan requested: {plan}")
                return Response(
                    {'error': 'Invalid plan', 'message': f'Plan must be one of {list(pricing.keys())}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get amount for plan
            plan_info = pricing[plan]
            amount = plan_info['amount']
            
            logger.info(f"[CREATE_PAYMENT_ORDER] Processing payment: amount={amount}, plan={plan}, user_id={user_id}")
            
            # Check if user already has an active subscription for the SAME plan (prevent duplicates, but allow upgrades)
            try:
                existing_subscription = UserSubscription.objects.get(user_id=user_id)
                if existing_subscription.subscription_status == 'active' and existing_subscription.plan == plan:
                    # Same plan - reject as duplicate
                    logger.warning(f"[CREATE_PAYMENT_ORDER] User {user_id} already has active {plan} subscription - duplicate attempt")
                    return Response(
                        {
                            'error': 'Already Subscribed',
                            'message': f'User already has an active {plan} subscription',
                            'current_plan': existing_subscription.plan,
                            'is_trial': existing_subscription.is_trial,
                            'trial_end_date': existing_subscription.trial_end_date.isoformat() if existing_subscription.trial_end_date else None,
                            'next_billing_date': existing_subscription.next_billing_date.isoformat() if existing_subscription.next_billing_date else None,
                            'next_billing_amount': 99,
                            'subscription_status': existing_subscription.subscription_status,
                            'days_until_next_billing': max(0, (existing_subscription.next_billing_date - timezone.now()).days) if existing_subscription.next_billing_date else 0
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                elif existing_subscription.subscription_status == 'active' and existing_subscription.plan != plan:
                    # Different plan - allow upgrade
                    logger.info(f"[CREATE_PAYMENT_ORDER] User {user_id} upgrading from {existing_subscription.plan} to {plan}")
            except UserSubscription.DoesNotExist:
                pass  # New user, proceed with order creation
            
            # Create Razorpay order
            order_response = payment_service.create_order(
                amount=amount,
                user_id=user_id,
                plan_type=plan,
                description=plan_info['description']
            )
            
            if not order_response['success']:
                logger.error(f"[CREATE_PAYMENT_ORDER] Failed to create order for user {user_id}: {order_response.get('error')}")
                return Response(
                    {'error': 'Payment order creation failed', 'details': order_response.get('error')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create Payment record in database (status: pending)
            try:
                subscription = UserSubscription.objects.get(user_id=user_id)
                logger.info(f"[CREATE_PAYMENT_ORDER] Found existing subscription for user {user_id}")
            except UserSubscription.DoesNotExist:
                # Create subscription if not exists
                logger.info(f"[CREATE_PAYMENT_ORDER] Creating new subscription for user {user_id}")
                subscription = UserSubscription.objects.create(
                    user_id=user_id,
                    plan='free'
                )
            
            # Create payment record
            payment = Payment.objects.create(
                subscription=subscription,
                amount=amount,
                currency='INR',
                status='pending',
                payment_method='razorpay',
                transaction_id=order_response['order_id'],  # Store order_id as transaction_id initially
                razorpay_order_id=order_response['order_id'],
                billing_cycle_start=timezone.now(),
                billing_cycle_end=timezone.now() + (
                    timedelta(days=365) if 'annual' in plan else timedelta(days=30)
                )
            )
            
            logger.info(f"[CREATE_PAYMENT_ORDER] Payment record created: {payment.id} for user {user_id}, order_id: {order_response['order_id']}")
            
            # Return response with Razorpay key and order details
            response_data = {
                'success': True,
                'order_id': order_response['order_id'],
                'amount': order_response['amount'],
                'amount_paise': order_response['amount_paise'],
                'currency': order_response['currency'],
                'key_id': payment_service.key_id,
                'plan': plan,
                'payment_record_id': str(payment.id)
            }
            logger.info(f"[CREATE_PAYMENT_ORDER] Success response: {response_data}")
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.exception(f"[CREATE_PAYMENT_ORDER] ERROR creating payment order: {str(e)}")
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VerifyPaymentView(APIView):
    """
    Verify Razorpay payment signature
    This is called after user completes payment on frontend
    
    Request:
        POST /api/payment/verify/
        {
            "razorpay_order_id": "order_xxxxx",
            "razorpay_payment_id": "pay_xxxxx",
            "razorpay_signature": "signature_xxxxx"
        }
    
    Response:
        {
            "success": true,
            "message": "Payment verified successfully",
            "payment_id": "...",
            "subscription_updated": true
        }
    """
    
    def post(self, request):
        """Verify payment and update subscription"""
        try:
            # Get user from token OR user_id from request body
            user = get_user_from_token(request)
            user_id = None
            
            if user:
                user_id = str(user.id)
                logger.info(f"[VERIFY_PAYMENT] Authenticated user from token: {user_id}")
            else:
                # Try to get user_id from request body (for flexibility)
                user_id = request.data.get('user_id')
                if user_id:
                    logger.info(f"[VERIFY_PAYMENT] Using user_id from request body: {user_id}")
                    try:
                        user = User.objects.get(id=user_id)
                    except User.DoesNotExist:
                        user = None
                else:
                    logger.warning("[VERIFY_PAYMENT] No token or user_id provided")
            
            if not user and not user_id:
                return Response(
                    {'error': 'Unauthorized', 'message': 'Invalid or missing token. Provide either Bearer token or user_id in request body'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get payment details from request
            order_id = request.data.get('razorpay_order_id')
            payment_id = request.data.get('razorpay_payment_id')
            signature = request.data.get('razorpay_signature')
            
            if not all([order_id, payment_id, signature]):
                return Response(
                    {'error': 'Missing payment details'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify payment signature
            is_valid = payment_service.verify_payment_signature(order_id, payment_id, signature)
            
            if not is_valid:
                logger.warning(f"Invalid payment signature for order {order_id}")
                return Response(
                    {'error': 'Payment verification failed', 'message': 'Invalid signature'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if this is a test payment (for local testing)
            is_test_payment = payment_id.startswith('pay_test_')
            
            # Get payment details from Razorpay (skip for test payments)
            if is_test_payment:
                logger.info(f"Test payment detected: {payment_id}. Skipping Razorpay API call.")
                payment_details = {
                    'success': True,
                    'status': 'captured',
                    'amount': 100  # Test amount in paise
                }
            else:
                payment_details = payment_service.get_payment_details(payment_id)
            
            if not payment_details['success']:
                logger.error(f"Failed to get payment details for {payment_id}")
                return Response(
                    {'error': 'Could not fetch payment details'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update payment record in database
            try:
                payment = Payment.objects.get(razorpay_order_id=order_id)
            except Payment.DoesNotExist:
                logger.error(f"Payment record not found for order {order_id}")
                return Response(
                    {'error': 'Payment record not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Update payment with Razorpay details
            payment.razorpay_payment_id = payment_id
            payment.status = 'completed' if payment_details['status'] == 'captured' else payment_details['status']
            payment.transaction_id = payment_id
            payment.updated_at = timezone.now()
            payment.save()
            
            # Update subscription to premium if payment successful
            if payment.status == 'completed':
                subscription = payment.subscription
                subscription.plan = 'premium'
                subscription.auto_pay_enabled = request.data.get('auto_pay', False)
                subscription.last_payment_date = timezone.now()
                subscription.next_billing_date = timezone.now() + timedelta(days=30)
                subscription.save()
                
                logger.info(f"Subscription upgraded to premium for user {user.id}")
            
            return Response(
                {
                    'success': True,
                    'message': 'Payment verified successfully',
                    'payment_id': payment_id,
                    'status': payment.status,
                    'subscription_updated': True,
                    'plan': subscription.plan
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return Response(
                {'error': 'Payment verification failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentStatusView(APIView):
    """
    Get payment status
    
    Request:
        GET /api/payment/status/<order_id>/
    
    Response:
        {
            "success": true,
            "payment": {
                "id": "...",
                "amount": 199,
                "status": "completed",
                "created_at": "...",
                "razorpay_order_id": "...",
                "razorpay_payment_id": "..."
            }
        }
    """
    
    def get(self, request, order_id=None):
        """Get payment status"""
        try:
            # Get user from token
            user = get_user_from_token(request)
            if not user:
                return Response(
                    {'error': 'Unauthorized'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get order_id from query params or URL
            order_id = order_id or request.query_params.get('order_id')
            
            if not order_id:
                return Response(
                    {'error': 'order_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get payment from database
            try:
                payment = Payment.objects.get(razorpay_order_id=order_id)
            except Payment.DoesNotExist:
                return Response(
                    {'error': 'Payment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(
                {
                    'success': True,
                    'payment': {
                        'id': str(payment.id),
                        'amount': float(payment.amount),
                        'currency': payment.currency,
                        'status': payment.status,
                        'payment_method': payment.payment_method,
                        'razorpay_order_id': payment.razorpay_order_id,
                        'razorpay_payment_id': payment.razorpay_payment_id,
                        'created_at': payment.created_at.isoformat(),
                        'updated_at': payment.updated_at.isoformat()
                    }
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(f"Error getting payment status: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentHistoryView(APIView):
    """
    Get payment history for user
    
    Request:
        GET /api/payment/history/
    
    Response:
        {
            "success": true,
            "payments": [
                {
                    "id": "...",
                    "amount": 199,
                    "status": "completed",
                    "created_at": "...",
                    "razorpay_payment_id": "..."
                }
            ]
        }
    """
    
    def get(self, request):
        """Get user's payment history"""
        try:
            # Get user from token
            user = get_user_from_token(request)
            if not user:
                return Response(
                    {'error': 'Unauthorized'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get subscription
            try:
                subscription = UserSubscription.objects.get(user_id=user.id)
            except UserSubscription.DoesNotExist:
                return Response(
                    {
                        'success': True,
                        'payments': []
                    },
                    status=status.HTTP_200_OK
                )
            
            # Get payments
            payments = Payment.objects.filter(subscription=subscription).order_by('-created_at')
            
            payment_list = [
                {
                    'id': str(payment.id),
                    'amount': float(payment.amount),
                    'currency': payment.currency,
                    'status': payment.status,
                    'payment_method': payment.payment_method,
                    'razorpay_payment_id': payment.razorpay_payment_id or 'N/A',
                    'created_at': payment.created_at.isoformat(),
                    'billing_cycle': {
                        'start': payment.billing_cycle_start.isoformat(),
                        'end': payment.billing_cycle_end.isoformat()
                    }
                }
                for payment in payments
            ]
            
            return Response(
                {
                    'success': True,
                    'total_payments': len(payment_list),
                    'payments': payment_list
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(f"Error getting payment history: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RefundPaymentView(APIView):
    """
    Request a refund for a payment
    
    Request:
        POST /api/payment/refund/
        {
            "payment_id": "...",
            "reason": "Not satisfied with service"
        }
    
    Response:
        {
            "success": true,
            "refund_id": "rfnd_xxxxx",
            "message": "Refund initiated successfully"
        }
    """
    
    def post(self, request):
        """Process refund request"""
        try:
            # Get user from token
            user = get_user_from_token(request)
            if not user:
                return Response(
                    {'error': 'Unauthorized'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get payment details
            payment_id = request.data.get('payment_id')
            reason = request.data.get('reason', 'User requested refund')
            
            if not payment_id:
                return Response(
                    {'error': 'payment_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get payment from database
            try:
                payment = Payment.objects.get(id=payment_id)
            except Payment.DoesNotExist:
                return Response(
                    {'error': 'Payment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if already refunded
            if payment.status == 'refunded':
                return Response(
                    {'error': 'Payment already refunded'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if payment is completed
            if payment.status != 'completed':
                return Response(
                    {'error': 'Only completed payments can be refunded'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process refund via Razorpay
            refund_response = payment_service.refund_payment(
                payment.razorpay_payment_id,
                amount=payment.amount,
                reason=reason
            )
            
            if not refund_response['success']:
                logger.error(f"Failed to process refund for payment {payment_id}")
                return Response(
                    {'error': 'Refund processing failed', 'details': refund_response.get('error')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update payment status
            payment.status = 'refunded'
            payment.updated_at = timezone.now()
            payment.save()
            
            # Update subscription back to free
            subscription = payment.subscription
            subscription.plan = 'free'
            subscription.save()
            
            logger.info(f"Refund processed for payment {payment_id}: {refund_response['refund_id']}")
            
            return Response(
                {
                    'success': True,
                    'message': 'Refund initiated successfully',
                    'refund_id': refund_response['refund_id'],
                    'amount': float(payment.amount),
                    'status': payment.status
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}")
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RazorpayKeyView(APIView):
    """
    Get Razorpay public key for frontend
    
    Request:
        GET /api/payment/razorpay-key/
    
    Response:
        {
            "key_id": "rzp_live_xxxxx"
        }
    """
    
    def get(self, request):
        """Get Razorpay public key"""
        try:
            key_id = payment_service.key_id
            
            return Response(
                {
                    'success': True,
                    'key_id': key_id
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(f"Error getting Razorpay key: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
