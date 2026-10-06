#!/usr/bin/env python3
"""Measure attach -> milestone-reference time on a REAL Hornet node (CLAUDE.md §3, §8).

Submits N tagged-data blocks (same encoding as the upstream Messages API), spaced by a random
0..JITTER s so submissions land at random phases of the milestone interval, then polls each
block's metadata until `referencedByMilestoneIndex` appears. Standard library only.

Writes reports/hornet/<stamp>_timing/{timing.csv,summary.txt}.
Usage: scripts/measure_confirmation.py [N]   (env HORNET, JITTER, POLL)
"""
import json
import os
import random
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HORNET = os.getenv("HORNET", "http://localhost:14265")
JITTER = float(os.getenv("JITTER", "6"))
POLL = float(os.getenv("POLL", "0.25"))
TIMEOUT = 120


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(HORNET + path, data=data, method=method,
                               headers={"Accept": "application/json", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as resp:
        return resp.status, json.loads(resp.read() or b"{}")


def hexs(text):
    return "0x" + text.encode("utf-8").hex()


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(__file__).resolve().parent.parent / "reports" / "hornet" / f"{stamp}_timing"
    out.mkdir(parents=True)
    rows = []
    for i in range(n):
        time.sleep(random.uniform(0, JITTER))
        msg = json.dumps({"probe": "measure_confirmation", "i": i, "stamp": stamp})
        t0 = time.monotonic()
        status, body = req("POST", "/api/core/v2/blocks",
                           {"protocolVersion": 2, "payload": {"type": 5, "tag": hexs("veles.timing"), "data": hexs(msg)}})
        t_submit = time.monotonic() - t0
        bid = body["blockId"]
        first_solid = ref = None
        while time.monotonic() - t0 < TIMEOUT:
            _, meta = req("GET", f"/api/core/v2/blocks/{bid}/metadata")
            el = time.monotonic() - t0
            if meta.get("isSolid") and first_solid is None:
                first_solid = el
            if "referencedByMilestoneIndex" in meta:
                ref = (el, meta["referencedByMilestoneIndex"], meta.get("ledgerInclusionState"))
                break
            time.sleep(POLL)
        row = {"i": i, "block_id": bid, "submit_status": status, "submit_s": round(t_submit, 3),
               "first_solid_s": round(first_solid, 3) if first_solid is not None else "",
               "referenced_s": round(ref[0], 3) if ref else "", "milestone": ref[1] if ref else "",
               "ledger_inclusion_state": ref[2] if ref else ""}
        rows.append(row)
        print(row, flush=True)

    with open(out / "timing.csv", "w") as f:
        f.write(",".join(rows[0]) + "\n")
        for r in rows:
            f.write(",".join(str(v) for v in r.values()) + "\n")
    refs = [r["referenced_s"] for r in rows if r["referenced_s"] != ""]
    summary = (f"hornet={HORNET} n={n} referenced={len(refs)} poll={POLL}s jitter=0..{JITTER}s\n"
               f"referenced_s min={min(refs):.3f} median={statistics.median(refs):.3f} "
               f"mean={statistics.mean(refs):.3f} max={max(refs):.3f}\n"
               f"first_solid_s max={max(r['first_solid_s'] for r in rows if r['first_solid_s'] != ''):.3f}\n"
               f"submit_status={sorted({r['submit_status'] for r in rows})} "
               f"inclusion_states={sorted({r['ledger_inclusion_state'] for r in rows})}\n")
    (out / "summary.txt").write_text(summary)
    print(summary, "->", out)


if __name__ == "__main__":
    main()
