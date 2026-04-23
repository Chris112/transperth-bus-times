"""Shared fixtures for API contract tests.

These tests hit the live Transperth API. They verify response schemas so we
catch breaking changes the Transperth team might introduce.
"""

import re
from datetime import datetime, timedelta

import pytest
import requests


BASE_URL = "https://www.transperth.wa.gov.au"

ROUTE_AUTH_PAGE = f"{BASE_URL}/timetables/details?Bus=414"
STOP_AUTH_PAGE = f"{BASE_URL}/Journey-Planner/Stops-Near-You?locationtype=stop&location=12627"

# Fixed test inputs — 414 is a well-known route through stop 12627 (Main St After Lawley St).
TEST_BUS = "414"
TEST_STOP = "12627"


def _extract_token(html):
    m = re.search(
        r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"',
        html,
    )
    assert m, "No __RequestVerificationToken in HTML — page structure may have changed"
    return m.group(1)


@pytest.fixture(scope="session")
def session():
    return requests.Session()


@pytest.fixture(scope="session")
def route_token(session):
    r = session.get(ROUTE_AUTH_PAGE)
    assert r.status_code == 200, f"Route auth page returned {r.status_code}"
    return _extract_token(r.text)


@pytest.fixture(scope="session")
def stop_token(session):
    r = session.get(STOP_AUTH_PAGE)
    assert r.status_code == 200, f"Stop auth page returned {r.status_code}"
    return _extract_token(r.text)


@pytest.fixture
def route_headers(route_token):
    return {
        "RequestVerificationToken": route_token,
        "ModuleId": "5345",
        "TabId": "133",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }


@pytest.fixture
def stop_request_headers(stop_token):
    return {
        "RequestVerificationToken": stop_token,
        "ModuleId": "5310",
        "TabId": "141",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": STOP_AUTH_PAGE,
        "Origin": BASE_URL,
    }


@pytest.fixture(scope="session")
def tomorrow_midday():
    """A reference time guaranteed to have upcoming buses (avoids late-night empties)."""
    when = datetime.now() + timedelta(days=1)
    return when.replace(hour=13, minute=0, second=0, microsecond=0)
