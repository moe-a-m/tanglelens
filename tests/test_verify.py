"""Unit tests for compare_content / verify_message (CLAUDE.md §8, §10), no network.

Hornet responses come from real captures (tests/fixtures/hornet, see reports/hornet/README.md).
States never observed on the real node (isSolid false, conflicting) are derived from a real
capture by changing only the field under test; each such case says so.
"""
import copy
import json

import httpx
import pytest

from app.db import Message, SessionLocal, Validation
from app.verify import Hornet, compare_content, sha256_hex, verify_message
from conftest import load

BLOCK = load("block")
BLOCK_ID = load("submit")["blockId"]
META_PENDING = load("metadata_immediate")      # real: before milestone reference
META_CONFIRMED = load("metadata_referenced")   # real: after milestone reference
MILESTONE = load("milestone_by_index")
NOT_FOUND = load("metadata_unknown")


def hexs(text: str) -> str:
    return "0x" + text.encode().hex()


def make_message(session, **overrides) -> Message:
    tag_hex, data_hex = BLOCK["payload"]["tag"], BLOCK["payload"]["data"]
    text = bytes.fromhex(data_hex[2:]).decode()
    fields = dict(block_id=BLOCK_ID, tag=bytes.fromhex(tag_hex[2:]).decode(), tag_hex=tag_hex,
                  payload=json.loads(text), payload_text=text, data_hex=data_hex,
                  data_sha256=sha256_hex(data_hex), status="unverified")
    fields.update(overrides)
    m = Message(**fields)
    from app.db import utcnow
    m.submitted_at = m.received_at = utcnow()
    session.add(m)
    session.commit()
    return m


def fake_hornet(meta=META_CONFIRMED, block=BLOCK, milestone=MILESTONE, fail=None) -> Hornet:
    """Hornet client backed by httpx.MockTransport. meta/block None -> real 404 body.
    fail: an httpx exception to raise, or an int status for every request."""
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(fail, Exception):
            raise fail
        if isinstance(fail, int):
            return httpx.Response(fail, json={"error": {"code": str(fail), "message": "boom"}})
        path = request.url.path
        if path.endswith("/metadata"):
            body = meta
        elif "/milestones/by-index/" in path:
            body = milestone
        else:
            body = block
        return httpx.Response(404, json=NOT_FOUND) if body is None else httpx.Response(200, json=body)

    h = Hornet("http://hornet.test")
    h.client = httpx.Client(base_url="http://hornet.test", transport=httpx.MockTransport(handler))
    return h


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


# ---------- compare_content ----------
def test_identical_block_matches(session):
    m = make_message(session)
    assert compare_content(m, BLOCK) == (True, True, [])


def test_tag_changed_in_db(session):
    m = make_message(session, tag="other.tag", tag_hex=hexs("other.tag"))
    tag_ok, data_ok, problems = compare_content(m, BLOCK)
    assert (tag_ok, data_ok) == (False, True) and "tag differs" in problems[0]


def test_tag_text_changed_in_db_only(session):
    m = make_message(session, tag="other.tag")         # hex untouched, human-readable copy edited
    assert compare_content(m, BLOCK)[0] is False


def test_data_hex_changed_in_db(session):
    m = make_message(session, data_hex=hexs('{"probe": "forged"}'))
    _, data_ok, problems = compare_content(m, BLOCK)
    assert data_ok is False and "raw data bytes differ from what was submitted" in problems


def test_decoded_json_changed_in_db_only(session):
    m = make_message(session, payload={"probe": "forged"})
    _, data_ok, problems = compare_content(m, BLOCK)
    assert data_ok is False and problems == ["decoded message in the database differs from the Tangle copy"]


def test_sha256_changed_in_db_only(session):
    m = make_message(session, data_sha256="0" * 64)
    _, data_ok, problems = compare_content(m, BLOCK)
    assert data_ok is False and problems == ["stored sha256 fingerprint differs from the Tangle data"]


def test_payload_type_not_tagged_data(session):
    m = make_message(session)
    block = copy.deepcopy(BLOCK)
    block["payload"]["type"] = 6
    assert any("expected 5" in p for p in compare_content(m, block)[2])


def test_non_utf8_chain_data_is_a_mismatch_not_a_crash(session):
    m = make_message(session)
    block = copy.deepcopy(BLOCK)
    block["payload"]["data"] = "0xfffe00"
    _, data_ok, problems = compare_content(m, block)
    assert data_ok is False and problems


# ---------- verify_message: status semantics (§8) ----------
def test_confirmed_with_milestone_time(session):
    m = make_message(session)
    v = verify_message(session, m, fake_hornet())
    assert v.status == "confirmed" and v.referenced_by_milestone_index == META_CONFIRMED["referencedByMilestoneIndex"]
    assert m.milestone_index == MILESTONE["index"]
    assert m.milestone_time.isoformat() == "2026-10-06T15:23:28"    # 1791300208 from the real capture
    assert m.content_match is True and m.is_solid is True and m.ledger_inclusion_state == "noTransaction"


def test_pending_uses_real_pre_reference_metadata(session):
    """Real pre-reference metadata has no ledgerInclusionState at all (H4)."""
    assert "ledgerInclusionState" not in META_PENDING
    m = make_message(session)
    v = verify_message(session, m, fake_hornet(meta=META_PENDING))
    assert v.status == "pending" and v.ledger_inclusion_state is None and m.milestone_index is None


def test_not_solid(session):
    meta = dict(META_PENDING, isSolid=False)           # derived: never observed on the real node
    v = verify_message(session, make_message(session), fake_hornet(meta=meta))
    assert v.status == "not_solid"


def test_conflicting(session):
    meta = dict(META_CONFIRMED, ledgerInclusionState="conflicting", conflictReason=1)   # derived
    v = verify_message(session, make_message(session), fake_hornet(meta=meta))
    assert v.status == "conflicting"


def test_metadata_404_is_not_found(session):
    v = verify_message(session, make_message(session), fake_hornet(meta=None))
    assert v.status == "not_found"


def test_block_404_after_metadata_is_not_found(session):
    v = verify_message(session, make_message(session), fake_hornet(block=None))
    assert v.status == "not_found"


@pytest.mark.parametrize("meta", [dict(META_PENDING, isSolid=False),
                                  dict(META_CONFIRMED, ledgerInclusionState="conflicting"),
                                  META_PENDING, META_CONFIRMED])
def test_content_mismatch_takes_precedence(session, meta):
    m = make_message(session, payload={"probe": "forged"})
    assert verify_message(session, m, fake_hornet(meta=meta)).status == "content_mismatch"


@pytest.mark.parametrize("fail", [500, 503, httpx.ReadTimeout("timed out"), httpx.ConnectError("refused")])
def test_hornet_failure_is_error_and_keeps_last_known_state(session, fail):
    m = make_message(session)
    verify_message(session, m, fake_hornet())                       # confirmed first
    v = verify_message(session, m, fake_hornet(fail=fail))
    assert v.status == "error" and m.status == "error"
    assert m.is_solid is True and m.milestone_index == MILESTONE["index"] and m.content_match is True


def test_every_check_appends_a_validation_row(session):
    m = make_message(session)
    for meta in (META_PENDING, META_CONFIRMED, META_CONFIRMED):
        verify_message(session, m, fake_hornet(meta=meta))
    rows = session.query(Validation).filter_by(message_id=m.id).order_by(Validation.id).all()
    assert [r.status for r in rows] == ["pending", "confirmed", "confirmed"] and m.check_count == 3


# ---------- code review: malformed node responses ----------
def html_hornet():
    h = Hornet("http://hornet.test")
    h.client = httpx.Client(base_url="http://hornet.test", transport=httpx.MockTransport(
        lambda r: httpx.Response(200, text="<html>proxy error</html>")))
    return h


def test_non_json_hornet_body_is_error_not_crash(session):
    v = verify_message(session, make_message(session), html_hornet())
    assert v.status == "error" and "malformed" in v.detail


def test_non_hex_chain_data_is_error_not_crash(session):
    block = copy.deepcopy(BLOCK)
    block["payload"]["data"] = "0xZZ"
    v = verify_message(session, make_message(session), fake_hornet(block=block))
    assert v.status == "error" and "malformed" in v.detail      # node answered nonsense: not a verdict
