####################################################################################################
# TRANSPERTH BUS TIMES PYSCRIPT SERVICE
####################################################################################################
# Provides real-time bus departure times and stop information from the Transperth API
#
# INSTALLATION:
# 1. Install PyScript via HACS
# 2. Place this file at: config/pyscript/apps/bus_times/__init__.py
# 3. Reload PyScript or restart Home Assistant
#
# SERVICES PROVIDED:
# - pyscript.get_bus_stops - Get all stops for the next departure of a bus route
# - pyscript.get_bus_times - Get all times when a bus arrives at a specific stop
# - pyscript.bus_times_health_check - Check if the integration is working
#
# USAGE EXAMPLES:
#
# Get all stops for bus 209:
#   service: pyscript.get_bus_stops
#   data:
#     bus_number: "209"
#
# Get all times bus 209 arrives at stop 10001:
#   service: pyscript.get_bus_times
#   data:
#     bus_number: "209"
#     stop_code: "10001"
#
# Check service health:
#   service: pyscript.bus_times_health_check
#
####################################################################################################

####################################################################################################
# IMPORT MODULES
####################################################################################################
import requests
import json
from datetime import datetime
import re

####################################################################################################
# CONFIGURATION
####################################################################################################
BASE_URL = "https://www.transperth.wa.gov.au"
MODULE_ID = "5345"
TAB_ID = "133"

# Direction constants
DIRECTION_BOTH = "both"
DIRECTION_INBOUND = "inbound"
DIRECTION_OUTBOUND = "outbound"

# API direction mappings
API_DIRECTION_OUTBOUND = ["0", 0]
API_DIRECTION_INBOUND = ["1", 1]

####################################################################################################
# HELPER FUNCTIONS
####################################################################################################
def normalize_direction(api_direction):
    """
    Normalize API direction value to standard string format.
    
    Args:
        api_direction: Direction value from API (can be 0, 1, "0", "1", or string)
        
    Returns:
        str: Normalized direction ("inbound" or "outbound")
    """
    if api_direction in API_DIRECTION_OUTBOUND:
        return DIRECTION_OUTBOUND
    elif api_direction in API_DIRECTION_INBOUND:
        return DIRECTION_INBOUND
    else:
        # Default to whatever string was provided, or outbound as fallback
        return str(api_direction) if api_direction else DIRECTION_OUTBOUND

def extract_token(html_content):
    """
    Extract the RequestVerificationToken from HTML using regex.
    This token is required for API authentication.
    
    Args:
        html_content: HTML page content containing the token
        
    Returns:
        str: The extracted token or None if not found
    """
    token_match = re.search(r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', html_content)
    if token_match:
        return token_match.group(1)
    return None

def get_session_and_token(bus_number):
    """
    Create a session and get authentication token for API calls.
    
    Args:
        bus_number: Bus number to use for initial auth page
        
    Returns:
        tuple: (session object, token string) or (None, None) on error
    """
    session = requests.Session()
    
    # Get authentication token from the timetable page
    auth_url = f"{BASE_URL}/timetables/details?Bus={bus_number}"
    
    try:
        auth_response = task.executor(session.get, auth_url)
        
        if auth_response.status_code != 200:
            log.error(f"Failed to get authentication page: {auth_response.status_code}")
            return None, None
        
        token = extract_token(auth_response.text)
        
        if not token:
            log.error("Failed to extract authentication token from HTML")
            return None, None
        
        return session, token
        
    except Exception as e:
        log.error(f"Error getting session/token: {e}")
        return None, None

def get_api_headers(token):
    """
    Get standard headers for Transperth API calls.
    
    Args:
        token: Authentication token
        
    Returns:
        dict: Headers dictionary for API requests
    """
    return {
        "RequestVerificationToken": token,
        "ModuleId": MODULE_ID,
        "TabId": TAB_ID,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }

####################################################################################################
# GET BUS STOPS SERVICE
####################################################################################################
@service(supports_response="only")
def get_bus_stops(bus_number, direction="both", return_response=True):
    """yaml
name: Get Bus Stops
description: Get a complete list of all stops for the next departure of a bus route
fields:
    bus_number:
        description: Bus route number (e.g. 209, 950, 881)
        example: "209"
        required: true
        selector:
            text:
    direction:
        description: Direction for the trip (inbound, outbound, or both to try both)
        example: "both"
        required: false
        default: "both"
        selector:
            select:
                options:
                  - both
                  - inbound
                  - outbound
    """
    """
    Returns a dictionary with the following structure:
    {
        "result": "success" or "error",
        "error": "Error message if result is error",
        "bus_number": "The bus route number requested",
        "departure_time": "When this bus departs from its first stop (HH:MM format)",
        "arrival_time": "When this bus arrives at its final stop (HH:MM format)", 
        "headsign": "The destination sign shown on the bus (e.g. '209 to Warwick Stn')",
        "direction": "Direction of travel (outbound/inbound)",
        "stops": [
            {
                "stop_number": "Sequential number of this stop on the route (1, 2, 3...)",
                "stop_name": "Full name of the stop (e.g. 'Mirrabooka Bus Stn Platform 4')",
                "stop_code": "Unique Transperth stop identifier (e.g. '10001')",
                "time": "Scheduled arrival/departure time at this stop (HH:MM format)",
                "zone": "Fare zone for this stop (1-9)",
                "can_board": "Boolean - whether passengers can board the bus here",
                "can_alight": "Boolean - whether passengers can exit the bus here",
                "is_timing_point": "Boolean - whether this is a timing point (bus waits if early)",
                "latitude": "GPS latitude coordinate of the stop",
                "longitude": "GPS longitude coordinate of the stop"
            }
        ],
        "total_stops": "Total number of stops on this route",
        "timestamp": "When this data was fetched (ISO 8601 format)"
    }
    """
    result = {}
    
    try:
        # Validate inputs
        if not bus_number:
            result['result'] = 'error'
            result['error'] = 'Bus number is required'
            return result
        
        # Ensure bus_number is a string
        bus_number = str(bus_number).strip()
        
        # Validate direction parameter
        valid_directions = [DIRECTION_BOTH, DIRECTION_INBOUND, DIRECTION_OUTBOUND]
        if direction and direction not in valid_directions:
            result['result'] = 'error'
            result['error'] = f'Invalid direction. Must be one of: {", ".join(valid_directions)}'
            return result
        
        # Get current date and time
        now = datetime.now()
        qry_date = now.strftime("%Y-%m-%d")
        qry_time = now.strftime("%H:%M")
        
        log.info(f"Getting stops for bus {bus_number}")
        
        # Get session and authentication token
        session, token = get_session_and_token(bus_number)
        if not session or not token:
            result['result'] = 'error'
            result['error'] = 'Authentication failed'
            return result
        
        # Step 1: Get the next departure for this bus
        options_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
        
        options_data = {
            "ExactlyMatchedRouteOnly": "true",
            "Mode": "bus",
            "Route": str(bus_number),
            "QryDate": qry_date,
            "QryTime": qry_time,
            "MaxOptions": "1"  # Just get the next departure
        }
        
        options_response = task.executor(
            session.post, 
            options_url, 
            headers=get_api_headers(token), 
            data=options_data
        )
        
        if options_response.status_code != 200:
            log.error(f"Failed to get bus options: {options_response.status_code}")
            result['result'] = 'error'
            result['error'] = f"Failed to get bus times: {options_response.status_code}"
            return result
        
        try:
            options_json = json.loads(options_response.text)
        except json.JSONDecodeError:
            result['result'] = 'error'
            result['error'] = 'Invalid response from bus times API'
            return result
        
        # Check if we got valid departure data
        if options_json.get("result") != "success" or "data" not in options_json:
            result['result'] = 'error'
            result['error'] = 'No bus times available'
            return result
        
        options = options_json["data"].get("Options", [])
        
        if not options:
            result['result'] = 'error'
            result['error'] = f"No departures found for bus {bus_number}"
            return result
        
        # Get the direction from the API response
        api_direction = normalize_direction(options_json["data"].get("Direction", DIRECTION_OUTBOUND))
        
        # Handle direction parameter
        if direction == DIRECTION_BOTH or direction is None:
            # Try API direction first, then opposite if needed
            trip_direction = api_direction
            log.info(f"Will try API direction ({api_direction}) first, then opposite if needed")
        else:
            # User specified a specific direction
            trip_direction = direction
            log.info(f"Using user-specified direction: {trip_direction}")
        
        # Get the first (next) departure
        next_departure = options[0]
        trip_key = next_departure.get("TripKey")
        route_uid = next_departure.get("RouteUid")
        
        if not trip_key or not route_uid:
            result['result'] = 'error'
            result['error'] = 'Missing trip information in response'
            return result
        
        log.info(f"Getting full route for {next_departure.get('StartTime')} departure")
        
        # Step 2: Get all stops for this trip
        trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
        
        trip_data = {
            "RouteUid": route_uid,
            "TripUid": trip_key,
            "TripDate": qry_date,
            "TripDirection": trip_direction,
            "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
        }
        
        trip_response = task.executor(
            session.post, 
            trip_url, 
            headers=get_api_headers(token), 
            data=trip_data
        )
        
        # If the response is 200 but has no data, try the opposite direction ONLY if direction="both"
        trip_json = None
        if trip_response.status_code == 200:
            try:
                trip_json = json.loads(trip_response.text)
                # Check if we got empty data
                if trip_json.get("result") == "success" and not trip_json.get("data"):
                    # Only try opposite direction if user didn't specify a specific direction
                    if direction == DIRECTION_BOTH or direction is None:
                        log.info(f"No data with {trip_direction}, trying opposite direction...")
                        opposite_direction = DIRECTION_INBOUND if trip_direction == DIRECTION_OUTBOUND else DIRECTION_OUTBOUND
                        trip_data["TripDirection"] = opposite_direction
                        trip_response = task.executor(
                            session.post, 
                            trip_url, 
                            headers=get_api_headers(token), 
                            data=trip_data
                        )
                        if trip_response.status_code == 200:
                            trip_json = json.loads(trip_response.text)
                            if trip_json.get("result") == "success" and trip_json.get("data"):
                                log.info(f"Success with {opposite_direction} direction")
                    else:
                        log.info(f"No data for specified direction {trip_direction}, not trying opposite")
            except json.JSONDecodeError:
                pass
        
        if trip_response.status_code != 200:
            # Fall back to basic info without detailed stops
            result['result'] = 'success'
            result['bus_number'] = bus_number
            result['departure_time'] = next_departure.get("StartTime", "")
            result['arrival_time'] = next_departure.get("FinishTime", "")
            result['headsign'] = f"{bus_number} to {next_departure.get('FinishLocation', 'Unknown')}"
            result['stops'] = []
            result['total_stops'] = 0
            result['note'] = "Could not retrieve detailed stop information"
            result['timestamp'] = now.isoformat()
            return result
        
        # Parse the response if we haven't already
        if not trip_json:
            try:
                trip_json = json.loads(trip_response.text)
            except json.JSONDecodeError:
                result['result'] = 'error'
                result['error'] = 'Invalid response from trip details API'
                return result
        
        # Process the trip data if we got it
        if trip_json.get("result") == "success":
            # Check if we have data field and TripStopTimings
            if "data" in trip_json and trip_json["data"]:
                trip_info = trip_json["data"]
                stop_timings = trip_info.get("TripStopTimings", [])
                
                if stop_timings:
                    # We have full stop data
                    # Build the result
                    result['result'] = 'success'
                    result['bus_number'] = bus_number
                    result['departure_time'] = next_departure.get("StartTime", "")
                    result['arrival_time'] = next_departure.get("FinishTime", "")
                    result['headsign'] = trip_info.get("Headsign", f"{bus_number} to {next_departure.get('FinishLocation', '')}")
                    result['direction'] = trip_info.get("Direction", "")
                    
                    # Process all stops
                    stops = []
                    for i, stop_timing in enumerate(stop_timings, 1):
                        stop_info = stop_timing.get("Stop", {})
                        
                        # Determine the time to show (departure time preferred, fall back to arrival)
                        stop_time = stop_timing.get("DepartTime") or stop_timing.get("ArrivalTime", "")
                        
                        stop = {
                            "stop_number": i,
                            "stop_name": stop_info.get("Description", ""),
                            "stop_code": stop_info.get("Code", ""),
                            "time": stop_time,
                            "zone": stop_info.get("Zone", ""),
                            "can_board": stop_timing.get("CanBoard", False),
                            "can_alight": stop_timing.get("CanAlight", False),
                            "is_timing_point": stop_timing.get("IsTimingPoint", False),
                            "latitude": stop_info.get("Latitude", ""),
                            "longitude": stop_info.get("Longitude", "")
                        }
                        stops.append(stop)
                    
                    result['stops'] = stops
                    result['total_stops'] = len(stops)
                    result['timestamp'] = now.isoformat()
                    
                    log.info(f"Successfully retrieved {len(stops)} stops for bus {bus_number}")
                else:
                    # API returned success but no stop timings - return basic info
                    log.warning(f"API returned success but no TripStopTimings for bus {bus_number}")
                    result['result'] = 'success'
                    result['bus_number'] = bus_number
                    result['departure_time'] = next_departure.get("StartTime", "")
                    result['arrival_time'] = next_departure.get("FinishTime", "")
                    result['start_location'] = next_departure.get("StartLocation", "")
                    result['finish_location'] = next_departure.get("FinishLocation", "")
                    result['headsign'] = f"{bus_number} to {next_departure.get('FinishLocation', '')}"
                    result['stops'] = []
                    result['total_stops'] = 0
                    result['note'] = "Detailed stop information not available - API returned limited data"
                    result['timestamp'] = now.isoformat()
            else:
                # API returned success but empty data - return basic info from GetTimetableOptions
                log.warning(f"API returned success but empty data for bus {bus_number}")
                result['result'] = 'success'
                result['bus_number'] = bus_number
                result['departure_time'] = next_departure.get("StartTime", "")
                result['arrival_time'] = next_departure.get("FinishTime", "")
                result['start_location'] = next_departure.get("StartLocation", "")
                result['finish_location'] = next_departure.get("FinishLocation", "")
                result['headsign'] = f"{bus_number} to {next_departure.get('FinishLocation', '')}"
                result['stops'] = []
                result['total_stops'] = 0
                result['note'] = "Detailed stop information not available - API returned limited data"
                result['timestamp'] = now.isoformat()
        else:
            result['result'] = 'error'
            result['error'] = 'Trip details API request failed'
            return result
        
        return result
        
    except Exception as e:
        log.error(f"Unexpected error in get_bus_stops service: {e}")
        result['result'] = 'error'
        result['error'] = str(e)
        return result

####################################################################################################
# GET BUS TIMES SERVICE
####################################################################################################
@service(supports_response="only")
def get_bus_times(bus_number, stop_code, direction="both", return_response=True):
    """yaml
name: Get Bus Times at Stop
description: Get all times when a specific bus arrives at a specific stop throughout the day
fields:
    bus_number:
        description: Bus route number (e.g. 209, 950, 881)
        example: "209"
        required: true
        selector:
            text:
    stop_code:
        description: Transperth stop code (e.g. 10001, 21940)
        example: "10001"
        required: true
        selector:
            text:
    direction:
        description: Direction for the trip (inbound, outbound, or both to try both)
        example: "both"
        required: false
        default: "both"
        selector:
            select:
                options:
                  - both
                  - inbound
                  - outbound
    """
    """
    Returns a dictionary with the following structure:
    {
        "result": "success" or "error",
        "error": "Error message if result is error",
        "bus_number": "The bus route number requested",
        "stop_code": "The stop code requested",
        "stop_name": "Full name of the stop",
        "times": [
            {
                "departure_time": "Time the bus departs from this stop (HH:MM format)",
                "headsign": "The destination sign for this departure",
                "zone": "Fare zone for this stop",
                "journey_time": "Minutes from first stop to this stop",
                "final_destination": "Last stop of this bus journey",
                "final_arrival_time": "When this bus reaches its final destination"
            }
        ],
        "total_found": "Number of times found for this bus at this stop",
        "timestamp": "When this data was fetched (ISO 8601 format)"
    }
    
    Note: Only includes stops where can_board=true (you can actually get on the bus)
    """
    result = {}
    
    try:
        # Validate inputs
        if not bus_number:
            result['result'] = 'error'
            result['error'] = 'Bus number is required'
            return result
        
        if not stop_code:
            result['result'] = 'error'
            result['error'] = 'Stop code is required'
            return result
        
        # Ensure inputs are strings
        bus_number = str(bus_number).strip()
        stop_code = str(stop_code).strip()
        
        # Validate direction parameter
        valid_directions = [DIRECTION_BOTH, DIRECTION_INBOUND, DIRECTION_OUTBOUND]
        if direction and direction not in valid_directions:
            result['result'] = 'error'
            result['error'] = f'Invalid direction. Must be one of: {", ".join(valid_directions)}'
            return result
        
        # Get current date and time
        now = datetime.now()
        qry_date = now.strftime("%Y-%m-%d")
        qry_time = now.strftime("%H:%M")
        
        log.info(f"Getting times for bus {bus_number} at stop {stop_code}")
        
        # Get session and authentication token
        session, token = get_session_and_token(bus_number)
        if not session or not token:
            result['result'] = 'error'
            result['error'] = 'Authentication failed'
            return result
        
        # Step 1: Get all departures for this bus
        options_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
        
        options_data = {
            "ExactlyMatchedRouteOnly": "true",
            "Mode": "bus",
            "Route": str(bus_number),
            "QryDate": qry_date,
            "QryTime": qry_time,
            "MaxOptions": "10"  # Get many departures to check
        }
        
        options_response = task.executor(
            session.post, 
            options_url, 
            headers=get_api_headers(token), 
            data=options_data
        )
        
        if options_response.status_code != 200:
            log.error(f"Failed to get bus options: {options_response.status_code}")
            result['result'] = 'error'
            result['error'] = f"Failed to get bus times: {options_response.status_code}"
            return result
        
        try:
            options_json = json.loads(options_response.text)
        except json.JSONDecodeError:
            result['result'] = 'error'
            result['error'] = 'Invalid response from bus times API'
            return result
        
        # Check if we got valid departure data
        if options_json.get("result") != "success" or "data" not in options_json:
            result['result'] = 'error'
            result['error'] = 'No bus times available'
            return result
        
        departures = options_json["data"].get("Options", [])
        
        if not departures:
            result['result'] = 'error'
            result['error'] = f"No departures found for bus {bus_number}"
            return result
        
        # Get the direction from the API response
        api_direction = normalize_direction(options_json["data"].get("Direction", DIRECTION_OUTBOUND))
        
        # Handle direction parameter
        if direction == DIRECTION_BOTH or direction is None:
            # Try API direction first, then opposite if needed
            trip_direction = api_direction
            log.info(f"Will try API direction ({api_direction}) first, then opposite if needed for stop search")
        else:
            # User specified a specific direction
            trip_direction = direction
            log.info(f"Using user-specified direction: {trip_direction} for stop search")
        
        log.info(f"Checking {len(departures)} departures for stop {stop_code}")
        
        # Step 2: For each departure, check if it stops at the requested stop
        times_found = []
        stop_name = ""
        
        for departure in departures:
            trip_key = departure.get("TripKey")
            route_uid = departure.get("RouteUid")
            
            if not trip_key or not route_uid:
                continue
            
            # Get trip details
            trip_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTrip"
            
            trip_data = {
                "RouteUid": route_uid,
                "TripUid": trip_key,
                "TripDate": qry_date,
                "TripDirection": trip_direction,
                "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK"
            }
            
            trip_response = task.executor(
                session.post, 
                trip_url, 
                headers=get_api_headers(token), 
                data=trip_data
            )
            
            # If we get 200 but no data, try opposite direction ONLY if direction="both"
            if trip_response.status_code == 200:
                try:
                    trip_json = json.loads(trip_response.text)
                    if trip_json.get("result") == "success" and not trip_json.get("data"):
                        # Only try opposite direction if user didn't specify a specific direction
                        if direction == "both" or direction is None:
                            opposite_direction = DIRECTION_INBOUND if trip_direction == DIRECTION_OUTBOUND else DIRECTION_OUTBOUND
                            trip_data["TripDirection"] = opposite_direction
                            trip_response = task.executor(
                                session.post, 
                                trip_url, 
                                headers=get_api_headers(token), 
                                data=trip_data
                            )
                except json.JSONDecodeError:
                    pass
            
            if trip_response.status_code != 200:
                continue
            
            try:
                trip_json = json.loads(trip_response.text)
            except json.JSONDecodeError:
                continue
            
            # Process trip data
            if trip_json.get("result") == "success" and "data" in trip_json:
                trip_info = trip_json["data"]
                stop_timings = trip_info.get("TripStopTimings", [])
                
                # Find the requested stop
                first_stop_time = None
                for i, stop_timing in enumerate(stop_timings):
                    stop_info = stop_timing.get("Stop", {})
                    
                    # Remember the first stop's time for journey time calculation
                    if i == 0:
                        first_stop_time = stop_timing.get("DepartTime", stop_timing.get("ArrivalTime"))
                    
                    # Check if this is our stop
                    if stop_info.get("Code") == str(stop_code):
                        # Only include if passengers can board here
                        if stop_timing.get("CanBoard", False):
                            stop_time = stop_timing.get("DepartTime") or stop_timing.get("ArrivalTime", "")
                            
                            # Calculate journey time if possible
                            journey_time = None
                            if first_stop_time and stop_time:
                                try:
                                    start = datetime.strptime(first_stop_time, "%H:%M")
                                    stop = datetime.strptime(stop_time, "%H:%M")
                                    journey_time = int((stop - start).total_seconds() / 60)
                                except:
                                    journey_time = None
                            
                            # Store the stop name (it should be the same for all times)
                            if not stop_name:
                                stop_name = stop_info.get("Description", "")
                            
                            time_info = {
                                "departure_time": stop_time,
                                "headsign": trip_info.get("Headsign", f"{bus_number} to {departure.get('FinishLocation', '')}"),
                                "zone": stop_info.get("Zone", ""),
                                "journey_time": journey_time,
                                "final_destination": departure.get("FinishLocation", ""),
                                "final_arrival_time": departure.get("FinishTime", "")
                            }
                            times_found.append(time_info)
                            log.debug(f"Found stop at {stop_time}")
                        else:
                            log.debug(f"Found stop but can_board=false")
                        break  # Stop looking once we found this stop
        
        # Build the result
        result['result'] = 'success'
        result['bus_number'] = bus_number
        result['stop_code'] = stop_code
        result['stop_name'] = stop_name or f"Stop {stop_code}"
        result['times'] = times_found
        result['total_found'] = len(times_found)
        result['timestamp'] = now.isoformat()
        
        if len(times_found) == 0:
            result['note'] = f"Bus {bus_number} does not stop at stop {stop_code}, or no services found"
        
        log.info(f"Found {len(times_found)} times for bus {bus_number} at stop {stop_code}")
        
        return result
        
    except Exception as e:
        log.error(f"Unexpected error in get_bus_times service: {e}")
        result['result'] = 'error'
        result['error'] = str(e)
        return result

####################################################################################################
# HEALTH CHECK SERVICE
####################################################################################################
@service(supports_response="only")
def bus_times_health_check(return_response=True):
    """yaml
name: Bus Times Health Check
description: Check if the Transperth API integration is working correctly
    """
    """
    Returns a dictionary with health check results:
    {
        "result": "success" or "error",
        "api_accessible": Boolean - whether we can reach the API,
        "authentication_working": Boolean - whether we can get auth tokens,
        "test_bus_number": "209",
        "test_results": {
            "get_stops_working": Boolean,
            "get_times_working": Boolean
        },
        "timestamp": "ISO 8601 timestamp"
    }
    """
    result = {
        "result": "error",
        "api_accessible": False,
        "authentication_working": False,
        "test_bus_number": "209",
        "test_results": {
            "get_stops_working": False,
            "get_times_working": False
        },
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Test 1: Check if we can get a session and token
        log.info("Health check: Testing authentication...")
        session, token = get_session_and_token("209")
        
        if session and token:
            result["authentication_working"] = True
            log.info("Health check: Authentication successful")
            
            # Test 2: Check if we can access the API
            try:
                options_url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptions"
                test_data = {
                    "ExactlyMatchedRouteOnly": "true",
                    "Mode": "bus",
                    "Route": "209",
                    "QryDate": datetime.now().strftime("%Y-%m-%d"),
                    "QryTime": datetime.now().strftime("%H:%M"),
                    "MaxOptions": "1"
                }
                
                response = task.executor(
                    session.post,
                    options_url,
                    headers=get_api_headers(token),
                    data=test_data
                )
                
                if response.status_code == 200:
                    result["api_accessible"] = True
                    log.info("Health check: API accessible")
                    
                    # Test if we get valid data
                    try:
                        json_data = json.loads(response.text)
                        if json_data.get("result") == "success" and "data" in json_data:
                            if json_data["data"].get("Options"):
                                result["test_results"]["get_stops_working"] = True
                                result["test_results"]["get_times_working"] = True
                                result["result"] = "success"
                                log.info("Health check: All tests passed")
                    except json.JSONDecodeError:
                        log.warning("Health check: API returned invalid JSON")
                else:
                    log.warning(f"Health check: API returned status {response.status_code}")
                    
            except Exception as e:
                log.error(f"Health check: API test failed: {e}")
        else:
            log.warning("Health check: Authentication failed")
            
    except Exception as e:
        log.error(f"Health check error: {e}")
        result["error"] = str(e)
    
    return result

####################################################################################################
# ERROR RESPONSE DOCUMENTATION
####################################################################################################
"""
Error responses have the following structure:
{
    "result": "error",
    "error": "Descriptive error message",
    "details": "Additional error context (optional)"
}

Common errors:
- "Authentication failed": Could not get API token
- "Bus route not found": Invalid bus number
- "Stop not found": Stop code doesn't exist or bus doesn't stop there
- "No services found": No buses running (e.g., late night)
- "API request failed": Transperth API is down or unavailable
"""