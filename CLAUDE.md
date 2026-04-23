# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A single-file PyScript service (`src/bus_times.py`) that exposes six Home Assistant services backed by Transperth's unofficial website API. There is no package to install — the file is copied verbatim to `config/pyscript/bus_times.py` in a Home Assistant deployment. `pyproject.toml` exists only so pytest can discover the contract tests.

## Commands

```bash
pip install -r requirements-dev.txt         # one-time setup
pytest tests/ -n auto                       # all contract tests in parallel
pytest tests/test_api_contract.py::test_get_stop_timetable_async   # single test
```

The tests hit the **live** Transperth API. Don't run them in tight loops — Transperth's 429 cooldown is sticky (>60s, shared with the Transperth website itself).

## Runtime environment constraints

`src/bus_times.py` runs inside PyScript, not stock Python. It relies on PyScript-provided globals that do **not exist** in a local interpreter:

- `@service(supports_response="only")` — registers the function as a HA service
- `task.executor(fn, ...)` — runs blocking I/O off the asyncio loop (required for every `requests` call)
- `log.error(...)` / `log.info(...)` — PyScript logger

Consequences:
- You cannot `import` or directly execute `bus_times.py` locally; it will `NameError` on `service`/`task`/`log`.
- Any new blocking HTTP call must go through `task.executor(...)`, otherwise PyScript blocks the HA event loop.
- The tests deliberately do **not** import from `src/` — they reimplement the same API calls from scratch so they can run under plain Python.

## Architecture

### Two auth contexts, one process

Every API call needs a CSRF token extracted from an HTML page, and **tokens are scoped**. Using the wrong one returns HTTP 401.

| Context | Token page | `ModuleId` / `TabId` | Endpoints |
|---------|------------|----------------------|-----------|
| Route   | `/timetables/details?Bus={n}` | `5345` / `133` | `GetTimetableOptionsAsync`, `GetTimetableTripAsync` |
| Stop    | `/Journey-Planner/Stops-Near-You?locationtype=stop&location={code}` | `5310` / `141` | `GetStopTimetableAsync` |

Auth helpers and headers live in the "AUTH HELPERS" section of `bus_times.py`. If adding a new endpoint, figure out which page issues the token first — the health check (`bus_times_health_check`) verifies both contexts independently.

### Service → endpoint mapping

- Five of six services (`get_next_bus`, `get_leave_time`, `get_bus_countdown`, `get_stop_departures`, `get_bus_schedule`) share one call to `GetStopTimetableAsync` and filter/shape its `trips[]`. The `parse_stop_trip` helper normalises each entry.
- `get_bus_stops` is the outlier: route-context, two calls (`GetTimetableOptionsAsync` → `GetTimetableTripAsync`), with a direction fallback when the first try returns empty `data`.

### Error handling shape

All services return a dict with `result: "success" | "error"`. Three custom exceptions (`RateLimitError`, `AuthError`, `NetworkError`) are raised inside helpers and caught at the service boundary. Rate limits surface as `rate_limited: true` so callers can back off — this is a load-bearing contract with the README, don't silently swallow 429s.

### The `at` parameter

Every service accepts an optional `at` for testing and planning. `resolve_reference_time` handles three shapes — `None`, `"HH:MM"` (rolls to tomorrow when past), `"YYYY-MM-DD HH:MM"` (exact moment, no rollover). Preserve this three-case behaviour if you touch it: the rollover is intentional for morning automations set the night before.

### `minutes_until` sentinel

Past or unparseable times return `-1`, not `None` and not a negative count. Consistent across services (see commits 288d46e / ae6c1b4). Template sensors rely on this.

## Tests

`tests/test_api_contract.py` is schema-only — it pins field names the service reads (`DepartTime`, `Summary.RouteCode`, `TripStopTimings[].Stop.Code`, etc.). If a test fails, the API has drifted and the affected service is broken in production; update both the test assertions and the reader in `bus_times.py`. Tests use fixed inputs: bus `414`, stop `12627`, tomorrow midday (to guarantee a non-empty schedule).
