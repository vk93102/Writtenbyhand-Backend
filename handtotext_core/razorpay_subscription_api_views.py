"""
Razorpay Subscription API Integration
Handles ₹1 for first month, then ₹99/month auto-debit
Uses Razorpay Subscriptions (not one-time payments)
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
from django.db import transaction as db_transaction
from django.views.decorators.csrf import csrf_exempt
from .models import UserSubscription, SubscriptionPlan

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


@api_view(['POST'])
def create_razorpay_subscription(request):
    """Create Razorpay subscription"""
    try:
        data = request.data
        plan_id = data.get('plan_id')
        user_id = data.get('user_id', 'anonymous')
        
        if not plan_id:
            return Response({'success': False, 'error': 'plan_id is required'}, status=400)
        
        # Get or create the Razorpay plan first
        try:
            razorpay_plan = razorpay_client.plan.fetch(plan_id)
            logger.info(f"Using existing Razorpay plan: {plan_id}")
        except razorpay.errors.BadRequestError:
            logger.warning(f"Plan {plan_id} not found in Razorpay. Creating new plan...")
            
            # Create plan based on plan_id
            plan_config = {
                'monthly': {
                    'period': 'monthly',
                    'interval': 1,
                    'amount': 199,  # ₹1.99 in paise
                    'currency': 'INR',
                    'description': 'Monthly Premium Plan',
                },
                'yearly': {
                    'period': 'yearly',
                    'interval': 1,
                    'amount': 1999,  # ₹19.99 in paise
                    'currency': 'INR',
                    'description': 'Yearly Premium Plan',
                },
            }
            
            config = plan_config.get(plan_id, plan_config['monthly'])
            
            try:
                razorpay_plan = razorpay_client.plan.create(
                    period=config['period'],
                    interval=config['interval'],
                    amount=config['amount'],
                    currency=config['currency'],
                    description=config['description'],
                )
                plan_id = razorpay_plan['id']
                logger.info(f"Created new Razorpay plan: {plan_id}")
            except Exception as plan_error:
                logger.error(f"Failed to create Razorpay plan: {str(plan_error)}")
                return Response({
                    'success': False,
                    'error': f'Failed to create plan: {str(plan_error)}'
                }, status=500)
        
        # Now create the subscription with the valid plan_id
        subscription_data = {
            'plan_id': plan_id,
            'customer_notify': 1,
            'quantity': 1,
            'total_count': 12,  # Billing cycles
            'description': f'Subscription for user {user_id}',
        }
        
        try:
            razorpay_subscription = razorpay_client.subscription.create(subscription_data)
            
            # Save subscription to database
            subscription = UserSubscription.objects.create(
                user_id=user_id,
                razorpay_subscription_id=razorpay_subscription['id'],
                razorpay_plan_id=plan_id,
                status='created',
                plan_name=data.get('plan_name', 'Premium'),
                amount=razorpay_subscription.get('amount', 0),
                currency='INR',
            )
            
            return Response({
                'success': True,
                'subscription_id': razorpay_subscription['id'],
                'plan_id': plan_id,
                'amount': razorpay_subscription.get('amount', 0),
            })
            
        except razorpay.errors.BadRequestError as e:
            logger.error(f"Razorpay subscription creation failed: {str(e)}")
            return Response({
                'success': False,
                'error': f'Subscription creation failed: {str(e)}'
            }, status=500)
    
    except Exception as e:
        logger.error(f"Unexpected error in create_razorpay_subscription: {str(e)}")
        return Response({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)


@api_view(['POST'])
@csrf_exempt
def razorpay_subscription_webhook(request):
    """
    Handle Razorpay Subscription Webhooks
    
    POST /api/subscription/webhook/
    
    Events Handled:
    - subscription.activated
    - subscription.charged
    - subscription.cancelled
    - subscription.completed
    - payment.failed
    """
    try:
        # Verify webhook signature
        webhook_signature = request.headers.get('X-Razorpay-Signature')
        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', settings.RAZORPAY_KEY_SECRET)
        
        if not webhook_signature:
            logger.error("Webhook signature missing")
            return Response({'error': 'Signature missing'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify signature
        try:
            request_body = request.body.decode('utf-8')
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                request_body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if webhook_signature != expected_signature:
                logger.error("Webhook signature verification failed")
                return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return Response({'error': 'Signature verification failed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse webhook data
        webhook_data = request.data
        event = webhook_data.get('event')
        payload = webhook_data.get('payload', {})
        subscription_entity = payload.get('subscription', {}).get('entity', {})
        payment_entity = payload.get('payment', {}).get('entity', {})
        
        logger.info(f"Received webhook event: {event}")
        
        # Handle events
        if event == 'subscription.activated':
            # Subscription activated - grant premium access
            razorpay_subscription_id = subscription_entity.get('id')
            
            try:
                subscription = UserSubscription.objects.get(razorpay_subscription_id=razorpay_subscription_id)
                
                with db_transaction.atomic():
                    subscription.plan = 'premium'
                    subscription.subscription_status = 'active'
                    subscription.is_trial = True
                    subscription.subscription_start_date = timezone.now()
                    subscription.subscription_end_date = timezone.now() + timedelta(days=30)
                    subscription.next_billing_date = timezone.now() + timedelta(days=30)
                    subscription.last_payment_date = timezone.now()
                    subscription.save()
                    
                    logger.info(f"Activated premium for subscription: {razorpay_subscription_id}")
                
                return Response({'status': 'success', 'message': 'Subscription activated'}, status=status.HTTP_200_OK)
                
            except UserSubscription.DoesNotExist:
                logger.error(f"Subscription not found: {razorpay_subscription_id}")
                return Response({'error': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
        
        elif event == 'subscription.charged':
            # Payment successful for a billing cycle
            razorpay_subscription_id = subscription_entity.get('id')
            
            try:
                subscription = UserSubscription.objects.get(razorpay_subscription_id=razorpay_subscription_id)
                
                subscription.subscription_status = 'active'
                subscription.last_payment_date = timezone.now()
                subscription.next_billing_date = timezone.now() + timedelta(days=30)
                subscription.is_trial = False  # No longer trial after first charge
                subscription.save()
                
                logger.info(f"Payment charged for subscription: {razorpay_subscription_id}")
                
                return Response({'status': 'success', 'message': 'Payment processed'}, status=status.HTTP_200_OK)
                
            except UserSubscription.DoesNotExist:
                logger.error(f"Subscription not found: {razorpay_subscription_id}")
                return Response({'error': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
        
        elif event == 'subscription.cancelled':
            # Subscription cancelled - downgrade after current period ends
            razorpay_subscription_id = subscription_entity.get('id')
            
            try:
                subscription = UserSubscription.objects.get(razorpay_subscription_id=razorpay_subscription_id)
                
                # Keep premium access till period end
                subscription.subscription_status = 'cancelled'
                subscription.save()
                
                logger.info(f"Subscription cancelled: {razorpay_subscription_id}")
                
                return Response({'status': 'success', 'message': 'Subscription cancelled'}, status=status.HTTP_200_OK)
                
            except UserSubscription.DoesNotExist:
                logger.error(f"Subscription not found: {razorpay_subscription_id}")
                return Response({'error': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
        
        elif event == 'subscription.completed':
            # Subscription completed - downgrade to free
            razorpay_subscription_id = subscription_entity.get('id')
            
            try:
                subscription = UserSubscription.objects.get(razorpay_subscription_id=razorpay_subscription_id)
                
                subscription.plan = 'free'
                subscription.subscription_status = 'completed'
                subscription.save()
                
                logger.info(f"Subscription completed: {razorpay_subscription_id}")
                
                return Response({'status': 'success', 'message': 'Subscription completed'}, status=status.HTTP_200_OK)
                
            except UserSubscription.DoesNotExist:
                logger.error(f"Subscription not found: {razorpay_subscription_id}")
                return Response({'error': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)
        
        elif event == 'payment.failed':
            # Payment failed - mark subscription as failed
            subscription_id = payment_entity.get('subscription_id')
            
            if subscription_id:
                try:
                    subscription = UserSubscription.objects.get(razorpay_subscription_id=subscription_id)
                    
                    subscription.subscription_status = 'failed'
                    subscription.plan = 'free'  # Downgrade to free immediately
                    subscription.save()
                    
                    logger.info(f"Payment failed for subscription: {subscription_id}")
                    
                    return Response({'status': 'success', 'message': 'Payment failure processed'}, status=status.HTTP_200_OK)
                    
                except UserSubscription.DoesNotExist:
                    pass
        
        return Response({'status': 'success', 'message': 'Webhook received'}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        return Response({'error': 'Webhook processing failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cancel_razorpay_subscription(request):
    """
    Cancel Razorpay Subscription
    
    POST /api/subscription/cancel-razorpay/
    
    Request Body:
    {
        "user_id": "user123",
        "cancel_at_cycle_end": true  // If true, access continues till period end
    }
    """
    try:
        if not razorpay_client:
            return Response({
                'success': False,
                'error': 'Payment gateway not configured'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        user_id = request.data.get('user_id')
        cancel_at_cycle_end = request.data.get('cancel_at_cycle_end', True)
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        subscription = UserSubscription.objects.get(user_id=user_id)
        
        if not subscription.razorpay_subscription_id:
            return Response({
                'success': False,
                'error': 'No active Razorpay subscription found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Cancel subscription via Razorpay API
        razorpay_client.subscription.cancel(
            subscription.razorpay_subscription_id,
            {
                'cancel_at_cycle_end': 1 if cancel_at_cycle_end else 0
            }
        )
        
        # Update local record
        if cancel_at_cycle_end:
            subscription.subscription_status = 'cancelled'
        else:
            subscription.subscription_status = 'cancelled'
            subscription.plan = 'free'
        
        subscription.save()
        
        logger.info(f"Cancelled subscription for user: {user_id}")
        
        return Response({
            'success': True,
            'message': 'Subscription cancelled successfully',
            'access_till': subscription.subscription_end_date if cancel_at_cycle_end else timezone.now()
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
