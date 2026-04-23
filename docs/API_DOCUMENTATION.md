# Transperth API — Overview

This project calls Transperth's public website API (the same endpoints the Transperth site uses in the browser). These aren't officially documented — we reverse-engineered them from network traces.

For full request/response details see **[API_REFERENCE.md](API_REFERENCE.md)**.

## What we actually use

Three endpoints power all six services:

| Endpoint | Used by |
|----------|---------|
| `GetStopTimetableAsync` | `get_next_bus`, `get_leave_time`, `get_bus_countdown`, `get_stop_departures`, `get_bus_schedule` |
| `GetTimetableOptionsAsync` | `get_bus_stops` (to find the next upcoming trip) |
| `GetTimetableTripAsync` | `get_bus_stops` (to get the full stop list for that trip) |

Most services make **one** API call per invocation (plus one auth page fetch). `get_bus_stops` makes two.

## Authentication

Every API call needs a CSRF token. Tokens are **scoped to the page that issued them**:

| Auth context | Page to fetch | Used for |
|--------------|---------------|----------|
| Route | `/timetables/details?Bus={n}` | `GetTimetableOptionsAsync`, `GetTimetableTripAsync` |
| Stop | `/Journey-Planner/Stops-Near-You?locationtype=stop&location={code}` | `GetStopTimetableAsync` |

Using the wrong token returns HTTP 401. The two contexts also use different `ModuleId` and `TabId` header values. See API_REFERENCE.md for the exact headers.

## Rate limiting

Transperth returns **HTTP 429 Too Many Requests** (plain text, not JSON) when rate-limited. Key behaviours:

- Triggered by rapid successive API calls (e.g. looping through many trips)
- No `Retry-After` header
- Cooldown is sticky — observed >60 seconds
- Once limited, **every** subsequent request is blocked until the window clears
- Affects the Transperth website too — if you hit it, browsing transperth.wa.gov.au shows "Uh-oh, something broke"

Our service detects 429s and returns `rate_limited: true` in its error response. Under normal automation use we don't hit it — each service call makes only 1–2 HTTP requests.

## Data shape

- Scheduled times only (not real-time vehicle position)
- Stop codes match the physical signage
- No fare info, no service alerts, no historical data in the responses

## Known limitations

1. No real-time delay information — only scheduled times
2. No fare information
3. No service alerts / disruptions (may live in `GetTripInfoAsync`, not yet explored)
4. No historical data

## Legal note

This API is not officially documented or supported by Transperth. Use at your own risk and be respectful of their infrastructure — this tool makes one or two HTTP requests per service call and is not designed for polling.
