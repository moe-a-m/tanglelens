"""
Eclipse aeriOS IOTA Messages API -- extended for the Advanced Explorer.

MODIFIED from eclipse-aerios/iota-messages-api@1ed089a (Apache-2.0, see LICENSE and ../NOTICE):
forwards accepted blocks to the explorer, adds optional "type"/"source", validates tag length,
adds blockId to the response and a /health route. Success status stays HTTP 200 as upstream.

Backward compatible with the original:  POST /upload?node=<hornet-host>
  body: {"tag": "...", "message": {...}}
New optional body fields (stored as explorer metadata, NOT written to the Tangle):
  "type":   message type, e.g. "trust.score" / "self.reorchestration"
  "source": producing component, e.g. "aeriOS/IE-3"

After Hornet accepts the block, the exact bytes that were sent (tag_hex, data_hex)
plus the blockId are forwarded to the explorer, so the explorer can later prove
the Tangle holds exactly what it stored.
"""
import codecs
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

EXPLORER_URL = os.getenv("EXPLORER_URL", "http://advanced-explorer:8090")
DEFAULT_NODE = os.getenv("HORNET_NODE", "iota-hornet")
FORWARD_RETRIES = int(os.getenv("FORWARD_RETRIES", "5"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("messages-api")
app = Flask(__name__)


def to_hex(text: str) -> str:
    return "0x" + codecs.encode(text, "utf-8").hex()


def forward_to_explorer(record: dict) -> None:
    """Forward with exponential backoff; never blocks or fails the upload itself.
    The explorer ingest is idempotent on block_id, so retries are safe."""
    delay = 0.5
    for attempt in range(1, FORWARD_RETRIES + 1):
        try:
            r = requests.post(f"{EXPLORER_URL}/api/ingest", json=record, timeout=5)
            if r.status_code < 300:
                log.info("forwarded %s to explorer (%s)", record["block_id"], r.status_code)
                return
            log.warning("explorer answered %s: %s", r.status_code, r.text[:200])
        except requests.RequestException as e:
            log.warning("explorer unreachable (attempt %d/%d): %s", attempt, FORWARD_RETRIES, e)
        time.sleep(delay)
        delay *= 2
    log.error("gave up forwarding %s; explorer can backfill via POST /api/ingest", record["block_id"])


@app.route("/upload", methods=["POST"])
def upload():
    node_host = request.args.get("node", DEFAULT_NODE)
    node = f"http://{node_host}:14265/api/core/v2/blocks"
    body = request.get_json(silent=True) or {}
    if "tag" not in body or "message" not in body:
        return jsonify(error="body must contain 'tag' and 'message'"), 400

    tag = body["tag"]
    message = json.dumps(body["message"])          # same encoding as the original API
    tag_hex, data_hex = to_hex(tag), to_hex(message)
    if len(tag.encode("utf-8")) > 64:
        return jsonify(error="tag must be at most 64 bytes (Stardust tagged-data limit)"), 400

    payload = {"protocolVersion": 2, "payload": {"type": 5, "tag": tag_hex, "data": data_hex}}
    submitted_at = datetime.now(timezone.utc).isoformat()
    try:
        resp = requests.post(node, json=payload, headers={"Accept": "application/json"}, timeout=30)
    except requests.RequestException:
        return "Hornet node not found, check that the Hornet node exists.\n", 400

    block_id = None
    try:
        block_id = resp.json().get("blockId")
    except ValueError:
        pass
    log.info("hornet %s -> %s block=%s", node_host, resp.status_code, block_id)

    if resp.status_code in (200, 201) and block_id:
        record = {
            "block_id": block_id,
            "tag": tag,
            "message": body["message"],
            "tag_hex": tag_hex,
            "data_hex": data_hex,
            "node": node_host,
            "submitted_at": submitted_at,
            "message_type": body.get("type"),
            "source": body.get("source"),
        }
        threading.Thread(target=forward_to_explorer, args=(record,), daemon=True).start()

    # Original response shape and HTTP 200 kept (upstream returns Flask's default 200 and
    # reports Hornet's status in the body), plus blockId for convenience. See docs/DESIGN.md D4.
    return jsonify(status_code=resp.status_code, return_payload=resp.text, blockId=block_id)


@app.route("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(port=5555, host="0.0.0.0")
