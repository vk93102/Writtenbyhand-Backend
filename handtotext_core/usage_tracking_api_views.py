"""
Usage Dashboard API Views
Endpoints for user to track feature usage and plan limits
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .feature_usage_service import FeatureUsageService
from .decorators import require_auth
from .models import FeatureUsageLog

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
@require_auth
def usage_dashboard(request):
    """
    Get user's usage dashboard
    GET /api/usage/dashboard/
    Returns: Feature usage, limits, billing info
    """
    try:
        user_id = request.user_id
        
        dashboard = FeatureUsageService.get_usage_dashboard(user_id)
        
        return JsonResponse({
            'success': True,
            'dashboard': dashboard,
        })
    
    except Exception as e:
        logger.exception(f"[USAGE_DASHBOARD] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def feature_status(request, feature_name):
    """
    Check status of a specific feature
    GET /api/usage/feature/<feature_name>/
    Returns: Can use, limit, usage, remaining
    """
    try:
        user_id = request.user_id
        
        status = FeatureUsageService.check_feature_available(user_id, feature_name)
        
        return JsonResponse({
            'success': True,
            'feature': feature_name,
            'status': status,
        })
    
    except Exception as e:
        logger.exception(f"[FEATURE_STATUS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
@require_auth
def check_feature_usage(request):
    """
    Check if user can use a feature before making the actual request
    POST /api/usage/check/
    Body: {"feature": "quiz", "extra_info": {...}}
    """
    try:
        user_id = request.user_id
        data = json.loads(request.body)
        feature_name = data.get('feature')
        
        if not feature_name:
            return JsonResponse({
                'success': False,
                'error': 'feature name is required',
            }, status=400)
        
        status = FeatureUsageService.check_feature_available(user_id, feature_name)
        
        if not status['allowed']:
            return JsonResponse({
                'success': False,
                'error': status['reason'],
                'status': status,
            }, status=403)
        
        return JsonResponse({
            'success': True,
            'message': 'Feature available',
            'status': status,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON',
        }, status=400)
    except Exception as e:
        logger.exception(f"[CHECK_FEATURE_USAGE] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
@require_auth
def record_feature_usage(request):
    """
    Record feature usage after successful usage
    POST /api/usage/record/
    Body: {"feature": "quiz", "input_size": 1000, "usage_type": "text"}
    """
    try:
        user_id = request.user_id
        data = json.loads(request.body)
        
        feature_name = data.get('feature')
        input_size = data.get('input_size', 0)
        usage_type = data.get('usage_type', 'default')
        
        if not feature_name:
            return JsonResponse({
                'success': False,
                'error': 'feature name is required',
            }, status=400)
        
        result = FeatureUsageService.use_feature(
            user_id=user_id,
            feature_name=feature_name,
            input_size=input_size,
            usage_type=usage_type,
        )
        
        return JsonResponse(result)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON',
        }, status=400)
    except Exception as e:
        logger.exception(f"[RECORD_FEATURE_USAGE] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def subscription_status(request):
    """
    Get user's subscription status
    GET /api/usage/subscription/
    """
    try:
        user_id = request.user_id
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        is_active = FeatureUsageService.check_subscription_active(user_id)
        
        return JsonResponse({
            'success': True,
            'subscription': {
                'id': str(subscription.id),
                'plan': subscription.plan.upper(),
                'is_active': is_active,
                'status': subscription.subscription_status,
                'is_trial': subscription.is_trial,
                'trial_end_date': subscription.trial_end_date.isoformat() if subscription.trial_end_date else None,
                'subscription_start_date': subscription.subscription_start_date.isoformat(),
                'next_billing_date': subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
                'last_payment_date': subscription.last_payment_date.isoformat() if subscription.last_payment_date else None,
            }
        })
    
    except Exception as e:
        logger.exception(f"[SUBSCRIPTION_STATUS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def usage_stats(request):
    """
    Get usage statistics and trends
    GET /api/usage/stats/
    """
    try:
        user_id = request.user_id
        stats = FeatureUsageService.get_usage_stats(user_id)
        
        return JsonResponse({
            'success': True,
            'stats': stats,
        })
    
    except Exception as e:
        logger.exception(f"[USAGE_STATS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


# ============================================================================
# REAL-TIME USAGE TRACKING ENDPOINTS
# ============================================================================

@require_http_methods(["GET"])
@require_auth
def real_time_usage(request):
    """
    Get real-time usage data for all features
    GET /api/usage/real-time/
    
    Returns detailed usage information updated in real-time
    """
    try:
        user_id = request.user_id
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        
        # Get latest usage logs (last 24 hours) - filter through subscription
        today = timezone.now() - timezone.timedelta(days=1)
        recent_logs = FeatureUsageLog.objects.filter(
            subscription=subscription,
            created_at__gte=today
        ).values('feature_name').order_by('feature_name')
        
        # Build feature usage breakdown
        feature_usage = {}
        for feature_name in FeatureUsageService.FEATURES.keys():
            status = FeatureUsageService.check_feature_available(user_id, feature_name)
            limits = subscription.get_feature_limits()
            
            if feature_name in limits:
                feature_data = limits[feature_name]
                feature_usage[feature_name] = {
                    'name': FeatureUsageService.FEATURES.get(feature_name, feature_name),
                    'used': feature_data.get('used', 0),
                    'limit': feature_data.get('limit'),
                    'remaining': feature_data.get('limit', 0) - feature_data.get('used', 0) if feature_data.get('limit') else 'Unlimited',
                    'percentage': round((feature_data.get('used', 0) / feature_data.get('limit', 1) * 100), 2) if feature_data.get('limit') else 100,
                    'allowed': status['allowed'],
                }
        
        return JsonResponse({
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'plan': subscription.plan,
            'subscription_status': subscription.subscription_status,
            'feature_usage': feature_usage,
            'summary': {
                'total_features': len(feature_usage),
                'features_available': sum(1 for f in feature_usage.values() if f['allowed']),
                'features_exhausted': sum(1 for f in feature_usage.values() if not f['allowed']),
            }
        })
    
    except Exception as e:
        logger.exception(f"[REAL_TIME_USAGE] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def usage_history(request):
    """
    Get detailed usage history
    GET /api/usage/history/?feature=quiz&days=7
    
    Query parameters:
    - feature: specific feature name (optional)
    - days: number of days to retrieve (default: 7, max: 30)
    """
    try:
        user_id = request.user_id
        feature = request.GET.get('feature')
        days = int(request.GET.get('days', 7))
        
        # Validate days parameter
        days = min(days, 30)  # Max 30 days
        days = max(days, 1)   # Min 1 day
        
        # Get subscription first
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        
        # Get historical logs - filter through subscription
        start_date = timezone.now() - timezone.timedelta(days=days)
        query = FeatureUsageLog.objects.filter(
            subscription=subscription,
            created_at__gte=start_date
        )
        
        if feature:
            query = query.filter(feature_name=feature)
        
        logs = query.order_by('-created_at').values(
            'feature_name', 'input_size', 'usage_type', 'created_at'
        )[:100]  # Limit to 100 entries
        
        # Group by feature
        history_by_feature = {}
        for log in logs:
            feat = log['feature_name']
            if feat not in history_by_feature:
                history_by_feature[feat] = []
            history_by_feature[feat].append({
                'input_size': log['input_size'],
                'type': log['usage_type'],
                'timestamp': log['created_at'].isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'query_period_days': days,
            'start_date': start_date.isoformat(),
            'end_date': timezone.now().isoformat(),
            'history': history_by_feature,
            'total_entries': len(logs),
        })
    
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid days parameter (must be integer between 1 and 30)',
        }, status=400)
    except Exception as e:
        logger.exception(f"[USAGE_HISTORY] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


# ============================================================================
# TEST ENDPOINTS FOR USAGE RESTRICTIONS
# ============================================================================

@require_http_methods(["POST"])
@csrf_exempt
@require_auth
def test_feature_restriction(request):
    """
    Test endpoint to verify feature restrictions are working
    POST /api/usage/test/restriction/
    Body: {"feature": "quiz", "simulate_quota_exhausted": true}
    
    This endpoint is for testing purposes only and simulates feature usage
    """
    try:
        user_id = request.user_id
        data = json.loads(request.body)
        feature_name = data.get('feature')
        simulate_exhausted = data.get('simulate_quota_exhausted', False)
        
        if not feature_name:
            return JsonResponse({
                'success': False,
                'error': 'feature name is required',
            }, status=400)
        
        # Check current status
        status = FeatureUsageService.check_feature_available(user_id, feature_name)
        
        if simulate_exhausted:
            # Simulate exhausting the quota for testing
            subscription = FeatureUsageService.get_or_create_subscription(user_id)
            limits = subscription.get_feature_limits()
            
            if feature_name in limits:
                limit = limits[feature_name]['limit']
                used = limits[feature_name]['used']
                remaining = limit - used if limit else 'Unlimited'
                
                return JsonResponse({
                    'success': True,
                    'test_type': 'quota_exhaustion_simulation',
                    'feature': feature_name,
                    'current_usage': {
                        'used': used,
                        'limit': limit,
                        'remaining': remaining,
                    },
                    'would_be_allowed': True if remaining > 0 else False,
                    'status': status,
                })
        
        # Normal check
        return JsonResponse({
            'success': True,
            'test_type': 'feature_availability_check',
            'feature': feature_name,
            'allowed': status['allowed'],
            'reason': status['reason'],
            'status': status,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON',
        }, status=400)
    except Exception as e:
        logger.exception(f"[TEST_RESTRICTION] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
@require_auth
def test_multiple_features(request):
    """
    Test all features for availability and restrictions
    POST /api/usage/test/all-features/
    
    Comprehensive test to check if all features respect usage limits
    """
    try:
        user_id = request.user_id
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        
        test_results = {
            'timestamp': timezone.now().isoformat(),
            'user_id': user_id,
            'plan': subscription.plan,
            'subscription_status': subscription.subscription_status,
            'features_tested': {},
        }
        
        # Test each feature
        for feature_name, feature_display_name in FeatureUsageService.FEATURES.items():
            status = FeatureUsageService.check_feature_available(user_id, feature_name)
            limits = subscription.get_feature_limits()
            
            feature_info = {
                'display_name': feature_display_name,
                'allowed': status['allowed'],
                'reason': status.get('reason', ''),
                'is_unlimited': status.get('unlimited', False),
            }
            
            # Add limit info if applicable
            if feature_name in limits and not status.get('unlimited'):
                limit_data = limits[feature_name]
                feature_info.update({
                    'usage': limit_data['used'],
                    'limit': limit_data['limit'],
                    'remaining': limit_data['limit'] - limit_data['used'],
                    'percentage_used': round((limit_data['used'] / limit_data['limit'] * 100), 2) if limit_data['limit'] else 0,
                })
            
            test_results['features_tested'][feature_name] = feature_info
        
        # Summary
        all_features = test_results['features_tested']
        test_results['summary'] = {
            'total_features': len(all_features),
            'features_available': sum(1 for f in all_features.values() if f['allowed']),
            'features_restricted': sum(1 for f in all_features.values() if not f['allowed']),
            'features_unlimited': sum(1 for f in all_features.values() if f['is_unlimited']),
        }
        
        return JsonResponse({
            'success': True,
            'test_results': test_results,
        })
    
    except Exception as e:
        logger.exception(f"[TEST_ALL_FEATURES] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


# ============================================================================
# ENFORCEMENT ENDPOINTS - RESTRICT ENDPOINTS BASED ON USAGE
# ============================================================================

@require_http_methods(["POST"])
@csrf_exempt
@require_auth
def enforce_usage_check(request):
    """
    Enforce strict usage checks before allowing feature access
    POST /api/usage/enforce-check/
    Body: {"feature": "quiz"}
    
    Returns 403 if usage limit exceeded, 200 if allowed
    """
    try:
        user_id = request.user_id
        data = json.loads(request.body)
        feature_name = data.get('feature')
        
        if not feature_name:
            return JsonResponse({
                'success': False,
                'error': 'feature name is required',
            }, status=400)
        
        # Strict enforcement - check feature availability
        status = FeatureUsageService.check_feature_available(user_id, feature_name)
        
        if not status['allowed']:
            logger.warning(f"[ENFORCE_CHECK] {user_id}/{feature_name}: BLOCKED - {status['reason']}")
            return JsonResponse({
                'success': False,
                'error': f'Feature access denied: {status["reason"]}',
                'feature': feature_name,
                'status': status,
            }, status=403)
        
        logger.info(f"[ENFORCE_CHECK] {user_id}/{feature_name}: ALLOWED")
        return JsonResponse({
            'success': True,
            'message': 'Feature access granted',
            'feature': feature_name,
            'remaining': status.get('limit'),
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON',
        }, status=400)
    except Exception as e:
        logger.exception(f"[ENFORCE_CHECK] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


@require_http_methods(["GET"])
@require_auth
def feature_restriction_details(request, feature_name):
    """
    Get detailed restriction information for a specific feature
    GET /api/usage/restriction/<feature_name>/
    
    Shows detailed limits, usage, and restriction reasons
    """
    try:
        user_id = request.user_id
        
        if feature_name not in FeatureUsageService.FEATURES:
            return JsonResponse({
                'success': False,
                'error': f'Feature "{feature_name}" not found',
            }, status=404)
        
        subscription = FeatureUsageService.get_or_create_subscription(user_id)
        status = FeatureUsageService.check_feature_available(user_id, feature_name)
        limits = subscription.get_feature_limits()
        
        restriction_info = {
            'feature': feature_name,
            'feature_display_name': FeatureUsageService.FEATURES[feature_name],
            'allowed': status['allowed'],
            'plan': subscription.plan,
            'subscription_status': subscription.subscription_status,
        }
        
        # Add detailed restriction info
        if feature_name in limits:
            limit_data = limits[feature_name]
            restriction_info.update({
                'usage': limit_data['used'],
                'limit': limit_data['limit'],
                'remaining': limit_data['limit'] - limit_data['used'],
                'percentage_used': round((limit_data['used'] / limit_data['limit'] * 100), 2),
                'can_use': limit_data['limit'] - limit_data['used'] > 0 if limit_data['limit'] else True,
            })
        elif status.get('unlimited'):
            restriction_info['unlimited'] = True
            restriction_info['can_use'] = True
        
        # Add reason if not allowed
        if not status['allowed']:
            restriction_info['restriction_reason'] = status.get('reason', 'Unknown')
            restriction_info['how_to_unlock'] = 'Upgrade your subscription plan to unlimited access'
        
        return JsonResponse({
            'success': True,
            'restriction_details': restriction_info,
            'timestamp': timezone.now().isoformat(),
        })
    
    except Exception as e:
        logger.exception(f"[RESTRICTION_DETAILS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

