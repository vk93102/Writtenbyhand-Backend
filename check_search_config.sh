#!/bin/bash

cd /Users/vishaljha/Ed_tech_backend

echo "🔍 Checking Search API Configuration..."
echo ""

python3 manage.py shell << 'EOF'
from django.conf import settings
import requests

print("=" * 70)
print("SEARCH API CONFIGURATION & DIAGNOSTIC")
print("=" * 70)
print()

# Check SearchAPI
searchapi_key = getattr(settings, 'SEARCHAPI_KEY', None)
print("SearchAPI.io Configuration:")
if not searchapi_key:
    print("  Status: ❌ NOT CONFIGURED")
else:
    key_display = f"...{searchapi_key[-4:]}" if len(searchapi_key) > 4 else "***"
    print(f"  Status: ✅ CONFIGURED")
    print(f"  Key (last 4 chars): {key_display}")
print()

# Check SerpAPI  
serp_api_key = getattr(settings, 'SERP_API_KEY', None)
print("SerpAPI Configuration:")
if not serp_api_key:
    print("  Status: ❌ NOT CONFIGURED")
    print("  Impact: Search queries will return MOCK DATA with broken links")
else:
    key_display = f"...{serp_api_key[-4:]}" if len(serp_api_key) > 4 else "***"
    print(f"  Key (last 4 chars): {key_display}")
    
    # Test the key
    print("  Testing key validity...")
    try:
        response = requests.get(
            "https://serpapi.com/search",
            params={
                "q": "test",
                "api_key": serp_api_key,
                "engine": "google"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            print("  ✅ KEY IS VALID - Real search results will work")
        elif response.status_code == 401:
            print("  ❌ KEY IS INVALID (401 Unauthorized)")
            print("     This is why you get broken mock links!")
        elif response.status_code == 403:
            print("  ⚠️  Quota exceeded (403 Forbidden)")
        else:
            print(f"  ⚠️  HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Error testing: {e}")

print()
print("=" * 70)
print("WHAT TO DO:")
print("=" * 70)
print()
print("The reason search returns broken mock links:")
print("  • SerpAPI key is invalid/expired (401 Unauthorized)")
print("  • When both APIs fail, fallback returns mock data")
print()
print("To get REAL search results:")
print("  1. Go to https://serpapi.com")
print("  2. Sign up and get a valid API key")
print("  3. Update Django settings: SERP_API_KEY = 'your_new_key'")
print("  4. Restart Django server")
print("  5. Search will now return real links, not broken ones")
print()

exit()
EOF


