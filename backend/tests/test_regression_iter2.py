"""Regression tests for iteration 2 - post query-projection optimization.

Focused on the endpoints touched in the review:
- POST /api/planning/generate
- POST /api/planning/reschedule
- GET  /api/interventions
- GET  /api/calendar/export.ics
- GET  /api/dashboard/stats
- POST /api/ai/planning-chat
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
USER_ID = os.environ.get("TEST_USER_ID")
SESSION_TOKEN = os.environ.get("TEST_SESSION_TOKEN")

assert USER_ID and SESSION_TOKEN, "Set TEST_USER_ID and TEST_SESSION_TOKEN env vars"

HEADERS = {"Authorization": f"Bearer {SESSION_TOKEN}", "Content-Type": "application/json"}


# ---------- Fixtures: seed a client + contract for planning ----------

@pytest.fixture(scope="module")
def seeded():
    """Seed a client and a contract for this test module."""
    # Client
    r = requests.post(f"{BASE_URL}/api/clients", headers=HEADERS, json={
        "name": "TEST_ITER2 Client",
        "city": "Milano",
        "address": "Via Roma 1",
    })
    assert r.status_code == 200, f"seed client failed: {r.status_code} {r.text}"
    client_id = r.json()["id"]

    # Contract
    r = requests.post(f"{BASE_URL}/api/contracts", headers=HEADERS, json={
        "client_id": client_id,
        "title": "TEST_ITER2 Consulenza",
        "total_days": 4,
        "priority": "high",
        "daily_rate": 500,
    })
    assert r.status_code == 200, f"seed contract failed: {r.status_code} {r.text}"
    contract_id = r.json()["id"]

    yield {"client_id": client_id, "contract_id": contract_id}

    # Teardown: delete contract + interventions + client
    requests.delete(f"{BASE_URL}/api/contracts/{contract_id}", headers=HEADERS)
    requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=HEADERS)


# ---------- Planning generate/reschedule ----------

def test_planning_generate_returns_200_and_interventions(seeded):
    r = requests.post(f"{BASE_URL}/api/planning/generate", headers=HEADERS, json={
        "workdays_only": True,
        "max_days_per_client_block": 2,
        "start_from": "2026-03-02",  # Monday
    })
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    data = r.json()
    assert "planned" in data and "interventions" in data
    assert isinstance(data["interventions"], list)
    # Should include our contract's 4 days
    ours = [iv for iv in data["interventions"] if iv["contract_id"] == seeded["contract_id"]]
    assert len(ours) >= 4
    # No ObjectId leakage
    for iv in ours:
        assert "_id" not in iv
        # weekday check
        from datetime import date
        d = date.fromisoformat(iv["date"])
        assert d.weekday() < 5, f"Weekend intervention created: {iv['date']}"


def test_planning_reschedule_respects_manual_events(seeded):
    # Create a manual event on 2026-03-02 to force shift
    r = requests.post(f"{BASE_URL}/api/manual-events", headers=HEADERS, json={
        "date": "2026-03-02",
        "title": "TEST_ITER2 Block",
        "all_day": True,
    })
    assert r.status_code == 200
    ev_id = r.json()["id"]

    try:
        r = requests.post(f"{BASE_URL}/api/planning/reschedule", headers=HEADERS, json={
            "workdays_only": True,
            "max_days_per_client_block": 5,
            "start_from": "2026-03-02",
        })
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert isinstance(data.get("interventions"), list)
        # 2026-03-02 must not be assigned as an intervention
        dates = [iv["date"] for iv in data["interventions"]]
        assert "2026-03-02" not in dates
    finally:
        requests.delete(f"{BASE_URL}/api/manual-events/{ev_id}", headers=HEADERS)


# ---------- List interventions ----------

def test_list_interventions_sorted_by_date():
    r = requests.get(f"{BASE_URL}/api/interventions", headers=HEADERS)
    assert r.status_code == 200
    docs = r.json()
    assert isinstance(docs, list)
    dates = [d["date"] for d in docs]
    assert dates == sorted(dates), "Interventions not sorted by date ascending"
    for d in docs:
        assert "_id" not in d


# ---------- ICS export ----------

def test_calendar_export_ics_returns_calendar():
    r = requests.get(
        f"{BASE_URL}/api/calendar/export.ics",
        params={"user_id": USER_ID, "token": SESSION_TOKEN},
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    assert "text/calendar" in r.headers.get("content-type", "")
    body = r.text
    assert body.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in body
    # Should contain at least one VEVENT (we generated interventions)
    assert body.count("BEGIN:VEVENT") >= 1


def test_calendar_export_ics_rejects_bad_token():
    r = requests.get(
        f"{BASE_URL}/api/calendar/export.ics",
        params={"user_id": USER_ID, "token": "bogus-token"},
    )
    assert r.status_code == 401


# ---------- Dashboard stats ----------

def test_dashboard_stats_shape():
    r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    for k in ("active_contracts", "clients_count", "interventions_planned",
              "projected_revenue", "upcoming", "total_contracts", "total_workdays"):
        assert k in data, f"missing key {k}"
    assert isinstance(data["upcoming"], list)
    assert isinstance(data["projected_revenue"], (int, float))
    assert isinstance(data["interventions_planned"], int)
    # upcoming items should not carry _id
    for iv in data["upcoming"]:
        assert "_id" not in iv


# ---------- AI planning chat (Claude Haiku 4.5) ----------

def test_ai_planning_chat_returns_reply():
    r = requests.post(
        f"{BASE_URL}/api/ai/planning-chat",
        headers=HEADERS,
        json={"message": "Ciao, quanti contratti attivi ho? Rispondi in una frase."},
        timeout=90,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text[:500]}"
    data = r.json()
    # Response could be {"reply": "..."} or similar - accept common shapes
    reply = data.get("reply") or data.get("message") or data.get("text")
    assert isinstance(reply, str) and len(reply) > 0, f"Empty or missing reply: {data}"
