"""Explorer REST API contract (CLAUDE.md §9, §10). TestClient is used without its context
manager, so the lifespan (background verifier loops) does not run."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from test_verify import BLOCK, BLOCK_ID, fake_hornet

client = TestClient(main.app)


def bid(n: int) -> str:
    return "0x" + f"{n:064x}"


def ingest(n: int, tag: str = "trust.score", when: str = "2026-10-06T10:00:00Z", **extra):
    body = {"block_id": bid(n), "tag": tag, "message": {"n": n, "word": extra.pop("word", "hello")},
            "submitted_at": when, **extra}
    r = client.post("/api/ingest", json=body)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def seeded():
    ingest(0xabcdef01, "trust.score", "2026-10-06T10:00:00Z", message_type="trust.update", source="aeriOS/IE-1")
    ingest(0xabcdef02, "trust.score", "2026-10-06T11:00:00Z", message_type="trust.update", source="aeriOS/IE-2")
    ingest(0x12345603, "trust.alert", "2026-10-06T12:00:00Z", source="aeriOS/IE-2", word="migrate")
    ingest(0x12345604, "self.reorchestration", "2026-10-07T09:30:00+02:00", message_type="orchestration")


def total(**params) -> int:
    r = client.get("/api/messages", params=params)
    assert r.status_code == 200, r.text
    return r.json()["total"]


# ---------- ingest ----------
def test_ingest_twice_is_idempotent():
    assert ingest(1)["created"] is True
    r = client.post("/api/ingest", json={"block_id": bid(1), "tag": "x", "message": {}})
    assert r.status_code == 201 and r.json() == {"block_id": bid(1), "created": False}
    assert total() == 1


@pytest.mark.parametrize("bad", ["0x1234", "0x" + "A" * 64, "ab" * 32, "0x" + "a" * 65, ""])
def test_ingest_rejects_malformed_block_id(bad):
    """Hornet zero-pads short ids (H6), so they must never be stored."""
    assert client.post("/api/ingest", json={"block_id": bad, "tag": "t", "message": {}}).status_code == 422


def test_ingest_keeps_forwarded_exact_hex():
    data_hex = "0x" + b'{"a":1}'.hex()           # compact JSON, not what json.dumps would produce
    client.post("/api/ingest", json={"block_id": bid(2), "tag": "t", "message": {"a": 1}, "data_hex": data_hex})
    assert client.get(f"/api/messages/{bid(2)}").json()["raw"]["data_hex"] == data_hex


# ---------- the three mandatory search keys (brief): block id, date, tag ----------
def test_search_by_exact_block_id(seeded):
    r = client.get("/api/messages", params={"block_id": bid(0xabcdef01)}).json()
    assert r["total"] == 1 and r["items"][0]["block_id"] == bid(0xabcdef01)


def test_search_by_block_id_prefix(seeded):
    assert total(block_id=bid(0xabcdef01)[:62]) == 2      # shared prefix of ...abcdef01/02
    assert total(block_id=bid(0xabcdef01)[:62].upper().replace("0X", "0x")) == 2
    assert total(block_id="0x000000") == 4               # exactly 6 hex chars is enough
    assert total(block_id=bid(0xabcdef01)[2:62]) == 2     # "0x" is optional for a prefix


@pytest.mark.parametrize("bad", ["0xzzzzzz", "0x000000 ", "0x" + "0" * 65])
def test_block_id_filter_rejects_non_hex(seeded, bad):
    assert client.get("/api/messages", params={"block_id": bad}).status_code == 422


@pytest.mark.parametrize("short", ["0x", "0x0000", "0x00000", "00000"])
def test_block_id_prefix_shorter_than_6_hex_chars_is_rejected(seeded, short):
    assert client.get("/api/messages", params={"block_id": short}).status_code == 422


def test_search_by_tag_exact_and_prefix(seeded):
    assert total(tag="trust.score") == 2
    assert total(tag="trust*") == 3
    assert total(tag="trust") == 0


def test_search_by_date_bounds_are_inclusive_and_utc(seeded):
    assert total(**{"from": "2026-10-06T11:00:00Z"}) == 3
    assert total(to="2026-10-06T11:00:00Z") == 2
    assert total(**{"from": "2026-10-06T11:00:00Z", "to": "2026-10-06T11:00:00Z"}) == 1
    assert total(**{"from": "2026-10-06T13:00:00+02:00", "to": "2026-10-06T13:00:00+02:00"}) == 1  # = 11:00Z
    assert total(**{"from": "2026-10-07T07:30:00Z"}) == 1      # stored from +02:00 input


# ---------- other filters, combinations, paging ----------
def test_other_filters(seeded):
    assert total(type="trust.update") == 2
    assert total(source="aeriOS/IE-2") == 2
    assert total(q="migrate") == 1
    assert total(q="MIGRATE") == 1                     # case-insensitive
    assert total(status="unverified") == 4
    assert total(status="confirmed,pending") == 0
    assert total(milestone=25) == 0


def test_combined_filters(seeded):
    assert total(tag="trust*", source="aeriOS/IE-2") == 2
    assert total(tag="trust*", source="aeriOS/IE-2", **{"from": "2026-10-06T11:30:00Z"}) == 1
    assert total(tag="trust.score", block_id=bid(0x12345603)) == 0


def test_paging_and_sort(seeded):
    page = client.get("/api/messages", params={"limit": 3, "offset": 0}).json()
    rest = client.get("/api/messages", params={"limit": 3, "offset": 3}).json()
    assert page["total"] == rest["total"] == 4 and len(page["items"]) == 3 and len(rest["items"]) == 1
    newest = page["items"][0]["block_id"]
    assert newest == bid(0x12345604)                   # default sort -submitted_at
    asc = client.get("/api/messages", params={"sort": "submitted_at"}).json()["items"]
    assert asc[0]["block_id"] == bid(0xabcdef01)
    assert client.get("/api/messages", params={"sort": "payload"}).status_code == 422


# ---------- detail, verify, tags, stats, health ----------
def test_detail_and_unknown(seeded):
    assert client.get(f"/api/messages/{bid(0xabcdef01)}").json()["history"] == []
    assert client.get(f"/api/messages/{bid(99)}").status_code == 404
    assert client.post(f"/api/messages/{bid(99)}/verify").status_code == 404


def test_verify_endpoint_against_real_fixture(monkeypatch):
    payload = BLOCK["payload"]
    text = bytes.fromhex(payload["data"][2:]).decode()
    import json
    client.post("/api/ingest", json={"block_id": BLOCK_ID, "tag": bytes.fromhex(payload["tag"][2:]).decode(),
                                     "message": json.loads(text), "tag_hex": payload["tag"], "data_hex": payload["data"]})
    monkeypatch.setattr(main, "hornet", fake_hornet())
    d = client.post(f"/api/messages/{BLOCK_ID}/verify").json()
    assert d["verification"]["status"] == "confirmed" and d["history"][0]["status"] == "confirmed"


def test_tags_and_stats(seeded):
    tags = {t["tag"]: t["count"] for t in client.get("/api/tags").json()}
    assert tags == {"trust.score": 2, "trust.alert": 1, "self.reorchestration": 1}
    assert client.get("/api/stats").json() == {"total": 4, "by_status": {"unverified": 4}, "latest_milestone": None}


def test_health_reports_unreachable_hornet(monkeypatch):
    monkeypatch.setattr(main, "hornet", fake_hornet(fail=httpx.ConnectError("refused")))
    assert client.get("/api/health").json()["hornet"]["reachable"] is False


def test_health_uses_real_info_fields(monkeypatch):
    from conftest import load
    info = load("info")
    h = fake_hornet()
    h.client = httpx.Client(base_url="http://h", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=info)))
    monkeypatch.setattr(main, "hornet", h)
    node = client.get("/api/health").json()["hornet"]
    assert node == {"reachable": True, "name": "HORNET", "latest_milestone": info["status"]["latestMilestone"]["index"],
                    "healthy": False}


# ---------- trace id (DESIGN D8) and additive schema upgrade (D11) ----------
def test_trace_id_stored_and_searchable():
    ingest(10, trace_id="flow-1")
    ingest(11, trace_id="flow-1")
    ingest(12, trace_id="flow-2")
    ingest(13)
    assert total(trace="flow-1") == 2 and total(trace="flow-2") == 1 and total(trace="flow") == 0
    assert client.get(f"/api/messages/{bid(10)}").json()["trace_id"] == "flow-1"
    assert client.get(f"/api/messages/{bid(13)}").json()["trace_id"] is None


@pytest.mark.parametrize("bad", ["x" * 129, "", "a/b", "a b", "a?b"])
def test_trace_id_must_be_path_safe_and_at_most_128(bad):
    r = client.post("/api/ingest", json={"block_id": bid(14), "tag": "t", "message": {}, "trace_id": bad})
    assert r.status_code == 422


def test_startup_adds_missing_trace_column():
    """An explorer DB created before D8 has no trace_id column; startup must add it."""
    from sqlalchemy import inspect, text
    from app.db import add_missing_columns, engine
    with engine.begin() as c:
        c.execute(text("DROP INDEX ix_messages_trace_id"))
        c.execute(text("ALTER TABLE messages DROP COLUMN trace_id"))
    assert "trace_id" not in {col["name"] for col in inspect(engine).get_columns("messages")}
    assert add_missing_columns() == ["messages.trace_id"]
    assert add_missing_columns() == []                       # idempotent
    ingest(15, trace_id="after-upgrade")
    assert total(trace="after-upgrade") == 1


# ---------- trace timeline (DESIGN D9) ----------
def test_traces_list_and_timeline_order():
    ingest(20, "trust.score", "2026-10-06T10:00:02Z", trace_id="ie-1")
    ingest(21, "trust.reliability", "2026-10-06T10:00:01Z", trace_id="ie-1")
    ingest(22, "trust.score", "2026-10-06T09:00:00Z", trace_id="ie-2")
    ingest(23, "trust.score", "2026-10-06T08:00:00Z")
    lst = client.get("/api/traces").json()
    assert [t["trace_id"] for t in lst] == ["ie-1", "ie-2"]           # most recently active first
    assert lst[0] == {"trace_id": "ie-1", "events": 2, "first_at": "2026-10-06T10:00:01Z",
                      "last_at": "2026-10-06T10:00:02Z", "by_status": {"unverified": 2},
                      "verified": False, "problems": 0}
    tl = client.get("/api/traces/ie-1").json()
    assert [e["block_id"] for e in tl["timeline"]] == [bid(21), bid(20)]   # chronological
    assert [e["seq"] for e in tl["timeline"]] == [1, 2] and "raw" not in tl["timeline"][0]
    assert client.get("/api/traces/nope").status_code == 404
    assert client.post("/api/traces/nope/verify").status_code == 404


def test_trace_verify_checks_every_event_against_hornet(monkeypatch):
    """verified is true only when every event is confirmed; one tampered copy flags the trace."""
    import json
    payload = BLOCK["payload"]
    text = bytes.fromhex(payload["data"][2:]).decode()
    tag = bytes.fromhex(payload["tag"][2:]).decode()
    base = {"tag": tag, "tag_hex": payload["tag"], "data_hex": payload["data"], "trace_id": "t-1"}
    client.post("/api/ingest", json={**base, "block_id": BLOCK_ID, "message": json.loads(text)})
    client.post("/api/ingest", json={**base, "block_id": bid(30), "message": json.loads(text)})
    monkeypatch.setattr(main, "hornet", fake_hornet())          # Hornet answers with the same real block for both
    tl = client.post("/api/traces/t-1/verify").json()
    assert tl["verified"] is True and tl["by_status"] == {"confirmed": 2}
    with main.SessionLocal() as s:                              # tamper one stored copy
        from app.db import Message
        m = s.scalar(main.select(Message).where(Message.block_id == bid(30)))
        m.payload = {"probe": "forged"}
        s.commit()
    tl = client.post("/api/traces/t-1/verify").json()
    assert tl["verified"] is False and tl["problems"] == 1
    assert {e["block_id"]: e["verification"]["status"] for e in tl["timeline"]}[bid(30)] == "content_mismatch"
