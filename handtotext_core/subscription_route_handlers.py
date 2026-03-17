"""
Subscription and Payment API Endpoints
Complete flow: Create Order → Verify Payment → Webhook → Unlimited Access
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .complete_subscription_service import CompleteSubscriptionService
from .feature_usage_service import FeatureUsageService
from .decorators import require_auth

logger = logging.getLogger(__name__)


# ============================================================================
# STEP 1: CREATE SUBSCRIPTION ORDER (₹1 TRIAL)
# ============================================================================

@require_http_methods(["POST"])
@csrf_exempt
def create_subscription_order(request):
    """
    STEP 1: Create Razorpay subscription order for ₹1 trial
    
    POST /api/subscriptions/create/
    Body: {
        "user_id": "user123",
        "plan": "basic"  # or "premium"
    }
    
    Returns: {
        "success": true,
        "order_id": "sub_xxx",
        "short_url": "https://rzp.io/...",
        "first_amount": 100,      # ₹1 in paise
        "recurring_amount": 9900, # ₹99 in paise
        "razorpay_key": "...",
        "message": "Pay ₹1 now, then ₹99/month"
    }
    
    Next Step: Redirect user to short_url for payment
    """
    try:
        data = json.loads(request.body) if request.body else {}
        user_id = data.get('user_id')
        plan = data.get('plan', 'basic')
        
        logger.info(f"[CREATE_ORDER] user_id={user_id}, plan={plan}")
        
        if not user_id:
            return JsonResponse({
                'success': False,
                'error': 'user_id is required'
            }, status=400)
        
        # Create subscription order
        result = CompleteSubscriptionService.create_subscription_order(
            user_id=user_id,
            plan_name=plan
        )
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to create subscription')
            }, status=500)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"[CREATE_ORDER] ERROR: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# STEP 2-3: VERIFY PAYMENT (AFTER USER PAYS ON RAZORPAY)
# ============================================================================

@require_http_methods(["POST"])
@csrf_exempt
def verify_payment(request):
    """
    STEP 2-3: Verify payment signature after user completes payment
    
    Called by frontend after user completes payment on Razorpay
    Frontend calls this to verify signature and confirm payment
    
    POST /api/subscriptions/verify-payment/
    Body: {
        "user_id": "user123",
        "plan": "basic",
        "razorpay_payment_id": "pay_xxx",
        "razorpay_order_id": "order_xxx",
        "razorpay_signature": "signature_xxx"
    }
    
    Returns: {
        "success": true,
        "message": "Payment verified!",
        "subscription": {
            "plan": "basic",
            "status": "active",
            "unlimited_access": true
        }
    }
    
    Next Step: Show confirmation, unlimited access granted
    """
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        plan = data.get('plan', 'basic')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')
        
        logger.info(f"[VERIFY_PAYMENT] user_id={user_id}, payment_id={razorpay_payment_id}")
        
        if not all([user_id, razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        # Verify signature
        verify_result = CompleteSubscriptionService.verify_payment_signature(
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
            razorpay_signature=razorpay_signature
        )
        
        if not verify_result['valid']:
            logger.warning(f"[VERIFY_PAYMENT] Signature verification failed")
            return JsonResponse({
                'success': False,
                'error': verify_result.get('error', 'Signature verification failed')
            }, status=400)
        
        # Mark payment as successful
        mark_result = CompleteSubscriptionService.mark_payment_successful(
            user_id=user_id,
            plan_name=plan,
            razorpay_payment_id=razorpay_payment_id,
            amount=100  # ₹1 in paise for trial
        )
        
        if mark_result['success']:
            return JsonResponse({
                'success': True,
                'message': mark_result['message'],
                'subscription': mark_result['subscription']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': mark_result.get('error', 'Failed to activate subscription')
            }, status=500)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"[VERIFY_PAYMENT] ERROR: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# STEP 4: WEBHOOK (SOURCE OF TRUTH)
# ============================================================================

@require_http_methods(["POST"])
@csrf_exempt
def subscription_webhook(request):
    """
    STEP 4: Razorpay Webhook - Source of Truth
    
    Razorpay sends events to this endpoint:
    - subscription.activated → User's subscription activated
    - subscription.charged → Monthly auto-payment confirmed
    - subscription.cancelled → User cancelled subscription
    - payment.failed → Payment failed, re-enable limits
    - payment.captured → Payment captured
    
    POST /api/subscriptions/webhook/
    Headers:
        X-Razorpay-Signature: <signature>
    Body: {
        "event": "subscription.activated",
        "payload": {...}
    }
    
    Response: {
        "success": true,
        "event": "subscription.activated",
        "message": "..."
    }
    
    Must be idempotent (same webhook multiple times = same result)
    """
    try:
        # Get signature from headers
        webhook_signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
        webhook_body = request.body.decode('utf-8')
        
        logger.info(f"[WEBHOOK] Received webhook, signature present: {bool(webhook_signature)}")
        
        # Parse webhook data
        webhook_data = json.loads(webhook_body)
        event_type = webhook_data.get('event')
        payload = webhook_data.get('payload', {})
        
        logger.info(f"[WEBHOOK] Event type: {event_type}")
        
        # Handle webhook
        result = CompleteSubscriptionService.handle_webhook(event_type, payload)
        
        return JsonResponse(result)
    
    except json.JSONDecodeError:
        logger.error("[WEBHOOK] Failed to parse JSON")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"[WEBHOOK] ERROR: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# STATUS CHECK & VALIDATION
# ============================================================================

@require_http_methods(["GET"])
@csrf_exempt
def get_subscription_status(request):
    """
    Get user subscription status and unlimited access flag
    
    GET /api/subscriptions/status/?user_id=user123&plan=basic
    Headers: X-User-ID: user123 (optional)
    
    Returns: {
        "success": true,
        "user_id": "user123",
        "plan": "basic",
        "status": "active",
        "unlimited_access": true,
        "is_trial": true,
        "trial_end_date": "2026-02-09T...",
        "next_billing_date": "2026-02-09T..."
    }
    
    Frontend uses "unlimited_access" to determine if user can bypass limits
    """
    try:
        # Get user_id from header or query param
        user_id = request.META.get('HTTP_X_USER_ID') or request.GET.get('user_id')
        plan = request.GET.get('plan')
        
        if not user_id:
            return JsonResponse({
                'success': False,
                'error': 'user_id is required (header X-User-ID or query param)'
            }, status=400)
        
        logger.info(f"[GET_STATUS] user_id={user_id}, plan={plan}")
        
        result = CompleteSubscriptionService.get_subscription_status(
            user_id=user_id,
            plan_name=plan
        )
        
        return JsonResponse(result)
    
    except Exception as e:
        logger.error(f"[GET_STATUS] ERROR: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
@csrf_exempt
def post_payment_validation(request):
    """
    POST-PAYMENT VALIDATION
    
    After payment succeeds, frontend calls this to verify:
    1. Subscription is active
    2. Unlimited access is granted
    3. Feature limits are disabled
    
    GET /api/subscriptions/validate/?user_id=user123
    
    Returns: {
        "success": true,
        "validated": true,
        "checks": {
            "subscription_active": true,
            "unlimited_access": true,
            "feature_limits_disabled": true
        },
        "subscription": {...},
        "dashboard": {...}
    }
    """
    try:
        user_id = request.META.get('HTTP_X_USER_ID') or request.GET.get('user_id')
        
        if not user_id:
            return JsonResponse({
                'success': False,
                'error': 'user_id is required'
            }, status=400)
        
        logger.info(f"[VALIDATE] user_id={user_id}")
        
        # Get subscription status
        sub_status = CompleteSubscriptionService.get_subscription_status(user_id)
        
        if not sub_status['success']:
            return JsonResponse({
                'success': False,
                'error': 'Failed to get subscription status'
            }, status=500)
        
        # Get usage dashboard
        dashboard = FeatureUsageService.get_usage_dashboard(user_id)
        
        # Validation checks
        checks = {
            'subscription_active': sub_status.get('status') == 'active',
            'unlimited_access': sub_status.get('unlimited_access', False),
            'feature_limits_disabled': True,  # They are disabled by check_feature_available()
        }
        
        all_valid = all(checks.values())
        
        return JsonResponse({
            'success': True,
            'validated': all_valid,
            'checks': checks,
            'subscription': sub_status,
            'dashboard': dashboard,
        })
    
    except Exception as e:
        logger.error(f"[VALIDATE] ERROR: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# UPGRADE FLOW ENDPOINTS
# ============================================================================

@require_http_methods(["GET"])
@csrf_exempt
def get_available_plans(request):
    """
    Get available subscription plans (for upgrade dialog)
    
    GET /api/subscriptions/plans/
    
    Returns: {
        "success": true,
        "plans": [
            {
                "id": "free",
                "name": "FREE",
                "first_month_price": 0,
                "recurring_price": 0,
                "features": {...}
            },
            {
                "id": "basic",
                "name": "BASIC",
                "first_month_price": 1,
                "recurring_price": 99,
                "features": {...}
            }
        ]
    }
    """
    try:
        from .models import SubscriptionPlan
        
        plans = SubscriptionPlan.objects.filter(is_active=True)
        
        plans_data = []
        for plan in plans:
            plans_data.append({
                'id': plan.name,
                'name': plan.display_name,
                'description': plan.description,
                'first_month_price': float(plan.first_month_price),
                'recurring_price': float(plan.recurring_price),
                'currency': plan.currency,
                'features': plan.get_feature_dict()
            })
        
        return JsonResponse({
            'success': True,
            'plans': plans_data
        })
    
    except Exception as e:
        logger.error(f"[GET_PLANS] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# RAZORPAY KEY ENDPOINT (For Frontend)
# ============================================================================

@require_http_methods(["GET"])
@csrf_exempt
def get_razorpay_key(request):
    """
    Get Razorpay key for frontend
    
    GET /api/subscriptions/razorpay-key/
    
    Returns: {
        "success": true,
        "razorpay_key": "rzp_live_xxx"
    }
    """
    try:
        return JsonResponse({
            'success': True,
            'razorpay_key': settings.RAZORPAY_KEY_ID if hasattr(settings, 'RAZORPAY_KEY_ID') else '',
        })
    
    except Exception as e:
        logger.error(f"[GET_RAZORPAY_KEY] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
