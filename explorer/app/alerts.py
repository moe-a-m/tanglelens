"""Alerts for critical events (DESIGN D10).

integrity:   a check moved a message INTO content_mismatch / not_found / conflicting
application: an ingested message's tag matches ALERT_TAGS (comma list of fnmatch globs)
Delivery: the alerts table (REST + UI), MQTT topic aerios/explorer/alerts when MQTT is enabled (D12),
and an optional best-effort webhook (ALERT_WEBHOOK_URL).
"""
import fnmatch
import logging
import os
import threading

import httpx

from .db import Alert, Message, iso, utcnow

PROBLEMS = {"content_mismatch", "not_found", "conflicting"}
ALERT_TAGS = [p.strip() for p in os.getenv("ALERT_TAGS", "").split(",") if p.strip()]
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
log = logging.getLogger("explorer.alerts")


def tag_is_critical(tag: str, patterns: list[str] | None = None) -> bool:
    return any(fnmatch.fnmatchcase(tag, p) for p in (ALERT_TAGS if patterns is None else patterns))


def new_alert(msg: Message, kind: str, previous_status: str | None, detail: str | None) -> Alert:
    return Alert(created_at=utcnow(), kind=kind, status=msg.status, previous_status=previous_status,
                 message_id=msg.id, block_id=msg.block_id, tag=msg.tag, trace_id=msg.trace_id, detail=detail)


def to_dict(a: Alert) -> dict:
    return {"id": a.id, "created_at": iso(a.created_at), "kind": a.kind, "status": a.status,
            "previous_status": a.previous_status, "block_id": a.block_id, "tag": a.tag,
            "trace_id": a.trace_id, "detail": a.detail, "acknowledged_at": iso(a.acknowledged_at)}


def post_webhook(payload: dict) -> None:
    try:
        r = httpx.post(ALERT_WEBHOOK_URL, json=payload, timeout=3)
        log.info("alert %s sent to webhook (%s)", payload["id"], r.status_code)
    except httpx.HTTPError as e:
        log.warning("alert %s webhook failed: %s", payload["id"], e)


def notify(alert: Alert) -> None:
    """Called after the alert row is committed. Never raises, never blocks the caller."""
    log.warning("ALERT %s %s %s %s", alert.kind, alert.status, alert.block_id[:18], alert.detail or "")
    payload = to_dict(alert)
    from . import mqtt                      # local import: mqtt is optional and imports nothing from here
    mqtt.publish_alert(payload)
    if ALERT_WEBHOOK_URL:
        threading.Thread(target=post_webhook, args=(payload,), daemon=True).start()
