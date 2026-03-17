#!/bin/bash

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:9000"
USER_ID="test_user_$(date +%s)"

echo ""
echo "=============================================================================="
echo "  🚀 RANDOM DAILY QUIZ ENDPOINT TEST (CURL)"
echo "=============================================================================="
echo ""
echo "Test Start Time: $(date)"
echo "Base URL: $BASE_URL"
echo "User ID: $USER_ID"
echo ""

# ==============================================================================
# TEST 1: Fetch English Quiz (RANDOM - Call 1)
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 1: Fetch English Quiz (RANDOM QUESTIONS - Call 1)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

RESPONSE_1=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/quiz/daily-quiz/?user_id=$USER_ID&language=english")
HTTP_CODE_1=$(echo "$RESPONSE_1" | tail -n 1)
BODY_1=$(echo "$RESPONSE_1" | head -n -1)

echo "📌 Request URL:"
echo "   GET $BASE_URL/api/quiz/daily-quiz/?user_id=$USER_ID&language=english"
echo ""
echo "📌 HTTP Status: $HTTP_CODE_1"
echo ""

if [ "$HTTP_CODE_1" == "200" ]; then
    echo -e "${GREEN}✅ Status: SUCCESS${NC}"
    echo ""
    echo "📌 Response (First 100 lines):"
    echo "$BODY_1" | python3 -m json.tool | head -100
    
    # Extract question 1 from response
    QUESTION_1=$(echo "$BODY_1" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['questions'][0]['question'] if data.get('questions') else 'N/A')" 2>/dev/null)
    echo ""
    echo "📌 Sample Question from Call 1:"
    echo "   $QUESTION_1"
else
    echo -e "${RED}❌ Status: FAILED${NC}"
    echo "Response: $BODY_1"
fi

echo ""
echo ""

# ==============================================================================
# TEST 2: Fetch English Quiz Again (SHOULD BE DIFFERENT - Call 2)
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 2: Fetch English Quiz Again (SHOULD BE DIFFERENT - Call 2)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

sleep 1

RESPONSE_2=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/quiz/daily-quiz/?user_id=$USER_ID&language=english")
HTTP_CODE_2=$(echo "$RESPONSE_2" | tail -n 1)
BODY_2=$(echo "$RESPONSE_2" | head -n -1)

echo "📌 Request URL:"
echo "   GET $BASE_URL/api/quiz/daily-quiz/?user_id=$USER_ID&language=english"
echo ""
echo "📌 HTTP Status: $HTTP_CODE_2"
echo ""

if [ "$HTTP_CODE_2" == "200" ]; then
    echo -e "${GREEN}✅ Status: SUCCESS${NC}"
    echo ""
    echo "📌 Response (First 50 lines):"
    echo "$BODY_2" | python3 -m json.tool | head -50
    
    # Extract question 1 from response
    QUESTION_2=$(echo "$BODY_2" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['questions'][0]['question'] if data.get('questions') else 'N/A')" 2>/dev/null)
    echo ""
    echo "📌 Sample Question from Call 2:"
    echo "   $QUESTION_2"
    
    # Compare questions
    echo ""
    if [ "$QUESTION_1" != "$QUESTION_2" ]; then
        echo -e "${GREEN}✅ RANDOMNESS VERIFIED: Questions are DIFFERENT between calls!${NC}"
    else
        echo -e "${YELLOW}⚠️  Questions are the SAME (might be coincidence)${NC}"
    fi
else
    echo -e "${RED}❌ Status: FAILED${NC}"
    echo "Response: $BODY_2"
fi

echo ""
echo ""

# ==============================================================================
# TEST 3: Fetch Hindi Quiz
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 3: Fetch Hindi Quiz${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

RESPONSE_3=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/quiz/daily-quiz/?user_id=$USER_ID&language=hindi")
HTTP_CODE_3=$(echo "$RESPONSE_3" | tail -n 1)
BODY_3=$(echo "$RESPONSE_3" | head -n -1)

echo "📌 Request URL:"
echo "   GET $BASE_URL/api/quiz/daily-quiz/?user_id=$USER_ID&language=hindi"
echo ""
echo "📌 HTTP Status: $HTTP_CODE_3"
echo ""

if [ "$HTTP_CODE_3" == "200" ]; then
    echo -e "${GREEN}✅ Status: SUCCESS${NC}"
    echo ""
    echo "📌 Response (First 100 lines):"
    echo "$BODY_3" | python3 -m json.tool | head -100
else
    echo -e "${RED}❌ Status: FAILED${NC}"
    echo "Response: $BODY_3"
fi

echo ""
echo ""

# ==============================================================================
# TEST 4: Start Quiz (Award coins for participation)
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 4: Start Quiz (Award Coins for Participation)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

RESPONSE_4=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/quiz/daily-quiz/start/" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER_ID\", \"language\": \"english\"}")
HTTP_CODE_4=$(echo "$RESPONSE_4" | tail -n 1)
BODY_4=$(echo "$RESPONSE_4" | head -n -1)

echo "📌 Request URL:"
echo "   POST $BASE_URL/api/quiz/daily-quiz/start/"
echo ""
echo "📌 Payload:"
echo "   {\"user_id\": \"$USER_ID\", \"language\": \"english\"}"
echo ""
echo "📌 HTTP Status: $HTTP_CODE_4"
echo ""

if [ "$HTTP_CODE_4" == "200" ]; then
    echo -e "${GREEN}✅ Status: SUCCESS${NC}"
    echo ""
    echo "📌 Response:"
    echo "$BODY_4" | python3 -m json.tool
else
    echo -e "${RED}❌ Status: FAILED${NC}"
    echo "Response: $BODY_4"
fi

echo ""
echo ""

# ==============================================================================
# TEST 5: Submit Quiz Answers
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST 5: Submit Quiz Answers${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# First, fetch a quiz to know what answers to submit
QUIZ=$(curl -s "$BASE_URL/api/quiz/daily-quiz/?user_id=$USER_ID&language=english")

# Create answers (assume first 3 correct, last 2 wrong)
ANSWERS_JSON="{
  \"user_id\": \"$USER_ID\",
  \"language\": \"english\",
  \"answers\": {
    \"1\": \"0\",
    \"2\": \"0\",
    \"3\": \"0\",
    \"4\": \"1\",
    \"5\": \"1\"
  }
}"

RESPONSE_5=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/api/quiz/daily-quiz/submit/" \
  -H "Content-Type: application/json" \
  -d "$ANSWERS_JSON")
HTTP_CODE_5=$(echo "$RESPONSE_5" | tail -n 1)
BODY_5=$(echo "$RESPONSE_5" | head -n -1)

echo "📌 Request URL:"
echo "   POST $BASE_URL/api/quiz/daily-quiz/submit/"
echo ""
echo "📌 Payload:"
echo "$ANSWERS_JSON" | python3 -m json.tool
echo ""
echo "📌 HTTP Status: $HTTP_CODE_5"
echo ""

if [ "$HTTP_CODE_5" == "200" ]; then
    echo -e "${GREEN}✅ Status: SUCCESS${NC}"
    echo ""
    echo "📌 Response:"
    echo "$BODY_5" | python3 -m json.tool
else
    echo -e "${RED}❌ Status: FAILED${NC}"
    echo "Response: $BODY_5"
fi

echo ""
echo ""

# ==============================================================================
# SUMMARY
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}TEST SUMMARY${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "TEST 1 (Get English Quiz - Call 1): HTTP $HTTP_CODE_1"
echo "TEST 2 (Get English Quiz - Call 2): HTTP $HTTP_CODE_2"
echo "TEST 3 (Get Hindi Quiz):            HTTP $HTTP_CODE_3"
echo "TEST 4 (Start Quiz):                HTTP $HTTP_CODE_4"
echo "TEST 5 (Submit Answers):            HTTP $HTTP_CODE_5"
echo ""

if [ "$HTTP_CODE_1" == "200" ] && [ "$HTTP_CODE_2" == "200" ] && [ "$HTTP_CODE_3" == "200" ] && [ "$HTTP_CODE_4" == "200" ] && [ "$HTTP_CODE_5" == "200" ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
fi

echo ""
echo "Test End Time: $(date)"
echo ""
