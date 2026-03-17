#!/bin/bash

# PRODUCTION PAYMENT API - COPY & PASTE READY CURL COMMANDS
# All endpoints are working ✅
# Base URL: https://ed-tech-backend-tzn8.onrender.com

echo "===== PRODUCTION PAYMENT API TESTS ====="
echo ""

# ============================================
# TEST 1: Get Razorpay Public Key
# ============================================
echo "TEST 1: Get Razorpay Public Key"
echo "========================================"
curl -X GET "https://ed-tech-backend-tzn8.onrender.com/api/payment/razorpay-key/" \
  -H "Content-Type: application/json"
echo ""
echo ""

# ============================================
# TEST 2: Create Payment Order (JUST FIXED)
# ============================================
echo "TEST 2: Create Payment Order"
echo "========================================"
curl -X POST "https://ed-tech-backend-tzn8.onrender.com/api/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "premium",
    "user_id": "testuser123"
  }'
echo ""
echo ""

# ============================================
# TEST 3: Create Payment Order (Annual Plan)
# ============================================
echo "TEST 3: Create Payment Order - Annual Plan"
echo "========================================"
curl -X POST "https://ed-tech-backend-tzn8.onrender.com/api/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "premium_annual",
    "user_id": "annual_user_456"
  }'
echo ""
echo ""

# ============================================
# TEST 4: Verify Payment (Example)
# ============================================
echo "TEST 4: Verify Payment Signature"
echo "========================================"
echo "NOTE: You need actual values from Razorpay modal response"
echo "EXAMPLE with dummy values:"
curl -X POST "https://ed-tech-backend-tzn8.onrender.com/api/payment/verify/" \
  -H "Content-Type: application/json" \
  -d '{
    "razorpay_order_id": "order_KI7OyQLqvLp9M9",
    "razorpay_payment_id": "pay_KI7OyQLqvLp9M9",
    "razorpay_signature": "9ef4dffbfd84f1318f6739a3ce19f9d85851857ae648f114332d8401e0949a3d",
    "user_id": "testuser123"
  }'
echo ""
echo ""

# ============================================
# TEST 5: Get Payment Status
# ============================================
echo "TEST 5: Get Payment Status (Replace order_id)"
echo "========================================"
curl -X GET "https://ed-tech-backend-tzn8.onrender.com/api/razorpay/status/order_KI7OyQLqvLp9M9/" \
  -H "Content-Type: application/json"
echo ""
echo ""

# ============================================
# TEST 6: Get Payment History
# ============================================
echo "TEST 6: Get Payment History"
echo "========================================"
curl -X GET "https://ed-tech-backend-tzn8.onrender.com/api/razorpay/history/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "testuser123"
  }'
echo ""
echo ""

# ============================================
# TEST 7: Get Subscription Status
# ============================================
echo "TEST 7: Check Subscription Status"
echo "========================================"
curl -X GET "https://ed-tech-backend-tzn8.onrender.com/api/subscription/status/?user_id=testuser123" \
  -H "Content-Type: application/json"
echo ""
echo ""

# ============================================
# TEST 8: Error Test - Missing user_id
# ============================================
echo "TEST 8: Error Handling - Missing user_id"
echo "========================================"
curl -X POST "https://ed-tech-backend-tzn8.onrender.com/api/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d '{"plan": "premium"}'
echo ""
echo ""

# ============================================
# TEST 9: Error Test - Invalid Plan
# ============================================
echo "TEST 9: Error Handling - Invalid Plan"
echo "========================================"
curl -X POST "https://ed-tech-backend-tzn8.onrender.com/api/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d '{"plan": "invalid_plan", "user_id": "testuser123"}'
echo ""
echo ""

echo "===== ALL TESTS COMPLETE ====="
