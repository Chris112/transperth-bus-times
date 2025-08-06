#!/usr/bin/env python3
"""
Quick test to get stop codes for bus 209
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

# Get options
now = datetime.now()
options_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"

headers = {
    "RequestVerificationToken": token,
    "ModuleId": "5345",
    "TabId": "133",
    "Content-Type": "application/x-www-form-urlencoded",
}

options_data = {
    "ExactlyMatchedRouteOnly": "true",
    "Mode": "bus",
    "Route": "209",
    "QryDate": now.strftime("%Y-%m-%d"),
    "QryTime": now.strftime("%H:%M"),
    "MaxOptions": "1"
}

options_response = session.post(options_url, headers=headers, data=options_data)
options_json = options_response.json()

if options_json.get("result") == "success":
    options = options_json["data"].get("Options", [])
    if options:
        first = options[0]
        print(f"Next departure: {first.get('StartTime')} - {first.get('FinishTime')}")
        print(f"Route: {first.get('StartLocation')} → {first.get('FinishLocation')}")
        
        # Get trip details
        trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
        
        trip_data = {
            "RouteUid": first.get("RouteUid"),
            "TripUid": first.get("TripKey"),
            "TripDate": now.strftime("%Y-%m-%d"),
            "TripDirection": "outbound",
            "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
        }
        
        trip_response = session.post(trip_url, headers=headers, data=trip_data)
        
        if trip_response.status_code != 200:
            # Try inbound
            trip_data["TripDirection"] = "inbound"
            trip_response = session.post(trip_url, headers=headers, data=trip_data)
        
        if trip_response.status_code == 200:
            trip_json = trip_response.json()
            if trip_json.get("result") == "success" and "data" in trip_json:
                stops = trip_json["data"].get("TripStopTimings", [])
                print(f"\nFound {len(stops)} stops. First 5 with can_board=true:")
                count = 0
                for stop_timing in stops:
                    if stop_timing.get("CanBoard") and count < 5:
                        stop = stop_timing["Stop"]
                        print(f"  • Code: {stop['Code']:<6} - {stop['Description']}")
                        count += 1
            else:
                print(f"No data in response: {trip_json}")
        else:
            print(f"Failed to get trip: {trip_response.status_code}")