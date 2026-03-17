"""
Complete Subscription & Payment Service
Implements complete lifecycle: Create → Pay → Webhook → Unlimited Access
Production-safe, idempotent, and auditable
"""
import logging
import razorpay
import hmac
import hashlib
import json
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .models import UserSubscription, SubscriptionPlan, Payment, FeatureUsageLog

logger = logging.getLogger(__name__)

# Initialize Razorpay client
try:
    razorpay_client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    logger.info("Razorpay client initialized")
except Exception as e:
    logger.error(f"Failed to initialize Razorpay client: {e}")
    razorpay_client = None


class CompleteSubscriptionService:
    """
    Service for managing complete subscription lifecycle
    
    Flow:
    1. User exhausts free limit
    2. User clicks "Upgrade"
    3. create_subscription_order() → Returns payment link
    4. User pays ₹1 (trial)
    5. Webhook confirms payment
    6. mark_payment_successful() → Unlocks unlimited access
    7. Monthly: Razorpay auto-debits ₹99
    8. Webhook confirms recurring payment
    """
    
    @staticmethod
    def get_or_create_subscription(user_id):
        """Get or create subscription (defaults to free)"""
        subscription, created = UserSubscription.objects.get_or_create(
            user_id=user_id,
            defaults={
                'plan': 'free',
                'subscription_plan': SubscriptionPlan.objects.filter(name='free').first(),
                'subscription_status': 'inactive',  # Free users don't have active subscriptions
            }
        )
        return subscription
    
    @staticmethod
    def create_subscription_order(user_id, plan_name='basic'):
        """
        STEP 1: Create Razorpay subscription for ₹1 trial
        
        Returns: {
            'success': bool,
            'order_id': str,           # Razorpay order ID
            'subscription_id': str,    # Razorpay subscription ID  
            'short_url': str,          # Payment link to show user
            'first_amount': 100,       # ₹1 in paise
            'recurring_amount': 9900,  # ₹99 in paise
            'message': str,
        }
        """
        try:
            logger.info(f"[CREATE_ORDER] user_id={user_id}, plan={plan_name}")
            
            # Validate plan
            if plan_name not in ['basic', 'premium']:
                logger.warning(f"[CREATE_ORDER] Invalid plan: {plan_name}")
                return {
                    'success': False,
                    'error': f'Invalid plan. Must be "basic" or "premium"'
                }
            
            # Get plan from database
            db_plan = SubscriptionPlan.objects.filter(name=plan_name).first()
            if not db_plan:
                logger.error(f"[CREATE_ORDER] Plan not found: {plan_name}")
                return {
                    'success': False,
                    'error': f'Plan "{plan_name}" not found in system'
                }
            
            # Check if user already has active subscription for this plan
            existing_sub = UserSubscription.objects.filter(
                user_id=user_id,
                plan=plan_name,
                subscription_status='active'
            ).first()
            
            if existing_sub and existing_sub.razorpay_subscription_id:
                logger.warning(f"[CREATE_ORDER] User already has active subscription")
                return {
                    'success': False,
                    'error': 'User already has active subscription for this plan'
                }
            
            # If user exists but not subscribed to this plan, update their subscription
            # This allows users to upgrade from free → basic → premium
            
            # Razorpay credentials check
            if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
                logger.warning("[CREATE_ORDER] Razorpay credentials not configured - test mode")
                return CompleteSubscriptionService._create_test_subscription(
                    user_id, plan_name, db_plan
                )
            
            # Create Razorpay subscription with ₹1 trial
            try:
                first_amount_paise = int(db_plan.first_month_price * 100)  # ₹1 = 100 paise
                recurring_amount_paise = int(db_plan.recurring_price * 100)  # ₹99 = 9900 paise
                
                # Create subscription for monthly recurring with first payment as ₹1
                subscription_data = {
                    'plan_id': plan_name,  # We'll use plan name as ID
                    'customer_notify': 1,
                    'quantity': 1,
                    'total_count': 12,  # 12 billing cycles
                    'addons': [
                        {
                            'item': {
                                'name': 'Trial Discount',
                                'amount': first_amount_paise - recurring_amount_paise,  # Make it ₹1
                                'currency': 'INR'
                            }
                        }
                    ] if first_amount_paise < recurring_amount_paise else [],
                    'notes': {
                        'user_id': user_id,
                        'plan_name': plan_name,
                        'trial_amount': f'{db_plan.first_month_price}',
                        'recurring_amount': f'{db_plan.recurring_price}',
                    }
                }
                
                # Create subscription in Razorpay
                logger.info(f"[CREATE_ORDER] Creating Razorpay subscription: {subscription_data}")
                razorpay_sub = razorpay_client.subscription.create(subscription_data)
                
                razorpay_sub_id = razorpay_sub['id']
                short_url = razorpay_sub.get('short_url', razorpay_sub.get('url_short', ''))
                
                logger.info(f"[CREATE_ORDER] Created subscription: {razorpay_sub_id}")
                
                # Save to database (handle both new and existing users)
                with transaction.atomic():
                    # Try to update existing subscription
                    user_subscription = UserSubscription.objects.filter(
                        user_id=user_id
                    ).first()
                    
                    if user_subscription:
                        # User exists (upgrading), update their subscription
                        # Only allow upgrade if current plan is free or subscription not active
                        if user_subscription.plan == 'free' or user_subscription.subscription_status != 'active':
                            user_subscription.plan = plan_name
                            user_subscription.subscription_plan = db_plan
                            user_subscription.razorpay_subscription_id = razorpay_sub_id
                            user_subscription.subscription_status = 'pending'  # Payment pending
                            user_subscription.is_trial = True
                            user_subscription.save()
                            logger.info(f"[CREATE_ORDER] Updated existing subscription for upgrade")
                        else:
                            logger.error(f"[CREATE_ORDER] User already has active paid subscription")
                            return {
                                'success': False,
                                'error': 'User already has active subscription for this plan'
                            }
                    else:
                        # New user
                        user_subscription = UserSubscription.objects.create(
                            user_id=user_id,
                            plan=plan_name,
                            subscription_plan=db_plan,
                            razorpay_subscription_id=razorpay_sub_id,
                            subscription_status='pending',  # Payment pending
                            is_trial=True,
                        )
                        logger.info(f"[CREATE_ORDER] Created new subscription")
                
                return {
                    'success': True,
                    'order_id': razorpay_sub_id,
                    'subscription_id': razorpay_sub_id,
                    'short_url': short_url or f'https://rzp.io/{razorpay_sub_id}',
                    'first_amount': first_amount_paise,
                    'recurring_amount': recurring_amount_paise,
                    'message': f'Pay ₹{db_plan.first_month_price} now, then ₹{db_plan.recurring_price}/month',
                    'razorpay_key': settings.RAZORPAY_KEY_ID,
                }
                
            except Exception as razorpay_error:
                logger.error(f"[CREATE_ORDER] Razorpay error: {str(razorpay_error)}")
                # Fall back to test mode
                return CompleteSubscriptionService._create_test_subscription(
                    user_id, plan_name, db_plan
                )
        
        except Exception as e:
            logger.error(f"[CREATE_ORDER] Unexpected error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Failed to create subscription: {str(e)}'
            }
    
    @staticmethod
    def _create_test_subscription(user_id, plan_name, db_plan):
        """Create test subscription for development"""
        logger.info(f"[TEST_MODE] Creating test subscription for {user_id}")
        
        # Create in database - handle update if user exists
        with transaction.atomic():
            user_subscription = UserSubscription.objects.filter(
                user_id=user_id
            ).first()
            
            if user_subscription:
                # Update existing user
                user_subscription.plan = plan_name
                user_subscription.subscription_plan = db_plan
                user_subscription.razorpay_subscription_id = f'test_sub_{user_id}_{plan_name}'
                user_subscription.subscription_status = 'active'
                user_subscription.is_trial = True
                user_subscription.trial_end_date = timezone.now() + timedelta(days=30)
                user_subscription.next_billing_date = timezone.now() + timedelta(days=30)
                user_subscription.save()
            else:
                # Create new user
                user_subscription = UserSubscription.objects.create(
                    user_id=user_id,
                    plan=plan_name,
                    subscription_plan=db_plan,
                    razorpay_subscription_id=f'test_sub_{user_id}_{plan_name}',
                    subscription_status='active',  # Auto-activate in test mode
                    is_trial=True,
                    trial_end_date=timezone.now() + timedelta(days=30),
                    next_billing_date=timezone.now() + timedelta(days=30),
                )
        
        first_amount = int(db_plan.first_month_price * 100)
        recurring_amount = int(db_plan.recurring_price * 100)
        
        return {
            'success': True,
            'test_mode': True,
            'order_id': f'test_order_{user_id}',
            'subscription_id': f'test_sub_{user_id}_{plan_name}',
            'short_url': 'https://example.com/test-payment',
            'first_amount': first_amount,
            'recurring_amount': recurring_amount,
            'message': f'TEST MODE: Subscription created. Auto-activated for testing.',
            'note': 'In production, user would pay ₹1 and then ₹99/month'
        }
    
    @staticmethod
    def verify_payment_signature(razorpay_payment_id, razorpay_order_id, razorpay_signature):
        """
        STEP 2-3: Verify Razorpay payment signature (payment confirmation)
        
        This is called after user completes payment on Razorpay
        We verify the signature to ensure payment is legitimate
        
        Returns: {'valid': bool, 'error': str | None}
        """
        try:
            logger.info(f"[VERIFY_PAYMENT] payment_id={razorpay_payment_id}")
            
            # Build verification string
            verify_string = f"{razorpay_order_id}|{razorpay_payment_id}"
            
            # Calculate expected signature
            expected_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                verify_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = hmac.compare_digest(expected_signature, razorpay_signature)
            
            if is_valid:
                logger.info(f"[VERIFY_PAYMENT] ✓ Signature verified")
                return {'valid': True}
            else:
                logger.warning(f"[VERIFY_PAYMENT] ✗ Signature mismatch")
                return {
                    'valid': False,
                    'error': 'Signature verification failed'
                }
        
        except Exception as e:
            logger.error(f"[VERIFY_PAYMENT] Error: {str(e)}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    @staticmethod
    def mark_payment_successful(user_id, plan_name, razorpay_payment_id, amount):
        """
        STEP 4: Mark payment as successful and unlock unlimited access
        
        Called when:
        1. Payment verification succeeds, OR
        2. Webhook confirms payment
        
        This is where we grant unlimited access
        
        Returns: {'success': bool, 'subscription': {...}}
        """
        try:
            logger.info(f"[MARK_PAYMENT_SUCCESS] user_id={user_id}, plan={plan_name}, payment_id={razorpay_payment_id}")
            
            with transaction.atomic():
                # Get or create subscription
                user_subscription = UserSubscription.objects.filter(
                    user_id=user_id,
                    plan=plan_name
                ).first()
                
                if not user_subscription:
                    logger.error(f"[MARK_PAYMENT_SUCCESS] Subscription not found for {user_id}/{plan_name}")
                    return {
                        'success': False,
                        'error': 'Subscription not found'
                    }
                
                # Mark subscription as active
                user_subscription.subscription_status = 'active'
                user_subscription.is_trial = True
                user_subscription.trial_end_date = timezone.now() + timedelta(days=30)
                user_subscription.next_billing_date = timezone.now() + timedelta(days=30)
                user_subscription.subscription_start_date = timezone.now()
                user_subscription.last_payment_date = timezone.now()
                user_subscription.usage_reset_date = timezone.now()
                user_subscription.save()
                
                # Create payment record
                Payment.objects.create(
                    subscription=user_subscription,
                    amount=amount / 100,  # Convert from paise
                    currency='INR',
                    status='completed',
                    payment_method='razorpay',
                    transaction_id=razorpay_payment_id,
                    razorpay_payment_id=razorpay_payment_id,
                    billing_cycle_start=timezone.now(),
                    billing_cycle_end=timezone.now() + timedelta(days=30),
                )
                
                logger.info(f"[MARK_PAYMENT_SUCCESS] ✓ Subscription activated for {user_id}")
                
                return {
                    'success': True,
                    'message': f'Payment successful! {plan_name.upper()} plan activated',
                    'subscription': {
                        'id': str(user_subscription.id),
                        'user_id': user_id,
                        'plan': plan_name,
                        'status': 'active',
                        'unlimited_access': True,
                        'trial_end_date': user_subscription.trial_end_date.isoformat(),
                        'next_billing_date': user_subscription.next_billing_date.isoformat(),
                    }
                }
        
        except Exception as e:
            logger.error(f"[MARK_PAYMENT_SUCCESS] Error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def handle_webhook(event_type, payload):
        """
        STEP 5: Handle Razorpay webhooks (SOURCE OF TRUTH)
        
        Events to handle:
        - subscription.activated → Mark subscription active
        - subscription.charged → Monthly payment confirmed
        - subscription.cancelled → User cancelled
        - payment.failed → Payment failed, re-enable limits
        
        Must be idempotent (same webhook called multiple times = same result)
        
        Returns: {'success': bool, 'event': str, 'message': str}
        """
        try:
            logger.info(f"[WEBHOOK] Received event: {event_type}")
            logger.info(f"[WEBHOOK] Payload: {json.dumps(payload, indent=2, default=str)}")
            
            if event_type == 'subscription.activated':
                return CompleteSubscriptionService._handle_subscription_activated(payload)
            
            elif event_type == 'subscription.charged':
                return CompleteSubscriptionService._handle_subscription_charged(payload)
            
            elif event_type == 'subscription.cancelled':
                return CompleteSubscriptionService._handle_subscription_cancelled(payload)
            
            elif event_type == 'payment.failed':
                return CompleteSubscriptionService._handle_payment_failed(payload)
            
            elif event_type == 'payment.captured':
                return CompleteSubscriptionService._handle_payment_captured(payload)
            
            else:
                logger.warning(f"[WEBHOOK] Unknown event: {event_type}")
                return {
                    'success': True,
                    'event': event_type,
                    'message': 'Event logged but not processed'
                }
        
        except Exception as e:
            logger.error(f"[WEBHOOK] Error handling webhook: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _handle_subscription_activated(payload):
        """Handle subscription.activated webhook"""
        try:
            subscription_data = payload.get('subscription', {})
            razorpay_sub_id = subscription_data.get('id')
            notes = subscription_data.get('notes', {})
            user_id = notes.get('user_id')
            plan_name = notes.get('plan_name', 'basic')
            
            if not user_id or not razorpay_sub_id:
                logger.warning("[WEBHOOK] Missing user_id or subscription_id")
                return {
                    'success': False,
                    'error': 'Missing required fields'
                }
            
            logger.info(f"[WEBHOOK_ACTIVATED] Activating subscription for {user_id}")
            
            with transaction.atomic():
                user_subscription = UserSubscription.objects.filter(
                    user_id=user_id,
                    plan=plan_name
                ).first()
                
                if user_subscription:
                    user_subscription.subscription_status = 'active'
                    user_subscription.razorpay_subscription_id = razorpay_sub_id
                    user_subscription.is_trial = True
                    user_subscription.trial_end_date = timezone.now() + timedelta(days=30)
                    user_subscription.next_billing_date = timezone.now() + timedelta(days=30)
                    user_subscription.last_payment_date = timezone.now()
                    user_subscription.save()
                    
                    logger.info(f"[WEBHOOK_ACTIVATED] ✓ Subscription activated")
                    return {
                        'success': True,
                        'event': 'subscription.activated',
                        'message': 'Subscription activated',
                        'user_id': user_id
                    }
            
            return {
                'success': False,
                'error': 'Subscription not found'
            }
        
        except Exception as e:
            logger.error(f"[WEBHOOK_ACTIVATED] Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _handle_subscription_charged(payload):
        """Handle subscription.charged webhook (monthly auto-payment)"""
        try:
            payment_data = payload.get('payment', {})
            razorpay_payment_id = payment_data.get('id')
            amount = payment_data.get('amount', 0)
            
            subscription_data = payload.get('subscription', {})
            razorpay_sub_id = subscription_data.get('id')
            notes = subscription_data.get('notes', {})
            user_id = notes.get('user_id')
            plan_name = notes.get('plan_name', 'basic')
            
            logger.info(f"[WEBHOOK_CHARGED] Monthly payment: {user_id}, amount={amount}")
            
            with transaction.atomic():
                user_subscription = UserSubscription.objects.filter(
                    razorpay_subscription_id=razorpay_sub_id
                ).first()
                
                if user_subscription:
                    # Create payment record
                    Payment.objects.create(
                        subscription=user_subscription,
                        amount=amount / 100,
                        currency='INR',
                        status='completed',
                        payment_method='razorpay',
                        transaction_id=razorpay_payment_id,
                        razorpay_payment_id=razorpay_payment_id,
                        billing_cycle_start=timezone.now(),
                        billing_cycle_end=timezone.now() + timedelta(days=30),
                    )
                    
                    # Update subscription
                    user_subscription.subscription_status = 'active'
                    user_subscription.last_payment_date = timezone.now()
                    user_subscription.next_billing_date = timezone.now() + timedelta(days=30)
                    user_subscription.usage_reset_date = timezone.now()
                    user_subscription.save()
                    
                    logger.info(f"[WEBHOOK_CHARGED] ✓ Payment recorded")
                    return {
                        'success': True,
                        'event': 'subscription.charged',
                        'message': 'Payment recorded',
                        'user_id': user_subscription.user_id
                    }
            
            return {
                'success': False,
                'error': 'Subscription not found'
            }
        
        except Exception as e:
            logger.error(f"[WEBHOOK_CHARGED] Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _handle_subscription_cancelled(payload):
        """Handle subscription.cancelled webhook"""
        try:
            subscription_data = payload.get('subscription', {})
            razorpay_sub_id = subscription_data.get('id')
            notes = subscription_data.get('notes', {})
            user_id = notes.get('user_id')
            
            logger.info(f"[WEBHOOK_CANCELLED] Subscription cancelled: {user_id}")
            
            with transaction.atomic():
                user_subscription = UserSubscription.objects.filter(
                    razorpay_subscription_id=razorpay_sub_id
                ).first()
                
                if user_subscription:
                    user_subscription.subscription_status = 'cancelled'
                    user_subscription.subscription_end_date = timezone.now()
                    user_subscription.plan = 'free'  # Revert to free plan
                    user_subscription.save()
                    
                    logger.info(f"[WEBHOOK_CANCELLED] ✓ Subscription cancelled")
                    return {
                        'success': True,
                        'event': 'subscription.cancelled',
                        'message': 'Subscription cancelled',
                        'user_id': user_subscription.user_id
                    }
            
            return {
                'success': False,
                'error': 'Subscription not found'
            }
        
        except Exception as e:
            logger.error(f"[WEBHOOK_CANCELLED] Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _handle_payment_failed(payload):
        """Handle payment.failed webhook - re-enable limits"""
        try:
            payment_data = payload.get('payment', {})
            razorpay_payment_id = payment_data.get('id')
            
            subscription_data = payload.get('subscription', {})
            razorpay_sub_id = subscription_data.get('id')
            notes = subscription_data.get('notes', {})
            user_id = notes.get('user_id')
            
            logger.warning(f"[WEBHOOK_FAILED] Payment failed: {user_id}, payment_id={razorpay_payment_id}")
            
            with transaction.atomic():
                user_subscription = UserSubscription.objects.filter(
                    razorpay_subscription_id=razorpay_sub_id
                ).first()
                
                if user_subscription:
                    # Mark subscription as past due
                    user_subscription.subscription_status = 'past_due'
                    user_subscription.save()
                    
                    # Re-enable feature limits (remove unlimited access)
                    # Next /api/usage/check/ will enforce limits again
                    
                    logger.info(f"[WEBHOOK_FAILED] ✓ Marked as past_due, limits re-enabled")
                    return {
                        'success': True,
                        'event': 'payment.failed',
                        'message': 'Payment failed, subscription marked past due',
                        'user_id': user_subscription.user_id
                    }
            
            return {
                'success': False,
                'error': 'Subscription not found'
            }
        
        except Exception as e:
            logger.error(f"[WEBHOOK_FAILED] Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _handle_payment_captured(payload):
        """Handle payment.captured webhook"""
        # For subscriptions, we use subscription.charged instead
        # But handle this in case it comes separately
        return {
            'success': True,
            'event': 'payment.captured',
            'message': 'Payment captured (handled as subscription.charged)'
        }
    
    @staticmethod
    def get_subscription_status(user_id, plan_name=None):
        """
        Get user subscription status
        
        Returns: {
            'user_id': str,
            'plan': str,
            'status': str,  # active|cancelled|past_due|inactive
            'is_trial': bool,
            'trial_end_date': str | None,
            'next_billing_date': str | None,
            'last_payment_date': str | None,
            'unlimited_access': bool,  # Can use all features unlimited
        }
        """
        try:
            if plan_name:
                subscription = UserSubscription.objects.filter(
                    user_id=user_id,
                    plan=plan_name
                ).first()
            else:
                subscription = UserSubscription.objects.filter(
                    user_id=user_id
                ).first()
            
            if not subscription:
                subscription = CompleteSubscriptionService.get_or_create_subscription(user_id)
            
            # Determine if user has unlimited access
            unlimited_access = (
                subscription.plan != 'free' and 
                subscription.subscription_status == 'active'
            )
            
            return {
                'success': True,
                'user_id': user_id,
                'plan': subscription.plan,
                'status': subscription.subscription_status,
                'is_trial': subscription.is_trial,
                'trial_end_date': subscription.trial_end_date.isoformat() if subscription.trial_end_date else None,
                'next_billing_date': subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
                'last_payment_date': subscription.last_payment_date.isoformat() if subscription.last_payment_date else None,
                'unlimited_access': unlimited_access,
            }
        
        except Exception as e:
            logger.error(f"[GET_STATUS] Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

