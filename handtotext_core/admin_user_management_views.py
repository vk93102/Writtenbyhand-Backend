"""
Admin Users Dashboard API Views
Endpoints for admin to view users and feature usage tracking
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, Sum
from django.db import models
from .models import UserSubscription, FeatureUsageLog, UserCoins
from .decorators import require_auth
from .feature_usage_service import FeatureUsageService

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
@require_auth
def get_all_users(request):
    """
    Get all users with their subscription details and feature usage
    GET /api/admin/users/
    Returns: List of users with plans, usage, coins
    """
    try:
        # Check if user is admin (for now, we'll accept all authenticated users - you can add admin check)
        user_id = request.user_id
        
        # Get all users
        users = UserSubscription.objects.all().order_by('-created_at')
        
        users_data = []
        for user in users:
            # Get feature usage
            limits = user.get_feature_limits()
            
            # Calculate total usage
            total_used = sum(feature['used'] for feature in limits.values())
            total_limit = sum(feature['limit'] for feature in limits.values() if feature['limit'] is not None)
            
            # Get recent feature logs
            recent_logs = FeatureUsageLog.objects.filter(subscription=user).order_by('-created_at')[:5]
            
            # Get user coins
            user_coins = UserCoins.objects.filter(user_id=user.user_id).first()
            
            users_data.append({
                'user_id': user.user_id,
                'plan': user.plan.upper(),
                'subscription_id': str(user.id),
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
                'usage': {
                    'total_used': total_used,
                    'total_limit': total_limit if total_limit > 0 else None,
                },
                'feature_usage': limits,
                'recent_features_used': [
                    {
                        'feature': log.feature_name,
                        'usage_type': log.usage_type,
                        'input_size': log.input_size,
                        'used_at': log.created_at.isoformat(),
                    }
                    for log in recent_logs
                ],
                'coins': {
                    'total_coins': user_coins.coins if user_coins else 0,
                    'coins_earned': user_coins.coins_earned if user_coins else 0,
                    'coins_spent': user_coins.coins_spent if user_coins else 0,
                } if user_coins else {'total_coins': 0, 'coins_earned': 0, 'coins_spent': 0},
                'subscription_status': user.subscription_status,
                'is_trial': user.is_trial,
                'trial_end_date': user.trial_end_date.isoformat() if user.trial_end_date else None,
            })
        
        return JsonResponse({
            'success': True,
            'total_users': len(users_data),
            'users': users_data,
        })
    
    except Exception as e:
        logger.exception(f"[ADMIN_GET_USERS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def get_feature_users(request, feature_name):
    """
    Get all users who used a specific feature
    GET /api/admin/users/feature/<feature_name>/
    Returns: List of users with that feature usage
    """
    try:
        # Get all usage logs for the feature
        usage_logs = FeatureUsageLog.objects.filter(
            feature_name=feature_name
        ).select_related('subscription').order_by('-created_at')
        
        # Group by user
        users_features = {}
        for log in usage_logs:
            user_id = log.subscription.user_id
            if user_id not in users_features:
                users_features[user_id] = {
                    'user_id': user_id,
                    'subscription_id': str(log.subscription.id),
                    'plan': log.subscription.plan.upper(),
                    'feature': feature_name,
                    'total_uses': 0,
                    'total_input_size': 0,
                    'usage_types': set(),
                    'first_used': log.created_at.isoformat(),
                    'last_used': log.created_at.isoformat(),
                    'uses': []
                }
            
            # Update usage info
            users_features[user_id]['total_uses'] += 1
            users_features[user_id]['total_input_size'] += log.input_size
            users_features[user_id]['usage_types'].add(log.usage_type)
            users_features[user_id]['last_used'] = log.created_at.isoformat()
            users_features[user_id]['uses'].append({
                'usage_type': log.usage_type,
                'input_size': log.input_size,
                'used_at': log.created_at.isoformat(),
            })
        
        # Convert sets to lists
        for user_id in users_features:
            users_features[user_id]['usage_types'] = list(users_features[user_id]['usage_types'])
        
        return JsonResponse({
            'success': True,
            'feature': feature_name,
            'total_users_using_feature': len(users_features),
            'users': list(users_features.values()),
        })
    
    except Exception as e:
        logger.exception(f"[ADMIN_FEATURE_USERS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def get_user_detail(request, user_id):
    """
    Get detailed information about a specific user
    GET /api/admin/users/<user_id>/
    Returns: Complete user profile with all features and usage
    """
    try:
        user = UserSubscription.objects.get(user_id=user_id)
        
        # Get all feature logs for this user
        all_logs = FeatureUsageLog.objects.filter(subscription=user).order_by('-created_at')
        
        # Group logs by feature
        features_used = {}
        for log in all_logs:
            feature = log.feature_name
            if feature not in features_used:
                features_used[feature] = {
                    'feature': feature,
                    'total_uses': 0,
                    'usage_types': set(),
                    'total_input_size': 0,
                    'first_used': log.created_at.isoformat(),
                    'last_used': log.created_at.isoformat(),
                    'logs': []
                }
            
            features_used[feature]['total_uses'] += 1
            features_used[feature]['usage_types'].add(log.usage_type)
            features_used[feature]['total_input_size'] += log.input_size
            features_used[feature]['last_used'] = log.created_at.isoformat()
            features_used[feature]['logs'].append({
                'usage_type': log.usage_type,
                'input_size': log.input_size,
                'used_at': log.created_at.isoformat(),
            })
        
        # Convert sets to lists
        for feature in features_used:
            features_used[feature]['usage_types'] = list(features_used[feature]['usage_types'])
        
        # Get subscription limits
        limits = user.get_feature_limits()
        
        # Get user coins
        user_coins = UserCoins.objects.filter(user_id=user_id).first()
        
        return JsonResponse({
            'success': True,
            'user_id': user.user_id,
            'subscription_id': str(user.id),
            'plan': user.plan.upper(),
            'subscription_status': user.subscription_status,
            'created_at': user.created_at.isoformat(),
            'updated_at': user.updated_at.isoformat(),
            'is_trial': user.is_trial,
            'trial_end_date': user.trial_end_date.isoformat() if user.trial_end_date else None,
            'subscription_start_date': user.subscription_start_date.isoformat(),
            'next_billing_date': user.next_billing_date.isoformat() if user.next_billing_date else None,
            'plan_limits': limits,
            'features_used': features_used,
            'total_features_used': len(features_used),
            'total_feature_calls': sum(f['total_uses'] for f in features_used.values()),
            'coins': {
                'total_coins': user_coins.coins if user_coins else 0,
                'coins_earned': user_coins.coins_earned if user_coins else 0,
                'coins_spent': user_coins.coins_spent if user_coins else 0,
            } if user_coins else {'total_coins': 0, 'coins_earned': 0, 'coins_spent': 0},
        })
    
    except UserSubscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'User {user_id} not found',
        }, status=404)
    except Exception as e:
        logger.exception(f"[ADMIN_USER_DETAIL] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def get_usage_analytics(request):
    """
    Get overall platform usage analytics
    GET /api/admin/analytics/
    Returns: Total users, feature usage stats, plan distribution
    """
    try:
        # Total users
        total_users = UserSubscription.objects.count()
        
        # Plan distribution
        plan_distribution = UserSubscription.objects.values('plan').annotate(count=Count('plan')).order_by('-count')
        
        # Feature usage stats
        feature_usage = FeatureUsageLog.objects.values('feature_name').annotate(
            total_uses=Count('id'),
            total_input_size=models.Sum('input_size')
        ).order_by('-total_uses')
        
        # Total feature calls
        total_feature_calls = FeatureUsageLog.objects.count()
        
        # Get unique users who used features
        unique_feature_users = FeatureUsageLog.objects.values('subscription').distinct().count()
        
        # Get all features and count users who used them
        all_features = FeatureUsageService.FEATURES
        feature_user_counts = {}
        for feature_name in all_features:
            count = FeatureUsageLog.objects.filter(feature_name=feature_name).values('subscription').distinct().count()
            feature_user_counts[feature_name] = {
                'display_name': all_features[feature_name],
                'unique_users': count,
                'total_uses': FeatureUsageLog.objects.filter(feature_name=feature_name).count(),
            }
        
        return JsonResponse({
            'success': True,
            'platform_stats': {
                'total_users': total_users,
                'total_feature_calls': total_feature_calls,
                'unique_users_using_features': unique_feature_users,
            },
            'plan_distribution': list(plan_distribution),
            'feature_stats': list(feature_usage),
            'feature_user_breakdown': feature_user_counts,
        })
    
    except Exception as e:
        logger.exception(f"[ADMIN_ANALYTICS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def search_users(request):
    """
    Search users by user_id or plan
    GET /api/admin/users/search/?q=user_id_or_email&plan=free|basic|premium
    Returns: Matching users
    """
    try:
        query = request.GET.get('q', '').strip()
        plan_filter = request.GET.get('plan', '').strip().lower()
        
        users_query = UserSubscription.objects.all()
        
        # Filter by query
        if query:
            users_query = users_query.filter(user_id__icontains=query)
        
        # Filter by plan
        if plan_filter and plan_filter in ['free', 'basic', 'premium']:
            users_query = users_query.filter(plan=plan_filter)
        
        users_data = []
        for user in users_query.order_by('-created_at'):
            limits = user.get_feature_limits()
            
            # Get recent logs
            recent_logs = FeatureUsageLog.objects.filter(subscription=user).order_by('-created_at')[:3]
            
            # Get user coins
            user_coins = UserCoins.objects.filter(user_id=user.user_id).first()
            
            users_data.append({
                'user_id': user.user_id,
                'plan': user.plan.upper(),
                'subscription_id': str(user.id),
                'created_at': user.created_at.isoformat(),
                'total_uses': sum(feature['used'] for feature in limits.values()),
                'recent_features': [log.feature_name for log in recent_logs],
                'coins': user_coins.coins if user_coins else 0,
            })
        
        return JsonResponse({
            'success': True,
            'query': query,
            'plan': plan_filter,
            'results': users_data,
            'total_results': len(users_data),
        })
    
    except Exception as e:
        logger.exception(f"[ADMIN_SEARCH_USERS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)
