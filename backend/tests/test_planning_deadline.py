"""Tests for planning generator respecting contract start_date and deadline."""
import os
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://job-scheduler-pro-12.preview.emergentagent.com").rstrip("/")
TOKEN = os.environ.get("TEST_TOKEN", "test_session_1789046868284")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


@pytest.fixture
def clean_state(api):
    """Wipe all contracts, clients, interventions, manual events for user before test."""
    # delete interventions
    for iv in api.get(f"{BASE_URL}/api/interventions").json():
        api.delete(f"{BASE_URL}/api/interventions/{iv['id']}")
    for c in api.get(f"{BASE_URL}/api/contracts").json():
        api.delete(f"{BASE_URL}/api/contracts/{c['id']}")
    for cl in api.get(f"{BASE_URL}/api/clients").json():
        api.delete(f"{BASE_URL}/api/clients/{cl['id']}")
    for ev in api.get(f"{BASE_URL}/api/manual-events").json():
        api.delete(f"{BASE_URL}/api/manual-events/{ev['id']}")
    yield


def _make_client(api, name="TEST_Client"):
    r = api.post(f"{BASE_URL}/api/clients", json={"name": name, "address": "Via Roma 1", "city": "Milano"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _make_contract(api, client_id, total_days, start_date=None, deadline=None, max_per_month=None, title="TEST_C"):
    payload = {"client_id": client_id, "title": title, "total_days": total_days, "priority": "medium"}
    if start_date: payload["start_date"] = start_date
    if deadline: payload["deadline"] = deadline
    if max_per_month is not None: payload["max_per_month"] = max_per_month
    r = api.post(f"{BASE_URL}/api/contracts", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# --- Test 1: Planning respects contract start_date ---
def test_respects_start_date(api, clean_state):
    cid = _make_client(api, "TEST_StartDate")
    ctid = _make_contract(api, cid, total_days=5, start_date="2026-10-01", deadline="2026-11-03")
    r = api.post(f"{BASE_URL}/api/planning/generate", json={"start_from": "2026-09-01"})
    assert r.status_code == 200, r.text
    data = r.json()
    ivs = [iv for iv in data["interventions"] if iv["contract_id"] == ctid]
    assert len(ivs) == 5
    for iv in ivs:
        assert iv["date"] >= "2026-10-01", f"Intervention {iv['date']} before start_date"
        assert iv["date"] <= "2026-11-03"


# --- Test 2: Deadline reached produces skipped ---
def test_deadline_reached_skipped(api, clean_state):
    cid = _make_client(api, "TEST_DeadlineHit")
    ctid = _make_contract(api, cid, total_days=30, start_date="2026-10-01", deadline="2026-11-03")
    r = api.post(f"{BASE_URL}/api/planning/generate", json={"start_from": "2026-09-01"})
    assert r.status_code == 200
    data = r.json()
    assert "skipped" in data
    skipped_for = [s for s in data["skipped"] if s["contract_id"] == ctid]
    assert len(skipped_for) == 1
    assert skipped_for[0]["reason"] == "deadline_reached"
    assert skipped_for[0]["remaining"] > 0
    ivs = [iv for iv in data["interventions"] if iv["contract_id"] == ctid]
    for iv in ivs:
        assert iv["date"] <= "2026-11-03"


# --- Test 3: Deadline already expired ---
def test_deadline_expired(api, clean_state):
    cid = _make_client(api, "TEST_Expired")
    ctid = _make_contract(api, cid, total_days=3, start_date="2020-01-01", deadline="2020-06-30")
    r = api.post(f"{BASE_URL}/api/planning/generate", json={"start_from": "2026-09-01"})
    assert r.status_code == 200
    data = r.json()
    ivs = [iv for iv in data["interventions"] if iv["contract_id"] == ctid]
    assert len(ivs) == 0
    skipped_for = [s for s in data["skipped"] if s["contract_id"] == ctid]
    assert len(skipped_for) == 1
    assert skipped_for[0]["reason"] == "deadline_expired"
    assert skipped_for[0]["remaining"] == 3


# --- Test 4: No start_date uses payload.start_from ---
def test_no_start_date(api, clean_state):
    cid = _make_client(api, "TEST_NoStart")
    ctid = _make_contract(api, cid, total_days=3, start_date=None, deadline="2027-01-01")
    r = api.post(f"{BASE_URL}/api/planning/generate", json={"start_from": "2026-09-01"})
    assert r.status_code == 200
    data = r.json()
    ivs = [iv for iv in data["interventions"] if iv["contract_id"] == ctid]
    assert len(ivs) == 3
    for iv in ivs:
        assert iv["date"] >= "2026-09-01"
        assert iv["date"] <= "2027-01-01"


# --- Test 5: Contract with only 5 total_days fits fully - no skipped ---
def test_fits_fully_no_skipped(api, clean_state):
    cid = _make_client(api, "TEST_Fits")
    ctid = _make_contract(api, cid, total_days=5, start_date="2026-10-01", deadline="2026-11-03")
    r = api.post(f"{BASE_URL}/api/planning/generate", json={"start_from": "2026-09-01"})
    assert r.status_code == 200
    data = r.json()
    skipped_for = [s for s in data["skipped"] if s["contract_id"] == ctid]
    assert skipped_for == []


# --- Test 6: Multiple contracts, separate windows ---
def test_multiple_contracts_separate_windows(api, clean_state):
    cidA = _make_client(api, "TEST_MultiA")
    cidB = _make_client(api, "TEST_MultiB")
    ctA = _make_contract(api, cidA, total_days=3, start_date="2026-10-01", deadline="2026-11-03", title="A")
    ctB = _make_contract(api, cidB, total_days=2, start_date="2027-02-01", deadline="2027-04-30", title="B")
    r = api.post(f"{BASE_URL}/api/planning/generate", json={"start_from": "2026-09-01"})
    assert r.status_code == 200
    data = r.json()
    ivsA = [iv for iv in data["interventions"] if iv["contract_id"] == ctA]
    ivsB = [iv for iv in data["interventions"] if iv["contract_id"] == ctB]
    assert len(ivsA) == 3
    assert len(ivsB) == 2
    for iv in ivsA:
        assert "2026-10-01" <= iv["date"] <= "2026-11-03"
    for iv in ivsB:
        assert "2027-02-01" <= iv["date"] <= "2027-04-30"


# --- Test 7: max_per_month enforced within deadline ---
def test_max_per_month(api, clean_state):
    cid = _make_client(api, "TEST_MaxPM")
    ctid = _make_contract(api, cid, total_days=6, start_date="2026-10-01", deadline="2027-01-31", max_per_month=2)
    r = api.post(f"{BASE_URL}/api/planning/generate", json={"start_from": "2026-09-01"})
    assert r.status_code == 200
    data = r.json()
    ivs = [iv for iv in data["interventions"] if iv["contract_id"] == ctid]
    assert len(ivs) == 6
    from collections import Counter
    per_month = Counter(iv["date"][:7] for iv in ivs)
    for m, count in per_month.items():
        assert count <= 2, f"Month {m} has {count} interventions > 2"
    # Should be Oct, Nov, Dec 2026 (2 each)
    assert set(per_month.keys()) == {"2026-10", "2026-11", "2026-12"}


# --- Test 8: Reschedule honors contract dates ---
def test_reschedule_honors_dates(api, clean_state):
    cid = _make_client(api, "TEST_Resched")
    ctid = _make_contract(api, cid, total_days=5, start_date="2026-10-01", deadline="2026-11-03")
    # Generate first
    api.post(f"{BASE_URL}/api/planning/generate", json={"start_from": "2026-09-01"})
    # Reschedule
    r = api.post(f"{BASE_URL}/api/planning/reschedule", json={"start_from": "2026-09-01"})
    assert r.status_code == 200
    data = r.json()
    ivs = [iv for iv in data["interventions"] if iv["contract_id"] == ctid]
    assert len(ivs) == 5
    for iv in ivs:
        assert "2026-10-01" <= iv["date"] <= "2026-11-03"
