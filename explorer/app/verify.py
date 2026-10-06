"""
Verification of stored messages against the Tangle (Hornet 2.0 / Stardust REST API).

  GET /api/core/v2/blocks/{blockId}/metadata   -> solidity, milestone reference, inclusion state
  GET /api/core/v2/blocks/{blockId}            -> original block; payload.tag / payload.data (hex)
  GET /api/core/v2/milestones/by-index/{index} -> milestone timestamp (Tangle-attested time)

Status lifecycle:
  unverified -> pending (solid, not yet referenced by a milestone) -> confirmed
  terminal problems: content_mismatch, conflicting, not_found
  transient: not_solid, error   (retried by the background loop)
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

import httpx

from .db import Message, Validation, utcnow

HORNET_URL = os.getenv("HORNET_URL", "http://iota-hornet:14265")
log = logging.getLogger("explorer.verify")

RETRYABLE = {"unverified", "pending", "not_solid", "error"}


class Hornet:
    def __init__(self, base_url: str = HORNET_URL):
        self.client = httpx.Client(base_url=base_url, timeout=10,
                                   headers={"Accept": "application/json"})

    def _get(self, path: str) -> dict | None:
        r = self.client.get(path)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def info(self) -> dict | None:
        return self._get("/api/core/v2/info")

    def block_metadata(self, block_id: str) -> dict | None:
        return self._get(f"/api/core/v2/blocks/{block_id}/metadata")

    def block(self, block_id: str) -> dict | None:
        return self._get(f"/api/core/v2/blocks/{block_id}")

    def milestone_time(self, index: int) -> datetime | None:
        try:
            ms = self._get(f"/api/core/v2/milestones/by-index/{index}")
            ts = ms.get("timestamp") if ms else None
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None) if ts else None
        except (httpx.HTTPError, ValueError):
            return None


def _norm_hex(h: str | None) -> str:
    return (h or "").lower().removeprefix("0x")


def _decode(h: str | None) -> str | None:
    try:
        return bytes.fromhex(_norm_hex(h)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def sha256_hex(data_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(_norm_hex(data_hex))).hexdigest()


def compare_content(msg: Message, block: dict) -> tuple[bool, bool, list[str]]:
    """Compare everything the explorer stored with what the Tangle holds.
    Checks the exact bytes AND the human-readable copies, so tampering with
    either the hex or the decoded JSON in the database is detected."""
    payload = block.get("payload") or {}
    problems: list[str] = []

    if payload.get("type") != 5:
        problems.append(f"block payload type is {payload.get('type')}, expected 5 (tagged data)")

    chain_tag_hex, chain_data_hex = payload.get("tag"), payload.get("data")
    tag_match = _norm_hex(chain_tag_hex) == _norm_hex(msg.tag_hex) and _decode(chain_tag_hex) == msg.tag
    if not tag_match:
        problems.append(f"tag differs: tangle={_decode(chain_tag_hex)!r} stored={msg.tag!r}")

    data_match = _norm_hex(chain_data_hex) == _norm_hex(msg.data_hex)
    if not data_match:
        problems.append("raw data bytes differ from what was submitted")

    chain_text = _decode(chain_data_hex)
    try:
        chain_json = json.loads(chain_text) if chain_text is not None else None
    except ValueError:
        chain_json = None
    if chain_json != msg.payload:
        data_match = False
        problems.append("decoded message in the database differs from the Tangle copy")

    if chain_data_hex and sha256_hex(chain_data_hex) != msg.data_sha256:
        data_match = False
        problems.append("stored sha256 fingerprint differs from the Tangle data")

    return tag_match, data_match, problems


def verify_message(session, msg: Message, hornet: Hornet) -> Validation:
    v = Validation(message_id=msg.id, checked_at=utcnow())
    try:
        meta = hornet.block_metadata(msg.block_id)
        if meta is None:
            v.status, v.detail = "not_found", "Hornet has no block with this id"
        else:
            v.is_solid = bool(meta.get("isSolid"))
            v.referenced_by_milestone_index = meta.get("referencedByMilestoneIndex")
            v.ledger_inclusion_state = meta.get("ledgerInclusionState")

            block = hornet.block(msg.block_id)
            if block is None:
                v.status, v.detail = "not_found", "metadata exists but block body was not returned"
            else:
                v.tag_match, v.data_match, problems = compare_content(msg, block)
                if problems:
                    v.status, v.detail = "content_mismatch", "; ".join(problems)
                elif not v.is_solid:
                    v.status, v.detail = "not_solid", "block is not solid yet (missing past cone)"
                elif v.ledger_inclusion_state == "conflicting":
                    v.status, v.detail = "conflicting", meta.get("conflictReason")
                elif v.referenced_by_milestone_index is None:
                    v.status, v.detail = "pending", "solid, waiting for a milestone to reference it"
                else:
                    v.status = "confirmed"
                    v.detail = f"referenced by milestone {v.referenced_by_milestone_index}"
    except httpx.HTTPError as e:
        v.status, v.detail = "error", f"Hornet request failed: {e}"

    # Update the denormalised "latest state" on the message
    msg.status = v.status
    msg.last_checked_at = v.checked_at
    msg.check_count = (msg.check_count or 0) + 1
    if v.status != "error":
        msg.is_solid = v.is_solid
        msg.ledger_inclusion_state = v.ledger_inclusion_state
        msg.content_match = (v.tag_match and v.data_match) if v.tag_match is not None else None
        if v.referenced_by_milestone_index and v.referenced_by_milestone_index != msg.milestone_index:
            msg.milestone_index = v.referenced_by_milestone_index
            msg.milestone_time = hornet.milestone_time(v.referenced_by_milestone_index)

    session.add(v)
    session.commit()
    log.info("verified %s -> %s", msg.block_id[:18], v.status)
    return v
