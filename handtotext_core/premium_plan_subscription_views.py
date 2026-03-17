"""
Premium Subscription with Razorpay Integration
Handles ₹1 for first month, then ₹99/month auto-pay
"""
import razorpay
import hmac
import hashlib
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from django.db import transaction as db_transaction
from .models import (
    UserSubscription, 
    Payment, 
    SubscriptionPlan,
    RazorpayOrder
)

logger = logging.getLogger(__name__)

# Initialize Razorpay client
try:
    razorpay_client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    logger.info("Razorpay client initialized for subscriptions")
except Exception as e:
    logger.error(f"Failed to initialize Razorpay client: {e}")
    razorpay_client = None


class GetSubscriptionPlansView(APIView):
    """
    Get available subscription plans
    GET /api/subscription/plans/
    """
    parser_classes = [JSONParser]
    
    def get(self, request):
        try:
            # Initialize default plans if they don't exist
            SubscriptionPlan.initialize_default_plans()
            
            plans = SubscriptionPlan.objects.filter(is_active=True)
            plans_data = []
            
            for plan in plans:
                plans_data.append({
                    'id': str(plan.id),
                    'name': plan.name,
                    'display_name': plan.display_name,
                    'description': plan.description,
                    'first_month_price': float(plan.first_month_price),
                    'recurring_price': float(plan.recurring_price),
                    'currency': plan.currency,
                    'features': {
                        'mock_test': 'Unlimited' if plan.mock_test_limit is None else f'{plan.mock_test_limit} per month',
                        'quiz': 'Unlimited' if plan.quiz_limit is None else f'{plan.quiz_limit} per month',
                        'flashcards': 'Unlimited' if plan.flashcards_limit is None else f'{plan.flashcards_limit}',
                        'ask_question': 'Unlimited' if plan.ask_question_limit is None else f'{plan.ask_question_limit} per month',
                        'predicted_questions': 'Unlimited' if plan.predicted_questions_limit is None else f'{plan.predicted_questions_limit}',
                        'youtube_summarizer': 'Unlimited' if plan.youtube_summarizer_limit is None else f'{plan.youtube_summarizer_limit} videos per month',
                        'pyqs': 'Unlimited' if plan.pyq_features_limit is None else f'{plan.pyq_features_limit}',
                    }
                })
            
            return Response({
                'success': True,
                'plans': plans_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting subscription plans: {e}", exc_info=True)
            return Response({
                'error': 'Failed to get subscription plans',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def create_subscription_order(request):
    """
    Create Razorpay order for subscription
    
    POST /api/subscription/create-order/
    
    Request Body:
    {
        "user_id": "user123",
        "plan_name": "premium"
    }
    
    Response:
    {
        "success": true,
        "order_id": "order_xyz",
        "amount": 100,  // ₹1 in paise for first month
        "currency": "INR",
        "key_id": "rzp_test_xxx",
        "is_trial": true,
        "trial_price": 1.00,
        "recurring_price": 99.00
    }
    """
    try:
        if not razorpay_client:
            return Response({
                'success': False,
                'error': 'Payment gateway not configured'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        user_id = request.data.get('user_id')
        plan_name = request.data.get('plan_name', 'premium')
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get subscription and plan
        subscription, created = UserSubscription.objects.get_or_create(
            user_id=user_id,
            defaults={'plan': 'free'}
        )
        
        if subscription.plan == 'premium' and not created:
            return Response({
                'success': False,
                'error': 'User already has premium subscription'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        plan = SubscriptionPlan.objects.get(name=plan_name)
        
        # Determine amount (first month or recurring)
        amount_rupees = float(plan.first_month_price)
        is_trial = True
        
        # Convert to paise (smallest currency unit)
        amount_paise = int(amount_rupees * 100)
        
        # Create Razorpay order
        razorpay_order = razorpay_client.order.create({
            'amount': amount_paise,
            'currency': plan.currency,
            'receipt': f'sub_{user_id}_{int(timezone.now().timestamp())}',
            'notes': {
                'user_id': user_id,
                'plan': plan_name,
                'subscription_type': 'first_month' if is_trial else 'recurring',
                'amount_rupees': str(amount_rupees)
            }
        })
        
        # Save order to database
        now = timezone.now()
        billing_start = now
        billing_end = now + timedelta(days=30)
        
        with db_transaction.atomic():
            # Create RazorpayOrder record
            order = RazorpayOrder.objects.create(
                order_id=razorpay_order['id'],
                user_id=user_id,
                amount=amount_rupees,
                currency=plan.currency,
                status='created',
                notes={'plan': plan_name, 'subscription': True}
            )
            
            logger.info(f"Created subscription order {razorpay_order['id']} for user {user_id}")
        
        return Response({
            'success': True,
            'order_id': razorpay_order['id'],
            'amount': amount_paise,
            'amount_rupees': amount_rupees,
            'currency': razorpay_order['currency'],
            'key_id': settings.RAZORPAY_KEY_ID,
            'is_trial': is_trial,
            'trial_price': float(plan.first_month_price),
            'recurring_price': float(plan.recurring_price),
            'plan_name': plan.display_name,
            'plan_description': plan.description,
            'billing_start': billing_start,
            'billing_end': billing_end
        }, status=status.HTTP_200_OK)
        
    except SubscriptionPlan.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Subscription plan not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error creating subscription order: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to create order',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def verify_subscription_payment(request):
    """
    Verify Razorpay payment and activate premium subscription
    
    POST /api/subscription/verify-payment/
    
    Request Body:
    {
        "user_id": "user123",
        "razorpay_payment_id": "pay_xyz",
        "razorpay_order_id": "order_xyz",
        "razorpay_signature": "signature_xyz",
        "auto_pay_enabled": true
    }
    
    Response:
    {
        "success": true,
        "message": "Premium subscription activated!",
        "plan": "premium",
        "subscription_end_date": "2025-01-24",
        "next_billing_amount": 99.00
    }
    """
    try:
        if not razorpay_client:
            return Response({
                'success': False,
                'error': 'Payment gateway not configured'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        user_id = request.data.get('user_id')
        payment_id = request.data.get('razorpay_payment_id')
        order_id = request.data.get('razorpay_order_id')
        signature = request.data.get('razorpay_signature')
        auto_pay = request.data.get('auto_pay_enabled', True)
        
        if not all([user_id, payment_id, order_id, signature]):
            return Response({
                'success': False,
                'error': 'Missing required payment verification fields'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify signature
        try:
            params_dict = {
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': order_id,
                'razorpay_signature': signature
            }
            razorpay_client.utility.verify_payment_signature(params_dict)
        except razorpay.errors.SignatureVerificationError:
            logger.error(f"Payment signature verification failed for user {user_id}")
            return Response({
                'success': False,
                'error': 'Payment verification failed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get payment details from Razorpay
        payment_details = razorpay_client.payment.fetch(payment_id)
        
        # Update subscription
        with db_transaction.atomic():
            subscription = UserSubscription.objects.get(user_id=user_id)
            premium_plan = SubscriptionPlan.objects.get(name='premium')
            
            now = timezone.now()
            subscription.plan = 'premium'
            subscription.subscription_plan = premium_plan
            subscription.is_trial = True
            subscription.trial_end_date = now + timedelta(days=30)
            subscription.subscription_start_date = now
            subscription.subscription_end_date = now + timedelta(days=30)
            subscription.next_billing_date = now + timedelta(days=30)
            subscription.last_payment_date = now
            subscription.auto_pay_enabled = auto_pay
            subscription.payment_method = payment_details.get('method', 'unknown')
            subscription.save()
            
            # Create payment record
            payment = Payment.objects.create(
                subscription=subscription,
                amount=payment_details['amount'] / 100,  # Convert paise to rupees
                currency=payment_details['currency'],
                status='completed',
                payment_method=payment_details.get('method', 'unknown'),
                transaction_id=payment_id,
                razorpay_order_id=order_id,
                razorpay_payment_id=payment_id,
                razorpay_signature=signature,
                billing_cycle_start=now,
                billing_cycle_end=now + timedelta(days=30)
            )
            
            # Update RazorpayOrder status
            try:
                order = RazorpayOrder.objects.get(order_id=order_id)
                order.payment_id = payment_id
                order.status = 'paid'
                order.save()
            except RazorpayOrder.DoesNotExist:
                pass
            
            logger.info(f"Premium subscription activated for user {user_id}")
        
        return Response({
            'success': True,
            'message': 'Premium subscription activated successfully! 🎉',
            'plan': 'premium',
            'is_trial': True,
            'trial_period': '30 days',
            'subscription_start_date': subscription.subscription_start_date,
            'subscription_end_date': subscription.subscription_end_date,
            'next_billing_date': subscription.next_billing_date,
            'next_billing_amount': float(premium_plan.recurring_price),
            'auto_pay_enabled': subscription.auto_pay_enabled,
            'features_unlocked': 'All features are now unlimited!',
            'payment': {
                'payment_id': payment_id,
                'amount': float(payment.amount),
                'currency': payment.currency,
                'method': payment.payment_method
            }
        }, status=status.HTTP_200_OK)
        
    except UserSubscription.DoesNotExist:
        return Response({
            'success': False,
            'error': 'User subscription not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error verifying subscription payment: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to verify payment',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cancel_subscription(request):
    """
    Cancel premium subscription (downgrade to free)
    
    POST /api/subscription/cancel/
    
    Request Body:
    {
        "user_id": "user123"
    }
    """
    try:
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        subscription = UserSubscription.objects.get(user_id=user_id)
        
        if subscription.plan == 'free':
            return Response({
                'success': False,
                'error': 'User is already on free plan'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Downgrade to free plan
        free_plan = SubscriptionPlan.objects.get(name='free')
        subscription.plan = 'free'
        subscription.subscription_plan = free_plan
        subscription.auto_pay_enabled = False
        subscription.razorpay_subscription_id = None
        subscription.save()
        
        logger.info(f"Subscription cancelled for user {user_id}")
        
        return Response({
            'success': True,
            'message': 'Subscription cancelled successfully',
            'plan': 'free',
            'note': 'You now have access to 3 uses per feature per month'
        }, status=status.HTTP_200_OK)
        
    except UserSubscription.DoesNotExist:
        return Response({
            'success': False,
            'error': 'User subscription not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Failed to cancel subscription',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
