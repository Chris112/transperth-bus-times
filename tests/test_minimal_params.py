#!/usr/bin/env python3
"""
Test if we can get bus times with minimal parameters
"""

import requests
import re
import json
from datetime import datetime

session = requests.Session()
base_url = "https://www.transperth.wa.gov.au"

# Get session with just bus number
print("Getting session with just bus number...")
response = session.get(f"{base_url}/timetables/details?Bus=209")

if response.status_code != 200:
    print(f"Failed: {response.status_code}")
    exit(1)

# Get token from HTML
token_match = re.search(r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', response.text)
if not token_match:
    print("No token found")
    exit(1)

token = token_match.group(1)
print(f"Token: {token[:20]}...")

# Try API call with minimal parameters
url = f"{base_url}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"

headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "ModuleId": "5345",
    "TabId": "133",
    "RequestVerificationToken": token,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

# Test 1: Just bus number
print("\n--- Test 1: Just bus number ---")
data1 = {
    "Mode": "bus",
    "Route": "209",
    "QryDate": datetime.now().strftime('%Y-%m-%d'),
    "QryTime": datetime.now().strftime('%H:%M'),
    "MaxOptions": "4"
}
print(f"Request: {data1}")
response1 = session.post(url, headers=headers, data=data1)
print(f"Status: {response1.status_code}")
if response1.status_code == 200:
    try:
        result = response1.json()
        if result.get("result") == "success":
            print("✅ SUCCESS with just bus number!")
            # Check if we got RouteUid back
            if result.get("data", {}).get("Options"):
                first_option = result["data"]["Options"][0]
                print(f"RouteUid in response: {first_option.get('RouteUid')}")
        else:
            print(f"API returned: {result.get('result')}")
    except:
        print(f"Response: {response1.text[:200]}")
else:
    print(f"Error: {response1.text[:200]}")

# Test 2: Try with empty Key and RouteUid
print("\n--- Test 2: With empty Key and RouteUid ---")
data2 = {
    "Mode": "bus",
    "Route": "209",
    "Key": "",
    "RouteUid": "",
    "QryDate": datetime.now().strftime('%Y-%m-%d'),
    "QryTime": datetime.now().strftime('%H:%M'),
    "MaxOptions": "4"
}
print(f"Request: {data2}")
response2 = session.post(url, headers=headers, data=data2)
print(f"Status: {response2.status_code}")
if response2.status_code == 200:
    try:
        result = response2.json()
        print(f"Result: {result.get('result')}")
        if result.get("data", {}).get("Options"):
            print(f"Got {len(result['data']['Options'])} options")
    except:
        print(f"Response: {response2.text[:200]}")

# Test 3: Try ExactlyMatchedRouteOnly without Key/RouteUid
print("\n--- Test 3: ExactlyMatchedRouteOnly without Key/RouteUid ---")
data3 = {
    "ExactlyMatchedRouteOnly": "true",
    "Mode": "bus",
    "Route": "209",
    "QryDate": datetime.now().strftime('%Y-%m-%d'),
    "QryTime": datetime.now().strftime('%H:%M'),
    "MaxOptions": "4"
}
print(f"Request: {data3}")
response3 = session.post(url, headers=headers, data=data3)
print(f"Status: {response3.status_code}")
if response3.status_code == 200:
    try:
        result = response3.json()
        print(f"Result: {result.get('result')}")
        if result.get("data", {}).get("Options"):
            print(f"Got {len(result['data']['Options'])} options")
    except:
        print(f"Response: {response3.text[:200]}")