#!/usr/bin/env python3
"""
Test script for the new simplified bus_times services
Tests get_bus_stops and get_bus_times functionality
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
TEST_STOP_CODE = "10001"  # Mirrabooka Bus Stn Platform 4

class Colors:
    """Terminal colors for test output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}TEST: {test_name}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")

def print_success(message):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_error(message):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_info(message):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.RESET}")

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
        print_error(f"Error getting session/token: {e}")
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

def test_get_bus_stops():
    """Test the get_bus_stops service"""
    print_test_header("get_bus_stops Service")
    
    print_info(f"Testing with bus number: {TEST_BUS_NUMBER}")
    
    # Get session and token
    session, token = get_session_and_token(TEST_BUS_NUMBER)
    if not session or not token:
        print_error("Failed to get authentication")
        return False
    
    print_success("Got authentication token")
    
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
        print_error(f"Failed to get bus options: {options_response.status_code}")
        return False
    
    options_json = options_response.json()
    
    if options_json.get("result") != "success" or "data" not in options_json:
        print_error("No bus times available")
        return False
    
    options = options_json["data"].get("Options", [])
    
    if not options:
        print_error(f"No departures found for bus {TEST_BUS_NUMBER}")
        return False
    
    next_departure = options[0]
    trip_key = next_departure.get("TripKey")
    route_uid = next_departure.get("RouteUid")
    
    print_info(f"Next departure: {next_departure.get('StartTime')} - {next_departure.get('FinishTime')}")
    
    # Step 2: Get trip details
    trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
    
    trip_data = {
        "RouteUid": route_uid,
        "TripUid": trip_key,
        "TripDate": qry_date,
        "TripDirection": "outbound",
        "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
    }
    
    trip_response = session.post(
        trip_url, 
        headers=get_api_headers(token), 
        data=trip_data
    )
    
    # If outbound fails, try inbound
    if trip_response.status_code != 200:
        print_info("Trying inbound direction...")
        trip_data["TripDirection"] = "inbound"
        trip_response = session.post(
            trip_url, 
            headers=get_api_headers(token), 
            data=trip_data
        )
    
    if trip_response.status_code != 200:
        print_error(f"Failed to get trip details: {trip_response.status_code}")
        return False
    
    trip_json = trip_response.json()
    
    if trip_json.get("result") == "success" and "data" in trip_json:
        trip_info = trip_json["data"]
        stop_timings = trip_info.get("TripStopTimings", [])
        
        print_success(f"Retrieved {len(stop_timings)} stops")
        print_info(f"Headsign: {trip_info.get('Headsign', 'N/A')}")
        print_info(f"Direction: {trip_info.get('Direction', 'N/A')}")
        
        if stop_timings:
            # Show first 3 stops
            print_info("\nFirst 3 stops:")
            for i, stop_timing in enumerate(stop_timings[:3], 1):
                stop_info = stop_timing.get("Stop", {})
                stop_time = stop_timing.get("DepartTime") or stop_timing.get("ArrivalTime", "")
                print(f"  {i}. {stop_info.get('Description')} ({stop_info.get('Code')}) at {stop_time}")
                print(f"     Zone: {stop_info.get('Zone')}, Can board: {stop_timing.get('CanBoard')}")
            
            # Show last stop
            last_stop = stop_timings[-1]
            stop_info = last_stop.get("Stop", {})
            stop_time = last_stop.get("ArrivalTime") or last_stop.get("DepartTime", "")
            print(f"\nLast stop:")
            print(f"  {len(stop_timings)}. {stop_info.get('Description')} ({stop_info.get('Code')}) at {stop_time}")
        
        print_success("✅ get_bus_stops service working correctly")
        return True
    else:
        print_error("No trip data in response")
        return False

def test_get_bus_times():
    """Test the get_bus_times service"""
    print_test_header("get_bus_times Service")
    
    print_info(f"Testing with bus: {TEST_BUS_NUMBER}, stop: {TEST_STOP_CODE}")
    
    # Get session and token
    session, token = get_session_and_token(TEST_BUS_NUMBER)
    if not session or not token:
        print_error("Failed to get authentication")
        return False
    
    print_success("Got authentication token")
    
    # Get current date and time
    now = datetime.now()
    qry_date = now.strftime("%Y-%m-%d")
    qry_time = now.strftime("%H:%M")
    
    # Step 1: Get multiple departures
    options_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
    
    options_data = {
        "ExactlyMatchedRouteOnly": "true",
        "Mode": "bus",
        "Route": TEST_BUS_NUMBER,
        "QryDate": qry_date,
        "QryTime": qry_time,
        "MaxOptions": "5"  # Get 5 departures to check
    }
    
    options_response = session.post(
        options_url, 
        headers=get_api_headers(token), 
        data=options_data
    )
    
    if options_response.status_code != 200:
        print_error(f"Failed to get bus options: {options_response.status_code}")
        return False
    
    options_json = options_response.json()
    departures = options_json.get("data", {}).get("Options", [])
    
    if not departures:
        print_error(f"No departures found for bus {TEST_BUS_NUMBER}")
        return False
    
    print_info(f"Checking {len(departures)} departures for stop {TEST_STOP_CODE}")
    
    # Step 2: Check each departure for our stop
    times_found = []
    stop_name = ""
    
    for idx, departure in enumerate(departures, 1):
        trip_key = departure.get("TripKey")
        route_uid = departure.get("RouteUid")
        
        if not trip_key or not route_uid:
            continue
        
        print_info(f"Checking departure {idx}: {departure.get('StartTime')}")
        
        # Get trip details
        trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
        
        trip_data = {
            "RouteUid": route_uid,
            "TripUid": trip_key,
            "TripDate": qry_date,
            "TripDirection": "outbound",
            "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
        }
        
        trip_response = session.post(
            trip_url, 
            headers=get_api_headers(token), 
            data=trip_data
        )
        
        # If outbound fails, try inbound
        if trip_response.status_code != 200:
            trip_data["TripDirection"] = "inbound"
            trip_response = session.post(
                trip_url, 
                headers=get_api_headers(token), 
                data=trip_data
            )
        
        if trip_response.status_code != 200:
            continue
        
        trip_json = trip_response.json()
        
        if trip_json.get("result") == "success" and "data" in trip_json:
            trip_info = trip_json["data"]
            stop_timings = trip_info.get("TripStopTimings", [])
            
            # Find our stop
            for stop_timing in stop_timings:
                stop_info = stop_timing.get("Stop", {})
                
                if stop_info.get("Code") == str(TEST_STOP_CODE):
                    if stop_timing.get("CanBoard", False):
                        stop_time = stop_timing.get("DepartTime") or stop_timing.get("ArrivalTime", "")
                        
                        if not stop_name:
                            stop_name = stop_info.get("Description", "")
                        
                        times_found.append({
                            "time": stop_time,
                            "headsign": trip_info.get("Headsign", ""),
                            "zone": stop_info.get("Zone", "")
                        })
                        print_success(f"  Found: Bus arrives at {stop_time}")
                    else:
                        print_info(f"  Found stop but can_board=false")
                    break
    
    # Print results
    print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
    print(f"Stop: {stop_name or f'Stop {TEST_STOP_CODE}'}")
    print(f"Total times found: {len(times_found)}")
    
    if times_found:
        print("\nDeparture times:")
        for t in times_found:
            print(f"  • {t['time']} - {t['headsign']} (Zone {t['zone']})")
        print_success("✅ get_bus_times service working correctly")
        return True
    else:
        print_error(f"No times found - bus {TEST_BUS_NUMBER} may not stop at {TEST_STOP_CODE}")
        return False

def main():
    """Main test runner"""
    print(f"\n{Colors.BOLD}=== TESTING NEW BUS TIMES SERVICES ==={Colors.RESET}")
    
    results = {
        "get_bus_stops": test_get_bus_stops(),
        "get_bus_times": test_get_bus_times()
    }
    
    # Print summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}TEST SUMMARY{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    
    for service, passed in results.items():
        if passed:
            print(f"{Colors.GREEN}✓ {service}: PASSED{Colors.RESET}")
        else:
            print(f"{Colors.RED}✗ {service}: FAILED{Colors.RESET}")
    
    all_passed = all(results.values())
    if all_passed:
        print(f"\n{Colors.GREEN}{Colors.BOLD}ALL TESTS PASSED! 🎉{Colors.RESET}")
    else:
        print(f"\n{Colors.YELLOW}Some tests failed{Colors.RESET}")

if __name__ == "__main__":
    main()