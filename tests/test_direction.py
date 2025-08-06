#!/usr/bin/env python3
"""
Test to understand when to use inbound vs outbound
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

# Test with the actual current trip
trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"

# Test both directions for the current trip
trip_data = {
    "RouteUid": "PerthRestricted:SWA-SRI-4277",
    "TripUid": "PerthRestricted:5744819",
    "TripDate": "2025-08-06",
    "TripDirection": "outbound",
    "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
}

print("Testing OUTBOUND:")
response = session.post(trip_url, headers=headers, data=trip_data)
result = response.json()
if result.get("result") == "success" and "data" in result and result["data"]:
    stops = result["data"].get("TripStopTimings", [])
    print(f"  Got {len(stops)} stops")
    if stops:
        print(f"  Direction field: {result['data'].get('Direction')}")
        print(f"  First stop: {stops[0]['Stop']['Description']}")
        print(f"  Last stop: {stops[-1]['Stop']['Description']}")
else:
    print(f"  No data returned")

print("\nTesting INBOUND:")
trip_data["TripDirection"] = "inbound"
response = session.post(trip_url, headers=headers, data=trip_data)
result = response.json()
if result.get("result") == "success" and "data" in result and result["data"]:
    stops = result["data"].get("TripStopTimings", [])
    print(f"  Got {len(stops)} stops")
    if stops:
        print(f"  Direction field: {result['data'].get('Direction')}")
        print(f"  First stop: {stops[0]['Stop']['Description']}")
        print(f"  Last stop: {stops[-1]['Stop']['Description']}")
else:
    print(f"  No data returned")

# Check what's in the Direction field from options
print("\n\nChecking Direction from GetTimetableOptions:")
now = datetime.now()
options_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
options_data = {
    "ExactlyMatchedRouteOnly": "true",
    "Mode": "bus",
    "Route": "209",
    "QryDate": now.strftime("%Y-%m-%d"),
    "QryTime": now.strftime("%H:%M"),
    "MaxOptions": "1"
}

options_response = session.post(options_url, headers=headers, data=options_data)
if options_response.status_code == 200:
    options_json = options_response.json()
    if options_json.get("result") == "success" and "data" in options_json:
        print(f"  Direction from GetTimetableOptions: {options_json['data'].get('Direction')}")
        options = options_json['data'].get('Options', [])
        if options:
            first = options[0]
            print(f"  Route: {first.get('StartLocation')} → {first.get('FinishLocation')}")