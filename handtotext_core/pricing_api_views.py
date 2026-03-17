"""
Subscription and Pricing API Views (Production-Ready)
As per Product + Engineering Specification

Handles:
- Razorpay subscription creation (₹1 → ₹99/month)
- Subscription status checks
- Feature usage validation
- Webhook handlers for payment events
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import timedelta
import logging
import razorpay
import hmac
import hashlib

from .models import PlanSubscription, UsageQuota, SubscriptionPayment

logger = logging.getLogger(__name__)

# Initialize Razorpay client
try:
    razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except Exception as e:
    logger.warning(f"Razorpay client initialization failed: {e}")
    razorpay_client = None


# ============================================================================
# SUBSCRIPTION MANAGEMENT ENDPOINTS
# ============================================================================

class CreateSubscriptionView(APIView):
    """
    Create Razorpay subscription for user
    POST /api/subscription/create/
    
    Pricing:
    - First Month: ₹1
    - From Month 2: ₹99/month (auto-renew)
    
    Request Body:
    {
        "user_id": "user123",
        "email": "user@example.com",
        "contact": "9999999999"
    }
    """
    parser_classes = [JSONParser]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        email = request.data.get('email')
        contact = request.data.get('contact', '')
        
        if not user_id or not email:
            return Response({
                'success': False,
                'error': 'user_id and email are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check if user already has paid subscription
            existing_sub = PlanSubscription.objects.filter(user_id=user_id).first()
            if existing_sub and existing_sub.is_paid_active():
                return Response({
                    'success': False,
                    'error': 'User already has an active paid subscription'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create Razorpay subscription
            # Note: You need to create a Razorpay Plan first via dashboard
            # Plan should be: ₹1 for first month, then ₹99/month
            
            subscription_data = {
                'plan_id': settings.RAZORPAY_PLAN_ID,  # Set in settings
                'total_count': 12,  # 1 year, adjust as needed
                'quantity': 1,
                'customer_notify': 1,
                'addons': [],
                'notes': {
                    'user_id': user_id,
                    'email': email,
                    'plan_type': 'PAID'
                }
            }
            
            razorpay_subscription = razorpay_client.subscription.create(subscription_data)
            
            # Create or update PlanSubscription
            if existing_sub:
                plan_subscription = existing_sub
            else:
                plan_subscription = PlanSubscription.objects.create(user_id=user_id)
            
            # Store Razorpay subscription ID (will activate via webhook)
            plan_subscription.razorpay_subscription_id = razorpay_subscription['id']
            plan_subscription.razorpay_plan_id = settings.RAZORPAY_PLAN_ID
            plan_subscription.save()
            
            return Response({
                'success': True,
                'subscription_id': razorpay_subscription['id'],
                'short_url': razorpay_subscription.get('short_url'),
                'status': razorpay_subscription['status'],
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'message': 'Subscription created. Please complete payment.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            return Response({
                'success': False,
                'error': 'Failed to create subscription',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubscriptionStatusView(APIView):
    """
    Get user subscription status and usage quotas
    GET /api/subscription/status/?user_id=<user_id>
    
    Response includes:
    - Plan type (FREE/PAID)
    - Status (ACTIVE/PAST_DUE/CANCELLED)
    - Remaining usage for each paid feature
    """
    parser_classes = [JSONParser]
    
    def get(self, request):
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get or create subscription (defaults to FREE)
            subscription, created = PlanSubscription.objects.get_or_create(
                user_id=user_id,
                defaults={'plan_type': 'FREE', 'status': 'ACTIVE'}
            )
            
            # Get usage quotas (only for paid users)
            usage_data = None
            if subscription.plan_type == 'PAID':
                quota, _ = UsageQuota.objects.get_or_create(user_id=user_id)
                usage_data = {
                    'quizzes': {
                        'used': quota.quizzes_used,
                        'remaining': quota.get_remaining('quizzes'),
                        'limit': 30
                    },
                    'mock_tests': {
                        'used': quota.mock_tests_used,
                        'remaining': quota.get_remaining('mock_tests'),
                        'limit': 30
                    },
                    'flashcards': {
                        'used': quota.flashcards_used,
                        'remaining': quota.get_remaining('flashcards'),
                        'limit': 30
                    },
                    'predicted_questions': {
                        'used': quota.predicted_questions_used,
                        'remaining': quota.get_remaining('predicted_questions'),
                        'limit': 30
                    },
                    'youtube_summaries': {
                        'used': quota.youtube_summaries_used,
                        'remaining': quota.get_remaining('youtube_summaries'),
                        'limit': 30
                    }
                }
            
            return Response({
                'success': True,
                'user_id': subscription.user_id,
                'plan_type': subscription.plan_type,
                'status': subscription.status,
                'is_paid_active': subscription.is_paid_active(),
                'current_period_end': subscription.current_period_end,
                'usage_quotas': usage_data,
                'created': created
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting subscription status: {e}")
            return Response({
                'success': False,
                'error': 'Failed to get subscription status',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CancelSubscriptionView(APIView):
    """
    Cancel user subscription
    POST /api/subscription/cancel/
    
    Request Body:
    {
        "user_id": "user123"
    }
    """
    parser_classes = [JSONParser]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subscription = PlanSubscription.objects.filter(user_id=user_id).first()
            
            if not subscription or subscription.plan_type == 'FREE':
                return Response({
                    'success': False,
                    'error': 'No active paid subscription found'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Cancel Razorpay subscription
            if subscription.razorpay_subscription_id:
                try:
                    razorpay_client.subscription.cancel(subscription.razorpay_subscription_id, {
                        'cancel_at_cycle_end': 0  # Cancel immediately
                    })
                except Exception as e:
                    logger.error(f"Razorpay cancellation error: {e}")
            
            # Downgrade to free
            subscription.downgrade_to_free()
            
            return Response({
                'success': True,
                'message': 'Subscription cancelled successfully. Downgraded to Free plan.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            return Response({
                'success': False,
                'error': 'Failed to cancel subscription',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# FEATURE USAGE VALIDATION
# ============================================================================

class CheckFeatureAccessView(APIView):
    """
    Check if user can access a paid feature
    GET /api/subscription/check-access/?user_id=<user_id>&feature=<feature_name>
    
    Features: quizzes, mock_tests, flashcards, predicted_questions, youtube_summaries
    
    Returns:
    - can_access: boolean
    - remaining: number (for paid users)
    - reason: string (if blocked)
    """
    parser_classes = [JSONParser]
    
    def get(self, request):
        user_id = request.query_params.get('user_id')
        feature = request.query_params.get('feature')
        
        if not user_id or not feature:
            return Response({
                'success': False,
                'error': 'user_id and feature are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subscription = PlanSubscription.objects.filter(user_id=user_id).first()
            
            # Free features - always accessible
            free_features = ['daily_quizzes', 'mock_tests_basic', 'pyq_trends', 'pyq_papers', 'peer_quiz']
            if feature in free_features:
                return Response({
                    'success': True,
                    'can_access': True,
                    'feature': feature,
                    'reason': 'Free feature'
                }, status=status.HTTP_200_OK)
            
            # Paid features - check subscription and quota
            if not subscription or not subscription.is_paid_active():
                return Response({
                    'success': True,
                    'can_access': False,
                    'feature': feature,
                    'remaining': 0,
                    'reason': 'Subscription required. Upgrade for ₹1!'
                }, status=status.HTTP_200_OK)
            
            # Check usage quota
            quota = UsageQuota.objects.filter(user_id=user_id).first()
            if not quota:
                quota = UsageQuota.objects.create(user_id=user_id)
            
            can_use = quota.can_use(feature)
            remaining = quota.get_remaining(feature)
            
            return Response({
                'success': True,
                'can_access': can_use,
                'feature': feature,
                'remaining': remaining,
                'reason': 'Monthly limit reached' if not can_use else None
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error checking feature access: {e}")
            return Response({
                'success': False,
                'error': 'Failed to check feature access',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncrementFeatureUsageView(APIView):
    """
    Increment usage counter for a paid feature
    POST /api/subscription/increment-usage/
    
    Request Body:
    {
        "user_id": "user123",
        "feature": "quizzes"
    }
    
    Call this AFTER successful feature usage
    """
    parser_classes = [JSONParser]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        feature = request.data.get('feature')
        
        if not user_id or not feature:
            return Response({
                'success': False,
                'error': 'user_id and feature are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            quota = UsageQuota.objects.filter(user_id=user_id).first()
            if not quota:
                quota = UsageQuota.objects.create(user_id=user_id)
            
            quota.increment(feature)
            
            return Response({
                'success': True,
                'feature': feature,
                'used': getattr(quota, f'{feature}_used'),
                'remaining': quota.get_remaining(feature)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error incrementing usage: {e}")
            return Response({
                'success': False,
                'error': 'Failed to increment usage',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# RAZORPAY WEBHOOKS (SECURE)
# ============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    """
    Handle Razorpay webhook events
    POST /api/subscription/webhook/
    
    Events handled:
    - subscription.activated: Activate paid plan
    - payment.captured: Confirm billing
    - payment.failed: Mark past due
    - subscription.cancelled: Downgrade to free
    """
    parser_classes = [JSONParser]
    
    def post(self, request):
        try:
            # Verify webhook signature
            webhook_signature = request.headers.get('X-Razorpay-Signature')
            webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
            webhook_body = request.body
            
            # Verify signature
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                webhook_body,
                hashlib.sha256
            ).hexdigest()
            
            if webhook_signature != expected_signature:
                logger.warning("Invalid webhook signature")
                return Response({
                    'success': False,
                    'error': 'Invalid signature'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Process event
            event = request.data.get('event')
            payload = request.data.get('payload')
            
            if not event or not payload:
                return Response({
                    'success': False,
                    'error': 'Invalid webhook data'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Route to appropriate handler
            if event == 'subscription.activated':
                return self.handle_subscription_activated(payload)
            elif event == 'payment.captured':
                return self.handle_payment_captured(payload)
            elif event == 'payment.failed':
                return self.handle_payment_failed(payload)
            elif event == 'subscription.cancelled':
                return self.handle_subscription_cancelled(payload)
            else:
                logger.info(f"Unhandled webhook event: {event}")
                return Response({'success': True}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def handle_subscription_activated(self, payload):
        """Handle subscription.activated event"""
        try:
            subscription_entity = payload['subscription']['entity']
            subscription_id = subscription_entity['id']
            plan_id = subscription_entity['plan_id']
            user_id = subscription_entity['notes'].get('user_id')
            
            if not user_id:
                logger.error("No user_id in subscription notes")
                return Response({'success': False}, status=status.HTTP_400_BAD_REQUEST)
            
            # Activate subscription
            subscription = PlanSubscription.objects.filter(user_id=user_id).first()
            if subscription:
                subscription.activate_paid_plan(subscription_id, plan_id)
                logger.info(f"Activated subscription for user {user_id}")
            
            return Response({'success': True}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error handling subscription.activated: {e}")
            return Response({'success': False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def handle_payment_captured(self, payload):
        """Handle payment.captured event"""
        try:
            payment_entity = payload['payment']['entity']
            payment_id = payment_entity['id']
            amount = payment_entity['amount'] / 100  # Convert paise to rupees
            subscription_id = payment_entity.get('subscription_id')
            
            if subscription_id:
                subscription = PlanSubscription.objects.filter(
                    razorpay_subscription_id=subscription_id
                ).first()
                
                if subscription:
                    # Record payment
                    SubscriptionPayment.objects.create(
                        subscription=subscription,
                        razorpay_payment_id=payment_id,
                        amount=amount,
                        status='captured',
                        billing_period_start=subscription.current_period_start or timezone.now(),
                        billing_period_end=subscription.current_period_end or timezone.now() + timedelta(days=30),
                        captured_at=timezone.now()
                    )
                    
                    # Reset monthly quotas on successful payment
                    quota = UsageQuota.objects.filter(user_id=subscription.user_id).first()
                    if quota:
                        quota.reset_all()
                    
                    logger.info(f"Payment captured for subscription {subscription_id}: ₹{amount}")
            
            return Response({'success': True}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error handling payment.captured: {e}")
            return Response({'success': False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def handle_payment_failed(self, payload):
        """Handle payment.failed event"""
        try:
            payment_entity = payload['payment']['entity']
            subscription_id = payment_entity.get('subscription_id')
            
            if subscription_id:
                subscription = PlanSubscription.objects.filter(
                    razorpay_subscription_id=subscription_id
                ).first()
                
                if subscription:
                    subscription.mark_past_due()
                    logger.warning(f"Payment failed for subscription {subscription_id}")
            
            return Response({'success': True}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error handling payment.failed: {e}")
            return Response({'success': False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def handle_subscription_cancelled(self, payload):
        """Handle subscription.cancelled event"""
        try:
            subscription_entity = payload['subscription']['entity']
            subscription_id = subscription_entity['id']
            
            subscription = PlanSubscription.objects.filter(
                razorpay_subscription_id=subscription_id
            ).first()
            
            if subscription:
                subscription.downgrade_to_free()
                logger.info(f"Subscription cancelled: {subscription_id}")
            
            return Response({'success': True}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error handling subscription.cancelled: {e}")
            return Response({'success': False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
