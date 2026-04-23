# Transperth API — Reference

Detailed request/response documentation for the three endpoints our service uses. For the high-level overview and rationale, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

## Authentication

Tokens are scoped to the page that issued them. Fetch the right page for the endpoint you're about to call.

### Route auth context

Used for: `GetTimetableOptionsAsync`, `GetTimetableTripAsync`.

**Fetch:**
```
GET https://www.transperth.wa.gov.au/timetables/details?Bus={bus_number}
```

**Headers on subsequent API calls:**
```
RequestVerificationToken: <token from this page>
ModuleId: 5345
TabId: 133
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
```

### Stop auth context

Used for: `GetStopTimetableAsync`.

**Fetch:**
```
GET https://www.transperth.wa.gov.au/Journey-Planner/Stops-Near-You?locationtype=stop&location={stop_code}
```

**Headers on subsequent API calls:**
```
RequestVerificationToken: <token from this page>
ModuleId: 5310
TabId: 141
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
Referer: https://www.transperth.wa.gov.au/Journey-Planner/Stops-Near-You?locationtype=stop&location={stop_code}
Origin: https://www.transperth.wa.gov.au
```

### Extracting the token

Both pages contain the token as a hidden input:

```html
<input name="__RequestVerificationToken" type="hidden" value="CfDJ8NWxs..." />
```

A single `requests.Session()` can safely share cookies across both contexts — only the token and module/tab headers need to differ.

---

## `GetStopTimetableAsync`

Returns the next N upcoming buses at a stop, across all routes. Powers most of our services.

**Endpoint:**
```
POST https://www.transperth.wa.gov.au/API/SilverRailRestService/SilverRailService/GetStopTimetableAsync
```

**Auth context:** Stop.

**Request body (form-encoded):**
```
StopNumber=12627
SearchDate=2026-04-23
SearchTime=13:00
IsRealTimeChecked=false
ReturnNoteCodes=DV,LM,CM,TC,BG,FG,LK
MaxTripCount=8
```

**Parameters:**
- `StopNumber`: Stop code (the number on the stop sign)
- `SearchDate`: Date, `YYYY-MM-DD`
- `SearchTime`: Time, `HH:MM` (24-hour). Returns buses from this time onward.
- `IsRealTimeChecked`: Whether to include live vehicle tracking (we pass `false`)
- `MaxTripCount`: Maximum trips to return
- `ReturnNoteCodes`: Comma-separated note codes

**Example response (truncated to 2 trips):**
```json
{
  "result": "success",
  "trips": [
    {
      "ArriveTime": "2026-04-23T13:15",
      "DepartTime": "2026-04-23T13:15",
      "StopTimetableStop": {
        "Code": "12627",
        "Name": "Main St After Royal St",
        "StopUid": "PerthRestricted:12627"
      },
      "Summary": {
        "Mode": "Bus",
        "Direction": "0",
        "TripUid": "PerthRestricted:6974136",
        "TripSourceId": "6974136",
        "TripStartTime": "2026-04-23T13:07",
        "RouteCode": "402",
        "RouteUid": "PerthRestricted:SWA-MAR-2497",
        "Headsign": "Perth Busport",
        "NoteIds": [1, 2, 3, 4]
      },
      "IsTimingPoint": true,
      "Origin": {
        "Code": "11538",
        "Name": "Stirling Stn Stand 2",
        "ParentName": "Stirling Stn"
      },
      "Destination": {
        "Code": "27172",
        "Name": "Perth Busport Zone B",
        "ParentName": "Perth Busport"
      },
      "SequenceNumber": "13",
      "IsRealTime": false,
      "DisplayRouteCode": "402",
      "DisplayTripTitle": "To Perth Busport",
      "DisplayTripStatus": "1:15pm",
      "RealTimeStopStatus": -1,
      "RealTimeStopStatusDetail": "Not Available"
    },
    {
      "ArriveTime": "2026-04-23T13:19",
      "DepartTime": "2026-04-23T13:19",
      "Summary": {
        "RouteCode": "414",
        "RouteUid": "PerthRestricted:SWA-MAR-2504",
        "Headsign": "Glendalough Stn",
        "TripUid": "PerthRestricted:6423558"
      },
      "DisplayTripStatus": "1:19pm"
    }
  ],
  "stop": {
    "Code": "12627",
    "Description": "Main St After Royal St",
    "Position": "-31.897121, 115.828359",
    "Routes": "PerthRestricted:SWA-MAR-2471;PerthRestricted:SWA-MAR-2497;PerthRestricted:SWA-MAR-2504",
    "Zone": "1"
  }
}
```

**Key response fields:**
- `trips[]`: Upcoming departures, sorted by time
  - `ArriveTime` / `DepartTime`: ISO 8601 (date + time, Australia/Perth local)
  - `Summary.RouteCode`: Bus number (filter on this for single-route queries)
  - `Summary.TripUid`: Trip identifier for drill-through
  - `Summary.Headsign`: Destination display on the bus
  - `Summary.Direction`: `"0"` outbound / `"1"` inbound
  - `Origin` / `Destination`: Trip endpoints
  - `IsRealTime`: Live tracking available (observed always `false`)
  - `DisplayRouteCode` / `DisplayTripTitle` / `DisplayTripStatus`: Pre-formatted display strings
- `stop`: Metadata for the queried stop (includes `Routes` — all routes serving it)

---

## `GetTimetableOptionsAsync`

Returns upcoming trips for a specific bus route.

**Endpoint:**
```
POST https://www.transperth.wa.gov.au/API/SilverRailRestService/SilverRailService/GetTimetableOptionsAsync
```

**Auth context:** Route.

**Request body (form-encoded):**
```
ExactlyMatchedRouteOnly=true
Mode=bus
Route=414
QryDate=2026-04-22
QryTime=22:34
MaxOptions=4
```

**Parameters:**
- `Route`: Bus number (e.g. `"414"`, `"209"`)
- `QryDate`: Date, `YYYY-MM-DD`
- `QryTime`: Time, `HH:MM` (24-hour)
- `MaxOptions`: How many upcoming trips to return
- `ExactlyMatchedRouteOnly=true` + `Mode=bus`: always included; restricts to exact route matches

Optional fields the website sends but we don't need: `Key` (timetable series id), `RouteUid` (pre-resolves a route).

**Example response:**
```json
{
  "result": "success",
  "data": {
    "TransportMode": "bus",
    "Direction": "outbound",
    "Options": [
      {
        "Index": 1,
        "StartStopNo": 29720,
        "StartLocation": "Stirling Stn Stand B",
        "StartTime": "11:08 PM",
        "IsStartNextDay": false,
        "FinishStopNo": 27117,
        "FinishTime": "11:27 PM",
        "IsFinishNextDay": false,
        "FinishLocation": "Scarborough Beach Rd Stand 8",
        "RouteUid": "PerthRestricted:SWA-MAR-2504",
        "TripKey": "PerthRestricted:6423575",
        "TripVehicle": null
      }
    ]
  }
}
```

**Key response fields:**
- `data.Direction`: `"outbound"` or `"inbound"` (note: string, not `"0"`/`"1"` like some other endpoints)
- `data.Options[]`: Upcoming trips
  - `TripKey`: Trip identifier — feed into `GetTimetableTripAsync`
  - `RouteUid`: Route identifier — feed into `GetTimetableTripAsync`
  - `StartTime` / `FinishTime`: 12-hour strings (e.g. `"11:08 PM"`)
  - `StartStopNo` / `FinishStopNo`: Stop codes for start and end
  - `StartLocation` / `FinishLocation`: Human-readable endpoint names
  - `IsStartNextDay` / `IsFinishNextDay`: True if the time rolls past midnight

---

## `GetTimetableTripAsync`

Returns every stop on a specific trip, with times.

**Endpoint:**
```
POST https://www.transperth.wa.gov.au/API/SilverRailRestService/SilverRailService/GetTimetableTripAsync
```

**Auth context:** Route.

**Request body (form-encoded):**
```
RouteUid=PerthRestricted:SWA-MAR-2504
TripUid=PerthRestricted:6423575
TripDate=2026-04-22
TripDirection=outbound
ReturnNoteCodes=DV,LM,CM,TC,BG,FG,LK
```

**Parameters:**
- `RouteUid`: From `GetTimetableOptionsAsync.data.Options[].RouteUid`
- `TripUid`: From `GetTimetableOptionsAsync.data.Options[].TripKey`
- `TripDate`: Date, `YYYY-MM-DD`
- `TripDirection`: `"outbound"` or `"inbound"` — **critical**, wrong value returns `{"result": "success", "data": null}`
- `ReturnNoteCodes`: Comma-separated note codes

### Direction quirk

The value you pass in `TripDirection` must match the trip's actual direction. If the `GetTimetableOptionsAsync` response had `"Direction": "outbound"`, pass `"outbound"`. When the options endpoint returns a null response for one direction, try the other (our code does this automatically for `direction: "both"`).

**Example response (truncated — real payload lists every stop, often 20-50):**
```json
{
  "result": "success",
  "data": {
    "TripUid": "PerthRestricted:6423575",
    "TripSourceId": "6423575",
    "Direction": "0",
    "Headsign": "Glendalough Stn",
    "RouteUid": "PerthRestricted:SWA-MAR-2504",
    "TripStopTimings": [
      {
        "ArrivalTime": "",
        "DepartTime": "23:08",
        "CanAlight": false,
        "CanBoard": true,
        "MustRequestStop": false,
        "IsTimingPoint": true,
        "Stop": {
          "Code": "29720",
          "Description": "Stirling Stn Stand B",
          "ParentName": "Stirling Stn",
          "ParentUid": "PerthRestricted:98",
          "Position": "-31.893531, 115.805214",
          "Latitude": "-31.893531",
          "Longitude": "115.805214",
          "Routes": "PerthRestricted:SWA-MAR-2504;PerthRestricted:SWA-MAR-2569",
          "StopUid": "PerthRestricted:29720",
          "SupportedModes": "Bus",
          "WheelchairAccessible": 0,
          "Zone": "2"
        }
      },
      {
        "ArrivalTime": "23:19",
        "DepartTime": "23:19",
        "CanAlight": true,
        "CanBoard": true,
        "MustRequestStop": false,
        "IsTimingPoint": false,
        "Stop": {
          "Code": "12628",
          "Description": "Main St After Lawley St",
          "Latitude": "-31.901233",
          "Longitude": "115.82839",
          "Zone": "1"
        }
      },
      {
        "ArrivalTime": "23:27",
        "DepartTime": "",
        "CanAlight": true,
        "CanBoard": false,
        "Stop": {
          "Code": "27117",
          "Description": "Scarborough Beach Rd Stand 8"
        }
      }
    ],
    "NoteIds": [5, 2, 4]
  }
}
```

**Key response fields:**
- `data.Headsign`: What's displayed on the front of the bus
- `data.Direction`: `"0"` outbound / `"1"` inbound (note: opposite convention to `GetTimetableOptionsAsync`!)
- `data.TripStopTimings[]`: All stops, in order
  - `ArrivalTime` / `DepartTime`: `HH:MM` strings. Empty string (not null) at terminals.
  - `CanBoard` / `CanAlight`: Whether passengers can get on/off here
  - `IsTimingPoint`: Whether the bus waits here if early
  - `MustRequestStop`: Whether passengers must flag the bus
  - `Stop.Code`: Stop code (matches the physical sign)
  - `Stop.Description`: Human name
  - `Stop.Latitude` / `Stop.Longitude`: GPS (note: strings, not numbers)
  - `Stop.Zone`: Fare zone (1-9)
  - `Stop.Routes`: Semicolon-separated list of all routes serving this stop

---

## Error responses

**Rate limited (HTTP 429):**
```
HTTP/1.1 429 Too Many Requests
Content-Type: text/plain

Too Many Requests
```
Plain text body — do not attempt `.json()` before checking the status code.

**Unauthorized (wrong auth context, HTTP 401):**
```json
{"Message": "Authorization has been denied for this request."}
```

**Wrong direction for `GetTimetableTripAsync` (HTTP 200):**
```json
{"result": "success", "data": null}
```

**Invalid bus number for `GetTimetableOptionsAsync` (HTTP 200):**
```json
{"result": "success", "data": {"Options": []}}
```

## Other endpoints (not used)

These exist on the Transperth site but we don't currently call them. Listed here so future developers know not to rediscover them:

- **`GetTimetableOptions` / `GetTimetableTrip`** — older non-Async variants. Superseded by the Async endpoints above.
- **`GetTripAsync`** — returns a map polyline only. Useless for timetable queries.
- **`GetTripInfoAsync`** (under `/API/PTA_Common/Trip/`) — tiny payload with `Status`, `RealTime`, `Interruptions`. Potentially useful for service-alert functionality we haven't built.
- **`GetTimetablePdfsAsync`** (under `/API/PTA_Common/Tris/`) — metadata for printable PDF timetables.
- **`GetLocationAsync`** (under `/API/PTA_Common/Location/`) — resolves stop descriptions to structured info. Not needed since we take stop codes directly.
