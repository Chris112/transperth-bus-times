# Transperth Bus API Documentation

This document describes the undocumented Transperth API endpoints used to fetch real-time bus data. These are the same endpoints the official Transperth website uses.

## Overview

The Transperth bus system uses a SilverRail API backend. To access it, you need:
1. A session cookie from the website
2. A CSRF token extracted from the HTML
3. Specific headers including ModuleId and TabId

## Authentication Flow

### Step 1: Get Session and Token

**Request:**
```
GET https://www.transperth.wa.gov.au/timetables/details?Bus={bus_number}
```

**Example:**
```bash
curl 'https://www.transperth.wa.gov.au/timetables/details?Bus=209'
```

**What to extract from HTML response:**
Look for this hidden input field in the HTML:
```html
<input name="__RequestVerificationToken" type="hidden" value="CfDJ8NWxs...long_token_here..." />
```

You'll also get session cookies that need to be maintained for subsequent requests.

## API Endpoints

### 1. GetTimetableOptions - Get Bus Departures

Gets the next departures for a specific bus route.

**Endpoint:**
```
POST https://www.transperth.wa.gov.au/API/SilverRailRestService/SilverRailService/GetTimetableOptions
```

**Required Headers:**
```
RequestVerificationToken: {token_from_html}
ModuleId: 5345
TabId: 133
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
```

**Request Body (form-encoded):**
```
ExactlyMatchedRouteOnly=true
Mode=bus
Route=209
QryDate=2025-01-06
QryTime=14:30
MaxOptions=5
```

**Parameters:**
- `Route`: Bus number (e.g., "209", "950")
- `QryDate`: Date in YYYY-MM-DD format
- `QryTime`: Time in HH:MM format (24-hour)
- `MaxOptions`: How many departures to return (1-10 typically)

**Example Response:**
```json
{
  "result": "success",
  "data": {
    "Direction": "0",
    "Options": [
      {
        "TripKey": "BUS:209:1:14:45:MON-FRI",
        "RouteUid": "BUS:209",
        "StartTime": "14:45",
        "FinishTime": "15:23",
        "StartLocation": "Mirrabooka Bus Stn",
        "FinishLocation": "Warwick Stn",
        "Duration": 38,
        "RouteNumber": "209",
        "ServiceName": "209"
      }
    ]
  }
}
```

**Response Fields:**
- `Direction`: "0" for outbound, "1" for inbound
- `TripKey`: Unique identifier for this specific trip
- `RouteUid`: Route identifier
- `StartTime`: Departure time from first stop
- `FinishTime`: Arrival time at last stop
- `StartLocation`: First stop name
- `FinishLocation`: Last stop name
- `Duration`: Journey time in minutes

### 2. GetTimetableTrip - Get Full Journey Details

Gets all stops and times for a specific bus trip.

**Endpoint:**
```
POST https://www.transperth.wa.gov.au/API/SilverRailRestService/SilverRailService/GetTimetableTrip
```

**Required Headers:**
Same as GetTimetableOptions

**Request Body (form-encoded):**
```
RouteUid=BUS:209
TripUid=BUS:209:1:14:45:MON-FRI
TripDate=2025-01-06
TripDirection=outbound
ReturnNoteCodes=DV,LM,CM,TC,BG,FG,LK
```

**Parameters:**
- `RouteUid`: From GetTimetableOptions response
- `TripUid`: The TripKey from GetTimetableOptions
- `TripDate`: Date in YYYY-MM-DD format
- `TripDirection`: "inbound" or "outbound" (critical - wrong value returns empty data!)
- `ReturnNoteCodes`: Comma-separated note codes (optional)

**Example Response:**
```json
{
  "result": "success",
  "data": {
    "Headsign": "209 to Warwick Stn",
    "Direction": "outbound",
    "TripStopTimings": [
      {
        "Stop": {
          "Code": "21940",
          "Description": "Mirrabooka Bus Stn Platform 4",
          "Zone": "2",
          "Latitude": -31.863889,
          "Longitude": 115.863056
        },
        "ArrivalTime": null,
        "DepartTime": "14:45",
        "CanBoard": true,
        "CanAlight": false,
        "IsTimingPoint": true
      },
      {
        "Stop": {
          "Code": "10858",
          "Description": "Reid Hwy After Mirrabooka Av",
          "Zone": "2",
          "Latitude": -31.860278,
          "Longitude": 115.862778
        },
        "ArrivalTime": "14:47",
        "DepartTime": "14:47",
        "CanBoard": true,
        "CanAlight": true,
        "IsTimingPoint": false
      }
    ]
  }
}
```

**Response Fields:**
- `Headsign`: What's displayed on the front of the bus
- `Direction`: Travel direction
- `TripStopTimings`: Array of all stops
  - `Stop.Code`: Unique stop identifier (what's on the stop sign)
  - `Stop.Description`: Full stop name
  - `Stop.Zone`: Fare zone (1-9)
  - `Stop.Latitude/Longitude`: GPS coordinates
  - `ArrivalTime`: When bus arrives (null for first stop)
  - `DepartTime`: When bus departs (null for last stop)
  - `CanBoard`: Can passengers get on here?
  - `CanAlight`: Can passengers get off here?
  - `IsTimingPoint`: Does bus wait here if early?

## Important Notes

### Direction Parameter
The `TripDirection` parameter is **critical**. If you use the wrong direction, the API returns `{"result": "success", "data": null}`. 

Common values:
- Outbound: "outbound", "0"
- Inbound: "inbound", "1"

The API can be inconsistent - sometimes the GetTimetableOptions says Direction="0" but you need to use "inbound" for GetTimetableTrip to work. When in doubt, try both.

### Authentication Tokens
- Tokens expire after some time (appears to be session-based)
- Each token is tied to a session cookie
- You need to maintain cookies between requests

### Rate Limiting
No obvious rate limiting, but be respectful - this is Transperth's production API.

### Error Responses

**Invalid token or expired session:**
```json
{
  "result": "error",
  "message": "Unauthorized"
}
```

**Invalid bus number:**
```json
{
  "result": "success",
  "data": {
    "Options": []
  }
}
```

**Wrong direction (common issue):**
```json
{
  "result": "success",
  "data": null
}
```

## Example Python Implementation

```python
import requests
import re
from datetime import datetime

# Step 1: Get session and token
session = requests.Session()
auth_response = session.get('https://www.transperth.wa.gov.au/timetables/details?Bus=209')

# Extract token from HTML
token_match = re.search(r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', auth_response.text)
token = token_match.group(1)

# Step 2: Get bus times
headers = {
    'RequestVerificationToken': token,
    'ModuleId': '5345',
    'TabId': '133',
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-Requested-With': 'XMLHttpRequest'
}

data = {
    'ExactlyMatchedRouteOnly': 'true',
    'Mode': 'bus',
    'Route': '209',
    'QryDate': datetime.now().strftime('%Y-%m-%d'),
    'QryTime': datetime.now().strftime('%H:%M'),
    'MaxOptions': '1'
}

response = session.post(
    'https://www.transperth.wa.gov.au/API/SilverRailRestService/SilverRailService/GetTimetableOptions',
    headers=headers,
    data=data
)

print(response.json())
```

## Discovered Limitations

1. No real-time delay information - only scheduled times
2. No accessibility information beyond basic boarding/alighting
3. No fare information in the API
4. No service alerts or disruptions
5. Historical data not available

## Legal Note

This API is not officially documented or supported by Transperth. Use at your own risk and be respectful of their infrastructure.