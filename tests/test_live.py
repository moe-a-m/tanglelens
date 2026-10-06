"""Live smoke test against a running stack (make smoke-real, or make e2e-mock with the mock).
Messages API -> Hornet -> explorer: 3 uploads must reach `confirmed` with content match and be
findable by the brief's three mandatory keys: block id, date, tag. Records are saved under
reports/smoke/ as evidence."""
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.live
API = os.getenv("MESSAGES_API_URL", "http://localhost:5555")
EXP = os.getenv("EXPLORER_URL", "http://localhost:8090")
NODE = os.getenv("HORNET_NODE", "iota-hornet")
TIMEOUT = float(os.getenv("SMOKE_TIMEOUT", "40"))   # ~8x the slowest attach->confirmed seen (H11 + 3 s loop)


def test_three_messages_reach_confirmed_and_are_searchable():
    run = uuid.uuid4().hex[:8]
    tag = f"smoke.{run}"
    start = datetime.now(timezone.utc) - timedelta(seconds=1)
    ids = []
    for i in range(3):
        r = httpx.post(f"{API}/upload", params={"node": NODE}, timeout=30, json={
            "tag": tag, "type": "smoke", "source": f"smoke/{run}", "message": {"run": run, "i": i}})
        assert r.status_code == 200 and r.json()["status_code"] == 201, r.text
        ids.append(r.json()["blockId"])

    deadline, records = time.monotonic() + TIMEOUT, {}
    while time.monotonic() < deadline:
        for b in ids:
            r = httpx.get(f"{EXP}/api/messages/{b}", timeout=10)
            if r.status_code == 200:
                records[b] = r.json()
        if len(records) == 3 and all(d["verification"]["status"] == "confirmed" for d in records.values()):
            break
        time.sleep(1)

    out = Path(__file__).resolve().parent.parent / "reports" / "smoke"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"{stamp}_{run}.json").write_text(json.dumps({"explorer": EXP, "api": API, "records": records}, indent=2))

    assert len(records) == 3, f"not ingested: {set(ids) - set(records)}"
    for d in records.values():
        v = d["verification"]
        assert v["status"] == "confirmed", d["history"][:1]
        assert v["content_match"] is True and v["is_solid"] is True and v["milestone_index"]

    by_tag = httpx.get(f"{EXP}/api/messages", params={"tag": tag}).json()
    assert {m["block_id"] for m in by_tag["items"]} == set(ids)
    assert httpx.get(f"{EXP}/api/messages", params={"block_id": ids[0]}).json()["total"] == 1
    by_date = httpx.get(f"{EXP}/api/messages", params={
        "tag": tag, "from": start.isoformat(), "to": (datetime.now(timezone.utc)).isoformat()}).json()
    assert by_date["total"] == 3
