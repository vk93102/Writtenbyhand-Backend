"""
Production-Ready Ads Management API Views
Handles Unity Ads integration with Django REST Framework
"""

import logging
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.models import User, AnonymousUser
from django.db.models import Q, Sum, Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import (
    AdImpressionLog, FeatureAdConfig, UserAdLimitTracker, 
    AdAnalytics, UserSubscription, SubscriptionPlan
)

logger = logging.getLogger(__name__)


class AdManager:
    """Core logic for ads management"""
    
    @staticmethod
    def check_should_show_ad(user, feature_name, platform='ios'):
        """
        Determine if ad should be shown for this user on this feature
        
        Returns:
            {
                'should_show': bool,
                'reason': str,
                'placement_ids': dict or None,
                'ad_type': str
            }
        """
        try:
            # Check if user is premium
            try:
                subscription = UserSubscription.objects.filter(user=user, is_active=True).first()
                if subscription and subscription.plan.name == 'premium':
                    return {
                        'should_show': False,
                        'reason': 'Premium user - no ads',
                        'placement_ids': None,
                        'ad_type': None
                    }
            except:
                pass  # No subscription, continue
            
            # Get feature ad config
            try:
                config = FeatureAdConfig.objects.get(
                    feature_name=feature_name,
                    is_active=True
                )
            except FeatureAdConfig.DoesNotExist:
                return {
                    'should_show': False,
                    'reason': 'Feature not configured for ads',
                    'placement_ids': None,
                    'ad_type': None
                }
            
            if not config.show_ad_after_use:
                return {
                    'should_show': False,
                    'reason': 'Feature ads disabled',
                    'placement_ids': None,
                    'ad_type': None
                }
            
            # Get or create user ad tracker
            tracker, _ = UserAdLimitTracker.objects.get_or_create(user=user)
            tracker.reset_daily_if_needed()
            
            # Check daily limit
            if tracker.ads_shown_today >= config.max_ads_per_day:
                return {
                    'should_show': False,
                    'reason': f'Daily limit reached ({config.max_ads_per_day})',
                    'placement_ids': None,
                    'ad_type': None
                }
            
            # Check frequency
            feature_uses = tracker.feature_use_counts.get(feature_name, 0)
            if config.show_frequency > 1 and (feature_uses + 1) % config.show_frequency != 0:
                return {
                    'should_show': False,
                    'reason': f'Frequency not met (every {config.show_frequency} uses)',
                    'placement_ids': None,
                    'ad_type': None
                }
            
            # Check if ad was shown today
            if config.skip_if_ad_seen_today:
                last_ad_today = AdImpressionLog.objects.filter(
                    user=user,
                    feature=feature_name,
                    created_at__date=timezone.now().date()
                ).exists()
                
                if last_ad_today:
                    return {
                        'should_show': False,
                        'reason': 'Ad already shown today for this feature',
                        'placement_ids': None,
                        'ad_type': None
                    }
            
            return {
                'should_show': True,
                'reason': 'Show ad',
                'placement_ids': {
                    'ios': config.ios_placement_id,
                    'android': config.android_placement_id,
                },
                'ad_type': config.ad_type,
            }
        
        except Exception as e:
            logger.error(f"Error checking ad display: {str(e)}")
            return {
                'should_show': False,
                'reason': f'Error: {str(e)}',
                'placement_ids': None,
                'ad_type': None
            }
    
    @staticmethod
    def log_ad_impression(user, feature_name, ad_type, platform, status_value, request=None):
        """Log an ad impression/interaction"""
        try:
            # Get client IP
            ip_address = None
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                ip_address = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
            
            # Get feature config
            config = FeatureAdConfig.objects.filter(
                feature_name=feature_name,
                is_active=True
            ).first()
            
            placement_id = None
            if config:
                if platform == 'ios':
                    placement_id = config.ios_placement_id
                elif platform == 'android':
                    placement_id = config.android_placement_id
            
            # Create log entry
            log_entry = AdImpressionLog.objects.create(
                user=user,
                feature=feature_name,
                ad_type=ad_type,
                platform=platform,
                status=status_value,
                unity_placement_id=placement_id,
                ip_address=ip_address,
                user_agent=request.META.get('HTTP_USER_AGENT', '') if request else ''
            )
            
            # Update user tracker
            tracker, _ = UserAdLimitTracker.objects.get_or_create(user=user)
            tracker.increment_feature_use(feature_name)
            
            if status_value == 'shown':
                tracker.ads_shown_today += 1
                tracker.last_ad_shown = timezone.now()
                tracker.save()
            
            logger.info(f"Ad logged: {user.username} - {feature_name} ({status_value})")
            return log_entry
        
        except Exception as e:
            logger.error(f"Error logging ad impression: {str(e)}")
            return None


# ============ API ENDPOINTS ============

@api_view(['POST'])
@permission_classes([AllowAny])
def check_should_show_ad(request):
    """
    Check if ad should be shown
    
    POST /api/ads/check-should-show-ad/
    {
        "feature_name": "daily_quiz",
        "platform": "ios" or "android",
        "user_id": "optional - if not provided, uses authenticated user"
    }
    
    Response:
    {
        "success": true,
        "should_show": true,
        "reason": "Show ad",
        "ad_type": "interstitial",
        "placement_ids": {
            "ios": "ios-placement-id",
            "android": "android-placement-id"
        }
    }
    """
    try:
        feature_name = request.data.get('feature_name')
        platform = request.data.get('platform', 'ios')
        user_id = request.data.get('user_id')
        
        if not feature_name:
            return Response(
                {'error': 'feature_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': f'User {user_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif request.user.is_authenticated:
            user = request.user
        else:
            # Use testuser for testing
            user, _ = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com'})
        
        result = AdManager.check_should_show_ad(user, feature_name, platform)
        
        return Response({
            'success': True,
            'should_show': result['should_show'],
            'reason': result['reason'],
            'ad_type': result['ad_type'],
            'placement_ids': result['placement_ids']
        })
    
    except Exception as e:
        logger.error(f"Error in check_should_show_ad: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def log_ad_impression(request):
    """
    Log an ad impression/interaction
    
    POST /api/ads/log-impression/
    {
        "feature_name": "daily_quiz",
        "ad_type": "interstitial",
        "platform": "ios",
        "status": "shown" or "clicked" or "closed" or "failed",
        "user_id": "optional - if not provided, uses authenticated user"
    }
    
    Response:
    {
        "success": true,
        "message": "Ad shown logged successfully",
        "log_id": "uuid"
    }
    """
    try:
        feature_name = request.data.get('feature_name')
        ad_type = request.data.get('ad_type')
        platform = request.data.get('platform', 'ios')
        status_value = request.data.get('status', 'shown')
        user_id = request.data.get('user_id')
        
        if not all([feature_name, ad_type]):
            return Response(
                {'error': 'feature_name and ad_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': f'User {user_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif request.user.is_authenticated:
            user = request.user
        else:
            # Use testuser for testing
            user, _ = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com'})
        
        # Validate status
        valid_statuses = ['shown', 'clicked', 'closed', 'failed']
        if status_value not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        log_entry = AdManager.log_ad_impression(
            user=user,
            feature_name=feature_name,
            ad_type=ad_type,
            platform=platform,
            status_value=status_value,
            request=request
        )
        
        if not log_entry:
            return Response(
                {'error': 'Failed to log impression'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({
            'success': True,
            'message': f'Ad {status_value} logged successfully',
            'log_id': str(log_entry.id)
        })
    
    except Exception as e:
        logger.error(f"Error in log_ad_impression: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_user_ad_stats(request):
    """
    Get user's ad stats for today
    
    GET /api/ads/user-stats/
    
    Response:
    {
        "success": true,
        "is_premium": false,
        "ads_today": 3,
        "feature_uses": {"daily_quiz": 5, "mock_test": 2},
        "last_ad_shown": "2026-01-14T12:30:00Z",
        "impressions_breakdown": [...]
    }
    """
    try:
        user = request.user
        
        # Get tracker
        tracker, _ = UserAdLimitTracker.objects.get_or_create(user=user)
        tracker.reset_daily_if_needed()
        
        # Get today's impressions
        today = timezone.now().date()
        impressions = AdImpressionLog.objects.filter(
            user=user,
            created_at__date=today
        ).values('ad_type', 'status').annotate(count=Count('id'))
        
        # Get premium status
        is_premium = False
        try:
            subscription = UserSubscription.objects.filter(user=user, is_active=True).first()
            if subscription and subscription.plan.name == 'premium':
                is_premium = True
        except:
            pass
        
        return Response({
            'success': True,
            'is_premium': is_premium,
            'ads_today': tracker.ads_shown_today,
            'feature_uses': tracker.feature_use_counts,
            'last_ad_shown': tracker.last_ad_shown.isoformat() if tracker.last_ad_shown else None,
            'impressions_breakdown': list(impressions)
        })
    
    except Exception as e:
        logger.error(f"Error in get_user_ad_stats: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def configure_feature_ads(request):
    """
    Admin: Get or configure feature ad settings
    
    GET /api/ads/configure-features/
    
    POST /api/ads/configure-features/
    {
        "feature_name": "daily_quiz",
        "feature_display_name": "Daily Quiz",
        "show_ad_after_use": true,
        "ad_type": "interstitial",
        "show_frequency": 1,
        "ios_placement_id": "placement-id-ios",
        "android_placement_id": "placement-id-android",
        "max_ads_per_day": 10,
        "skip_for_premium": true
    }
    """
    try:
        # Check admin permission
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Admin access required")
        
        if request.method == 'GET':
            configs = FeatureAdConfig.objects.all().values(
                'id', 'feature_name', 'feature_display_name', 'show_ad_after_use',
                'ad_type', 'show_frequency', 'ios_placement_id', 'android_placement_id',
                'max_ads_per_day', 'skip_for_premium', 'is_active'
            )
            return Response({
                'success': True,
                'features': list(configs)
            })
        
        # POST - Create or update
        feature_name = request.data.get('feature_name')
        if not feature_name:
            return Response(
                {'error': 'feature_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        config, created = FeatureAdConfig.objects.get_or_create(
            feature_name=feature_name,
            defaults={
                'feature_display_name': request.data.get('feature_display_name', feature_name),
            }
        )
        
        # Update fields
        config.feature_display_name = request.data.get('feature_display_name', config.feature_display_name)
        config.show_ad_after_use = request.data.get('show_ad_after_use', config.show_ad_after_use)
        config.ad_type = request.data.get('ad_type', config.ad_type)
        config.show_frequency = request.data.get('show_frequency', config.show_frequency)
        config.ios_placement_id = request.data.get('ios_placement_id', config.ios_placement_id)
        config.android_placement_id = request.data.get('android_placement_id', config.android_placement_id)
        config.max_ads_per_day = request.data.get('max_ads_per_day', config.max_ads_per_day)
        config.skip_for_premium = request.data.get('skip_for_premium', config.skip_for_premium)
        config.is_active = request.data.get('is_active', config.is_active)
        config.save()
        
        return Response({
            'success': True,
            'message': 'Feature ad config updated' if not created else 'Feature ad config created',
            'config': {
                'id': str(config.id),
                'feature_name': config.feature_name,
                'is_active': config.is_active
            }
        })
    
    except PermissionDenied as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN
        )
    except Exception as e:
        logger.error(f"Error in configure_feature_ads: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ad_analytics(request):
    """
    Get ad analytics (admin only)
    
    GET /api/ads/analytics/?days=7&feature=daily_quiz
    
    Response:
    {
        "success": true,
        "analytics": [
            {
                "date": "2026-01-14",
                "feature": "daily_quiz",
                "platform": "ios",
                "impressions": 100,
                "clicks": 5,
                "closes": 95,
                "failures": 0,
                "ctr": 5.0
            }
        ]
    }
    """
    try:
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Admin access required")
        
        days = int(request.query_params.get('days', 7))
        feature = request.query_params.get('feature')
        
        # Get analytics
        query = AdAnalytics.objects.filter(
            date__gte=timezone.now().date() - timedelta(days=days)
        )
        
        if feature:
            query = query.filter(feature=feature)
        
        analytics = query.values('date', 'feature', 'platform').annotate(
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
            closes=Sum('closes'),
            failures=Sum('failures')
        ).order_by('-date')
        
        # Calculate CTR
        for item in analytics:
            if item['impressions'] > 0:
                item['ctr'] = round((item['clicks'] / item['impressions']) * 100, 2)
            else:
                item['ctr'] = 0
        
        return Response({
            'success': True,
            'analytics': list(analytics)
        })
    
    except PermissionDenied as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN
        )
    except Exception as e:
        logger.error(f"Error in get_ad_analytics: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initialize_feature_configs(request):
    """
    Initialize default feature configs (admin only)
    
    POST /api/ads/initialize-features/
    
    Response:
    {
        "success": true,
        "message": "Initialized 4 feature configs",
        "total_features": 4
    }
    """
    try:
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Admin access required")
        
        features = [
            {
                'feature_name': 'daily_quiz',
                'feature_display_name': 'Daily Quiz',
                'show_frequency': 1,
                'max_ads_per_day': 10,
            },
            {
                'feature_name': 'mock_test',
                'feature_display_name': 'Mock Test',
                'show_frequency': 2,
                'max_ads_per_day': 5,
            },
            {
                'feature_name': 'pair_quiz',
                'feature_display_name': 'Pair Quiz',
                'show_frequency': 1,
                'max_ads_per_day': 8,
            },
            {
                'feature_name': 'ask_question',
                'feature_display_name': 'Ask Question',
                'show_frequency': 3,
                'max_ads_per_day': 3,
            },
        ]
        
        created_count = 0
        for feature in features:
            config, created = FeatureAdConfig.objects.get_or_create(
                feature_name=feature['feature_name'],
                defaults={
                    'feature_display_name': feature['feature_display_name'],
                    'show_frequency': feature['show_frequency'],
                    'max_ads_per_day': feature['max_ads_per_day'],
                    'show_ad_after_use': True,
                    'ad_type': 'interstitial',
                    'ios_placement_id': f"ios-{feature['feature_name']}",
                    'android_placement_id': f"android-{feature['feature_name']}",
                    'skip_for_premium': True,
                }
            )
            if created:
                created_count += 1
        
        return Response({
            'success': True,
            'message': f'Initialized {created_count} feature configs',
            'total_features': len(features)
        })
    
    except PermissionDenied as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_403_FORBIDDEN
        )
    except Exception as e:
        logger.error(f"Error in initialize_feature_configs: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
