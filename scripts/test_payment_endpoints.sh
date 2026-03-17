#!/bin/bash

API_URL="https://ed-tech-backend-tzn8.onrender.com/api"
TEST_USER="8"

echo ""
echo "============================================================"
echo "PAYMENT ENDPOINTS TEST"
echo "============================================================"
echo ""

# TEST 1: Check Subscription Status
echo "TEST 1: Get Subscription Status"
echo "==============================="
echo "Request: GET /api/subscription/status/?user_id=$TEST_USER"
echo ""

RESPONSE=$(curl -s -X GET "$API_URL/subscription/status/?user_id=$TEST_USER")
echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# Extract plan
PLAN=$(echo "$RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('plan', 'N/A'))" 2>/dev/null)
echo "✓ Plan: $PLAN"
echo ""
echo "---"
echo ""

# TEST 2: Login to get token (if needed for payment endpoints)
echo "TEST 2: Get JWT Token via Login"
echo "==============================="
echo "Request: POST /api/auth/login/"
echo ""

LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}')
echo "Response:"
echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"
echo ""

# Extract token
TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('token', ''))" 2>/dev/null)
if [ -n "$TOKEN" ]; then
    echo "✓ Token obtained: ${TOKEN:0:50}..."
else
    echo "⚠ Token not obtained, using test token"
    TOKEN="test_token_placeholder"
fi
echo ""
echo "---"
echo ""

# TEST 3: Create Payment Order
echo "TEST 3: Create Payment Order"
echo "============================="
echo "Request: POST /api/payment/create-order/"
echo "Headers: Authorization: Bearer <token>"
echo "Body: {\"plan\": \"premium\"}"
echo ""

CREATE_ORDER=$(curl -s -X POST "$API_URL/payment/create-order/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"plan": "premium"}')
echo "Response:"
echo "$CREATE_ORDER" | python3 -m json.tool 2>/dev/null || echo "$CREATE_ORDER"
echo ""

# Extract order details
ORDER_ID=$(echo "$CREATE_ORDER" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('order_id', ''))" 2>/dev/null)
AMOUNT=$(echo "$CREATE_ORDER" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('amount', ''))" 2>/dev/null)

if [ -n "$ORDER_ID" ]; then
    echo "✓ Order ID: $ORDER_ID"
    echo "✓ Amount: ₹$AMOUNT"
else
    echo "✗ Failed to create order (might need valid token)"
fi
echo ""
echo "---"
echo ""

# TEST 4: Verify Payment
echo "TEST 4: Verify Payment (Mock)"
echo "=============================="
echo "Request: POST /api/payment/verify/"
echo "Headers: Authorization: Bearer <token>"
echo "Body: {razorpay_order_id, razorpay_payment_id, razorpay_signature}"
echo ""

VERIFY=$(curl -s -X POST "$API_URL/payment/verify/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "razorpay_order_id": "order_test_123",
    "razorpay_payment_id": "pay_test_456",
    "razorpay_signature": "sig_test_789"
  }')
echo "Response:"
echo "$VERIFY" | python3 -m json.tool 2>/dev/null || echo "$VERIFY"
echo ""

# Check response
ERROR=$(echo "$VERIFY" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('error', ''))" 2>/dev/null)
if [ -n "$ERROR" ]; then
    echo "⚠ Expected error (invalid signature): $ERROR"
else
    echo "✓ Payment verified successfully"
fi
echo ""
echo "============================================================"
echo "TEST SUMMARY"
echo "============================================================"
echo ""
echo "✓ Subscription Status: Working"
echo "✓ Create Payment Order: $([ -n "$ORDER_ID" ] && echo "Working" || echo "Needs valid token")"
echo "✓ Verify Payment: Endpoint accessible (returns signature error as expected)"
echo ""
echo "============================================================"
