# 🚌 Transperth Bus Times for Home Assistant

Perth public transport timetables in your Home Assistant dashboard. Get scheduled bus departure times, stop information, and journey details from Transperth directly in your smart home — perfect for "time to leave for the bus" automations.

## 🚀 Getting Started

### Prerequisites
- Home Assistant with HACS installed

### Step 1: Install PyScript via HACS

1. Open HACS in your Home Assistant
2. Click **Integrations** → **Explore & Download Repositories**
3. Search for **"PyScript"**
4. Click **Download** → **Download** (use latest version)
5. Restart Home Assistant
6. Go to **Settings** → **Devices & Services** → **Add Integration**
7. Search for **"PyScript"** and click it
8. Click **Submit** (keep "Allow all imports" checked)

### Step 2: Install the Bus Times Service

1. Download `src/bus_times.py` from this repository.

2. Drop it at `config/pyscript/bus_times.py` in your Home Assistant config:
   ```
   config/
   └── pyscript/
       └── bus_times.py
   ```

### Step 3: Test It Works

1. Go to **Developer Tools** → **Services**
2. Search for `pyscript.bus_times_health_check` and click **Call Service**. You should see `result: "success"` with all four `*_working` flags `true`.
3. For a real query, try `pyscript.get_next_bus` with:
   ```yaml
   stop_code: "12627"    # Main St After Lawley St — route 414 stops here
   bus_number: "414"
   ```
   You should see the next upcoming 414 at that stop.


## 📖 Available Services

Six services covering countdown sensors, "time to leave" decisions, stop departure boards, and full route listings. Plus a health check.

### Common parameters and response fields

All services below support an optional **`at`** parameter for testing or planning ahead:
- `"HH:MM"` — the **next** occurrence of that time (today if still upcoming, tomorrow if already past)
- `"YYYY-MM-DD HH:MM"` — any specific moment (no rollover)
- Omit to use the current time

All successful responses include `result: "success"` plus a `timestamp`. Errors return `result: "error"` with an `error` message, and rate-limit errors include `rate_limited: true`.

### `pyscript.get_next_bus`
The next bus at a stop, optionally filtered by route.

```yaml
service: pyscript.get_next_bus
data:
  stop_code: "12627"
  bus_number: "414"   # optional - omit for the very next bus, any route
```

**Returns:** `departure_time`, `minutes_until`, `bus_number`, `headsign`, `destination`

### `pyscript.get_leave_time`
Is it time to leave for the bus? Accounts for walk time to the stop.

```yaml
service: pyscript.get_leave_time
data:
  stop_code: "12627"
  bus_number: "414"
  walk_minutes: 5
```

**Returns:** `is_time_to_leave` (bool), `minutes_until_leave`, `minutes_until_bus`, `departure_time`

### `pyscript.get_bus_countdown`
Integer minutes until the next specified bus. Designed for template sensors.

```yaml
service: pyscript.get_bus_countdown
data:
  stop_code: "12627"
  bus_number: "414"
```

**Returns:** `{ "result": "success", "minutes": 12 }` — returns `minutes: -1` when no bus is coming.

### `pyscript.get_stop_departures`
Next N buses at a stop, across all routes.

```yaml
service: pyscript.get_stop_departures
data:
  stop_code: "12627"
  count: 5   # optional, default 5, max 20
```

**Returns:** `departures[]` with `bus_number`, `departure_time`, `minutes_until`, `headsign`, `destination`

### `pyscript.get_bus_schedule`
All upcoming times a bus stops at a stop. Defaults to now; pass `at` to query another time.

```yaml
service: pyscript.get_bus_schedule
data:
  bus_number: "414"
  stop_code: "12627"
```

**Returns:** `times[]` with `departure_time`, `minutes_until`, `headsign`, `destination`

### `pyscript.get_bus_stops`
All stops on a bus's next upcoming trip.

```yaml
service: pyscript.get_bus_stops
data:
  bus_number: "414"
  direction: "both"   # optional: both (default), inbound, outbound
```

**Returns:** Complete journey with all stops, times, and GPS coordinates

### `pyscript.bus_times_health_check`
Verifies both API auth contexts are working.

```yaml
service: pyscript.bus_times_health_check
```

**Returns:** Status flags for route auth, stop auth, options API, and stop-timetable API

## 🏠 Home Assistant Automations

### Morning Commute Reminder
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
              title: "🚌 Leave now!"
              message: >
                414 to {{ check.headsign }} departs at {{ check.departure_time }}
                ({{ check.minutes_until_bus }} min).
```


## 🔍 Finding Stop Codes

Stop codes are the numbers on the physical bus stop sign. You can also find them on the [Transperth website](https://www.transperth.wa.gov.au) — click any stop on the journey planner to see its code.

## 🛠️ Troubleshooting

### Services Not Appearing
- **Check PyScript is running:** Settings → Devices & Services → PyScript should show "Connected"
- **Check the file location:** Must be in `config/pyscript/bus_times.py`
- **Check logs:** Settings → System → Logs → Search for "pyscript"
- **Reload PyScript:** Developer Tools → Services → `pyscript.reload`

### No Bus Data Returned
- **Check bus number:** Ensure it's a valid Transperth route (e.g., "950", "209", not "Bus950")
- **Check stop code:** Must be the exact number from the stop sign
- **Run health check:** Call `pyscript.bus_times_health_check` service
- **API might be down:** Check if [transperth.wa.gov.au](https://www.transperth.wa.gov.au) is working

### Wrong Direction Data
- Try setting `direction: "both"` to automatically detect the correct direction
- Some routes only run in one direction at certain times

### Works First Time, Fails After (Rate Limiting)
If a service works the first time but then returns errors (or the Transperth website shows "Uh-oh, something broke"), you've hit Transperth's rate limit.

- Responses will include `rate_limited: true` and an error mentioning HTTP 429
- **Wait a few minutes** before retrying — the cooldown can last well over a minute
- **Reduce automation frequency** — don't call these services more than a few times per minute
- The rate limiter is shared with the Transperth website, so browsing the timetable while automations run can contribute


## 📚 References

- **PyScript Documentation:** [hacs-pyscript.readthedocs.io](https://hacs-pyscript.readthedocs.io/)
- **PyScript GitHub:** [github.com/custom-components/pyscript](https://github.com/custom-components/pyscript)
- **Transperth Website:** [transperth.wa.gov.au](https://www.transperth.wa.gov.au)
- **Home Assistant Services:** [home-assistant.io/docs/scripts/service-calls](https://www.home-assistant.io/docs/scripts/service-calls/)
- **HACS Documentation:** [hacs.xyz](https://hacs.xyz/)
- **API Overview:** [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) - What endpoints we use and why
- **API Reference:** [docs/API_REFERENCE.md](docs/API_REFERENCE.md) - Full request/response details

## 🔧 For Developers

### Project Structure
```
transperth-bus-times/
├── src/
│   └── bus_times.py         # The PyScript service (copy this to HA)
├── tests/                   # API contract tests — catch Transperth API changes
├── docs/                    # API documentation and reference
├── pyproject.toml           # Pytest configuration
└── requirements-dev.txt     # Testing dependencies
```

### Running the API contract tests
These tests hit the live Transperth API to verify the response schemas our code depends on. Run them after any Transperth service change or before releasing an update.

```bash
pip install -r requirements-dev.txt
pytest tests/ -n auto
```
The `-n auto` flag runs tests in parallel. If you see a failure, the Transperth API has probably changed and the affected service will be broken.

### How It Works
The service uses Transperth's public website API. It:
1. Obtains CSRF tokens from two public pages (route timetable page + stop page); each page issues tokens scoped to a different API surface.
2. Calls `GetStopTimetableAsync` for stop-centric queries (one HTTP request returns all upcoming buses at a stop).
3. Calls `GetTimetableOptionsAsync` + `GetTimetableTripAsync` for the route-centric `get_bus_stops` service.
4. Handles HTTP 429 rate limiting explicitly with a `rate_limited: true` flag in responses.

See [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) for the overview or [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for full endpoint details.

## 📝 Version History

- **2.0.0** — Rewrite: 6 user-friendly services (`get_next_bus`, `get_leave_time`, `get_bus_countdown`, `get_stop_departures`, `get_bus_schedule`, `get_bus_stops`), switched to stop-centric API, added `at` parameter for looking ahead, fixed silent 429 failure mode

## ⚖️ Disclaimer

This is an unofficial integration that uses Transperth's public website API. It may stop working at any time if Transperth changes their website. Don't hammer the API — be respectful of their infrastructure.

## 💬 Support

- **Discussions:** [Home Assistant Community](https://community.home-assistant.io/)
- **PyScript Help:** [PyScript Discord](https://discord.gg/ND4emRS)

## 🙏 Acknowledgments

Thanks to the PyScript developers for making Python automations possible in Home Assistant.