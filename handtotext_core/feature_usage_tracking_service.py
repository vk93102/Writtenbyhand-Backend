"""
Feature Usage Service
Tracks and enforces feature usage limits based on subscription plans
"""
import logging
from django.utils import timezone
from .models import UserSubscription, FeatureUsageLog, SubscriptionPlan
from datetime import timedelta

logger = logging.getLogger(__name__)


class FeatureUsageService:
    """Service to manage feature usage tracking and restrictions"""
    
    # Feature names
    FEATURES = {
        'mock_test': 'Mock Test',
        'quiz': 'Quiz',
        'pair_quiz': 'Pair Quiz',
        'flashcards': 'Flashcards',
        'ask_question': 'Ask Question',
        'predicted_questions': 'Predicted Questions',
        'previous_papers': 'Previous Papers',
        'pyqs': 'Previous Year Questions',
        'youtube_summarizer': 'YouTube Summarizer',
        'daily_quiz': 'Daily Quiz',
    }
    
    @staticmethod
    def get_or_create_subscription(user_id):
        """Get or create user subscription (defaults to free plan)"""
        subscription, created = UserSubscription.objects.get_or_create(
            user_id=user_id,
            defaults={
                'plan': 'free',
                'subscription_plan': SubscriptionPlan.objects.filter(name='free').first(),
            }
        )
        return subscription
    
    @staticmethod
    def check_feature_available(user_id, feature_name):
        """
        Check if user can use a feature based on plan limits
        
        CRITICAL: This is called BEFORE every feature usage
        It enforces the free tier 3-use limit
        After payment, subscription_status='active' → unlimited access
        
        Returns: {'allowed': bool, 'reason': str, 'limit': int, 'used': int}
        """
        if feature_name not in FeatureUsageService.FEATURES:
            return {
                'allowed': False,
                'reason': f'Feature "{feature_name}" not found',
                'limit': 0,
                'used': 0,
            }
        
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        
        # STEP 1: Check if user has active paid subscription
        # If plan is 'basic' or 'premium' AND subscription_status is 'active'
        # → Grant unlimited access immediately
        if subscription.plan != 'free' and subscription.subscription_status == 'active':
            logger.info(f"[CHECK_FEATURE] {user_id}/{feature_name}: UNLIMITED (subscription active)")
            return {
                'allowed': True,
                'reason': 'Unlimited access (paid subscription)',
                'unlimited': True,
                'plan': subscription.plan,
                'subscription_status': subscription.subscription_status,
            }
        
        # STEP 2: If user is past_due or subscription failed, re-enable limits
        if subscription.subscription_status in ['past_due', 'failed', 'cancelled']:
            logger.info(f"[CHECK_FEATURE] {user_id}/{feature_name}: LIMITS ACTIVE (subscription {subscription.subscription_status})")
            # Fall through to check free tier limits
        
        # STEP 3: Check free tier limits (3 uses per feature)
        limits = subscription.get_feature_limits()
        
        if feature_name not in limits:
            # Feature not in limits, allow it
            return {
                'allowed': True,
                'reason': 'Feature available',
                'limit': None,
                'used': 0,
            }
        
        feature = limits[feature_name]
        limit = feature['limit']
        used = feature['used']
        
        # Check if usage is within limit
        if limit is None:
            # Unlimited (shouldn't happen for free tier, but handle it)
            return {
                'allowed': True,
                'reason': 'Unlimited access',
                'limit': None,
                'used': used,
            }
        
        if used >= limit:
            logger.warning(f"[CHECK_FEATURE] {user_id}/{feature_name}: BLOCKED ({used}/{limit})")
            return {
                'allowed': False,
                'reason': f'Monthly limit reached ({used}/{limit} used)',
                'limit': limit,
                'used': used,
                'upgrade_required': True,
                'upgrade_message': f'Free tier limited to {limit} uses/month. Upgrade to continue.'
            }
        
        logger.info(f"[CHECK_FEATURE] {user_id}/{feature_name}: ALLOWED ({used}/{limit})")
        return {
            'allowed': True,
            'reason': f'Within limit ({used}/{limit})',
            'limit': limit,
            'used': used,
            'remaining': limit - used,
        }
    
    @staticmethod
    def use_feature(user_id, feature_name, input_size=0, usage_type='default'):
        """
        Record feature usage
        Returns: {'success': bool, 'message': str, 'usage': {...}}
        """
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        
        # Increment usage
        subscription.increment_feature_usage(feature_name)
        
        # Log usage
        FeatureUsageLog.objects.create(
            subscription=subscription,
            feature_name=feature_name,
            usage_type=usage_type,
            input_size=input_size,
        )
        
        # Get updated limits
        limits = subscription.get_feature_limits()
        feature_limit = limits.get(feature_name, {})
        
        logger.info(f"[FEATURE_USAGE] User {user_id} used {feature_name} "
                   f"({feature_limit.get('used', 0)}/{feature_limit.get('limit', 'unlimited')})")
        
        return {
            'success': True,
            'message': f'Feature "{feature_name}" usage recorded',
            'usage': {
                'feature': feature_name,
                'limit': feature_limit.get('limit'),
                'used': feature_limit.get('used'),
                'remaining': (feature_limit.get('limit') - feature_limit.get('used'))
                            if feature_limit.get('limit') else None,
            }
        }
    
    @staticmethod
    def get_usage_dashboard(user_id):
        """
        Get complete usage dashboard for user
        Returns all features with limits and usage
        """
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        limits = subscription.get_feature_limits()
        
        dashboard = {
            'user_id': user_id,
            'plan': subscription.plan.upper(),
            'subscription_id': str(subscription.id),
            'features': {},
            'billing': {},
        }
        
        # Add feature usage
        for feature_name, feature_data in limits.items():
            limit = feature_data['limit']
            used = feature_data['used']
            remaining = None if limit is None else max(0, limit - used)
            
            dashboard['features'][feature_name] = {
                'display_name': FeatureUsageService.FEATURES.get(feature_name, feature_name),
                'limit': limit,
                'used': used,
                'remaining': remaining,
                'unlimited': limit is None,
                'percentage_used': int((used / limit * 100)) if limit else 0,
            }
        
        # Add billing info
        if subscription.subscription_plan:
            plan = subscription.subscription_plan
            dashboard['billing'] = {
                'first_month_price': float(plan.first_month_price),
                'recurring_price': float(plan.recurring_price),
                'is_trial': subscription.is_trial,
                'trial_end_date': subscription.trial_end_date.isoformat() if subscription.trial_end_date else None,
                'subscription_start_date': subscription.subscription_start_date.isoformat(),
                'next_billing_date': subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
                'subscription_status': subscription.subscription_status,
            }
        
        return dashboard
    
    @staticmethod
    def check_subscription_active(user_id):
        """Check if user has active subscription"""
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        
        # Check if subscription is active
        if subscription.plan == 'free':
            return True  # Free plan is always active
        
        if subscription.subscription_status != 'active':
            return False
        
        # Check if subscription hasn't expired
        if subscription.subscription_end_date:
            if timezone.now() > subscription.subscription_end_date:
                return False
        
        return True
    
    @staticmethod
    def activate_subscription(user_id, plan_name='basic'):
        """Activate subscription after payment"""
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        
        plan = SubscriptionPlan.objects.filter(name=plan_name).first()
        if not plan:
            return {
                'success': False,
                'error': f'Plan "{plan_name}" not found',
            }
        
        subscription.plan = plan_name
        subscription.subscription_plan = plan
        subscription.subscription_status = 'active'
        subscription.is_trial = True
        subscription.trial_end_date = timezone.now() + timedelta(days=30)
        subscription.next_billing_date = subscription.trial_end_date
        subscription.subscription_start_date = timezone.now()
        subscription.usage_reset_date = timezone.now()
        subscription.save()
        
        logger.info(f"[SUBSCRIPTION_ACTIVATED] User {user_id} activated {plan_name} plan")
        
        return {
            'success': True,
            'message': f'Subscription activated for {plan_name} plan',
            'subscription': {
                'id': str(subscription.id),
                'plan': subscription.plan,
                'status': subscription.subscription_status,
                'is_trial': subscription.is_trial,
                'trial_end_date': subscription.trial_end_date.isoformat(),
            }
        }
    
    @staticmethod
    def reset_monthly_usage(user_id):
        """Reset monthly usage counters (usually called on billing date)"""
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        subscription.reset_monthly_usage()
        
        logger.info(f"[MONTHLY_RESET] User {user_id} monthly usage reset")
        
        return {
            'success': True,
            'message': 'Monthly usage reset',
        }
    
    @staticmethod
    def get_feature_limits_dict(user_id):
        """Get feature limits as simple dict for quick checks"""
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        limits = subscription.get_feature_limits()
        
        result = {}
        for feature_name, feature_data in limits.items():
            result[feature_name] = {
                'limit': feature_data['limit'],
                'used': feature_data['used'],
                'can_use': subscription.can_use_feature(feature_name),
            }
        
        return result
    
    @staticmethod
    def get_usage_stats(user_id):
        """Get usage statistics"""
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        limits = subscription.get_feature_limits()
        
        total_limit = 0
        total_used = 0
        
        for feature_name, feature_data in limits.items():
            limit = feature_data['limit']
            used = feature_data['used']
            
            if limit is not None:
                total_limit += limit
                total_used += used
        
        usage_logs = FeatureUsageLog.objects.filter(subscription=subscription)
        
        return {
            'total_limit': total_limit if total_limit > 0 else None,
            'total_used': total_used,
            'total_logs': usage_logs.count(),
            'latest_usage': usage_logs.first().created_at.isoformat() if usage_logs.exists() else None,
            'plan': subscription.plan,
        }
