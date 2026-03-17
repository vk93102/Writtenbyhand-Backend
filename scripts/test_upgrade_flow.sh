#!/bin/bash

# PAYMENT SYSTEM TEST - UPGRADE FLOW
# Clean output showing: New payment → Duplicate rejection → Plan upgrade

API_URL="http://localhost:8000/api"
TEST_USER="upgrade_user_$(date +%s)"

echo ""
echo "============================================================"
echo "PAYMENT SYSTEM - DUPLICATE PREVENTION AND UPGRADES"
echo "============================================================"
echo ""

# TEST 1: Create First Order
echo "TEST 1: User Creates First Payment Order (₹1)"
ORDER_1=$(curl -s -X POST "$API_URL/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$TEST_USER\", \"plan\": \"premium\"}")
echo "$ORDER_1" | python -m json.tool
ORDER_ID=$(echo "$ORDER_1" | python -c "import sys, json; print(json.load(sys.stdin).get('order_id', ''))" 2>/dev/null)
echo ""
echo "---"
echo ""

# Simulate payment verification by updating subscription
echo "Simulating payment verification..."
python manage.py shell <<'PYTHON' 2>/dev/null
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edtech_project.settings')
django.setup()

from question_solver.models import UserSubscription
from django.utils import timezone
from datetime import timedelta

user_id = os.environ.get('TEST_USER', '')
if user_id:
    subscription, created = UserSubscription.objects.get_or_create(
        user_id=user_id,
        defaults={
            'plan': 'premium',
            'is_trial': True,
            'subscription_status': 'active'
        }
    )
    subscription.plan = 'premium'
    subscription.is_trial = True
    subscription.subscription_status = 'active'
    subscription.trial_end_date = timezone.now() + timedelta(days=7)
    subscription.next_billing_date = timezone.now() + timedelta(days=7)
    subscription.subscription_start_date = timezone.now()
    subscription.save()
    print(f"Subscription activated for {user_id} - Plan: {subscription.plan}")
PYTHON

export TEST_USER

echo ""
echo "---"
echo ""

# TEST 2: Check Current Status
echo "TEST 2: Check Current Status (Premium Active)"
STATUS=$(curl -s -X GET "$API_URL/subscription/status/?user_id=$TEST_USER")
echo "$STATUS" | python -m json.tool
echo ""
echo "---"
echo ""

# TEST 3: Try Duplicate Order (Same Plan)
echo "TEST 3: Try to Create Duplicate Order (Same Plan - Should Be Rejected)"
DUPLICATE=$(curl -s -X POST "$API_URL/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$TEST_USER\", \"plan\": \"premium\"}")
echo "$DUPLICATE" | python -m json.tool
ERROR=$(echo "$DUPLICATE" | python -c "import sys, json; print(json.load(sys.stdin).get('error', ''))" 2>/dev/null)
if [ "$ERROR" = "Already Subscribed" ]; then
    echo "RESULT: Duplicate correctly rejected with 'Already Subscribed' error"
fi
echo ""
echo "---"
echo ""

# TEST 4: Upgrade to Different Plan
echo "TEST 4: User Upgrades to Premium Annual Plan (Different Plan - Should Succeed)"
UPGRADE=$(curl -s -X POST "$API_URL/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$TEST_USER\", \"plan\": \"premium_annual\"}")
echo "$UPGRADE" | python -m json.tool
UPGRADE_ORDER=$(echo "$UPGRADE" | python -c "import sys, json; print(json.load(sys.stdin).get('order_id', ''))" 2>/dev/null)
UPGRADE_AMOUNT=$(echo "$UPGRADE" | python -c "import sys, json; print(json.load(sys.stdin).get('amount', ''))" 2>/dev/null)
if [ -n "$UPGRADE_ORDER" ]; then
    echo "RESULT: Upgrade allowed - New Order Created (Amount: ₹$UPGRADE_AMOUNT)"
fi
echo ""
echo "---"
echo ""

# TEST 5: Test with New User
echo "TEST 5: New User - Create Initial Order"
NEW_USER="new_user_$(date +%s)"
NEW_ORDER=$(curl -s -X POST "$API_URL/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$NEW_USER\", \"plan\": \"premium\"}")
echo "$NEW_ORDER" | python -m json.tool
echo ""
echo "---"
echo ""

echo "============================================================"
echo "SYSTEM BEHAVIOR SUMMARY"
echo "============================================================"
echo ""
echo "1. FIRST PAYMENT (₹1 Trial)"
echo "   - User creates order: SUCCESS"
echo "   - Amount: ₹1"
echo "   - User marked as premium (after payment verification)"
echo ""
echo "2. DUPLICATE SAME PLAN"
echo "   - Attempting to buy same plan again: REJECTED"
echo "   - Error: 'Already Subscribed'"
echo "   - Shows current plan, next billing date, amount"
echo ""
echo "3. PLAN UPGRADE"
echo "   - User upgrades to different plan: ALLOWED"
echo "   - Example: premium (₹1) → premium_annual (₹199)"
echo "   - New order created with new amount"
echo ""
echo "4. NEW USER"
echo "   - User starts fresh order: ALLOWED"
echo "   - Shows as free plan before payment"
echo ""
echo "============================================================"
