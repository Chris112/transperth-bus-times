#!/usr/bin/env python3
"""
Compare results with and without Key/RouteUid
"""

import requests
import re
import json
from datetime import datetime

session = requests.Session()
base_url = "https://www.transperth.wa.gov.au"

# Get session
print("Getting session...")
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

current_date = datetime.now().strftime('%Y-%m-%d')
current_time = datetime.now().strftime('%H:%M')

# Request 1: With full parameters
print("\n--- With Key and RouteUid ---")
data_full = {
    "ExactlyMatchedRouteOnly": "true",
    "Mode": "bus",
    "Route": "209",
    "Key": "715",
    "QryDate": current_date,
    "QryTime": current_time,
    "RouteUid": "SWA-SRI-4277",
    "MaxOptions": "4"
}

response_full = session.post(url, headers=headers, data=data_full)
result_full = response_full.json()

# Request 2: Without Key and RouteUid
print("\n--- Without Key and RouteUid ---")
data_minimal = {
    "ExactlyMatchedRouteOnly": "true",
    "Mode": "bus",
    "Route": "209",
    "QryDate": current_date,
    "QryTime": current_time,
    "MaxOptions": "4"
}

response_minimal = session.post(url, headers=headers, data=data_minimal)
result_minimal = response_minimal.json()

# Compare results
print("\n--- Comparison ---")
if result_full.get("result") == "success" and result_minimal.get("result") == "success":
    options_full = result_full.get("data", {}).get("Options", [])
    options_minimal = result_minimal.get("data", {}).get("Options", [])
    
    print(f"Full params: {len(options_full)} departures")
    print(f"Minimal params: {len(options_minimal)} departures")
    
    if options_full and options_minimal:
        print("\nFull params - First departure:")
        print(f"  {options_full[0]['StartTime']} from {options_full[0]['StartLocation']}")
        print(f"  {options_full[0]['FinishTime']} to {options_full[0]['FinishLocation']}")
        
        print("\nMinimal params - First departure:")
        print(f"  {options_minimal[0]['StartTime']} from {options_minimal[0]['StartLocation']}")
        print(f"  {options_minimal[0]['FinishTime']} to {options_minimal[0]['FinishLocation']}")
        
        # Check if they're the same
        if (options_full[0]['StartTime'] == options_minimal[0]['StartTime'] and
            options_full[0]['StartLocation'] == options_minimal[0]['StartLocation']):
            print("\n✅ Results are IDENTICAL!")
        else:
            print("\n❌ Results are different")
            
        # Check RouteUid
        print(f"\nRouteUid returned: {options_minimal[0].get('RouteUid')}")
        print(f"Can extract: {options_minimal[0].get('RouteUid', '').replace('PerthRestricted:', '')}")
else:
    print(f"Full params result: {result_full.get('result')}")
    print(f"Minimal params result: {result_minimal.get('result')}")