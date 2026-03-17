#!/bin/bash

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

USER_ID=8
SECRET_KEY="4f5e2bac434c38bcf80b3f71df16ad50"

echo -e "${BLUE}========================================"
echo "Testing Daily Quiz for User 8"
echo "========================================${NC}"

# Generate token using Python
echo -e "\n${YELLOW}Step 1: Generate JWT Token for User 8${NC}"

TOKEN=$(python3 << 'EOF'
import jwt
from datetime import datetime, timedelta

SECRET_KEY = "4f5e2bac434c38bcf80b3f71df16ad50"
payload = {
    "user_id": 8,
    "username": "user8",
    "email": "user8@example.com",
    "exp": datetime.utcnow() + timedelta(hours=24),
    "iat": datetime.utcnow()
}

token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
print(token)
EOF
)

echo -e "${GREEN}Token Generated:${NC}"
echo "$TOKEN"

echo -e "\n${YELLOW}Step 2: Fetch Daily Quiz${NC}"
echo -e "${BLUE}Command:${NC}"
echo "curl -s -X GET \"http://127.0.0.1:11000/api/quiz/daily-quiz/?user_id=8&language=english\" \\"
echo "  -H \"Authorization: Bearer $TOKEN\" \\"
echo "  -H \"Content-Type: application/json\""
echo ""

echo -e "${BLUE}Response:${NC}"
QUIZ_RESPONSE=$(curl -s -X GET "http://127.0.0.1:11000/api/quiz/daily-quiz/?user_id=8&language=english" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "$QUIZ_RESPONSE" | python3 -m json.tool

echo -e "\n${YELLOW}Step 3: Check for quiz_id in response${NC}"
HAS_QUIZ_ID=$(echo "$QUIZ_RESPONSE" | grep -c "quiz_id")

if [ $HAS_QUIZ_ID -gt 0 ]; then
  echo -e "${GREEN}✅ quiz_id found in response${NC}"
  echo "$QUIZ_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print('quiz_id:', data.get('quiz_id', 'NOT FOUND'))"
else
  echo -e "${YELLOW}⚠️  quiz_id NOT found in response${NC}"
  echo "Response structure contains:"
  echo "$QUIZ_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print('Top-level keys:', list(data.keys()))"
fi

echo -e "\n${YELLOW}Step 4: Extract questions from response${NC}"
QUESTION_COUNT=$(echo "$QUIZ_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('questions', [])))" 2>/dev/null || echo "0")
echo -e "${GREEN}Questions in response: $QUESTION_COUNT${NC}"

echo -e "\n${BLUE}========================================"
echo "Summary for Frontend:"
echo "========================================${NC}"
echo "If quiz_id is NOT in the response, frontend MUST:"
echo "1. Generate quiz_id locally: quiz_\$(date +%s)_\$(random)"
echo "2. Store it in component state"
echo "3. Pass it when submitting answers"
