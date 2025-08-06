#!/usr/bin/env python3
"""
Minimal test for GetTimetableTrip using exact working payload format
"""

import requests
from datetime import datetime
import json

BASE_URL = "https://www.transperth.wa.gov.au"

# Create session
session = requests.Session()

# Step 1: Get auth token
print("Getting auth token...")
auth_response = session.get(f"{BASE_URL}/timetables/details?Bus=209")
import re
token_match = re.search(r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', auth_response.text)
token = token_match.group(1) if token_match else None
print(f"Token: {token[:20]}..." if token else "No token found")

# Step 2: Call GetTimetableTrip with exact payload structure
url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"

headers = {
    "RequestVerificationToken": token,
    "ModuleId": "5345",
    "TabId": "133",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Using your exact working payload
data = {
    "RouteUid": "PerthRestricted:SWA-SRI-4277",
    "TripUid": "PerthRestricted:5744760",
    "TripDate": "2025-08-06",
    "TripDirection": "outbound",
    "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
}

print(f"\nCalling API with data: {data}")
response = session.post(url, headers=headers, data=data)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    if result.get("result") == "success" and "data" in result:
        trip_data = result["data"]
        stops = trip_data.get("TripStopTimings", [])
        print(f"✓ Success! Got {len(stops)} stops")
        print(f"Headsign: {trip_data.get('Headsign')}")
        print(f"Direction: {trip_data.get('Direction')}")
        
        if stops:
            print(f"\nFirst 3 stops:")
            for i, stop_timing in enumerate(stops[:3]):
                stop = stop_timing["Stop"]
                print(f"  {i+1}. {stop['Description']} at {stop_timing.get('DepartTime', stop_timing.get('ArrivalTime'))}")
    else:
        print(f"Response: {result}")
else:
    print(f"Failed: {response.text[:200]}")