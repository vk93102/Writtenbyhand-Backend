"""
Access Control Decorators and Utilities
Manages feature access based on subscription status and usage quotas
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import logging

from .models import PlanSubscription, UsageQuota, SubscriptionPlan

logger = logging.getLogger(__name__)


def require_feature_access(feature_name):
    """
    Decorator to check feature access before allowing API call
    
    Usage:
    @require_feature_access('quiz')
    def post(self, request):
        ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            user_id = request.query_params.get('user_id') or \
                     request.data.get('user_id') or \
                     getattr(request.user, 'id', None)
            
            if not user_id:
                return Response({
                    'error': 'user_id is required',
                    'code': 'MISSING_USER_ID'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                # Get subscription
                subscription, _ = PlanSubscription.objects.get_or_create(
                    user_id=user_id,
                    defaults={'plan_type': 'FREE', 'status': 'ACTIVE'}
                )
                
                # Check if subscription expired
                if subscription.is_paid_active() and subscription.current_period_end:
                    if timezone.now() > subscription.current_period_end:
                        subscription.downgrade_to_free()
                        quota = UsageQuota.objects.get(user_id=user_id)
                        quota.reset_all()
                
                # For free users - always allow (we'll show upgrade prompt in response)
                # For paid users - check quota
                if subscription.plan_type == 'PAID' and subscription.is_paid_active():
                    quota = UsageQuota.objects.get(user_id=user_id)
                    
                    if not quota.can_use(feature_name):
                        return Response({
                            'success': False,
                            'error': 'Monthly quota exceeded',
                            'code': 'QUOTA_EXCEEDED',
                            'feature': feature_name,
                            'plan': subscription.plan_type,
                            'message': 'You have reached your monthly limit for this feature',
                            'reset_date': quota.last_reset_date + timedelta(days=30),
                            'upgrade_url': '/api/subscriptions/upgrade/'
                        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
                    
                    # Increment usage
                    quota.increment(feature_name)
                
                # Attach subscription info to request for use in view
                request.user_subscription = subscription
                request.user_quota = UsageQuota.objects.get_or_create(user_id=user_id)[0]
                
                return func(self, request, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in access control decorator: {e}", exc_info=True)
                return Response({
                    'error': 'Failed to check access',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return wrapper
    return decorator


def check_subscription_status(func):
    """
    Decorator to check subscription status and auto-renew if needed
    
    Usage:
    @check_subscription_status
    def post(self, request):
        ...
    """
    def decorator(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id') or \
                 request.data.get('user_id') or \
                 getattr(request.user, 'id', None)
        
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subscription, _ = PlanSubscription.objects.get_or_create(
                user_id=user_id,
                defaults={'plan_type': 'FREE', 'status': 'ACTIVE'}
            )
            
            # Check auto-renewal
            if subscription.is_paid_active():
                if subscription.current_period_end and timezone.now() > subscription.current_period_end:
                    # Trigger renewal (in real implementation, this would be via Razorpay)
                    logger.info(f"Subscription renewal triggered for {user_id}")
                    # For now, just update the period end date
                    subscription.current_period_end = timezone.now() + timedelta(days=30)
                    subscription.save()
            
            # Attach to request
            request.user_subscription = subscription
            
            return func(self, request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error checking subscription status: {e}", exc_info=True)
            return Response({
                'error': 'Failed to check subscription',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return decorator


class AccessControlMiddleware:
    """
    Middleware to automatically check subscription status on each request
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        user_id = request.query_params.get('user_id') or \
                 request.data.get('user_id') if hasattr(request, 'data') else None
        
        if user_id:
            try:
                subscription, _ = PlanSubscription.objects.get_or_create(
                    user_id=user_id,
                    defaults={'plan_type': 'FREE', 'status': 'ACTIVE'}
                )
                request.user_subscription = subscription
                request.user_quota = UsageQuota.objects.get_or_create(user_id=user_id)[0]
            except Exception as e:
                logger.warning(f"Could not load subscription info: {e}")
        
        response = self.get_response(request)
        return response


def get_subscription_status(user_id):
    """
    Helper function to get subscription and quota status
    
    Returns:
        {
            'subscription': PlanSubscription,
            'quota': UsageQuota,
            'is_paid': bool,
            'days_remaining': int or None,
            'quota_remaining': dict
        }
    """
    try:
        subscription, _ = PlanSubscription.objects.get_or_create(
            user_id=user_id,
            defaults={'plan_type': 'FREE', 'status': 'ACTIVE'}
        )
        
        quota, _ = UsageQuota.objects.get_or_create(user_id=user_id)
        
        # Calculate days remaining
        days_remaining = None
        if subscription.current_period_end:
            remaining = (subscription.current_period_end - timezone.now()).days
            days_remaining = max(0, remaining)
        
        # Check if expired
        if subscription.is_paid_active() and days_remaining == 0:
            subscription.downgrade_to_free()
            quota.reset_all()
        
        return {
            'subscription': subscription,
            'quota': quota,
            'is_paid': subscription.is_paid_active(),
            'days_remaining': days_remaining,
            'quota_remaining': {
                'quizzes': quota.get_remaining('quizzes'),
                'mock_tests': quota.get_remaining('mock_tests'),
                'flashcards': quota.get_remaining('flashcards'),
                'predicted_questions': quota.get_remaining('predicted_questions'),
                'youtube_summaries': quota.get_remaining('youtube_summaries'),
            }
        }
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        return None


def check_feature_limit(user_id, feature_name):
    """
    Check if user can use a feature
    
    Returns:
        {
            'can_use': bool,
            'remaining': int or None,
            'plan_type': str,
            'message': str
        }
    """
    status_info = get_subscription_status(user_id)
    
    if not status_info:
        return {
            'can_use': False,
            'remaining': 0,
            'plan_type': 'ERROR',
            'message': 'Could not check subscription status'
        }
    
    subscription = status_info['subscription']
    quota = status_info['quota']
    
    if subscription.plan_type == 'FREE':
        return {
            'can_use': True,  # Allow free users, but limit in UI
            'remaining': 3,  # Free users get 3/month
            'plan_type': 'FREE',
            'message': 'Free plan - Limited access (3/month)',
            'upgrade_prompt': True
        }
    
    if subscription.is_paid_active():
        remaining = quota.get_remaining(feature_name)
        return {
            'can_use': remaining > 0,
            'remaining': remaining,
            'plan_type': 'PAID',
            'message': f'{remaining} uses remaining this month' if remaining > 0 else 'Monthly quota exceeded',
            'subscription_expires': subscription.current_period_end
        }
    
    return {
        'can_use': False,
        'remaining': 0,
        'plan_type': 'INACTIVE',
        'message': 'Subscription inactive or expired'
    }


def handle_auto_renewal():
    """
    Background task to handle subscription auto-renewals
    Should be run periodically (via celery or APScheduler)
    
    Checks for subscriptions that expired and triggers renewal
    """
    try:
        from .models import SubscriptionPayment
        
        # Find subscriptions that ended and are due for renewal
        subscriptions = PlanSubscription.objects.filter(
            plan_type='PAID',
            status='ACTIVE',
            current_period_end__lte=timezone.now()
        )
        
        renewed_count = 0
        for subscription in subscriptions:
            try:
                # Get plan details
                plan_obj = SubscriptionPlan.objects.filter(
                    name='basic'  # or 'premium', depending on subscription
                ).first()
                
                if not plan_obj:
                    continue
                
                # Create renewal payment record
                SubscriptionPayment.objects.create(
                    subscription=subscription,
                    amount=plan_obj.recurring_price,
                    currency='INR',
                    status='captured',
                    payment_method='auto_renew',
                    billing_period_start=subscription.current_period_end,
                    billing_period_end=subscription.current_period_end + timedelta(days=30),
                    razorpay_payment_id=f'auto_renew_{subscription.user_id}_{timezone.now().timestamp()}',
                    captured_at=timezone.now()
                )
                
                # Update subscription period
                subscription.current_period_end = subscription.current_period_end + timedelta(days=30)
                subscription.save()
                
                # Reset quota
                quota = UsageQuota.objects.get(user_id=subscription.user_id)
                quota.reset_all()
                
                renewed_count += 1
                logger.info(f"Auto-renewed subscription for {subscription.user_id}")
                
            except Exception as e:
                logger.error(f"Error renewing subscription for {subscription.user_id}: {e}")
                continue
        
        logger.info(f"Auto-renewal completed: {renewed_count} subscriptions renewed")
        return renewed_count
        
    except Exception as e:
        logger.error(f"Error in auto-renewal process: {e}", exc_info=True)
        return 0
