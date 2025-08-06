#!/usr/bin/env python3
"""
Test all departures with both directions to understand the pattern
"""

import requests
from datetime import datetime
import json
import re

BASE_URL = "https://www.transperth.wa.gov.au"

# Create session
session = requests.Session()

# Get auth token
auth_response = session.get(f"{BASE_URL}/timetables/details?Bus=209")
token_match = re.search(r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', auth_response.text)
token = token_match.group(1) if token_match else None

headers = {
    "RequestVerificationToken": token,
    "ModuleId": "5345",
    "TabId": "133",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Get current options
now = datetime.now()
options_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"

options_data = {
    "ExactlyMatchedRouteOnly": "true",
    "Mode": "bus",
    "Route": "209",
    "QryDate": now.strftime("%Y-%m-%d"),
    "QryTime": now.strftime("%H:%M"),
    "MaxOptions": "10"  # Get more departures
}

print("Getting bus 209 departures...")
options_response = session.post(options_url, headers=headers, data=options_data)
options_json = options_response.json()

if options_json.get("result") == "success" and "data" in options_json:
    data = options_json["data"]
    print(f"API Direction field: {data.get('Direction')}\n")
    options = data.get("Options", [])
    
    trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
    
    results = []
    
    for i, opt in enumerate(options[:5], 1):  # Test first 5 departures
        print(f"Departure {i}: {opt.get('StartTime')}")
        print(f"  Route: {opt.get('StartLocation')[:25]}... → {opt.get('FinishLocation')[:25]}...")
        
        trip_data = {
            "RouteUid": opt.get("RouteUid"),
            "TripUid": opt.get("TripKey"),
            "TripDate": now.strftime("%Y-%m-%d"),
            "TripDirection": "outbound",
            "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
        }
        
        # Test outbound
        response = session.post(trip_url, headers=headers, data=trip_data)
        outbound_works = False
        if response.status_code == 200:
            result = response.json()
            if result.get("result") == "success" and "data" in result and result["data"]:
                stops = result["data"].get("TripStopTimings", [])
                if stops:
                    outbound_works = True
        
        # Test inbound
        trip_data["TripDirection"] = "inbound"
        response = session.post(trip_url, headers=headers, data=trip_data)
        inbound_works = False
        if response.status_code == 200:
            result = response.json()
            if result.get("result") == "success" and "data" in result and result["data"]:
                stops = result["data"].get("TripStopTimings", [])
                if stops:
                    inbound_works = True
        
        # Report results
        if outbound_works and inbound_works:
            print(f"  ✓ BOTH directions work")
        elif outbound_works:
            print(f"  → OUTBOUND only")
        elif inbound_works:
            print(f"  ← INBOUND only")
        else:
            print(f"  ✗ Neither direction works")
        
        results.append({
            'time': opt.get('StartTime'),
            'outbound': outbound_works,
            'inbound': inbound_works
        })
        print()
    
    # Summary
    print("="*60)
    print("SUMMARY:")
    print("="*60)
    outbound_count = sum(1 for r in results if r['outbound'])
    inbound_count = sum(1 for r in results if r['inbound'])
    both_count = sum(1 for r in results if r['outbound'] and r['inbound'])
    
    print(f"Total departures tested: {len(results)}")
    print(f"Work with OUTBOUND: {outbound_count}")
    print(f"Work with INBOUND: {inbound_count}")
    print(f"Work with BOTH: {both_count}")
    
    if outbound_count > 0 and inbound_count > 0 and both_count == 0:
        print("\n⚠️  Pattern detected: Different departures require different directions!")
        print("The API Direction field alone may not be sufficient.")
else:
    print("Failed to get departures")