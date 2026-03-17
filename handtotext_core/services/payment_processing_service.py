"""
Razorpay Payment Integration Service
Handles payment order creation, verification, and tracking
"""

import razorpay
import logging
import hashlib
import hmac
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)


class RazorpayPaymentService:
    """
    Razorpay payment processing service
    Handles order creation, payment verification, and refunds
    """
    
    def __init__(self):
        """Initialize Razorpay client"""
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        
        # Only initialize client if valid credentials are provided
        if self.key_id and self.key_secret and not self.key_id.startswith('rzp_test_XXXXXXXXXX'):
            try:
                self.client = razorpay.Client(
                    auth=(self.key_id, self.key_secret)
                )
                self.is_initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize Razorpay client: {str(e)}")
                self.client = None
                self.is_initialized = False
        else:
            logger.warning("Razorpay credentials not configured. Using test mode.")
            self.client = None
            self.is_initialized = False
    
    def create_order(self, amount, user_id, plan_type='premium', description='EdTech Premium Subscription'):
        """
        Create a Razorpay order
        
        Args:
            amount (float): Amount in INR (e.g., 199.00 for ₹199)
            user_id (str): User identifier
            plan_type (str): Type of plan ('premium', 'annual', etc.)
            description (str): Order description
        
        Returns:
            dict: Order details containing order_id, amount, currency
        """
        try:
            # Convert amount to paise (Razorpay uses paise, 1 INR = 100 paise)
            amount_paise = int(Decimal(str(amount)) * 100)
            
            # Create order data
            order_data = {
                'amount': amount_paise,  # Amount in paise
                'currency': 'INR',
                'receipt': f'order_{user_id}_{int(amount*100)}',  # Unique receipt ID
                'payment_capture': 1,  # Auto-capture payment after authorization
                'notes': {
                    'user_id': user_id,
                    'plan_type': plan_type,
                    'description': description
                }
            }
            
            # If Razorpay is not initialized, return test order
            if not self.is_initialized:
                logger.warning(f"Using test mode for order creation")
                import uuid
                test_order_id = f'order_test_{uuid.uuid4().hex[:12]}'
                
                return {
                    'success': True,
                    'order_id': test_order_id,
                    'amount': amount,
                    'amount_paise': amount_paise,
                    'currency': 'INR',
                    'created_at': int(__import__('time').time()),
                    'status': 'created',
                    'is_test': True
                }
            
            # Create order via Razorpay API
            response = self.client.order.create(data=order_data)
            
            logger.info(f"Order created for user {user_id}: {response.get('id')}")
            
            return {
                'success': True,
                'order_id': response['id'],
                'amount': amount,
                'amount_paise': amount_paise,
                'currency': response['currency'],
                'created_at': response['created_at'],
                'status': response['status']
            }
        
        except Exception as e:
            logger.error(f"Error creating Razorpay order for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to create payment order'
            }
    
    def verify_payment_signature(self, order_id, payment_id, signature):
        """
        Verify Razorpay payment signature
        This ensures the payment response came from Razorpay
        
        Args:
            order_id (str): Razorpay order ID
            payment_id (str): Razorpay payment ID
            signature (str): Payment signature from frontend
        
        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            # Create signature message
            message = f"{order_id}|{payment_id}"
            
            # Create HMAC SHA256 signature
            expected_signature = hmac.new(
                self.key_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = expected_signature == signature
            
            if is_valid:
                logger.info(f"Payment signature verified for order {order_id}")
            else:
                logger.warning(f"Payment signature mismatch for order {order_id}")
            
            return is_valid
        
        except Exception as e:
            logger.error(f"Error verifying payment signature: {str(e)}")
            return False
    
    def get_payment_details(self, payment_id):
        """
        Fetch payment details from Razorpay
        
        Args:
            payment_id (str): Razorpay payment ID
        
        Returns:
            dict: Payment details or error
        """
        try:
            response = self.client.payment.fetch(payment_id)
            
            return {
                'success': True,
                'payment_id': response.get('id'),
                'order_id': response.get('order_id'),
                'amount': response.get('amount') / 100,  # Convert from paise to INR
                'currency': response.get('currency'),
                'status': response.get('status'),
                'method': response.get('method'),
                'email': response.get('email'),
                'contact': response.get('contact'),
                'created_at': response.get('created_at'),
                'description': response.get('description'),
                'notes': response.get('notes', {})
            }
        
        except Exception as e:
            logger.error(f"Error fetching payment details for {payment_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_order_details(self, order_id):
        """
        Fetch order details from Razorpay
        
        Args:
            order_id (str): Razorpay order ID
        
        Returns:
            dict: Order details or error
        """
        try:
            response = self.client.order.fetch(order_id)
            
            return {
                'success': True,
                'order_id': response.get('id'),
                'amount': response.get('amount') / 100,  # Convert from paise to INR
                'currency': response.get('currency'),
                'status': response.get('status'),
                'receipt': response.get('receipt'),
                'created_at': response.get('created_at'),
                'payments': response.get('payments'),
                'notes': response.get('notes', {})
            }
        
        except Exception as e:
            logger.error(f"Error fetching order details for {order_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def refund_payment(self, payment_id, amount=None, reason='User requested refund'):
        """
        Refund a Razorpay payment
        
        Args:
            payment_id (str): Razorpay payment ID
            amount (float): Amount to refund in INR (None for full refund)
            reason (str): Refund reason
        
        Returns:
            dict: Refund details or error
        """
        try:
            refund_data = {
                'notes': {
                    'reason': reason
                }
            }
            
            # Add amount if specified (in paise)
            if amount:
                refund_data['amount'] = int(Decimal(str(amount)) * 100)
            
            response = self.client.payment.refund(payment_id, refund_data)
            
            logger.info(f"Refund created for payment {payment_id}: {response.get('id')}")
            
            return {
                'success': True,
                'refund_id': response.get('id'),
                'payment_id': response.get('payment_id'),
                'amount': response.get('amount') / 100,  # Convert from paise
                'status': response.get('status'),
                'created_at': response.get('created_at')
            }
        
        except Exception as e:
            logger.error(f"Error refunding payment {payment_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to process refund'
            }
    
    def create_recurring_payment(self, customer_id, token_id, amount, plan_id=None, 
                                 customer_name='', customer_email=''):
        """
        Create a recurring payment (for subscriptions)
        
        Args:
            customer_id (str): Customer identifier
            token_id (str): Razorpay token for saved card
            amount (float): Monthly amount in INR
            plan_id (str): Plan ID for subscription
            customer_name (str): Customer name
            customer_email (str): Customer email
        
        Returns:
            dict: Recurring payment details or error
        """
        try:
            subscription_data = {
                'plan_id': plan_id,
                'customer_notify': 1,  # Send notification to customer
                'quantity': 1,
                'notes': {
                    'customer_id': customer_id,
                    'customer_name': customer_name
                }
            }
            
            response = self.client.subscription.create(data=subscription_data)
            
            logger.info(f"Subscription created for customer {customer_id}: {response.get('id')}")
            
            return {
                'success': True,
                'subscription_id': response.get('id'),
                'plan_id': response.get('plan_id'),
                'customer_id': response.get('customer_id'),
                'status': response.get('status'),
                'created_at': response.get('created_at'),
                'start_at': response.get('start_at')
            }
        
        except Exception as e:
            logger.error(f"Error creating subscription for {customer_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to create subscription'
            }
    
    def get_razorpay_key(self):
        """
        Get Razorpay public key for frontend
        Safe to expose (public key)
        
        Returns:
            dict: Razorpay key configuration
        """
        return {
            'key_id': self.key_id,
            'key_secret': self.key_secret[:5] + '...',  # Don't expose full secret
        }
    
    def process_webhook(self, event_data):
        """
        Process Razorpay webhook events
        
        Args:
            event_data (dict): Webhook event data
        
        Returns:
            dict: Processing result
        """
        try:
            event_type = event_data.get('event')
            payload = event_data.get('payload', {})
            
            if event_type == 'payment.authorized':
                logger.info(f"Payment authorized: {payload}")
            
            elif event_type == 'payment.failed':
                logger.warning(f"Payment failed: {payload}")
            
            elif event_type == 'payment.captured':
                logger.info(f"Payment captured: {payload}")
            
            elif event_type == 'refund.created':
                logger.info(f"Refund created: {payload}")
            
            return {
                'success': True,
                'event_type': event_type,
                'message': 'Webhook processed successfully'
            }
        
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance
payment_service = RazorpayPaymentService()
