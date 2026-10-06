# Pitch: IOTA Advanced Explorer for Eclipse aeriOS

## 1. Problem

Eclipse aeriOS writes trust-relevant events to a private IOTA Tangle so that they are immutable.
But the Tangle offers little to *look at*: blocks are hex payloads addressed by 32-byte ids, there is
no search by tag or date, and nothing tells an operator whether a message they think was recorded
really is on the ledger, final, and unchanged. (Challenge brief, "Context & Motivation".)

## 2. What we built

Two applications plus a database, exactly as the brief asks:

1. **Messages API (extended)**: the aeriOS upstream API with the same `POST /upload?node=` contract and
   HTTP 200 response. After Hornet accepts a block, it forwards the block id **and the exact bytes it
   sent** to the explorer, in the background with retries, so an explorer outage never fails an upload.
2. **Advanced Explorer**: a FastAPI service with a PostgreSQL "parallel database" and a web UI.
   - Stores each message with human-readable, searchable metadata: decoded tag and JSON, type,
     source, submit time, milestone index and milestone time.
   - Searches by **block id (or prefix), date range and tag (or prefix)**, plus type, source,
     status, free text and milestone.
   - **Validates** every block with Hornet's GET block metadata (solid? referenced by a milestone?
     conflicting?).
   - **Verifies content** with Hornet's GET block, comparing the exact hex bytes, the decoded JSON
     and a SHA-256 fingerprint.
   - Keeps an append-only audit trail of every check and re-audits all messages every 5 minutes.

```
 aeriOS component ──► Messages API ──► Hornet ──► Tangle   (authoritative)
                          │                ▲
                          │ blockId +      │ GET /blocks/{id}/metadata  → solid / milestone / conflicting
                          │ exact hex      │ GET /blocks/{id}           → same bytes?
                          ▼                │ GET /milestones/by-index   → Tangle-attested time
                    Advanced Explorer ─────┘
                    REST API · web UI · PostgreSQL (messages + validations audit trail)
```

## 3. Why you can trust it (verified, not assumed)

- Everything ran against the **real aeriOS private tangle (HORNET 2.0.2)**, not a mock.
  Every Hornet endpoint, field and status code we rely on is backed by a saved raw response
  (`reports/hornet/README.md`).
- **Two Hornet behaviours we found by testing, not from docs:**
  - Metadata has *no* `ledgerInclusionState` until a milestone references the block.
  - Hornet *zero-pads* a short block id instead of rejecting it, so the explorer only accepts
    full ids.
- **Measured timing:** blocks are solid within 20 ms and milestone-referenced after 0.3–5.1 s
  (median 3.3 s, n = 20). The verifier interval (3 s) and retry budget are set from that
  measurement.
- **Tests:** 58 automated tests pass on both SQLite and PostgreSQL. The verification unit tests
  use real Hornet responses as fixtures. A live smoke test (`make smoke-real`) runs three messages
  end to end on the real node. All summaries are saved in `reports/tests/`.
- **Clean clone:** a fresh clone ran the stack, the tests, the smoke test and the demo
  (`reports/clean_clone/`).

## 4. Live demo (about 3 minutes)

Before going on stage: the tangle is up (`curl -s localhost:14265/api/core/v2/info` shows milestones increasing), `make up`, browser on http://localhost:8090.

| Step | Say | Do / show |
|---|---|---|
| 1 | "An aeriOS component publishes events through the unchanged Messages API." | `make demo` step 1: four uploads, each prints a block id |
| 2 | "Solid is not final. Here is a block that is on the Tangle but not yet referenced by a milestone." | Step 2: on-demand verify prints `pending` (or `confirmed` if a milestone already arrived; the window is ≤ 5 s) |
| 3 | "A few seconds later a milestone references it: confirmed, with a Tangle-attested time." | Step 3: stats show all `confirmed`. In the UI, open a message: the checklist, the milestone with its time, and the history *Awaiting milestone → Confirmed* |
| 4 | "Search by what humans know: tag, source, text, time." | Step 4 counts. In the UI: tag `trust*`, a block-id prefix, a date range |
| 5 | "Now someone edits the explorer's copy in the database." | Step 5 changes one field in Postgres directly, then re-verifies: **Content mismatch**, "decoded message in the database differs from the Tangle copy". Show it red in the UI |
| 6 | "The Tangle stays the authority: the explorer can't be quietly falsified, and neither can it lie about the ledger." | Point at the raw hex and SHA-256 in the detail view |

Fallback if the network or tangle fails on stage: the screenshots in `docs/screenshots/` and the saved runs in `reports/demo/`.
The development mock is **not** used in the demo. If it ever has to be, say so on screen.

## 5. Design decisions (full list with bases: `docs/DESIGN.md`)

- **Solid ≠ confirmed.** These are separate states, because finality comes from milestones.
- **Exact bytes forwarded.** Content checks compare like with like. Re-encoding JSON would cause
  false mismatches.
- **Three-level comparison** (hex, decoded JSON, SHA-256), so tampering with either the raw or the
  readable copy is caught.
- **Enrichment stays off-chain.** `type`/`source` live in the explorer only; the on-chain payload and
  the `/upload` contract are unchanged for existing aeriOS consumers.
- **Append-only audit trail** and periodic re-audit, so later tampering is still detected.
- **Idempotent ingest** on block id, so retries are always safe.

## 6. Limitations (honest list)

- No authentication on the explorer (local demo).
- Forwarding is best effort: if the explorer is down longer than the retry window (~15 s), the
  message is on the Tangle but missing from the explorer. A durable outbox or backfill is the next
  step; idempotent ingest makes either safe.
- Single-node tangle with the upstream default keys (public). Hornet reports `isHealthy: false` there
  although milestones flow; we don't depend on it.
- `conflicting` and `not_solid` never occur on a healthy single-node tangle. They are covered by
  tests built from real responses, not observed live.
