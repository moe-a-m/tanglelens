# Design decisions

Each entry has a **basis**: (a) the brief, (b) Hornet/IOTA official docs, (c) aeriOS docs,
(d) a saved real node response under `reports/hornet/`, or (e) a test in this repo.
Entries without a basis are proposals and are not implemented.

| # | Decision | Basis | Status |
|---|---|---|---|
| D1 | Validate solidity with `GET /api/core/v2/blocks/{id}/metadata` | (a) brief, "Tangle message validation" | implemented in the scaffold; field names verified/corrected in H4 (`reports/hornet/README.md`) |
| D2 | Verify content with `GET /api/core/v2/blocks/{id}` and compare it with what was received | (a) brief, "Message content verification"; (d) H3: the node returns the submitted hex unchanged | implemented in the scaffold |
| D6 | Ingest accepts only full lowercase 66-char block ids (`^0x[0-9a-f]{64}$`) | (d) H6 (Hornet zero-pads short ids) and H1 (Hornet returns lowercase 66-char ids) | implemented |
| D7 | `block_id` search filter: optional `0x` plus 6–64 hex chars, lowercased; 64 hex = exact match, fewer = prefix | (e) `tests/test_api.py`; CLAUDE.md §10 ("prefix id shorter than 6 chars"); the scaffold's own documented contract | implemented |
| D3 | The Messages API forwards the exact `tag_hex`/`data_hex` it sent, so content checks compare raw bytes | (a) brief + CLAUDE.md §3 (re-encoding can reorder keys) | implemented in the scaffold |
| D4 | `/upload` keeps the upstream HTTP 200 on success; Hornet's status code stays in the body as `status_code` | upstream `send_data.py@1ed089a` returns Flask's default 200; the user's decision of 2026-10-06 | implemented (62d6973) |
| D5 | Verifier loop every `VERIFY_INTERVAL`=3 s, at most `MAX_CHECKS`=60 checks (180 s) for retryable states | (d) H11: referenced after ≤ 5.07 s, milestone interval ≈ 5 s. 3 s < one milestone interval, so a block becomes `confirmed` ≤ ~8 s after attach; 180 s ≈ 35× the worst case observed | scaffold values kept, now with a basis |

## Beyond the mandatory scope (user decision, OPEN_QUESTIONS #11)

| # | Decision | Basis | Status |
|---|---|---|---|
| D8 | **Trace id (Idea #3).** Optional `trace` string (1–128 chars from `A-Za-z0-9._:-`, path-safe because it appears in `/api/traces/{id}`) on `/upload`, explorer-only metadata like `type`/`source`, forwarded as `trace_id`, indexed, and searchable (`GET /api/messages?trace=`). The on-chain payload and the upstream contract stay unchanged | (c) UPV slides p.6, Idea #3: "track messages that correspond to the same flow of events / user / IoT sensor"; same off-chain enrichment rule as `type`/`source` (README design decisions) | implemented |
| D9 | **Trace timeline (Idea #4).** `GET /api/traces` lists traces (count, first/last time, status counts). `GET /api/traces/{trace_id}` returns the events in chronological order (submit time), each with its block id, verification status, milestone and milestone time; `verified` is true only when every event is `confirmed`. `POST /api/traces/{trace_id}/verify` re-verifies every event against its block id now | (c) UPV slides p.6, Idea #4: "groups correlated events into a chronological timeline and verifies each one against its corresponding BlockID"; verification reuses D1/D2 unchanged | implemented; live: 3-event trace verified on the real node |
| D10 | **Alerts (Idea #4).** An `alerts` row is appended (never updated except `acknowledged_at`) when (a) a check moves a message *into* `content_mismatch`, `not_found` or `conflicting` from a different status (integrity alert; repeated audits with the same status do not repeat it), or (b) a message whose tag matches `ALERT_TAGS` (comma list, `prefix*` allowed, default empty) is ingested (application alert; *which* events are critical is left to configuration, not invented). Delivery: `GET /api/alerts` (`since_id` for polling), `POST /api/alerts/{id}/ack`, a UI banner, and an optional `ALERT_WEBHOOK_URL` (POST JSON, best effort, failures logged) | (c) UPV slides p.6, Idea #4: "real-time notifications or alerts when critical events occur"; problem statuses from §8 | planned |
| D11 | **Additive schema upgrade.** On startup, columns missing from existing tables are added with `ALTER TABLE … ADD COLUMN` (nullable), so an existing database keeps working after an upgrade. No other migration tooling | (e) test `test_startup_adds_missing_trace_column`; avoids a new dependency (rule 12) | implemented; verified on the running PostgreSQL |
