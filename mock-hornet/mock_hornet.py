"""
Minimal stand-in for a Hornet 2.0 node: just the endpoints the explorer and Messages API use.
For local development only. Blocks become solid immediately and get referenced by a
milestone after MILESTONE_DELAY seconds, mimicking the pending -> confirmed lifecycle.
Response shapes follow real HORNET 2.0.2 captures (reports/hornet/README.md H1-H8).
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
PARENT = "0x" + "11" * 32


def not_found(block_id: str):
    return err(404, f"Not Found, error: block not found: {block_id}: code=404, message=Not Found")


def milestone_index(t: float) -> int:
    return int((t - START) // MILESTONE_DELAY) + 1


def err(code: int, message: str):
    return jsonify(error={"code": str(code), "message": message}), code


def norm_id(block_id: str) -> str:
    """Hornet zero-pads short ids to 32 bytes (H6)."""
    return "0x" + block_id.lower().removeprefix("0x").ljust(64, "0")[:64]


@app.post("/api/core/v2/blocks")
def submit():
    body = request.get_json()
    payload = body.get("payload") or {}
    if payload.get("type") != 5:
        return err(400, "only tagged data supported in mock")
    if len(payload.get("tag", "").removeprefix("0x")) // 2 > 64:   # H7
        return err(400, "invalid parameter, error: failed to attach block: ... slice length is too long: "
                        "exceeds max length of 64 : invalid block: code=400, message=invalid parameter")
    raw = json.dumps(body, sort_keys=True) + str(time.time_ns())
    block_id = "0x" + hashlib.blake2b(raw.encode(), digest_size=32).hexdigest()
    blocks[block_id] = {"block": {"protocolVersion": 2, "parents": [PARENT], "payload": body["payload"], "nonce": "0"},
                        "t": time.time()}
    return jsonify(blockId=block_id), 201


@app.get("/api/core/v2/blocks/<block_id>")
def get_block(block_id):
    block_id = norm_id(block_id)
    b = blocks.get(block_id)
    return (jsonify(b["block"]), 200) if b else not_found(block_id)


@app.get("/api/core/v2/blocks/<block_id>/metadata")
def get_meta(block_id):
    block_id = norm_id(block_id)
    b = blocks.get(block_id)
    if not b:
        return not_found(block_id)
    # H4: before a milestone reference there is no ledgerInclusionState; after it,
    # shouldPromote/shouldReattach disappear and whiteFlagIndex appears.
    if time.time() - b["t"] < MILESTONE_DELAY:
        return jsonify(blockId=block_id, parents=[PARENT], isSolid=True, shouldPromote=False, shouldReattach=False)
    return jsonify(blockId=block_id, parents=[PARENT], isSolid=True,
                   referencedByMilestoneIndex=milestone_index(b["t"]) + 1,
                   ledgerInclusionState="noTransaction", whiteFlagIndex=0)


@app.get("/api/core/v2/milestones/by-index/<int:index>")
def milestone(index):
    return jsonify(type=7, index=index, timestamp=int(START + index * MILESTONE_DELAY))


@app.get("/api/core/v2/info")
def info():
    return jsonify(name="mock-hornet", version="mock", status={"isHealthy": True,
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
