#!/usr/bin/env python3
"""
Test if inbound vs outbound actually returns different data
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
    "MaxOptions": "4"
}

print("Getting bus 209 departures...")
options_response = session.post(options_url, headers=headers, data=options_data)
options_json = options_response.json()

if options_json.get("result") == "success" and "data" in options_json:
    data = options_json["data"]
    print(f"API Direction field: {data.get('Direction')}")
    options = data.get("Options", [])
    
    print(f"\nFound {len(options)} departures:")
    for i, opt in enumerate(options, 1):
        print(f"{i}. {opt.get('StartTime')} from {opt.get('StartLocation')[:30]}... to {opt.get('FinishLocation')[:30]}...")
    
    # Test first departure with both directions
    if options:
        first = options[0]
        trip_key = first.get("TripKey")
        route_uid = first.get("RouteUid")
        
        trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
        
        print(f"\n{'='*60}")
        print(f"Testing departure 1: {first.get('StartTime')}")
        print(f"TripKey: {trip_key}")
        print(f"RouteUid: {route_uid}")
        print(f"{'='*60}")
        
        # Test OUTBOUND
        print("\n1. Testing OUTBOUND direction:")
        trip_data = {
            "RouteUid": route_uid,
            "TripUid": trip_key,
            "TripDate": now.strftime("%Y-%m-%d"),
            "TripDirection": "outbound",
            "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
        }
        
        response = session.post(trip_url, headers=headers, data=trip_data)
        if response.status_code == 200:
            result = response.json()
            if result.get("result") == "success" and "data" in result and result["data"]:
                stops = result["data"].get("TripStopTimings", [])
                if stops:
                    print(f"   ✓ Got {len(stops)} stops")
                    print(f"   First: {stops[0]['Stop']['Description']}")
                    print(f"   Last: {stops[-1]['Stop']['Description']}")
                    outbound_stops = [s['Stop']['Description'] for s in stops]
                else:
                    print("   ✗ No stops returned")
                    outbound_stops = []
            else:
                print("   ✗ No data returned")
                outbound_stops = []
        else:
            print(f"   ✗ Request failed: {response.status_code}")
            outbound_stops = []
        
        # Test INBOUND
        print("\n2. Testing INBOUND direction:")
        trip_data["TripDirection"] = "inbound"
        
        response = session.post(trip_url, headers=headers, data=trip_data)
        if response.status_code == 200:
            result = response.json()
            if result.get("result") == "success" and "data" in result and result["data"]:
                stops = result["data"].get("TripStopTimings", [])
                if stops:
                    print(f"   ✓ Got {len(stops)} stops")
                    print(f"   First: {stops[0]['Stop']['Description']}")
                    print(f"   Last: {stops[-1]['Stop']['Description']}")
                    inbound_stops = [s['Stop']['Description'] for s in stops]
                else:
                    print("   ✗ No stops returned")
                    inbound_stops = []
            else:
                print("   ✗ No data returned")
                inbound_stops = []
        else:
            print(f"   ✗ Request failed: {response.status_code}")
            inbound_stops = []
        
        # Compare results
        print(f"\n{'='*60}")
        print("COMPARISON:")
        print(f"{'='*60}")
        
        if outbound_stops and inbound_stops:
            if outbound_stops == inbound_stops:
                print("⚠️  SAME DATA: Both directions return identical stops!")
            else:
                print("✓ DIFFERENT DATA: Directions return different stops")
                print(f"\nOutbound: {len(outbound_stops)} stops")
                print(f"Inbound: {len(inbound_stops)} stops")
                
                # Show differences
                only_outbound = set(outbound_stops) - set(inbound_stops)
                only_inbound = set(inbound_stops) - set(outbound_stops)
                
                if only_outbound:
                    print(f"\nStops only in outbound: {list(only_outbound)[:3]}")
                if only_inbound:
                    print(f"Stops only in inbound: {list(only_inbound)[:3]}")
        elif outbound_stops:
            print("Only OUTBOUND has data")
        elif inbound_stops:
            print("Only INBOUND has data")
        else:
            print("Neither direction returned data")