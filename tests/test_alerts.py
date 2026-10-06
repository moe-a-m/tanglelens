"""Alerts (DESIGN D10): integrity alerts on transitions into problem states, application alerts
on ALERT_TAGS, REST listing/ack, best-effort webhook."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import alerts, main
from app.db import Alert, SessionLocal
from test_verify import META_CONFIRMED, fake_hornet, make_message
from app.verify import verify_message

client = TestClient(main.app)


def alert_rows():
    with SessionLocal() as s:
        return [(a.kind, a.status, a.previous_status) for a in s.query(Alert).order_by(Alert.id)]


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


def test_integrity_alert_only_on_transition(session):
    m = make_message(session)
    verify_message(session, m, fake_hornet())                       # confirmed: no alert
    assert alert_rows() == []
    m.payload = {"probe": "forged"}
    session.commit()
    verify_message(session, m, fake_hornet())                       # -> content_mismatch: alert
    verify_message(session, m, fake_hornet())                       # still mismatch (audit): no repeat
    assert alert_rows() == [("integrity", "content_mismatch", "confirmed")]


def test_not_found_alerts_but_error_does_not(session):
    m = make_message(session)
    verify_message(session, m, fake_hornet(fail=503))               # error: no alert
    verify_message(session, m, fake_hornet(meta=None))              # not_found: alert
    assert alert_rows() == [("integrity", "not_found", "error")]


def test_conflicting_alerts(session):
    meta = dict(META_CONFIRMED, ledgerInclusionState="conflicting")  # derived, never seen live
    verify_message(session, make_message(session), fake_hornet(meta=meta))
    assert alert_rows() == [("integrity", "conflicting", "unverified")]


@pytest.mark.parametrize("tag,patterns,hit", [
    ("trust.security.alert", ["*.alert"], True), ("trust.score", ["*.alert"], False),
    ("trust.score", ["trust.*"], True), ("trust.score", [], False), ("Trust.alert", ["*.alert"], True),
    ("trust.alerts", ["*.alert"], False)])
def test_tag_patterns(tag, patterns, hit):
    assert alerts.tag_is_critical(tag, patterns) is hit


def test_application_alert_on_ingest_once(monkeypatch):
    monkeypatch.setattr(alerts, "ALERT_TAGS", ["*.alert"])
    body = {"block_id": "0x" + "c" * 64, "tag": "trust.security.alert", "message": {"priority": 4}, "trace_id": "ie-2"}
    client.post("/api/ingest", json=body)
    client.post("/api/ingest", json=body)                           # duplicate ingest: no second alert
    client.post("/api/ingest", json={**body, "block_id": "0x" + "d" * 64, "tag": "trust.score"})
    items = client.get("/api/alerts").json()["items"]
    assert [(a["kind"], a["tag"], a["trace_id"]) for a in items] == [("application", "trust.security.alert", "ie-2")]


def test_list_since_unacknowledged_and_ack(session):
    for i in range(3):
        m = make_message(session, block_id="0x" + f"{i:064x}")
        verify_message(session, m, fake_hornet(meta=None))          # 3 not_found alerts
    d = client.get("/api/alerts").json()
    ids = [a["id"] for a in d["items"]]
    assert d["open"] == 3 and ids == sorted(ids, reverse=True)      # newest first
    assert [a["id"] for a in client.get("/api/alerts", params={"since_id": ids[1]}).json()["items"]] == [ids[0]]
    first = client.post(f"/api/alerts/{ids[0]}/ack").json()
    again = client.post(f"/api/alerts/{ids[0]}/ack").json()
    assert first["acknowledged_at"] and again["acknowledged_at"] == first["acknowledged_at"]   # idempotent
    d = client.get("/api/alerts", params={"unacknowledged": True}).json()
    assert d["open"] == 2 and ids[0] not in [a["id"] for a in d["items"]]
    assert client.post("/api/alerts/999999/ack").status_code == 404


class SyncThread:
    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


def test_webhook_receives_alert_and_failures_do_not_raise(session, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "ALERT_WEBHOOK_URL", "http://hook.test/alerts")
    monkeypatch.setattr(alerts.threading, "Thread", SyncThread)
    monkeypatch.setattr(alerts.httpx, "post", lambda url, json, timeout: sent.append((url, json)) or httpx.Response(204))
    m = make_message(session)
    verify_message(session, m, fake_hornet(meta=None))
    assert sent[0][0] == "http://hook.test/alerts" and sent[0][1]["status"] == "not_found"
    assert sent[0][1]["block_id"] == m.block_id

    def boom(*a, **k):
        raise httpx.ConnectError("hook down")
    monkeypatch.setattr(alerts.httpx, "post", boom)
    m2 = make_message(session, block_id="0x" + "e" * 64)
    v = verify_message(session, m2, fake_hornet(meta=None))       # must not raise
    assert v.status == "not_found" and len(alert_rows()) == 2
