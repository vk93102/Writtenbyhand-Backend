"""
Subscription Views - SIMPLIFIED Payment & Billing Workflow
Shows subscription status and billing information:
- Create orders (₹1 for 7 days trial, ₹99 monthly)
- Verify payments
- Show subscription details with next billing date

FOCUS: Simple payment workflow, not feature access gating
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
from django.utils import timezone
from datetime import timedelta
import logging

from .models import UserSubscription, Payment, FeatureUsageLog

logger = logging.getLogger(__name__)


# ============= COMMENTED OUT: Feature Access Check =============
# ❌ REMOVED: CheckFeatureAccessView - Not needed (all paid users get full access)
# Feature access can be checked directly: if plan in ['basic', 'premium']: has_access = true


class SubscriptionStatusView(APIView):
    """
    ✅ MAIN ENDPOINT - Get user subscription & billing status
    
    GET /api/subscription/status/?user_id=<user_id>
    
    Shows:
    - Current plan (free/basic/premium)
    - Subscription active status
    - Next billing date
    - Billing amount
    - Trial information
    
    Response:
        {
            "success": true,
            "user_id": "user123",
            "plan": "premium",
            "is_paid": true,
            "subscription_active": true,
            "subscription_start_date": "2026-01-15T10:30:00Z",
            "next_billing_date": "2026-02-15T10:30:00Z",
            "next_billing_amount": 99,
            "currency": "INR",
            "is_trial": true,
            "trial_end_date": "2026-01-22T10:30:00Z",
            "days_until_next_billing": 31,
            "subscription_status": "active",
            "auto_renewal": true
        }
    """
    parser_classes = [JSONParser]
    
    def get(self, request):
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response({
                'error': 'user_id is required',
                'example': '/api/subscription/status/?user_id=user123'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subscription, created = UserSubscription.objects.get_or_create(
                user_id=user_id,
                defaults={'plan': 'free'}
            )
            
            # Check if paid
            is_paid = subscription.plan in ['basic', 'premium']
            is_active = subscription.subscription_status == 'active'
            
            # Calculate days until next billing
            days_until = 0
            if subscription.next_billing_date:
                days_until = max(0, (subscription.next_billing_date - timezone.now()).days)
            
            # Get next billing amount
            next_billing_amount = 99 if is_paid else 0
            
            response_data = {
                'success': True,
                'user_id': subscription.user_id,
                'plan': subscription.plan,
                'is_paid': is_paid,
                'subscription_active': is_active,
                'subscription_status': subscription.subscription_status,
                'auto_renewal': is_active and is_paid,  # Auto-renewal enabled for active paid
                'subscription_start_date': subscription.subscription_start_date.isoformat() if subscription.subscription_start_date else None,
                'currency': 'INR',
            }
            
            # Add billing details for paid users
            if is_paid:
                response_data['next_billing_date'] = subscription.next_billing_date.isoformat() if subscription.next_billing_date else None
                response_data['next_billing_amount'] = next_billing_amount
                response_data['days_until_next_billing'] = days_until
                response_data['is_trial'] = subscription.is_trial
                
                if subscription.is_trial and subscription.trial_end_date:
                    response_data['trial_end_date'] = subscription.trial_end_date.isoformat()
                    response_data['trial_days_remaining'] = max(0, (subscription.trial_end_date - timezone.now()).days)
            
            logger.info(f"[SUBSCRIPTION_STATUS] User: {user_id}, Plan: {subscription.plan}, Paid: {is_paid}, Active: {is_active}")
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting subscription status: {e}")
            return Response({
                'error': 'Failed to get subscription status',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogFeatureUsageView(APIView):
    """
    ✅ Log feature usage for tracking
    
    POST /api/subscription/log-usage/
    """
    parser_classes = [JSONParser]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        feature_name = request.data.get('feature')
        
        if not user_id or not feature_name:
            return Response({
                'error': 'user_id and feature are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subscription, _ = UserSubscription.objects.get_or_create(
                user_id=user_id,
                defaults={'plan': 'free'}
            )
            
            subscription.increment_feature_usage(feature_name)
            
            FeatureUsageLog.objects.create(
                subscription=subscription,
                feature_name=feature_name,
                usage_type='attempt',
                input_size=0
            )
            
            logger.info(f"[LOG_USAGE] Feature: {feature_name}, User: {user_id}, Plan: {subscription.plan}")
            
            return Response({
                'success': True,
                'message': 'Feature usage logged',
                'user_id': user_id,
                'feature': feature_name
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error logging feature usage: {e}")
            return Response({
                'error': 'Failed to log feature usage',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===================== OLD VIEWS - COMMENTED OUT =====================
# All payment/billing operations are handled in payment_views.py
#
# WORKING ENDPOINTS:
# ===================
# GET  /api/subscription/status/?user_id=X        - Get subscription & billing status
# POST /api/subscription/log-usage/               - Log feature usage
# POST /api/payment/create-order/                 - Create ₹1 or ₹99 order
# POST /api/payment/verify/                       - Verify payment
# GET  /api/payment/razorpay-key/                 - Get Razorpay key
# GET  /api/razorpay/history/?user_id=X          - Get payment history
#
# PAYMENT FLOW:
# ==============
# 1. POST /api/payment/create-order/ 
#    - Input: {"plan": "premium", "user_id": "user123"}
#    - Output: {"order_id": "order_...", "amount": 1, "key_id": "rzp_..."}
#
# 2. User completes payment in Razorpay modal
#
# 3. POST /api/payment/verify/
#    - Input: {"razorpay_order_id": "...", "razorpay_payment_id": "...", "razorpay_signature": "..."}
#    - Output: {"success": true, "subscription": {...}}
#
# 4. GET /api/subscription/status/?user_id=user123
#    - Shows: next_billing_date, is_trial, trial_end_date, etc.
#
# ====================================================================
    """
    ✅ Log feature usage for tracking
    
    POST /api/subscription/log-usage/
    
    Request:
        {
            "user_id": "user123",
            "feature": "quiz",
            "type": "attempt"
        }
    
    Response:
        {
            "success": true,
            "message": "Feature usage logged",
            "plan": "premium",
            "feature": "quiz"
        }
    """
    parser_classes = [JSONParser]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        feature_name = request.data.get('feature')
        usage_type = request.data.get('type', 'attempt')
        
        if not user_id or not feature_name:
            return Response({
                'error': 'user_id and feature are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            subscription, _ = UserSubscription.objects.get_or_create(
                user_id=user_id,
                defaults={'plan': 'free'}
            )
            
            # Log usage
            subscription.increment_feature_usage(feature_name)
            
            # Create detailed log
            FeatureUsageLog.objects.create(
                subscription=subscription,
                feature_name=feature_name,
                usage_type=usage_type,
                input_size=0
            )
            
            logger.info(f"[LOG_USAGE] Feature: {feature_name}, User: {user_id}, Plan: {subscription.plan}")
            
            return Response({
                'success': True,
                'message': 'Feature usage logged',
                'plan': subscription.plan,
                'feature': feature_name,
                'user_id': user_id
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error logging feature usage: {e}")
            return Response({
                'error': 'Failed to log feature usage',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============= COMMENTED OUT: OLD BILLING & PLAN VIEWS =============
# These views have been removed as per simplification request
# Pricing/plan information is now only in payment_views.py
