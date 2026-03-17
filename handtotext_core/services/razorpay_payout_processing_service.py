"""
Razorpay Payouts Service
Handles withdrawals from platform TO users via Razorpay Payouts API

This service creates:
1. Razorpay Contact (for user)
2. Fund Account (UPI only)
3. Payout (money transfer)
"""
import requests
from requests.auth import HTTPBasicAuth
import logging
from django.conf import settings
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RazorpayPayoutService:
    """Service to handle Razorpay Payouts for coin withdrawals using REST API"""
    
    BASE_URL = "https://api.razorpay.com/v1"
    
    def __init__(self):
        """Initialize Razorpay Payout service with credentials"""
        try:
            self.key_id = settings.RAZORPAY_KEY_ID
            self.key_secret = settings.RAZORPAY_KEY_SECRET
            self.account_number = getattr(settings, 'RAZORPAY_ACCOUNT_NUMBER', '')
            self.auth = HTTPBasicAuth(self.key_id, self.key_secret)
            self.headers = {"Content-Type": "application/json"}
            logger.info("Razorpay Payout Service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Razorpay Payout Service: {e}")
            self.auth = None
    
    def create_contact(self, user_id: str, name: str = None, email: str = None, phone: str = None) -> Tuple[bool, str, Dict]:
        """
        Create or fetch Razorpay Contact using REST API
        
        Args:
            user_id: Internal user identifier
            name: User's name (optional, will use User_{user_id} if not provided)
            email: User's email (optional)
            phone: User's phone (optional)
        
        Returns:
            (success, contact_id, data)
        """
        try:
            if not self.auth:
                return False, "", {"error": "Razorpay client not initialized"}
            
            # Ensure name is not empty
            if not name or name.strip() == "":
                name = f"User {user_id}"
            
            # Create contact data
            contact_data = {
                "name": name,
                "email": email or f"{user_id}@edtech.local",
                "contact": phone or "9999999999",
                "type": "customer",
                "reference_id": f"user_{user_id}",
                "notes": {
                    "user_id": str(user_id)
                }
            }
            
            # Create contact via REST API
            response = requests.post(
                f"{self.BASE_URL}/contacts",
                auth=self.auth,
                json=contact_data,
                headers=self.headers
            )
            
            if response.status_code in [200, 201]:
                contact = response.json()
                contact_id = contact.get('id')
                logger.info(f"✅ Created Razorpay contact: {contact_id} for user {user_id}")
                return True, contact_id, contact
            else:
                error_data = response.json()
                logger.error(f"Contact creation failed: {error_data}")
                return False, "", error_data
            
        except Exception as e:
            logger.error(f"Unexpected error creating contact: {str(e)}", exc_info=True)
            return False, "", {"error": str(e)}
    
    def create_fund_account_upi(self, contact_id: str, upi_id: str) -> Tuple[bool, str, Dict]:
        """
        Create Fund Account for UPI using REST API
        
        Args:
            contact_id: Razorpay contact ID
            upi_id: User's UPI ID (e.g., user@paytm)
        
        Returns:
            (success, fund_account_id, data)
        """
        try:
            if not self.auth:
                return False, "", {"error": "Razorpay client not initialized"}
            
            # Create fund account data
            fund_account_data = {
                "contact_id": contact_id,
                "account_type": "vpa",  # Virtual Payment Address (UPI)
                "vpa": {
                    "address": upi_id
                }
            }
            
            # Create fund account via REST API
            response = requests.post(
                f"{self.BASE_URL}/fund_accounts",
                auth=self.auth,
                json=fund_account_data,
                headers=self.headers
            )
            
            if response.status_code in [200, 201]:
                fund_account = response.json()
                fund_account_id = fund_account.get('id')
                logger.info(f"✅ Created fund account: {fund_account_id} for UPI {upi_id}")
                return True, fund_account_id, fund_account
            else:
                error_data = response.json()
                logger.error(f"Fund account creation failed: {error_data}")
                return False, "", error_data
            
        except Exception as e:
            logger.error(f"Unexpected error creating fund account: {str(e)}", exc_info=True)
            return False, "", {"error": str(e)}
    
    def create_payout(
        self,
        fund_account_id: str,
        amount_paise: int,
        currency: str = "INR",
        mode: str = "UPI",
        purpose: str = "payout",
        reference_id: str = None,
        narration: str = "EdTech Coin Withdrawal"
    ) -> Tuple[bool, str, str, Dict]:
        """
        Create Payout (Transfer money to user) using REST API
        
        Args:
            fund_account_id: Razorpay fund account ID
            amount_paise: Amount in paise (100 paise = ₹1)
            currency: Currency code (default: INR)
            mode: Transfer mode (default: UPI)
            purpose: Purpose of payout (default: payout)
            reference_id: Internal reference ID
            narration: Payout description
        
        Returns:
            (success, payout_id, status, data)
        """
        try:
            if not self.auth:
                return False, "", "failed", {"error": "Razorpay client not initialized"}
            
            # Minimum payout is ₹1 (100 paise)
            if amount_paise < 100:
                return False, "", "failed", {"error": "Minimum payout amount is ₹1 (100 paise)"}
            
            # Create payout data
            payout_data = {
                "account_number": self.account_number or "2323230099506802",
                "fund_account_id": fund_account_id,
                "amount": amount_paise,
                "currency": currency,
                "mode": mode,
                "purpose": purpose,
                "queue_if_low_balance": True,  # Queue if insufficient balance
                "reference_id": reference_id,
                "narration": narration
            }
            
            # Create payout via REST API
            response = requests.post(
                f"{self.BASE_URL}/payouts",
                auth=self.auth,
                json=payout_data,
                headers=self.headers
            )
            
            if response.status_code in [200, 201]:
                payout = response.json()
                payout_id = payout.get('id')
                payout_status = payout.get('status')  # pending, queued, processing, processed, reversed, cancelled, failed
                logger.info(f"✅ Created payout: {payout_id} - Status: {payout_status} - Amount: ₹{amount_paise/100}")
                return True, payout_id, payout_status, payout
            else:
                error_data = response.json()
                error_desc = error_data.get('error', {}).get('description', 'Payout failed')
                logger.error(f"Payout creation failed: {error_data}")
                return False, "", "failed", error_data
            
        except Exception as e:
            logger.error(f"Unexpected error creating payout: {str(e)}", exc_info=True)
            return False, "", "failed", {"error": str(e)}
    
    def get_payout_status(self, payout_id: str) -> Tuple[bool, str, Dict]:
        """
        Get payout status using REST API
        
        Args:
            payout_id: Razorpay payout ID
        
        Returns:
            (success, status, data)
        """
        try:
            if not self.auth:
                return False, "failed", {"error": "Razorpay client not initialized"}
            
            response = requests.get(
                f"{self.BASE_URL}/payouts/{payout_id}",
                auth=self.auth,
                headers=self.headers
            )
            
            if response.status_code == 200:
                payout = response.json()
                payout_status = payout.get('status')
                return True, payout_status, payout
            else:
                error_data = response.json()
                logger.error(f"Failed to fetch payout status: {error_data}")
                return False, "failed", error_data
            
        except Exception as e:
            logger.error(f"Failed to fetch payout status: {str(e)}")
            return False, "failed", {"error": str(e)}


# Global instance
razorpay_payout_service = RazorpayPayoutService()
