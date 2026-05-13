# Transperth Bus Times for Home Assistant

Live Perth bus departure times exposed as Home Assistant services. Built for "time to leave" automations, dashboard countdowns, and morning commute notifications.

This is a single-file PyScript service. If you've never used PyScript before, that's fine — the install walkthrough below covers it from scratch.

## What you get

Seven services you can call from any automation, script, or dashboard:

| Service | Purpose |
|---------|---------|
| `pyscript.get_next_bus` | The next bus at a stop, optionally filtered by route |
| `pyscript.get_leave_time` | Should I leave now? Accounts for walk time |
| `pyscript.get_bus_countdown` | Minutes until next bus as an integer — for template sensors |
| `pyscript.get_stop_departures` | Next N buses at a stop, across all routes |
| `pyscript.get_bus_schedule` | All upcoming times a specific bus stops at a stop |
| `pyscript.get_bus_stops` | All stops on a bus's next trip, with GPS coordinates |
| `pyscript.bus_times_health_check` | Verifies the integration can reach Transperth |

Full reference and examples for each are in [Service reference](#service-reference) below.

## Install

### 1. Install PyScript via HACS

PyScript lets you run Python files inside Home Assistant. You need it installed before this integration will work.

1. Open HACS in Home Assistant.
2. **Integrations** → **Explore & Download Repositories**.
3. Search for **PyScript**, click **Download** (latest version).
4. Restart Home Assistant.
5. **Settings** → **Devices & Services** → **Add Integration**.
6. Search for **PyScript**, click it, leave **Allow all imports** checked, click **Submit**.

### 2. Add the bus times file

1. Download [`src/bus_times.py`](src/bus_times.py) from this repo.
2. Place it at `config/pyscript/bus_times.py` in your Home Assistant config directory:

   ```
   config/
   └── pyscript/
       └── bus_times.py
   ```

3. Reload PyScript: **Developer Tools** → **Services** → call `pyscript.reload`.

### 3. Verify

In **Developer Tools** → **Services**, call `pyscript.bus_times_health_check`. A healthy install returns:

```yaml
result: success
route_auth_working: true
stop_auth_working: true
options_api_working: true
stop_timetable_api_working: true
```

Then try a real query — `pyscript.get_next_bus` with `stop_code: "12627"` and `bus_number: "414"` should return the next 414.

## Service reference

All services return a dict with `result: success` or `result: error`. Successful responses include a `timestamp`. Errors include an `error` message; rate-limit errors also include `rate_limited: true`.

### Common: the `at` parameter

Every service accepts an optional `at` for testing or planning ahead:

- `"HH:MM"` — the **next** occurrence of that time (today if upcoming, tomorrow if past).
- `"YYYY-MM-DD HH:MM"` — any specific moment, no rollover.
- Omit it to use the current time.

### `pyscript.get_next_bus`

The next bus at a stop, optionally filtered by route.

```yaml
service: pyscript.get_next_bus
data:
  stop_code: "12627"
  bus_number: "414"   # optional — omit for any next bus
```

Returns: `departure_time`, `minutes_until`, `bus_number`, `headsign`, `destination`.

### `pyscript.get_leave_time`

Is it time to leave for the bus? Accounts for walk time to the stop.

```yaml
service: pyscript.get_leave_time
data:
  stop_code: "12627"
  bus_number: "414"
  walk_minutes: 5
```

Returns: `is_time_to_leave` (bool), `minutes_until_leave`, `minutes_until_bus`, `departure_time`.

### `pyscript.get_bus_countdown`

Integer minutes until the next specified bus. Designed for template sensors.

```yaml
service: pyscript.get_bus_countdown
data:
  stop_code: "12627"
  bus_number: "414"
```

Returns: `minutes` — an integer, or `-1` when no bus is coming.

### `pyscript.get_stop_departures`

Next N buses at a stop, across all routes.

```yaml
service: pyscript.get_stop_departures
data:
  stop_code: "12627"
  count: 5   # optional, default 5, max 20
```

Returns: `departures[]` with `bus_number`, `departure_time`, `minutes_until`, `headsign`, `destination`.

### `pyscript.get_bus_schedule`

All upcoming times a specific bus stops at a stop.

```yaml
service: pyscript.get_bus_schedule
data:
  bus_number: "414"
  stop_code: "12627"
```

Returns: `times[]` with `departure_time`, `minutes_until`, `headsign`, `destination`.

### `pyscript.get_bus_stops`

All stops on a bus's next upcoming trip.

```yaml
service: pyscript.get_bus_stops
data:
  bus_number: "414"
  direction: "both"   # optional: both (default), inbound, outbound
```

Returns the full journey with all stops, times, and GPS coordinates.

### `pyscript.bus_times_health_check`

Verifies both API auth contexts the integration uses are reachable. Useful for diagnosing setup issues.

```yaml
service: pyscript.bus_times_health_check
```

Returns status flags for route auth, stop auth, the options API, and the stop-timetable API.

## Example automation

Morning commute reminder — checks every minute between 07:15 and 08:30, notifies your phone when it's time to leave for the 414:

```yaml
automation:
  - alias: "Time to leave for the 414"
    trigger:
      - platform: time_pattern
        minutes: "/1"
    condition:
      - condition: time
        after: "07:15:00"
        before: "08:30:00"
    action:
      - service: pyscript.get_leave_time
        data:
          stop_code: "12627"
          bus_number: "414"
          walk_minutes: 5
        response_variable: check
      - if: "{{ check.is_time_to_leave }}"
        then:
          - service: notify.mobile_app_your_phone
            data:
              title: "Leave now!"
              message: >
                414 to {{ check.headsign }} departs at {{ check.departure_time }}
                ({{ check.minutes_until_bus }} min).
```

## Finding stop codes

Stop codes are the numbers printed on the physical bus stop sign. You can also look them up on the [Transperth website](https://www.transperth.wa.gov.au) — click any stop in the journey planner to see its code.

## Troubleshooting

**Services don't appear in Developer Tools.**
Check PyScript is connected: **Settings** → **Devices & Services**. Confirm the file is at `config/pyscript/bus_times.py`. Call `pyscript.reload`. If still missing, check **Settings** → **System** → **Logs** for `pyscript` errors.

**No bus data returned.**
Verify the bus number is just the route digits (`"414"`, not `"Bus 414"`). Verify the stop code exactly matches the sign. Call `pyscript.bus_times_health_check` to confirm the integration can reach Transperth.

**Wrong direction.**
For `get_bus_stops`, set `direction: "both"` to let it auto-detect. Some routes only run one direction at certain times.

**Works once, then errors (rate limiting).**
Responses include `rate_limited: true` and an HTTP 429 message. The Transperth cooldown is well over a minute and is shared with the Transperth website itself, so browsing the timetable while automations run can contribute. Reduce automation frequency to a few calls per minute at most.

## For developers

### Project layout

```
transperth-bus-times/
├── src/bus_times.py        # The PyScript service — this is what gets deployed
├── tests/                  # Contract tests against the live Transperth API
├── docs/                   # API documentation and full endpoint reference
├── pyproject.toml          # Pytest configuration
└── requirements-dev.txt    # Test dependencies
```

### Running the tests

The tests hit the **live** Transperth API to catch schema drift. Don't run them in tight loops — the 429 cooldown is sticky.

```bash
pip install -r requirements-dev.txt
pytest tests/ -n auto
```

A failure usually means Transperth changed their response shape and the affected service is broken in production.

### How it works

Transperth has no public API. The integration scrapes CSRF tokens from two public pages (the route timetable page and the stop page — each page issues tokens scoped to a different API surface), then calls the same internal endpoints Transperth's own website uses:

- `GetStopTimetableAsync` — one request returns all upcoming buses at a stop. Used by five of the six services.
- `GetTimetableOptionsAsync` + `GetTimetableTripAsync` — route-centric pair used by `get_bus_stops`.

HTTP 429 rate limits are caught explicitly and surfaced via `rate_limited: true` so callers can back off.

See [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) for the architecture overview and [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for full request/response details.

## Disclaimer

Unofficial. Uses Transperth's public website API, which can change or stop working without notice. Be respectful of their infrastructure — don't hammer it.
