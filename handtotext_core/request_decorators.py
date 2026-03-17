"""
Feature Access Control Decorators
Enforce feature usage limits based on subscription plans
"""
from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from .models import UserSubscription
from django.utils import timezone
from django.http import JsonResponse
import jwt
import json
import logging

logger = logging.getLogger(__name__)


def require_feature_access(feature_name):
    """
    Decorator to check if user has access to a feature
    Usage: @require_feature_access('quiz')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Extract user_id from request
            if request.method == 'GET':
                user_id = request.query_params.get('user_id')
            else:
                user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({
                    'error': 'Authentication required',
                    'message': 'user_id is required to access this feature'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            try:
                # Get or create user subscription
                subscription, created = UserSubscription.objects.get_or_create(
                    user_id=user_id,
                    defaults={'plan': 'free'}
                )
                
                # Check if monthly reset is needed
                if subscription.usage_reset_date:
                    days_since_reset = (timezone.now() - subscription.usage_reset_date).days
                    if days_since_reset >= 30:
                        subscription.reset_monthly_usage()
                        logger.info(f"Reset monthly usage for user {user_id}")
                
                # Check feature access
                if not subscription.can_use_feature(feature_name):
                    limits = subscription.get_feature_limits()
                    feature_info = limits.get(feature_name, {})
                    
                    return Response({
                        'error': 'Feature limit reached',
                        'message': f'You have reached your {feature_name} limit for this month.',
                        'feature': feature_name,
                        'limit': feature_info.get('limit'),
                        'used': feature_info.get('used'),
                        'plan': subscription.plan,
                        'upgrade_required': True,
                        'upgrade_message': 'Upgrade to Premium for unlimited access! ₹1 for first month, then ₹99/month.'
                    }, status=status.HTTP_402_PAYMENT_REQUIRED)
                
                # Increment usage counter
                subscription.increment_feature_usage(feature_name)
                logger.info(f"User {user_id} used feature {feature_name}")
                
                # Proceed with the view
                return view_func(request, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error checking feature access: {e}", exc_info=True)
                return Response({
                    'error': 'Failed to check feature access',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return wrapper
    return decorator


def require_auth(view_func):
    """
    Decorator to verify JWT token and inject user_id into request
    Usage: @require_auth
    Extracts user_id from:
    1. JWT token in Authorization header (Bearer <token>)
    2. X-User-ID header (for testing/development)
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.conf import settings
        
        # Try X-User-ID header first (for testing and development)
        user_id = request.META.get('HTTP_X_USER_ID', '')
        if user_id:
            request.user_id = user_id
            request.user_token = {'user_id': user_id}
            return view_func(request, *args, **kwargs)
        
        # Try JWT token from Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'success': False,
                'error': 'Missing or invalid authorization header. Use "Authorization: Bearer <token>" or "X-User-ID: <user_id>"'
            }, status=401)
        
        token = auth_header.split(' ')[1]
        
        try:
            # Decode JWT token
            secret_key = getattr(settings, 'SECRET_KEY', 'your-secret-key')
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            
            # Extract user_id from token
            user_id = payload.get('user_id') or payload.get('id') or payload.get('sub')
            
            if not user_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid token: user_id not found'
                }, status=401)
            
            # Inject user_id into request
            request.user_id = user_id
            request.user_token = payload
            
            # Call the actual view
            return view_func(request, *args, **kwargs)
        
        except jwt.ExpiredSignatureError:
            return JsonResponse({
                'success': False,
                'error': 'Token has expired'
            }, status=401)
        except jwt.InvalidTokenError as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid token: {str(e)}'
            }, status=401)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Authentication failed: {str(e)}'
            }, status=401)
    
    return wrapper

def check_feature_access_class_based(feature_name):
    """
    Decorator for class-based views (APIView)
    Usage: @method_decorator(check_feature_access_class_based('quiz'), name='post')
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, request, *args, **kwargs):
            # Extract user_id from request
            if request.method == 'GET':
                user_id = request.query_params.get('user_id')
            else:
                user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({
                    'error': 'Authentication required',
                    'message': 'user_id is required to access this feature'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            try:
                # Get or create user subscription
                subscription, created = UserSubscription.objects.get_or_create(
                    user_id=user_id,
                    defaults={'plan': 'free'}
                )
                
                # Check if monthly reset is needed
                if subscription.usage_reset_date:
                    days_since_reset = (timezone.now() - subscription.usage_reset_date).days
                    if days_since_reset >= 30:
                        subscription.reset_monthly_usage()
                
                # Check feature access
                if not subscription.can_use_feature(feature_name):
                    limits = subscription.get_feature_limits()
                    feature_info = limits.get(feature_name, {})
                    
                    return Response({
                        'error': 'Feature limit reached',
                        'message': f'You have reached your {feature_name} limit for this month.',
                        'feature': feature_name,
                        'limit': feature_info.get('limit'),
                        'used': feature_info.get('used'),
                        'plan': subscription.plan,
                        'upgrade_required': True,
                        'upgrade_message': 'Upgrade to Premium for unlimited access! ₹1 for first month, then ₹99/month.'
                    }, status=status.HTTP_402_PAYMENT_REQUIRED)
                
                # Increment usage counter
                subscription.increment_feature_usage(feature_name)
                
                # Proceed with the method
                return method(self, request, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error checking feature access: {e}", exc_info=True)
                return Response({
                    'error': 'Failed to check feature access',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return wrapper
    return decorator
