#!/usr/bin/env python3
"""
Test the fixed get_bus_stops service
"""

import sys
import os
import json
from datetime import datetime

# Add the parent directory to path to import the service modules
sys.path.insert(0, '/mnt/homeassistant/pyscript/apps/bus_times')

# Import required modules for testing
import requests
import re

# Configuration
BASE_URL = "https://www.transperth.wa.gov.au"
TEST_BUS_NUMBER = "209"

def extract_token(html_content):
    """Extract the RequestVerificationToken from HTML"""
    token_match = re.search(r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', html_content)
    if token_match:
        return token_match.group(1)
    return None

def get_session_and_token(bus_number):
    """Create a session and get authentication token"""
    session = requests.Session()
    auth_url = f"{BASE_URL}/timetables/details?Bus={bus_number}"
    
    try:
        auth_response = session.get(auth_url)
        
        if auth_response.status_code != 200:
            return None, None
        
        token = extract_token(auth_response.text)
        return session, token
        
    except Exception as e:
        print(f"Error getting session/token: {e}")
        return None, None

def get_api_headers(token):
    """Get standard headers for API calls"""
    return {
        "RequestVerificationToken": token,
        "ModuleId": "5345",
        "TabId": "133",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }

def test_with_direction_fix():
    """Test the service with the fixed direction handling"""
    print(f"Testing bus {TEST_BUS_NUMBER} with fixed direction handling\n")
    
    # Get session and token
    session, token = get_session_and_token(TEST_BUS_NUMBER)
    if not session or not token:
        print("Failed to get authentication")
        return False
    
    print("✓ Got authentication token")
    
    # Get current date and time
    now = datetime.now()
    qry_date = now.strftime("%Y-%m-%d")
    qry_time = now.strftime("%H:%M")
    
    # Step 1: Get next departure
    options_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
    
    options_data = {
        "ExactlyMatchedRouteOnly": "true",
        "Mode": "bus",
        "Route": TEST_BUS_NUMBER,
        "QryDate": qry_date,
        "QryTime": qry_time,
        "MaxOptions": "1"
    }
    
    options_response = session.post(
        options_url, 
        headers=get_api_headers(token), 
        data=options_data
    )
    
    if options_response.status_code != 200:
        print(f"Failed to get bus options: {options_response.status_code}")
        return False
    
    options_json = options_response.json()
    
    if options_json.get("result") != "success" or "data" not in options_json:
        print("No bus times available")
        return False
    
    # Get the direction from API
    api_direction = options_json["data"].get("Direction", "outbound")
    
    # Normalize direction
    if api_direction == 0 or api_direction == "0":
        api_direction = "outbound"
    elif api_direction == 1 or api_direction == "1":
        api_direction = "inbound"
    
    print(f"API suggests direction: {api_direction}")
    
    options = options_json["data"].get("Options", [])
    
    if not options:
        print(f"No departures found")
        return False
    
    next_departure = options[0]
    trip_key = next_departure.get("TripKey")
    route_uid = next_departure.get("RouteUid")
    
    print(f"Next departure: {next_departure.get('StartTime')} - {next_departure.get('FinishTime')}")
    print(f"Route: {next_departure.get('StartLocation')} → {next_departure.get('FinishLocation')}")
    
    # Step 2: Get trip details with correct direction
    trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
    
    trip_data = {
        "RouteUid": route_uid,
        "TripUid": trip_key,
        "TripDate": qry_date,
        "TripDirection": api_direction,  # Use API-provided direction
        "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
    }
    
    print(f"\nTrying with {api_direction} direction...")
    trip_response = session.post(
        trip_url, 
        headers=get_api_headers(token), 
        data=trip_data
    )
    
    if trip_response.status_code == 200:
        trip_json = trip_response.json()
        
        if trip_json.get("result") == "success" and "data" in trip_json and trip_json["data"]:
            trip_info = trip_json["data"]
            stop_timings = trip_info.get("TripStopTimings", [])
            
            if stop_timings:
                print(f"✅ SUCCESS! Retrieved {len(stop_timings)} stops")
                print(f"Headsign: {trip_info.get('Headsign', 'N/A')}")
                print(f"Direction: {trip_info.get('Direction', 'N/A')}")
                
                # Show first 3 stops
                print("\nFirst 3 stops:")
                for i, stop_timing in enumerate(stop_timings[:3], 1):
                    stop_info = stop_timing.get("Stop", {})
                    stop_time = stop_timing.get("DepartTime") or stop_timing.get("ArrivalTime", "")
                    print(f"  {i}. {stop_info.get('Description')} ({stop_info.get('Code')}) at {stop_time}")
                
                # Show last stop
                last_stop = stop_timings[-1]
                stop_info = last_stop.get("Stop", {})
                stop_time = last_stop.get("ArrivalTime") or last_stop.get("DepartTime", "")
                print(f"\nLast stop:")
                print(f"  {len(stop_timings)}. {stop_info.get('Description')} ({stop_info.get('Code')}) at {stop_time}")
                
                return True
            else:
                print("No stop timings in response")
        else:
            print(f"No data returned, trying opposite direction...")
            
            # Try opposite direction
            opposite_direction = "inbound" if api_direction == "outbound" else "outbound"
            trip_data["TripDirection"] = opposite_direction
            
            trip_response = session.post(
                trip_url, 
                headers=get_api_headers(token), 
                data=trip_data
            )
            
            if trip_response.status_code == 200:
                trip_json = trip_response.json()
                
                if trip_json.get("result") == "success" and "data" in trip_json and trip_json["data"]:
                    trip_info = trip_json["data"]
                    stop_timings = trip_info.get("TripStopTimings", [])
                    
                    if stop_timings:
                        print(f"✅ SUCCESS with {opposite_direction}! Retrieved {len(stop_timings)} stops")
                        return True
    
    print("Failed to get trip details")
    return False

if __name__ == "__main__":
    print("=== Testing Fixed Direction Handling ===\n")
    success = test_with_direction_fix()
    
    if success:
        print("\n✅ Test PASSED - Service should now work correctly!")
    else:
        print("\n❌ Test FAILED - Still having issues")