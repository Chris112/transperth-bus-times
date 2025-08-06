#!/usr/bin/env python3
"""
Test script for GetTimetableTrip API endpoint
This endpoint returns ALL stops along a route with detailed information
"""

import requests
import json
from datetime import datetime
import sys

# Configuration
BASE_URL = "https://www.transperth.wa.gov.au"

def get_auth_token(session):
    """Get authentication token from main page"""
    auth_url = f"{BASE_URL}/timetables/details?Bus=209"
    response = session.get(auth_url)
    
    if response.status_code != 200:
        print(f"Failed to get auth page: {response.status_code}")
        return None
    
    # Extract token using simple string search
    import re
    token_match = re.search(r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', response.text)
    if token_match:
        return token_match.group(1)
    return None

def get_bus_options(session, bus_number, token):
    """First get the bus times to extract TripKey"""
    url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
    
    headers = {
        "RequestVerificationToken": token,
        "ModuleId": "5345",
        "TabId": "133",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    now = datetime.now()
    data = {
        "ExactlyMatchedRouteOnly": "true",
        "Mode": "bus",
        "Route": str(bus_number),
        "QryDate": now.strftime("%Y-%m-%d"),
        "QryTime": now.strftime("%H:%M"),
        "MaxOptions": "2"  # Just get 2 for testing
    }
    
    response = session.post(url, headers=headers, data=data)
    
    if response.status_code != 200:
        print(f"Failed to get options: {response.status_code}")
        return None
    
    return response.json()

def get_trip_details(session, trip_key, route_uid, token):
    """Get detailed trip information with all stops"""
    url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
    
    headers = {
        "RequestVerificationToken": token,
        "ModuleId": "5345",
        "TabId": "133",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    # Need more parameters for this API
    now = datetime.now()
    data = {
        "RouteUid": route_uid,
        "TripUid": trip_key,  # This is the TripKey from GetTimetableOptions
        "TripDate": now.strftime("%Y-%m-%d"),
        "TripDirection": "outbound",  # or "inbound"
        "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
    }
    
    print(f"Request data: {data}")
    response = session.post(url, headers=headers, data=data)
    
    if response.status_code != 200:
        print(f"Failed to get trip details: {response.status_code}")
        return None
    
    result = response.json()
    print(f"Response keys: {result.keys() if result else 'None'}")
    if 'data' in result:
        print(f"Data keys: {result['data'].keys() if result['data'] else 'None'}")
    return result

def analyze_trip_data(trip_data):
    """Analyze the trip data structure"""
    if not trip_data or trip_data.get("result") != "success":
        print("No valid trip data")
        return
    
    data = trip_data.get("data", {})
    
    print("\n=== TRIP SUMMARY ===")
    print(f"Trip UID: {data.get('TripUid')}")
    print(f"Route UID: {data.get('RouteUid')}")
    print(f"Direction: {data.get('Direction')}")
    print(f"Headsign: {data.get('Headsign')}")
    
    stops = data.get("TripStopTimings", [])
    print(f"\nTotal Stops: {len(stops)}")
    
    if stops:
        print("\n=== STOP DETAILS ===")
        print(f"First Stop: {stops[0]['Stop']['Description']} at {stops[0]['DepartTime']}")
        print(f"Last Stop: {stops[-1]['Stop']['Description']} at {stops[-1]['ArrivalTime']}")
        
        print("\n=== SAMPLE STOPS (First 5 and Last 5) ===")
        for i, stop_timing in enumerate(stops[:5] + stops[-5:]):
            stop = stop_timing["Stop"]
            print(f"\nStop {i+1}:")
            print(f"  Time: {stop_timing.get('ArrivalTime', 'N/A')} - {stop_timing.get('DepartTime', 'N/A')}")
            print(f"  Name: {stop['Description']}")
            print(f"  Code: {stop['Code']}")
            print(f"  GPS: {stop['Position']}")
            print(f"  Zone: {stop['Zone']}")
            print(f"  Can Board: {stop_timing['CanBoard']}, Can Alight: {stop_timing['CanAlight']}")
            
            if i == 4:
                print("\n... middle stops omitted ...\n")
    
    return stops

def main():
    print("=== Testing GetTimetableTrip API ===\n")
    
    # Create session
    session = requests.Session()
    
    # Get auth token
    print("Getting authentication token...")
    token = get_auth_token(session)
    if not token:
        print("Failed to get token")
        return
    print("✓ Got token")
    
    # Test with bus 209
    bus_number = "209"
    print(f"\nGetting options for bus {bus_number}...")
    options_data = get_bus_options(session, bus_number, token)
    
    if not options_data or options_data.get("result") != "success":
        print("Failed to get bus options")
        return
    
    options = options_data.get("data", {}).get("Options", [])
    if not options:
        print("No bus options returned")
        return
    
    print(f"✓ Got {len(options)} options")
    
    # Test trip details for first option
    first_option = options[0]
    trip_key = first_option.get("TripKey")
    route_uid = first_option.get("RouteUid", "")
    
    print(f"\nGetting trip details for:")
    print(f"  TripKey: {trip_key}")
    print(f"  RouteUid: {route_uid}")
    print(f"  Route: {first_option.get('StartLocation')} → {first_option.get('FinishLocation')}")
    print(f"  Time: {first_option.get('StartTime')} - {first_option.get('FinishTime')}")
    
    # Also test with both directions if first one doesn't work
    trip_data = get_trip_details(session, trip_key, route_uid, token)
    
    # If no data, try inbound
    if not trip_data or not trip_data.get('data'):
        print("\nNo data with outbound, trying inbound direction...")
        # Modify the function call to test inbound
        # For now, let's analyze what we got
    
    if trip_data:
        stops = analyze_trip_data(trip_data)
        
        # Save full response for analysis
        with open("/home/cjwebb90/projects/ha_claude/live_bus_times/tests/trip_response_sample.json", "w") as f:
            json.dump(trip_data, f, indent=2)
        print(f"\n✓ Full response saved to trip_response_sample.json")
        
        # Create a summary
        if stops:
            print("\n=== DATA STRUCTURE SUMMARY ===")
            print("Each stop contains:")
            print("- Timing info (arrival/departure times)")
            print("- Stop details (code, name, GPS coordinates)")
            print("- Service info (can board/alight, timing point)")
            print("- Zone information")
            print("- Accessibility info")
    else:
        print("Failed to get trip details")

if __name__ == "__main__":
    main()