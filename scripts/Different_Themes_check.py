#!/usr/bin/env python3
"""
Test daily quiz endpoint on production Render deployment
"""
import requests
import json
from datetime import datetimexw
x
BASE_URL = "https://ed-tech-backend-tzn8.onrender.com/api/quiz"
USER_ID = f"test_prod_user_{int(datetime.now().timestamp())}"

print("\n" + "="*80)
print("PRODUCTION DAILY QUIZ TEST")
print("="*80)
print(f"Base URL: {BASE_URL}")
print(f"User ID: {USER_ID}\n")

session = requests.Session()

# TEST 1: Health check
print("[TEST 0] Health Check")
print("-" * 80)
try:
    resp = requests.get("https://ed-tech-backend-tzn8.onrender.com/api/status/", timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print("✅ Server is running!")
    else:
        print(f"⚠️  Unexpected status: {resp.status_code}")
except Exception as e:
    print(f"❌ Error connecting to server: {e}")
    exit(1)

print()

# TEST 1: Fetch English Quiz
print("[TEST 1] Fetch English Quiz")
print("-" * 80)
try:
    resp = session.get(f"{BASE_URL}/daily-quiz/", params={"user_id": USER_ID, "language": "english"}, timeout=15)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Questions fetched: {len(data.get('questions', []))}")
        print(f"Language: {data['quiz_metadata'].get('language', 'N/A')}")
        if len(data.get('questions', [])) > 0:
            print(f"Q1: {data['questions'][0]['question'][:60]}...")
    else:
        print(f"❌ Error: {resp.status_code}")
        print(resp.text[:200])
except Exception as e:
    print(f"❌ Error: {e}")

print()

# TEST 2: Fetch Hindi Quiz
print("[TEST 2] Fetch Hindi Quiz")
print("-" * 80)
try:
    resp = session.get(f"{BASE_URL}/daily-quiz/", params={"user_id": USER_ID, "language": "hindi"}, timeout=15)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Hindi questions fetched: {len(data.get('questions', []))}")
        print(f"Language: {data['quiz_metadata'].get('language', 'N/A')}")
        if len(data.get('questions', [])) > 0:
            print(f"Q1 (Hindi): {data['questions'][0]['question'][:60]}...")
    else:
        print(f"❌ Error: {resp.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

print()

# TEST 3: Submit Quiz
print("[TEST 3] Submit Quiz Answers")
print("-" * 80)
try:
    submit_payload = {
        "user_id": USER_ID,
        "language": "english",
        "answers": {
            "1": "0",
            "2": "1",
            "3": "2",
            "4": "0",
            "5": "1"
        }
    }
    resp = session.post(f"{BASE_URL}/daily-quiz/submit/", json=submit_payload, timeout=15)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Quiz submitted!")
        print(f"Correct: {data.get('correct_count', 'N/A')}/5")
        print(f"Coins earned: {data.get('coins_earned', 'N/A')}")
    else:
        print(f"❌ Error: {resp.status_code}")
        print(resp.text[:200])
except Exception as e:
    print(f"❌ Error: {e}")

print()

# TEST 4: Check User Coins
print("[TEST 4] Check User Coins")
print("-" * 80)
try:
    resp = session.get(f"{BASE_URL}/daily-quiz/coins/", params={"user_id": USER_ID}, timeout=15)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Total coins: {data.get('total_coins', 0)}")
        print(f"Lifetime coins: {data.get('lifetime_coins', 0)}")
        print(f"Coins spent: {data.get('coins_spent', 0)}")
    else:
        print(f"❌ Error: {resp.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

print()
print("="*80)
print("PRODUCTION TEST COMPLETED")
print("="*80 + "\n")
