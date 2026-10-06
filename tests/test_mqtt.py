"""MQTT delivery path and alert publishing in the explorer (DESIGN D12), no broker needed."""
import json

from fastapi.testclient import TestClient

from app import alerts, main, mqtt
from test_verify import fake_hornet, make_message, SessionLocal
from app.verify import verify_message

client = TestClient(main.app)
REC = {"block_id": "0x" + "f" * 64, "tag": "trust.score", "message": {"ie": "ie-1"}, "trace_id": "ie-1"}


def via(block_id):
    return client.get(f"/api/messages/{block_id}").json()["received_via"]


def test_mqtt_record_is_stored_with_provenance():
    r = mqtt.handle_message(json.dumps(REC).encode(), main.store, main.IngestIn)
    assert r == {"block_id": REC["block_id"], "created": True} and via(REC["block_id"]) == "mqtt"


def test_second_path_is_a_no_op_first_path_wins():
    client.post("/api/ingest", json=REC)                                         # HTTP first
    assert mqtt.handle_message(json.dumps(REC).encode(), main.store, main.IngestIn)["created"] is False
    assert via(REC["block_id"]) == "http"
    rec2 = {**REC, "block_id": "0x" + "a" * 64}
    mqtt.handle_message(json.dumps(rec2).encode(), main.store, main.IngestIn)    # MQTT first
    assert client.post("/api/ingest", json=rec2).json()["created"] is False and via(rec2["block_id"]) == "mqtt"


def test_invalid_mqtt_records_are_dropped():
    for bad in (b"not json", json.dumps({**REC, "block_id": "0x1234"}).encode(), b"{}"):
        assert mqtt.handle_message(bad, main.store, main.IngestIn) is None
    assert client.get("/api/messages").json()["total"] == 0


class FakeClient:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload, qos=0):
        self.sent.append((topic, json.loads(payload), qos))

        class Info:
            rc = 0
        return Info()


def test_alerts_are_published_to_mqtt(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mqtt, "_client", fake)
    with SessionLocal() as s:
        verify_message(s, make_message(s), fake_hornet(meta=None))               # not_found -> alert
    topic, payload, qos = fake.sent[0]
    assert (topic, qos, payload["kind"], payload["status"]) == ("aerios/explorer/alerts", 1, "integrity", "not_found")


def test_mqtt_disabled_by_default():
    assert mqtt.start(main.store, main.IngestIn) is None                         # MQTT_HOST unset in tests
    mqtt.publish_alert({"id": 1})                                                # no client: no error


# ---------- manual acknowledgement (code review: never ack a record that was not stored) ----------
class AckClient:
    def __init__(self):
        self.acks = []

    def ack(self, mid, qos):
        self.acks.append((mid, qos))


class Msg:
    def __init__(self, payload, mid=7, qos=1):
        self.payload, self.mid, self.qos = payload, mid, qos


def test_ack_only_after_store_succeeds(monkeypatch):
    monkeypatch.setattr(mqtt.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky_store(item, via):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("database restarting")
        return main.store(item, via=via)
    c = AckClient()
    assert mqtt.deliver(c, Msg(json.dumps(REC).encode()), flaky_store, main.IngestIn) is True
    assert calls["n"] == 3 and c.acks == [(7, 1)] and via(REC["block_id"]) == "mqtt"


def test_store_keeps_failing_leaves_message_unacked(monkeypatch):
    slept = []
    monkeypatch.setattr(mqtt.time, "sleep", slept.append)

    def broken_store(item, via):
        raise RuntimeError("database down")
    c = AckClient()
    assert mqtt.deliver(c, Msg(json.dumps(REC).encode()), broken_store, main.IngestIn) is False
    assert c.acks == [] and slept == list(mqtt.STORE_RETRY_DELAYS) and sum(slept) < 90 * 0.6


def test_invalid_record_is_acked_and_dropped(monkeypatch):
    c = AckClient()
    assert mqtt.deliver(c, Msg(b"not json"), main.store, main.IngestIn) is True and c.acks == [(7, 1)]
