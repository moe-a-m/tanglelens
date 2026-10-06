import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from .db import Message, SessionLocal, init_db, utcnow
from .verify import RETRYABLE, Hornet, sha256_hex, verify_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("explorer")

VERIFY_INTERVAL = float(os.getenv("VERIFY_INTERVAL", "3"))     # seconds, for unconfirmed messages
AUDIT_INTERVAL = float(os.getenv("AUDIT_INTERVAL", "300"))     # seconds, full re-audit of confirmed ones
MAX_CHECKS = int(os.getenv("MAX_CHECKS", "60"))
hornet = Hornet()


# ---------- schemas ----------
# Full 32-byte id as Hornet returns it. Hornet zero-pads shorter ids instead of rejecting
# them (reports/hornet/README.md H6), so anything else would be verified against the wrong block.
BLOCK_ID_PATTERN = r"^0x[0-9a-f]{64}$"
# Trace ids appear in URL paths (/api/traces/{trace_id}), so keep them path-safe (DESIGN D8).
TRACE_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"


class IngestIn(BaseModel):
    block_id: str = Field(pattern=BLOCK_ID_PATTERN)
    tag: str
    message: Any
    tag_hex: str | None = None
    data_hex: str | None = None
    node: str | None = None
    submitted_at: datetime | None = None
    message_type: str | None = None
    source: str | None = None
    trace_id: str | None = Field(None, pattern=TRACE_PATTERN)


def _to_hex(text: str) -> str:
    return "0x" + text.encode("utf-8").hex()


def _naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def serialize(m: Message, with_history: bool = False) -> dict:
    out = {
        "block_id": m.block_id, "tag": m.tag, "message_type": m.message_type, "source": m.source,
        "node": m.node, "trace_id": m.trace_id, "message": m.payload, "data_sha256": m.data_sha256,
        "submitted_at": _iso(m.submitted_at), "received_at": _iso(m.received_at),
        "verification": {
            "status": m.status, "is_solid": m.is_solid, "content_match": m.content_match,
            "milestone_index": m.milestone_index, "milestone_time": _iso(m.milestone_time),
            "ledger_inclusion_state": m.ledger_inclusion_state,
            "last_checked_at": _iso(m.last_checked_at), "check_count": m.check_count,
        },
        "raw": {"tag_hex": m.tag_hex, "data_hex": m.data_hex},
    }
    if with_history:
        out["history"] = [{
            "checked_at": _iso(v.checked_at), "status": v.status, "is_solid": v.is_solid,
            "milestone_index": v.referenced_by_milestone_index,
            "ledger_inclusion_state": v.ledger_inclusion_state,
            "tag_match": v.tag_match, "data_match": v.data_match, "detail": v.detail,
        } for v in m.validations]
    return out


# ---------- background verification ----------
def _verify_batch(statuses: set[str] | None, limit: int = 50) -> int:
    with SessionLocal() as s:
        q = select(Message).order_by(Message.last_checked_at.asc().nullsfirst()).limit(limit)
        if statuses:
            q = q.where(Message.status.in_(statuses), Message.check_count < MAX_CHECKS)
        msgs = s.scalars(q).all()
        for m in msgs:
            verify_message(s, m, hornet)
        return len(msgs)


async def verifier_loop():
    while True:
        try:
            await asyncio.to_thread(_verify_batch, RETRYABLE)
        except Exception:
            log.exception("verifier loop failed")
        await asyncio.sleep(VERIFY_INTERVAL)


async def audit_loop():
    """Periodically re-verify everything, so later tampering with the DB copy is caught."""
    while True:
        await asyncio.sleep(AUDIT_INTERVAL)
        try:
            n = await asyncio.to_thread(_verify_batch, None, 1000)
            log.info("audit re-verified %d messages", n)
        except Exception:
            log.exception("audit loop failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    tasks = [asyncio.create_task(verifier_loop()), asyncio.create_task(audit_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="IOTA Advanced Explorer", version="1.0", lifespan=lifespan,
              description="Observability, search and integrity verification for aeriOS Tangle messages.")


# ---------- endpoints ----------
@app.post("/api/ingest", status_code=201)
def ingest(item: IngestIn):
    """Called by the Messages API after Hornet accepts a block. Idempotent on block_id."""
    text = json.dumps(item.message)                       # same encoding as the Messages API
    data_hex = item.data_hex or _to_hex(text)
    m = Message(
        block_id=item.block_id, tag=item.tag, tag_hex=item.tag_hex or _to_hex(item.tag),
        payload=item.message, payload_text=text, data_hex=data_hex, data_sha256=sha256_hex(data_hex),
        message_type=item.message_type, source=item.source, node=item.node, trace_id=item.trace_id,
        submitted_at=_naive_utc(item.submitted_at) or utcnow(), received_at=utcnow(), status="unverified",
    )
    with SessionLocal() as s:
        s.add(m)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            return {"block_id": item.block_id, "created": False}
    return {"block_id": item.block_id, "created": True}


@app.get("/api/messages")
def search(
    block_id: str | None = Query(None, pattern=r"^(0x)?[0-9a-fA-F]{6,64}$",
                                 description="exact id, or a prefix of at least 6 hex chars ('0x' optional)"),
    tag: str | None = Query(None, description="exact tag; end with * for prefix match"),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    type: str | None = None,
    source: str | None = None,
    trace: str | None = Query(None, description="trace id (exact), groups related events"),
    status: str | None = Query(None, description="comma-separated, e.g. pending,confirmed"),
    q: str | None = Query(None, description="free text inside the message body"),
    milestone: int | None = None,
    sort: str = Query("-submitted_at", pattern="^-?(submitted_at|milestone_index|tag)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conds = []
    if block_id:
        hex_id = "0x" + block_id.lower().removeprefix("0x")
        conds.append(Message.block_id == hex_id if len(hex_id) == 66 else Message.block_id.startswith(hex_id))
    if tag:
        conds.append(Message.tag.startswith(tag[:-1]) if tag.endswith("*") else Message.tag == tag)
    if date_from:
        conds.append(Message.submitted_at >= _naive_utc(date_from))
    if date_to:
        conds.append(Message.submitted_at <= _naive_utc(date_to))
    if type:
        conds.append(Message.message_type == type)
    if source:
        conds.append(Message.source == source)
    if trace:
        conds.append(Message.trace_id == trace)
    if status:
        conds.append(Message.status.in_([x.strip() for x in status.split(",")]))
    if q:
        conds.append(or_(Message.payload_text.ilike(f"%{q}%"), Message.tag.ilike(f"%{q}%")))
    if milestone is not None:
        conds.append(Message.milestone_index == milestone)

    col = getattr(Message, sort.lstrip("-"))
    order = col.desc() if sort.startswith("-") else col.asc()
    with SessionLocal() as s:
        total = s.scalar(select(func.count()).select_from(Message).where(*conds))
        rows = s.scalars(select(Message).where(*conds).order_by(order, Message.id.desc())
                         .limit(limit).offset(offset)).all()
        return {"total": total, "limit": limit, "offset": offset, "items": [serialize(m) for m in rows]}


def _get(s, block_id: str) -> Message:
    m = s.scalar(select(Message).where(Message.block_id == block_id))
    if not m:
        raise HTTPException(404, f"No message stored for block {block_id}")
    return m


@app.get("/api/messages/{block_id}")
def detail(block_id: str):
    with SessionLocal() as s:
        return serialize(_get(s, block_id), with_history=True)


@app.post("/api/messages/{block_id}/verify")
def verify_now(block_id: str):
    """Re-run solidity + content verification against Hornet right now."""
    with SessionLocal() as s:
        m = _get(s, block_id)
        verify_message(s, m, hornet)
        s.refresh(m)
        return serialize(m, with_history=True)


@app.get("/api/tags")
def tags():
    with SessionLocal() as s:
        rows = s.execute(select(Message.tag, func.count(), func.max(Message.submitted_at))
                         .group_by(Message.tag).order_by(func.count().desc())).all()
        return [{"tag": t, "count": c, "last_seen": _iso(ls)} for t, c, ls in rows]


@app.get("/api/stats")
def stats():
    with SessionLocal() as s:
        by_status = dict(s.execute(select(Message.status, func.count()).group_by(Message.status)).all())
        total = sum(by_status.values())
        return {"total": total, "by_status": by_status,
                "latest_milestone": s.scalar(select(func.max(Message.milestone_index)))}


@app.get("/api/health")
def health():
    try:
        info = hornet.info()
        node = {"reachable": True, "name": (info or {}).get("name"),
                "latest_milestone": ((info or {}).get("status") or {}).get("latestMilestone", {}).get("index"),
                "healthy": ((info or {}).get("status") or {}).get("isHealthy")}
    except Exception as e:  # noqa: BLE001
        node = {"reachable": False, "error": str(e)}
    return {"explorer": "ok", "hornet": node}


STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(STATIC / "index.html")
