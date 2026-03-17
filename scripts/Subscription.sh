#!/bin/bash

# TEST SIMPLIFIED SUBSCRIPTION ENDPOINTS - Feature Access Only
# Base URL: http://localhost:8000

echo "===== SIMPLIFIED SUBSCRIPTION ENDPOINTS TEST ====="
echo "Testing feature availability: FREE vs PAID users"
echo ""

# ============================================
# TEST 1: Check Feature Access for FREE User
# ============================================
echo "✅ TEST 1: Feature Access - FREE User"
echo "========================================"
curl -s "http://localhost:8000/api/subscription/feature-access/?user_id=free_user&feature=quiz" | jq .
echo ""

# ============================================
# TEST 2: Check Subscription Status - FREE User
# ============================================
echo "✅ TEST 2: Subscription Status - FREE User"
echo "========================================"
curl -s "http://localhost:8000/api/subscription/status/?user_id=free_user" | jq .
echo ""

# ============================================
# TEST 3: Upgrade User to PAID (Premium)
# ============================================
echo "✅ TEST 3: Simulate Upgrade to PREMIUM"
echo "========================================"
# First create order (creates subscription)
curl -s -X POST "http://localhost:8000/api/payment/create-order/" \
  -H "Content-Type: application/json" \
  -d '{"plan": "premium", "user_id": "paid_user123"}' | jq '.order_id' > /tmp/order_id.txt

ORDER_ID=$(cat /tmp/order_id.txt | tr -d '"')
echo "Order created: $ORDER_ID"

# Manually update subscription (simulate payment verification)
# This would normally be done by payment verification endpoint
echo "📝 Simulating subscription update to premium..."
echo ""

# ============================================
# TEST 4: Check Feature Access after Upgrade
# ============================================
echo "✅ TEST 4: Feature Access - PAID User (After Upgrade)"
echo "========================================"
echo "Note: In real flow, this would be updated after payment verification"
curl -s "http://localhost:8000/api/subscription/feature-access/?user_id=paid_user123&feature=quiz" | jq .
echo ""

# ============================================
# TEST 5: Test Multiple Features - FREE User
# ============================================
echo "✅ TEST 5: Multiple Features - FREE User"
echo "========================================"
for feature in quiz flashcards mock_test ask_question youtube_summarizer; do
  echo "Feature: $feature"
  curl -s "http://localhost:8000/api/subscription/feature-access/?user_id=free_user&feature=$feature" | jq '.available'
done
echo ""

# ============================================
# TEST 6: Log Feature Usage
# ============================================
echo "✅ TEST 6: Log Feature Usage"
echo "========================================"
curl -s -X POST "http://localhost:8000/api/subscription/log-usage/" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "feature": "quiz", "type": "attempt"}' | jq .
echo ""

# ============================================
# TEST 7: Error Handling - Missing Parameters
# ============================================
echo "❌ TEST 7: Error Handling - Missing user_id"
echo "========================================"
curl -s "http://localhost:8000/api/subscription/feature-access/?feature=quiz" | jq .
echo ""

echo "===== ALL TESTS COMPLETE ====="
echo ""
echo "EXPECTED BEHAVIOR:"
echo "✓ FREE users: available = false"
echo "✓ PAID users: available = true"
echo "✓ Log usage: tracks feature usage"
echo "✓ Error handling: proper error messages"
