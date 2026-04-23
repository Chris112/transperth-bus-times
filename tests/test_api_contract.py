"""API contract tests — verify the live Transperth API still returns the fields our code reads.

If these fail, the Transperth API has changed and the service will break.
Run with: pytest tests/ -n auto
"""

import requests

from .conftest import BASE_URL, TEST_BUS, TEST_STOP


def _assert_keys(obj, keys, context):
    for key in keys:
        assert key in obj, f"{context}: missing key '{key}' — got {sorted(obj.keys())}"


def test_get_stop_timetable_async(session, stop_request_headers, tomorrow_midday):
    """GetStopTimetableAsync powers 5 of our 6 services. Verify its shape."""
    r = session.post(
        f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetStopTimetableAsync",
        headers=stop_request_headers,
        data={
            "StopNumber": TEST_STOP,
            "SearchDate": tomorrow_midday.strftime("%Y-%m-%d"),
            "SearchTime": tomorrow_midday.strftime("%H:%M"),
            "IsRealTimeChecked": "false",
            "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK",
            "MaxTripCount": "10",
        },
    )
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    body = r.json()

    assert body.get("result") == "success"
    _assert_keys(body, ["trips", "stop"], "GetStopTimetableAsync root")

    trips = body["trips"]
    assert isinstance(trips, list)
    assert trips, f"No trips returned for stop {TEST_STOP} at midday tomorrow"

    trip = trips[0]
    _assert_keys(trip, ["DepartTime", "ArriveTime", "Summary", "Origin", "Destination"], "trip")

    summary = trip["Summary"]
    _assert_keys(
        summary,
        ["RouteCode", "RouteUid", "TripUid", "Headsign", "Direction"],
        "trip.Summary",
    )

    # DepartTime should be ISO 8601 (YYYY-MM-DDTHH:MM)
    depart = trip["DepartTime"]
    assert isinstance(depart, str) and len(depart) >= 16 and depart[10] == "T", \
        f"DepartTime shape changed: {depart!r}"

    # stop metadata
    stop = body["stop"]
    _assert_keys(stop, ["Code", "Description"], "stop")
    assert stop["Code"] == TEST_STOP


def test_get_timetable_options_async(session, route_headers, tomorrow_midday):
    """GetTimetableOptionsAsync — used by get_bus_stops to find the next trip."""
    r = session.post(
        f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptionsAsync",
        headers=route_headers,
        data={
            "ExactlyMatchedRouteOnly": "true",
            "Mode": "bus",
            "Route": TEST_BUS,
            "QryDate": tomorrow_midday.strftime("%Y-%m-%d"),
            "QryTime": tomorrow_midday.strftime("%H:%M"),
            "MaxOptions": "2",
        },
    )
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    body = r.json()

    assert body.get("result") == "success"
    _assert_keys(body, ["data"], "GetTimetableOptionsAsync root")

    data = body["data"]
    _assert_keys(data, ["Direction", "Options"], "data")

    options = data["Options"]
    assert isinstance(options, list) and options

    opt = options[0]
    _assert_keys(
        opt,
        ["TripKey", "RouteUid", "StartTime", "FinishTime", "StartLocation", "FinishLocation"],
        "options[0]",
    )


def test_get_timetable_trip_async(session, route_headers, tomorrow_midday):
    """GetTimetableTripAsync — used by get_bus_stops to list all stops on a trip.

    Depends on the options endpoint — fetches a real TripKey first.
    """
    qry_date = tomorrow_midday.strftime("%Y-%m-%d")

    opts = session.post(
        f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableOptionsAsync",
        headers=route_headers,
        data={
            "ExactlyMatchedRouteOnly": "true",
            "Mode": "bus",
            "Route": TEST_BUS,
            "QryDate": qry_date,
            "QryTime": tomorrow_midday.strftime("%H:%M"),
            "MaxOptions": "1",
        },
    ).json()
    option = opts["data"]["Options"][0]
    direction = opts["data"]["Direction"]

    r = session.post(
        f"{BASE_URL}/API/SilverRailRestService/SilverRailService/GetTimetableTripAsync",
        headers=route_headers,
        data={
            "RouteUid": option["RouteUid"],
            "TripUid": option["TripKey"],
            "TripDate": qry_date,
            "TripDirection": direction,
            "ReturnNoteCodes": "DV,LM,CM,TC,BG,FG,LK",
        },
    )
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    body = r.json()

    assert body.get("result") == "success"
    data = body.get("data")
    assert data is not None, "Got null data — wrong direction, or API returned empty trip"

    _assert_keys(data, ["Headsign", "Direction", "TripStopTimings"], "trip data")

    stops = data["TripStopTimings"]
    assert isinstance(stops, list) and len(stops) > 1

    timing = stops[0]
    _assert_keys(timing, ["DepartTime", "ArrivalTime", "CanBoard", "CanAlight", "Stop"], "timing[0]")

    stop = timing["Stop"]
    _assert_keys(stop, ["Code", "Description", "Latitude", "Longitude", "Zone"], "stop")
