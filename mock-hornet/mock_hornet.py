"""
Minimal stand-in for a Hornet 2.0 node: just the endpoints the explorer and Messages API use.
For local development only. Blocks become solid immediately and get referenced by a
milestone after MILESTONE_DELAY seconds, mimicking the pending -> confirmed lifecycle.
"""
import hashlib
import json
import os
import time

from flask import Flask, jsonify, request

app = Flask(__name__)
MILESTONE_DELAY = float(os.getenv("MILESTONE_DELAY", "5"))
START = time.time()
blocks: dict[str, dict] = {}


def milestone_index(t: float) -> int:
    return int((t - START) // MILESTONE_DELAY) + 1


@app.post("/api/core/v2/blocks")
def submit():
    body = request.get_json()
    if (body.get("payload") or {}).get("type") != 5:
        return jsonify(error={"code": "400", "message": "only tagged data supported in mock"}), 400
    raw = json.dumps(body, sort_keys=True) + str(time.time_ns())
    block_id = "0x" + hashlib.blake2b(raw.encode(), digest_size=32).hexdigest()
    blocks[block_id] = {"block": {"protocolVersion": 2, "parents": [], "payload": body["payload"], "nonce": "0"},
                        "t": time.time()}
    return jsonify(blockId=block_id), 201


@app.get("/api/core/v2/blocks/<block_id>")
def get_block(block_id):
    b = blocks.get(block_id)
    return (jsonify(b["block"]), 200) if b else (jsonify(error={"code": "404"}), 404)


@app.get("/api/core/v2/blocks/<block_id>/metadata")
def get_meta(block_id):
    b = blocks.get(block_id)
    if not b:
        return jsonify(error={"code": "404"}), 404
    meta = {"blockId": block_id, "parents": [], "isSolid": True,
            "ledgerInclusionState": "noTransaction", "shouldPromote": False, "shouldReattach": False}
    if time.time() - b["t"] >= MILESTONE_DELAY:
        meta["referencedByMilestoneIndex"] = milestone_index(b["t"]) + 1
    return jsonify(meta)


@app.get("/api/core/v2/milestones/by-index/<int:index>")
def milestone(index):
    return jsonify(type=7, index=index, timestamp=int(START + index * MILESTONE_DELAY))


@app.get("/api/core/v2/info")
def info():
    return jsonify(name="mock-hornet", status={"isHealthy": True,
                                               "latestMilestone": {"index": milestone_index(time.time())}})


@app.post("/mock/tamper/<block_id>")
def tamper(block_id):
    """Demo helper: rewrite a block's data on the 'node' to show content_mismatch detection."""
    b = blocks.get(block_id)
    if not b:
        return jsonify(error="unknown block"), 404
    b["block"]["payload"]["data"] = "0x" + json.dumps({"tampered": True}).encode().hex()
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=14265)
