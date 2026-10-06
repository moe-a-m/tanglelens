"""Messages API (modified upstream send_data.py): upstream contract kept, forwarding to the
explorer, explorer outage never fails an upload. requests and threading are faked in-process."""
import json

import pytest
import requests

import send_data

SUBMIT = {"blockId": "0x" + "ab" * 32}


class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class SyncThread:
    """Run the forwarder inline so the test can assert on it."""
    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def calls(monkeypatch):
    log = {"hornet": [], "explorer": [], "explorer_status": [201], "hornet_resp": (201, SUBMIT)}

    def fake_post(url, json=None, headers=None, timeout=None, **_):
        if url.endswith("/api/core/v2/blocks"):
            log["hornet"].append((url, json))
            return FakeResp(*log["hornet_resp"])
        log["explorer"].append(json)
        st = log["explorer_status"].pop(0) if len(log["explorer_status"]) > 1 else log["explorer_status"][0]
        if st == "down":
            raise requests.ConnectionError("explorer down")
        return FakeResp(st, {})

    monkeypatch.setattr(send_data.requests, "post", fake_post)
    monkeypatch.setattr(send_data.threading, "Thread", SyncThread)
    monkeypatch.setattr(send_data.time, "sleep", lambda s: None)
    return log


client = send_data.app.test_client()
BODY = {"tag": "trust.score", "message": {"ie": "IE-1", "score": 0.91}, "type": "trust.update", "source": "aeriOS/IE-1"}


def test_upload_keeps_upstream_200_and_shape(calls):
    r = client.post("/upload?node=iota-hornet", json=BODY)
    assert r.status_code == 200                                    # upstream returns Flask's default 200 (D4)
    assert r.get_json() == {"status_code": 201, "return_payload": json.dumps(SUBMIT), "blockId": SUBMIT["blockId"]}


def test_hornet_body_matches_upstream_encoding(calls):
    client.post("/upload?node=iota-hornet", json=BODY)
    url, sent = calls["hornet"][0]
    assert url == "http://iota-hornet:14265/api/core/v2/blocks"
    assert sent == {"protocolVersion": 2, "payload": {
        "type": 5, "tag": "0x" + b"trust.score".hex(), "data": "0x" + json.dumps(BODY["message"]).encode().hex()}}


def test_forward_carries_exact_bytes_sent_to_hornet(calls):
    client.post("/upload?node=iota-hornet", json=BODY)
    fwd, sent = calls["explorer"][0], calls["hornet"][0][1]["payload"]
    assert (fwd["tag_hex"], fwd["data_hex"]) == (sent["tag"], sent["data"])
    assert fwd["block_id"] == SUBMIT["blockId"] and fwd["message"] == BODY["message"]
    assert (fwd["message_type"], fwd["source"], fwd["node"]) == ("trust.update", "aeriOS/IE-1", "iota-hornet")


def test_explorer_down_upload_still_succeeds_and_forward_is_retried(calls):
    calls["explorer_status"] = ["down", "down", 201]
    r = client.post("/upload?node=iota-hornet", json=BODY)
    assert r.status_code == 200 and r.get_json()["blockId"] == SUBMIT["blockId"]
    assert len(calls["explorer"]) == 3


def test_explorer_down_for_good_gives_up_after_retries(calls):
    calls["explorer_status"] = ["down"]
    assert client.post("/upload?node=iota-hornet", json=BODY).status_code == 200
    assert len(calls["explorer"]) == send_data.FORWARD_RETRIES


def test_hornet_rejection_is_not_forwarded(calls):
    calls["hornet_resp"] = (400, {"error": {"code": "400", "message": "invalid block"}})
    r = client.post("/upload?node=iota-hornet", json=BODY)
    assert r.status_code == 200 and r.get_json()["status_code"] == 400   # upstream: 200 wrapping Hornet's error
    assert calls["explorer"] == []


def test_hornet_unreachable(calls, monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("no route")
    monkeypatch.setattr(send_data.requests, "post", boom)
    r = client.post("/upload?node=nowhere", json=BODY)
    assert r.status_code == 400 and b"Hornet node not found" in r.data


def test_missing_fields(calls):
    assert client.post("/upload", json={"tag": "t"}).status_code == 400
    assert calls["hornet"] == []


def test_tag_over_64_bytes_goes_to_hornet_like_upstream(calls):
    """No pre-check (OPEN_QUESTIONS #9): Hornet rejects 65 bytes with 400 (H7), returned in a 200."""
    calls["hornet_resp"] = (400, {"error": {"code": "400", "message": "slice (len 65) exceeds max length of 64"}})
    r = client.post("/upload", json={"tag": "a" * 65, "message": {}})
    assert r.status_code == 200 and r.get_json()["status_code"] == 400 and r.get_json()["blockId"] is None
    assert len(calls["hornet"]) == 1 and calls["explorer"] == []


def test_trace_is_forwarded_not_written_on_chain(calls):
    client.post("/upload?node=iota-hornet", json={**BODY, "trace": "flow-42"})
    assert calls["explorer"][0]["trace_id"] == "flow-42"
    on_chain = calls["hornet"][0][1]["payload"]
    assert json.loads(bytes.fromhex(on_chain["data"][2:])) == BODY["message"]   # on-chain payload unchanged
    assert bytes.fromhex(on_chain["tag"][2:]).decode() == BODY["tag"]


@pytest.mark.parametrize("bad", ["", "x" * 129, 42, {"a": 1}, "a/b", "a b", "ü"])
def test_invalid_trace_is_rejected_before_hornet(calls, bad):
    assert client.post("/upload", json={**BODY, "trace": bad}).status_code == 400
    assert calls["hornet"] == []
