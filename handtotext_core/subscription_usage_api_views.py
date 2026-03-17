"""
API Views for Subscription Management
Implements complete flow: Create → Pay → Webhook → Feature Access
"""
import json
import hmac
import hashlib
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .razorpay_subscription_service import RazorpaySubscriptionService
from .models import UserSubscription, SubscriptionPlan

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@csrf_exempt
def create_subscription(request):
    """
    Create new subscription with ₹1 trial
    POST /api/subscriptions/create/
    Body: {"user_id": "123", "plan": "basic"}
    """
    try:
        logger.info(f"[CREATE_SUBSCRIPTION] Request received. Content-Type: {request.content_type}")
        logger.info(f"[CREATE_SUBSCRIPTION] Raw body: {request.body}")
        
        data = json.loads(request.body)
        user_id = data.get('user_id')
        plan = data.get('plan', 'basic')
        
        logger.info(f"[CREATE_SUBSCRIPTION] Parsed data: user_id={user_id}, plan={plan}")
        
        if not user_id:
            logger.warning("[CREATE_SUBSCRIPTION] Missing user_id")
            return JsonResponse({
                'success': False,
                'error': 'user_id is required'
            }, status=400)
        
        # Validate plan
        if plan not in ['basic', 'premium']:
            logger.warning(f"[CREATE_SUBSCRIPTION] Invalid plan: {plan}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid plan. Choose: basic or premium'
            }, status=400)
        
        logger.info(f"[CREATE_SUBSCRIPTION] Creating subscription with RazorpaySubscriptionService")
        # Create subscription
        result = RazorpaySubscriptionService.create_subscription_with_trial(
            user_id=user_id,
            plan_name=plan
        )
        
        logger.info(f"[CREATE_SUBSCRIPTION] Service returned result: {result}")
        
        if result['success']:
            response_data = {
                'success': True,
                'subscription_id': result['subscription_id'],
                'payment_url': result['short_url'],
                'razorpay_key': settings.RAZORPAY_KEY_ID,
                'first_payment': f"₹{result['first_payment_amount']}",
                'recurring_payment': f"₹{result['recurring_amount']}",
                'message': result['message']
            }
            logger.info(f"[CREATE_SUBSCRIPTION] Returning success response: {response_data}")
            return JsonResponse(response_data)
        else:
            error_msg = result.get('error', 'Failed to create subscription')
            logger.error(f"[CREATE_SUBSCRIPTION] Service returned error: {error_msg}")
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=500)
            
    except json.JSONDecodeError as e:
        logger.error(f"[CREATE_SUBSCRIPTION] JSON decode error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.exception(f"[CREATE_SUBSCRIPTION] ERROR: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'debug_message': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def verify_payment(request):
    """
    Verify payment signature
    POST /api/subscriptions/verify-payment/
    Body: {
        "razorpay_subscription_id": "sub_xxx",
        "razorpay_payment_id": "pay_xxx",
        "razorpay_signature": "signature"
    }
    """
    try:
        data = json.loads(request.body)
        subscription_id = data.get('razorpay_subscription_id')
        payment_id = data.get('razorpay_payment_id')
        signature = data.get('razorpay_signature')
        
        if not all([subscription_id, payment_id, signature]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        # Verify signature
        is_valid = RazorpaySubscriptionService.verify_payment_signature(
            subscription_id, payment_id, signature
        )
        
        if is_valid:
            # Update subscription status
            user_sub = UserSubscription.objects.filter(
                razorpay_subscription_id=subscription_id
            ).first()
            
            if user_sub:
                user_sub.subscription_status = 'active'
                user_sub.save()
                
            return JsonResponse({
                'success': True,
                'message': 'Payment verified successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid signature'
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error in verify_payment: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def razorpay_webhook(request):
    """
    Razorpay webhook handler
    POST /api/subscriptions/webhook/
    
    Events handled:
    - subscription.activated
    - subscription.charged
    - subscription.cancelled
    - payment.failed
    """
    try:
        # Verify webhook signature
        webhook_signature = request.headers.get('X-Razorpay-Signature', '')
        webhook_body = request.body.decode('utf-8')
        
        # Verify signature
        expected_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode() if hasattr(settings, 'RAZORPAY_WEBHOOK_SECRET') else settings.RAZORPAY_KEY_SECRET.encode(),
            webhook_body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, webhook_signature):
            logger.warning("Invalid webhook signature")
            return JsonResponse({'success': False, 'error': 'Invalid signature'}, status=400)
        
        # Parse webhook data
        webhook_data = json.loads(webhook_body)
        event_type = webhook_data.get('event')
        payload = webhook_data.get('payload', {})
        
        logger.info(f"Webhook received: {event_type}")
        
        # Handle webhook
        result = RazorpaySubscriptionService.handle_webhook(event_type, payload)
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error in webhook handler: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_subscription_status(request):
    """
    Get user subscription status
    GET /api/subscriptions/status/?user_id=123
    """
    try:
        user_id = request.GET.get('user_id')
        
        if not user_id:
            return JsonResponse({
                'success': False,
                'error': 'user_id is required'
            }, status=400)
        
        try:
            user_sub = UserSubscription.objects.get(user_id=user_id)
            plan = user_sub.subscription_plan
            
            return JsonResponse({
                'success': True,
                'subscription': {
                    'plan': user_sub.plan,
                    'plan_name': plan.display_name if plan else user_sub.plan.upper(),
                    'status': user_sub.subscription_status,
                    'is_trial': user_sub.is_trial,
                    'trial_end_date': user_sub.trial_end_date.isoformat() if user_sub.trial_end_date else None,
                    'next_billing_date': user_sub.next_billing_date.isoformat() if user_sub.next_billing_date else None,
                    'last_payment_date': user_sub.last_payment_date.isoformat() if user_sub.last_payment_date else None,
                    'features': user_sub.get_feature_limits()
                }
            })
        except UserSubscription.DoesNotExist:
            return JsonResponse({
                'success': True,
                'subscription': {
                    'plan': 'basic',
                    'plan_name': 'BASIC',
                    'status': 'inactive',
                    'is_trial': False,
                    'features': SubscriptionPlan.objects.get(name='basic').get_feature_dict()
                }
            })
            
    except Exception as e:
        logger.error(f"Error in get_subscription_status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def cancel_subscription(request):
    """
    Cancel user subscription
    POST /api/subscriptions/cancel/
    Body: {"user_id": "123", "immediate": false}
    """
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        immediate = data.get('immediate', False)
        
        if not user_id:
            return JsonResponse({
                'success': False,
                'error': 'user_id is required'
            }, status=400)
        
        result = RazorpaySubscriptionService.cancel_subscription(
            user_id=user_id,
            cancel_at_cycle_end=not immediate
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error in cancel_subscription: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_available_plans(request):
    """
    Get all available subscription plans
    GET /api/subscriptions/plans/
    """
    try:
        plans = SubscriptionPlan.objects.all()
        
        plans_data = []
        for plan in plans:
            plans_data.append({
                'id': plan.id,
                'name': plan.name,
                'display_name': plan.display_name,
                'first_month_price': float(plan.first_month_price),
                'recurring_price': float(plan.recurring_price),
                'description': plan.description,
                'features': plan.get_feature_dict()
            })
        
        return JsonResponse({
            'success': True,
            'plans': plans_data
        })
        
    except Exception as e:
        logger.error(f"Error in get_available_plans: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
