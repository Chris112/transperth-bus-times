####################################################################################################
# TRANSPERTH BUS TIMES PYSCRIPT SERVICE
####################################################################################################
# Provides scheduled bus departure times and stop information from the Transperth API
#
# INSTALLATION:
# 1. Install PyScript via HACS
# 2. Place this file at: config/pyscript/bus_times.py
# 3. Reload PyScript or restart Home Assistant
#
# SERVICES PROVIDED:
# - pyscript.get_next_bus             - Next bus at a stop (optionally filter by route)
# - pyscript.get_leave_time           - "Is it time to leave?" for a specific bus and stop
# - pyscript.get_bus_countdown        - Integer minutes until next bus (sensor-friendly)
# - pyscript.get_stop_departures      - Next N buses at a stop (any route)
# - pyscript.get_bus_schedule   - All upcoming times a bus stops at a stop (from 'at' onward)
# - pyscript.get_bus_stops            - All stops on a bus's next upcoming trip
# - pyscript.bus_times_health_check   - Check the integration is working
#
# USAGE EXAMPLES:
#
# When's my next 414?
#   service: pyscript.get_next_bus
#   data:
#     stop_code: "12627"
#     bus_number: "414"
#
# Time to leave for the 414? (need 5 min walk to the stop)
#   service: pyscript.get_leave_time
#   data:
#     stop_code: "12627"
#     bus_number: "414"
#     walk_minutes: 5
#
####################################################################################################

import requests
import json
from datetime import datetime, timedelta
import re

####################################################################################################
# CONFIGURATION
####################################################################################################
BASE_URL = "https://www.transperth.wa.gov.au"

# Route (timetable) page auth context
ROUTE_MODULE_ID = "5345"
ROUTE_TAB_ID = "133"

# Stop page auth context (different module scope — route token returns 401 here)
STOP_MODULE_ID = "5310"
STOP_TAB_ID = "141"

# Transperth returns HTTP 429 with body "Too Many Requests" when its rate limit is hit.
# Cooldown is sticky (observed >60s). Surface it as a distinct error so callers can back off.
RATE_LIMIT_MESSAGE = (
    "Transperth API rate limit hit (HTTP 429). Wait a few minutes before retrying, "
    "or reduce automation frequency."
)

# Service note codes Transperth's website passes when requesting timetables. The response
# returns NoteIds that index into this list (e.g. notes like "Does not run Christmas Day").
# We don't parse the returned notes, but we send the same list the website does to stay
# aligned with its behaviour. Individual code meanings aren't documented by Transperth.
NOTE_CODES = "DV,LM,CM,TC,BG,FG,LK"

# Whether to ask the API to include live vehicle tracking data. We always pass "false" —
# we only care about scheduled times, and in all observed responses the realtime feed
# was empty anyway.
INCLUDE_REALTIME = "false"

# Direction constants
DIRECTION_BOTH = "both"
DIRECTION_INBOUND = "inbound"
DIRECTION_OUTBOUND = "outbound"
VALID_DIRECTIONS = [DIRECTION_BOTH, DIRECTION_INBOUND, DIRECTION_OUTBOUND]

# API direction mappings (the options API returns 0/1 or "0"/"1")
API_DIRECTION_OUTBOUND = ["0", 0]
API_DIRECTION_INBOUND = ["1", 1]


####################################################################################################
# EXCEPTIONS
####################################################################################################
class RateLimitError(Exception):
    """Raised when Transperth returns HTTP 429. Services catch and return a structured error."""
    pass


class AuthError(Exception):
    """Raised when we can't obtain a valid token from a page."""
    pass


class NetworkError(Exception):
    """Raised when the HTTP request itself failed (DNS, timeout, connection refused, etc.)."""
    pass


####################################################################################################
# HELPER FUNCTIONS
####################################################################################################
def extract_token(html_content):
    """Extract the __RequestVerificationToken hidden input from an HTML page."""
    m = re.search(
        r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"',
        html_content,
    )
    return m.group(1) if m else None


def normalize_direction(api_direction):
    """Normalize API direction value (0/1/"0"/"1"/"outbound"/"inbound") to a standard string."""
    if api_direction in API_DIRECTION_OUTBOUND:
        return DIRECTION_OUTBOUND
    if api_direction in API_DIRECTION_INBOUND:
        return DIRECTION_INBOUND
    return str(api_direction) if api_direction else DIRECTION_OUTBOUND


####################################################################################################
# AUTH HELPERS
####################################################################################################
def _fetch_token_page(session, url, label):
    """Fetch a token-bearing page. Raises AuthError or NetworkError."""
    try:
        r = task.executor(session.get, url)
    except requests.RequestException as e:
        log.error(f"Network error fetching {label}: {e}")
        raise NetworkError(f"Could not reach Transperth ({type(e).__name__})")
    if r.status_code != 200:
        raise AuthError(f"{label} returned {r.status_code}")
    token = extract_token(r.text)
    if not token:
        raise AuthError(f"Could not extract token from {label}")
    return token


def get_route_auth(session, bus_number):
    """Fetch a route-context token. Used for options/trip endpoints."""
    url = f"{BASE_URL}/timetables/details?Bus={bus_number}"
    return _fetch_token_page(session, url, "route auth page")


def get_stop_auth(session, stop_code):
    """Fetch a stop-context token. Used for GetStopTimetableAsync."""
    url = f"{BASE_URL}/Journey-Planner/Stops-Near-You?locationtype=stop&location={stop_code}"
    return _fetch_token_page(session, url, "stop auth page")


def route_headers(token):
    return {
        "RequestVerificationToken": token,
        "ModuleId": ROUTE_MODULE_ID,
        "TabId": ROUTE_TAB_ID,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }


def stop_headers(token, stop_code):
    stop_page = f"{BASE_URL}/Journey-Planner/Stops-Near-You?locationtype=stop&location={stop_code}"
    return {
        "RequestVerificationToken": token,
        "ModuleId": STOP_MODULE_ID,
        "TabId": STOP_TAB_ID,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": stop_page,
        "Origin": BASE_URL,
    }


####################################################################################################
# API CALL HELPERS
####################################################################################################
def _post_json(session, url, headers, data):
    """POST and return parsed JSON. Raises RateLimitError on 429, NetworkError on connection issues."""
    try:
        r = task.executor(session.post, url, headers=headers, data=data)
    except requests.RequestException as e:
        log.error(f"Network error calling {url}: {e}")
        raise NetworkError(f"Could not reach Transperth API ({type(e).__name__})")
    if r.status_code == 429:
        raise RateLimitError()
    if r.status_code != 200:
        log.error(f"Transperth API {url} returned {r.status_code}")
        return None
    try:
        return json.loads(r.text)
    except json.JSONDecodeError:
        log.error(f"Transperth API {url} returned non-JSON")
        return None


def call_stop_timetable(session, stop_code, search_date, search_time, max_trips):
    """GetStopTimetableAsync — one call, all upcoming buses at a stop."""
    token = get_stop_auth(session, stop_code)
    url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetStopTimetableAsync"
    data = {
        "StopNumber": str(stop_code),
        "SearchDate": search_date,
        "SearchTime": search_time,
        "IsRealTimeChecked": INCLUDE_REALTIME,
        "ReturnNoteCodes": NOTE_CODES,
        "MaxTripCount": str(max_trips),
    }
    resp = _post_json(session, url, stop_headers(token, stop_code), data)
    if not resp or resp.get("result") != "success":
        return None, None
    return resp.get("trips", []), resp.get("stop")


def call_options_async(session, token, bus_number, qry_date, qry_time, max_options):
    """GetTimetableOptionsAsync — upcoming trips for a route."""
    url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptionsAsync"
    data = {
        "ExactlyMatchedRouteOnly": "true",
        "Mode": "bus",
        "Route": str(bus_number),
        "QryDate": qry_date,
        "QryTime": qry_time,
        "MaxOptions": str(max_options),
    }
    resp = _post_json(session, url, route_headers(token), data)
    if not resp or resp.get("result") != "success":
        return None, None
    payload = resp.get("data") or {}
    return payload.get("Options", []), payload.get("Direction")


def call_trip_async(session, token, route_uid, trip_uid, trip_date, trip_direction):
    """GetTimetableTripAsync — full stop list for one trip."""
    url = f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTripAsync"
    data = {
        "RouteUid": route_uid,
        "TripUid": trip_uid,
        "TripDate": trip_date,
        "TripDirection": trip_direction,
        "ReturnNoteCodes": NOTE_CODES,
    }
    resp = _post_json(session, url, route_headers(token), data)
    if not resp or resp.get("result") != "success":
        return None
    return resp.get("data")


####################################################################################################
# SHAPING HELPERS
####################################################################################################
def parse_stop_trip(entry):
    """Normalize one entry from GetStopTimetableAsync.trips[] to our flat shape."""
    summary = entry.get("Summary", {}) or {}
    origin = entry.get("Origin", {}) or {}
    destination = entry.get("Destination", {}) or {}
    depart_iso = entry.get("DepartTime") or entry.get("ArrivalTime") or ""
    return {
        "route_code": summary.get("RouteCode", ""),
        "headsign": summary.get("Headsign", ""),
        "depart_time": _iso_to_hhmm(depart_iso),
        "depart_iso": depart_iso,
        "origin_name": origin.get("Name", ""),
        "destination_name": destination.get("Name", ""),
        "trip_uid": summary.get("TripUid", ""),
        "direction": normalize_direction(summary.get("Direction")),
        "is_real_time": bool(entry.get("IsRealTime", False)),
    }


def _iso_to_hhmm(iso_string):
    """Convert '2026-04-23T13:19' to '13:19'. Pass through empty/invalid strings."""
    if not iso_string:
        return ""
    try:
        return datetime.strptime(iso_string[:16], "%Y-%m-%dT%H:%M").strftime("%H:%M")
    except ValueError:
        return iso_string


def minutes_until_iso(iso_string, now):
    """Return integer minutes from `now` until `iso_string`.
    Returns -1 as a sentinel if the string is empty/invalid OR if the target is in the past.
    """
    if not iso_string:
        return -1
    try:
        target = datetime.strptime(iso_string[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return -1
    minutes = int((target - now).total_seconds() // 60)
    return minutes if minutes >= 0 else -1


def resolve_reference_time(at):
    """Convert an optional `at` input into a datetime.

    Accepts:
        None / empty -> datetime.now()
        "HH:MM"      -> next occurrence of that time (today if still upcoming, else tomorrow)
        "YYYY-MM-DD HH:MM" or "YYYY-MM-DDTHH:MM" -> exact moment (no rollover)
    Returns the resolved datetime, or raises ValueError.

    The HH:MM form rolls to tomorrow when the time has already passed today, so
    setting "08:00" at 9pm returns tomorrow morning 8am — what you'd want for
    morning automations set up the night before. For literal same-day past times
    (e.g. to debug what happened at 8am), use the explicit YYYY-MM-DD HH:MM form.
    """
    if not at:
        return datetime.now()
    s = str(at).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%H:%M"):
        try:
            parsed = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if fmt == "%H:%M":
            now = datetime.now()
            candidate = now.replace(
                hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0
            )
            if candidate < now:
                candidate += timedelta(days=1)
            return candidate
        return parsed
    raise ValueError(
        f"Invalid time '{at}'. Use 'HH:MM' for today/tomorrow or 'YYYY-MM-DD HH:MM' for a specific moment."
    )


def rate_limit_error_dict():
    return {
        "result": "error",
        "error": RATE_LIMIT_MESSAGE,
        "rate_limited": True,
    }


def error_dict(message):
    return {"result": "error", "error": message}


####################################################################################################
# SERVICE: get_next_bus
####################################################################################################
@service(supports_response="only")
def get_next_bus(stop_code, bus_number=None, at=None, return_response=True):
    """yaml
name: Get Next Bus
description: Next bus at a stop, optionally filtered by route number
fields:
    stop_code:
        description: Transperth stop code (e.g. 12627)
        example: "12627"
        required: true
        selector:
            text:
    bus_number:
        description: Optional bus route filter (e.g. 414). If omitted, returns the very next bus regardless of route.
        example: "414"
        selector:
            text:
    at:
        description: Reference time to search from. 'HH:MM' rolls to tomorrow if past; 'YYYY-MM-DD HH:MM' for an exact moment. Defaults to now.
        example: "08:00"
        selector:
            text:
    """
    try:
        if not stop_code:
            return error_dict("stop_code is required")
        stop_code = str(stop_code).strip()
        target_route = str(bus_number).strip() if bus_number else None

        try:
            ref = resolve_reference_time(at)
        except ValueError as e:
            return error_dict(str(e))
        session = requests.Session()

        trips, stop_info = call_stop_timetable(
            session, stop_code, ref.strftime("%Y-%m-%d"), ref.strftime("%H:%M"), max_trips=20
        )
        if trips is None:
            return error_dict(f"No data available for stop {stop_code}")

        for raw in trips:
            parsed = parse_stop_trip(raw)
            if target_route and parsed["route_code"] != target_route:
                continue
            return {
                "result": "success",
                "stop_code": stop_code,
                "stop_name": (stop_info or {}).get("Description", ""),
                "bus_number": parsed["route_code"],
                "departure_time": parsed["depart_time"],
                "minutes_until": minutes_until_iso(parsed["depart_iso"], datetime.now()),
                "headsign": parsed["headsign"],
                "destination": parsed["destination_name"],
                "reference_time": ref.isoformat(),
                "timestamp": datetime.now().isoformat(),
            }

        note = f"No upcoming bus {target_route} at stop {stop_code}" if target_route else f"No upcoming buses at stop {stop_code}"
        return {
            "result": "success",
            "stop_code": stop_code,
            "bus_number": target_route,
            "note": note,
            "reference_time": ref.isoformat(),
            "timestamp": datetime.now().isoformat(),
        }

    except RateLimitError:
        return rate_limit_error_dict()
    except NetworkError as e:
        return error_dict(str(e))
    except AuthError as e:
        return error_dict(f"Authentication failed: {e}")
    except Exception as e:
        log.error(f"get_next_bus error: {e}")
        return error_dict(str(e))


####################################################################################################
# SERVICE: get_leave_time
####################################################################################################
@service(supports_response="only")
def get_leave_time(stop_code, bus_number, walk_minutes=0, at=None, return_response=True):
    """yaml
name: Get Leave Time
description: Tells you whether it's time to leave for the bus, accounting for walk time
fields:
    stop_code:
        description: Transperth stop code
        example: "12627"
        required: true
        selector:
            text:
    bus_number:
        description: Bus route number
        example: "414"
        required: true
        selector:
            text:
    walk_minutes:
        description: How long it takes to walk to the stop (minutes)
        example: 5
        default: 0
        selector:
            number:
                min: 0
                max: 60
    at:
        description: Reference time to search from. 'HH:MM' rolls to tomorrow if past; 'YYYY-MM-DD HH:MM' for an exact moment. Defaults to now.
        example: "08:00"
        selector:
            text:
    """
    try:
        if not stop_code or not bus_number:
            return error_dict("stop_code and bus_number are required")
        try:
            walk = int(walk_minutes)
        except (TypeError, ValueError):
            return error_dict("walk_minutes must be an integer")

        next_bus = get_next_bus(stop_code=stop_code, bus_number=bus_number, at=at, return_response=True)
        if next_bus.get("result") != "success" or "minutes_until" not in next_bus:
            return next_bus  # propagate error or "no buses" note

        minutes_until_bus = next_bus["minutes_until"]
        if minutes_until_bus is None:
            return error_dict("Could not determine bus departure time")

        minutes_until_leave = minutes_until_bus - walk
        return {
            "result": "success",
            "stop_code": str(stop_code).strip(),
            "bus_number": str(bus_number).strip(),
            "walk_minutes": walk,
            "departure_time": next_bus["departure_time"],
            "minutes_until_bus": minutes_until_bus,
            "minutes_until_leave": minutes_until_leave,
            "is_time_to_leave": minutes_until_leave <= 0,
            "headsign": next_bus.get("headsign", ""),
            "timestamp": next_bus.get("timestamp"),
        }
    except Exception as e:
        log.error(f"get_leave_time error: {e}")
        return error_dict(str(e))


####################################################################################################
# SERVICE: get_bus_countdown
####################################################################################################
@service(supports_response="only")
def get_bus_countdown(stop_code, bus_number, at=None, return_response=True):
    """yaml
name: Get Bus Countdown
description: Integer minutes until the next specified bus at a stop (sensor-friendly). Returns -1 if no bus is coming.
fields:
    stop_code:
        description: Transperth stop code
        example: "12627"
        required: true
        selector:
            text:
    bus_number:
        description: Bus route number
        example: "414"
        required: true
        selector:
            text:
    at:
        description: Reference time. 'HH:MM' rolls to tomorrow if past; 'YYYY-MM-DD HH:MM' for an exact moment. Defaults to now.
        example: "08:00"
        selector:
            text:
    """
    try:
        next_bus = get_next_bus(stop_code=stop_code, bus_number=bus_number, at=at, return_response=True)
        if next_bus.get("result") != "success":
            return {"result": "error", "minutes": -1, "error": next_bus.get("error", "unknown error")}
        return {"result": "success", "minutes": next_bus.get("minutes_until", -1)}
    except Exception as e:
        log.error(f"get_bus_countdown error: {e}")
        return {"result": "error", "minutes": -1, "error": str(e)}


####################################################################################################
# SERVICE: get_stop_departures
####################################################################################################
@service(supports_response="only")
def get_stop_departures(stop_code, count=5, at=None, return_response=True):
    """yaml
name: Get Stop Departures
description: List the next N buses at a stop, across all routes
fields:
    stop_code:
        description: Transperth stop code
        example: "12627"
        required: true
        selector:
            text:
    count:
        description: How many upcoming buses to return (1-20)
        example: 5
        default: 5
        selector:
            number:
                min: 1
                max: 20
    at:
        description: Reference time. 'HH:MM' rolls to tomorrow if past; 'YYYY-MM-DD HH:MM' for an exact moment. Defaults to now.
        example: "08:00"
        selector:
            text:
    """
    try:
        if not stop_code:
            return error_dict("stop_code is required")
        stop_code = str(stop_code).strip()
        try:
            count = max(1, min(int(count), 20))
        except (TypeError, ValueError):
            count = 5

        try:
            ref = resolve_reference_time(at)
        except ValueError as e:
            return error_dict(str(e))

        session = requests.Session()
        trips, stop_info = call_stop_timetable(
            session, stop_code, ref.strftime("%Y-%m-%d"), ref.strftime("%H:%M"), max_trips=count
        )
        if trips is None:
            return error_dict(f"No data available for stop {stop_code}")

        departures = []
        for raw in trips[:count]:
            parsed = parse_stop_trip(raw)
            departures.append({
                "bus_number": parsed["route_code"],
                "departure_time": parsed["depart_time"],
                "minutes_until": minutes_until_iso(parsed["depart_iso"], datetime.now()),
                "headsign": parsed["headsign"],
                "destination": parsed["destination_name"],
            })
        return {
            "result": "success",
            "stop_code": stop_code,
            "stop_name": (stop_info or {}).get("Description", ""),
            "departures": departures,
            "total_found": len(departures),
            "reference_time": ref.isoformat(),
            "timestamp": datetime.now().isoformat(),
        }
    except RateLimitError:
        return rate_limit_error_dict()
    except NetworkError as e:
        return error_dict(str(e))
    except AuthError as e:
        return error_dict(f"Authentication failed: {e}")
    except Exception as e:
        log.error(f"get_stop_departures error: {e}")
        return error_dict(str(e))


####################################################################################################
# SERVICE: get_bus_schedule
####################################################################################################
@service(supports_response="only")
def get_bus_schedule(bus_number, stop_code, at=None, return_response=True):
    """yaml
name: Get Bus Schedule
description: All upcoming times the given bus stops at the given stop (from the reference time onward). Use `at` to query a different date/time.
fields:
    bus_number:
        description: Bus route number
        example: "414"
        required: true
        selector:
            text:
    stop_code:
        description: Transperth stop code
        example: "12627"
        required: true
        selector:
            text:
    at:
        description: Reference time. 'HH:MM' rolls to tomorrow if past; 'YYYY-MM-DD HH:MM' for an exact moment. Defaults to now.
        example: "08:00"
        selector:
            text:
    """
    try:
        if not bus_number or not stop_code:
            return error_dict("bus_number and stop_code are required")
        bus_number = str(bus_number).strip()
        stop_code = str(stop_code).strip()

        try:
            ref = resolve_reference_time(at)
        except ValueError as e:
            return error_dict(str(e))

        session = requests.Session()
        # Max from observed API is unclear; request generously — response is still small
        trips, stop_info = call_stop_timetable(
            session, stop_code, ref.strftime("%Y-%m-%d"), ref.strftime("%H:%M"), max_trips=50
        )
        if trips is None:
            return error_dict(f"No data available for stop {stop_code}")

        times = []
        for raw in trips:
            parsed = parse_stop_trip(raw)
            if parsed["route_code"] != bus_number:
                continue
            times.append({
                "departure_time": parsed["depart_time"],
                "minutes_until": minutes_until_iso(parsed["depart_iso"], datetime.now()),
                "headsign": parsed["headsign"],
                "destination": parsed["destination_name"],
            })

        return {
            "result": "success",
            "bus_number": bus_number,
            "stop_code": stop_code,
            "stop_name": (stop_info or {}).get("Description", ""),
            "times": times,
            "total_found": len(times),
            "note": None if times else f"Bus {bus_number} does not stop at {stop_code} in the upcoming schedule",
            "reference_time": ref.isoformat(),
            "timestamp": datetime.now().isoformat(),
        }
    except RateLimitError:
        return rate_limit_error_dict()
    except NetworkError as e:
        return error_dict(str(e))
    except AuthError as e:
        return error_dict(f"Authentication failed: {e}")
    except Exception as e:
        log.error(f"get_bus_schedule error: {e}")
        return error_dict(str(e))


####################################################################################################
# SERVICE: get_bus_stops
####################################################################################################
@service(supports_response="only")
def get_bus_stops(bus_number, direction="both", at=None, return_response=True):
    """yaml
name: Get Bus Stops
description: All stops on the next upcoming trip of this bus
fields:
    bus_number:
        description: Bus route number
        example: "414"
        required: true
        selector:
            text:
    direction:
        description: Direction for the trip
        example: "both"
        default: "both"
        selector:
            select:
                options:
                  - both
                  - inbound
                  - outbound
    at:
        description: Reference time. 'HH:MM' rolls to tomorrow if past; 'YYYY-MM-DD HH:MM' for an exact moment. Defaults to now.
        example: "08:00"
        selector:
            text:
    """
    try:
        if not bus_number:
            return error_dict("bus_number is required")
        bus_number = str(bus_number).strip()
        if direction and direction not in VALID_DIRECTIONS:
            return error_dict(f"direction must be one of: {', '.join(VALID_DIRECTIONS)}")

        try:
            ref = resolve_reference_time(at)
        except ValueError as e:
            return error_dict(str(e))
        qry_date = ref.strftime("%Y-%m-%d")
        qry_time = ref.strftime("%H:%M")

        session = requests.Session()
        token = get_route_auth(session, bus_number)

        options, api_direction_raw = call_options_async(
            session, token, bus_number, qry_date, qry_time, max_options=1
        )
        if not options:
            return error_dict(f"No upcoming trips for bus {bus_number}")

        next_dep = options[0]
        trip_uid = next_dep.get("TripKey")
        route_uid = next_dep.get("RouteUid")
        if not trip_uid or not route_uid:
            return error_dict("Missing trip information in API response")

        api_direction = normalize_direction(api_direction_raw)
        trip_direction = api_direction if direction in (DIRECTION_BOTH, None) else direction

        trip_data = call_trip_async(session, token, route_uid, trip_uid, qry_date, trip_direction)

        # Direction fallback if empty data came back for "both"
        if not trip_data and direction in (DIRECTION_BOTH, None):
            opposite = DIRECTION_INBOUND if trip_direction == DIRECTION_OUTBOUND else DIRECTION_OUTBOUND
            trip_data = call_trip_async(session, token, route_uid, trip_uid, qry_date, opposite)

        result = {
            "result": "success",
            "bus_number": bus_number,
            "departure_time": _clock_12_to_24(next_dep.get("StartTime", "")),
            "arrival_time": _clock_12_to_24(next_dep.get("FinishTime", "")),
            "start_location": next_dep.get("StartLocation", ""),
            "finish_location": next_dep.get("FinishLocation", ""),
            "headsign": f"{bus_number} to {next_dep.get('FinishLocation', '')}",
            "direction": trip_direction,
            "reference_time": ref.isoformat(),
            "timestamp": datetime.now().isoformat(),
        }

        if not trip_data:
            result["stops"] = []
            result["total_stops"] = 0
            result["note"] = "Could not retrieve detailed stop information"
            return result

        stops = []
        for i, timing in enumerate(trip_data.get("TripStopTimings", []), 1):
            stop_info = timing.get("Stop", {}) or {}
            stops.append({
                "stop_number": i,
                "stop_name": stop_info.get("Description", ""),
                "stop_code": stop_info.get("Code", ""),
                "time": timing.get("DepartTime") or timing.get("ArrivalTime", ""),
                "zone": stop_info.get("Zone", ""),
                "can_board": timing.get("CanBoard", False),
                "can_alight": timing.get("CanAlight", False),
                "is_timing_point": timing.get("IsTimingPoint", False),
                "latitude": stop_info.get("Latitude", ""),
                "longitude": stop_info.get("Longitude", ""),
            })
        result["stops"] = stops
        result["total_stops"] = len(stops)
        result["headsign"] = trip_data.get("Headsign", result["headsign"])
        return result

    except RateLimitError:
        return rate_limit_error_dict()
    except NetworkError as e:
        return error_dict(str(e))
    except AuthError as e:
        return error_dict(f"Authentication failed: {e}")
    except Exception as e:
        log.error(f"get_bus_stops error: {e}")
        return error_dict(str(e))


def _clock_12_to_24(clock_string):
    """Convert '10:29 PM' → '22:29'. Pass through if already 24h or empty."""
    if not clock_string:
        return ""
    s = clock_string.strip()
    try:
        return datetime.strptime(s, "%I:%M %p").strftime("%H:%M")
    except ValueError:
        return s


####################################################################################################
# SERVICE: bus_times_health_check
####################################################################################################
@service(supports_response="only")
def bus_times_health_check(return_response=True):
    """yaml
name: Bus Times Health Check
description: Verify both auth contexts and both API families are reachable
    """
    result = {
        "result": "error",
        "route_auth_working": False,
        "stop_auth_working": False,
        "options_api_working": False,
        "stop_timetable_api_working": False,
        "timestamp": datetime.now().isoformat(),
    }
    now = datetime.now()
    session = requests.Session()

    try:
        # Route-context check
        try:
            route_token = get_route_auth(session, "209")
            result["route_auth_working"] = True
            options, _ = call_options_async(
                session, route_token, "209",
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), max_options=1
            )
            if options:
                result["options_api_working"] = True
        except RateLimitError:
            result["error"] = RATE_LIMIT_MESSAGE
            result["rate_limited"] = True
            return result
        except NetworkError as e:
            result["error"] = str(e)
            return result
        except AuthError as e:
            result["route_auth_error"] = str(e)

        # Stop-context check — use Perth Underground (stop 10351).
        # A successful call returning `trips` (even empty, e.g. middle of the night)
        # confirms the API is reachable; we don't require actual departures.
        try:
            trips, _ = call_stop_timetable(
                session, "10351",
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), max_trips=1
            )
            if trips is not None:
                result["stop_auth_working"] = True
                result["stop_timetable_api_working"] = True
        except RateLimitError:
            result["error"] = RATE_LIMIT_MESSAGE
            result["rate_limited"] = True
            return result
        except NetworkError as e:
            result["error"] = str(e)
            return result
        except AuthError as e:
            result["stop_auth_error"] = str(e)

        if result["options_api_working"] and result["stop_timetable_api_working"]:
            result["result"] = "success"

    except Exception as e:
        log.error(f"health check error: {e}")
        result["error"] = str(e)

    return result
