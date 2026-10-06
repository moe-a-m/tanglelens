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
   - **Traces (UPV Idea #3):** an optional `trace` id groups the events of one flow, IE or sensor.
   - **Incident Explorer (UPV Idea #4):** each trace is a chronological timeline with every event
     verified against its own block id. Alerts fire when a message stops matching the Tangle, or
     when a critical tag (`*.alert`) arrives. They show in a UI banner and can go to a webhook.
   - **MQTT (UPV Idea #1):** the Messages API also publishes every record to a broker. The explorer
     subscribes with a persistent session, so a record still arrives after an explorer outage
     longer than the HTTP retry window (tested live). Alerts are published as a live feed.

```
 aeriOS component ──► Messages API (extended) ──► Hornet ──► Tangle   (authoritative)
                        │            │                 ▲
          HTTP forward  │            │ MQTT publish    │ GET /blocks/{id}/metadata  solid? milestone? conflicting?
          (blockId +    │            ▼                 │ GET /blocks/{id}           same bytes?
           exact hex)   │      Mosquitto broker        │ GET /milestones/by-index   Tangle-attested time
                        │      aerios/iota/blocks      │
                        ▼            │ (persistent     │
                   Advanced Explorer ◄─  session)      │
                   REST API · web UI · PostgreSQL ─────┘
                   messages · validations (audit) · traces/timeline · alerts ──► UI banner, webhook,
                                                                                 MQTT aerios/explorer/alerts
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
- **Tests:** 115 automated tests pass on both SQLite and PostgreSQL. The verification unit tests
  use real Hornet responses as fixtures. A live smoke test (`make smoke-real`) runs three messages
  end to end on the real node. All summaries are saved in `reports/tests/`.
- **Clean clone:** a fresh clone ran the stack, the tests, the smoke test and the demo
  (`reports/clean_clone/`).

## 4. Live demo (about 4 minutes)

Before going on stage: the tangle is up (`curl -s localhost:14265/api/core/v2/info` shows milestones increasing), `make up`, browser on http://localhost:8090.

| Step | Say | Do / show |
|---|---|---|
| 1 | "aeriOS components (Self-Awareness, Trust Manager, Self-Security) publish through the unchanged Messages API. One field, `trace`, groups the events of one IE." | `make demo` step 1: five uploads, each prints a block id |
| 2 | "Solid is not final. This block is on the Tangle but no milestone has referenced it yet." | Step 2: on-demand verify prints `pending` (or `confirmed` if a milestone already arrived; the window is ≤ 5 s) |
| 3 | "Seconds later a milestone references it: confirmed, with a Tangle-attested time." | Step 3: all `confirmed`. In the UI, open a message: checklist, milestone and time, history *Awaiting milestone → Confirmed* |
| 4 | "Search by what humans know: block id, date, tag, plus source and text." | Step 4 counts. In the UI: a block-id prefix, a date range, tag `trust*` |
| 4b | "Every record also travels over MQTT: a live feed, and a second path that survives explorer downtime." | In a second terminal: `make mqtt-watch` shows the block records and alerts as they happen. Step 3 prints which path stored each message |
| 5 | "Related events become a verified timeline. A security alert from Self-Security raised an alert as soon as it arrived." | Step 5: the trace timeline, every event checked against its own block id. In the UI: the alerts banner, then the trace link → timeline |
| 6 | "Now someone inflates ie-2's trust score in the explorer's database, 0.61 → 0.95." | Step 6: **Content mismatch** ("decoded message in the database differs from the Tangle copy"), the trace flips to *not verified*, a new integrity alert appears in the banner. Open the message: stored copy and Tangle copy side by side, "Fields that differ: **trust_score**" |
| 7 | "The Tangle stays the authority. The explorer makes it readable, and it can't be quietly falsified." | Point at the raw hex and SHA-256 in the detail view |

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
- Delivery isn't fully durable. MQTT covers explorer outages, but if the broker *and* the explorer
  are both unreachable, a message is on the Tangle but missing from the explorer. There is no
  backfill from the Tangle yet; idempotent ingest makes it safe to add.
- The MQTT broker runs with demo settings (anonymous, no TLS).
- Single-node tangle with the upstream default keys (public). Hornet reports `isHealthy: false` there
  although milestones flow; we don't depend on it.
- `conflicting` and `not_solid` never occur on a healthy single-node tangle. They are covered by
  tests built from real responses, not observed live.
