# Verification log

Every behaviour change to verification or ingest: what changed, why, the evidence, and the result on the real node.
Failed attempts stay in the log.

| Date (UTC) | Change | Why | Evidence | Result on the real node |
|---|---|---|---|---|
| 2026-10-06 15:30 | None: first run of the unmodified scaffold verifier on real Hornet 2.0.2 + PostgreSQL 16.15 | P1: check the scaffold against P0 evidence | `reports/demo/20261006T152950Z_demo_real.txt` | **pass**: 4/4 `confirmed` at ms 102; tag/source/q/date searches OK on Postgres (JSON, ILIKE, NULLS FIRST all OK); DB tamper → `content_mismatch` ("decoded message in the database differs") |
| 2026-10-06 15:30 | Observation (not a failure): demo step 2 printed `unverified`, never `pending` | Verifier loop runs every 3 s while milestone reference takes a median 3.3 s (H11), so the first automatic check often lands after the reference | `reports/demo/20261006T153054Z_demo_real.txt` | Demo now calls `POST /verify` right after upload; re-run showed `pending` (solid, no milestone, content match) → `confirmed` 8 s later |
| 2026-10-06 15:35 | Ingest rejects `block_id` not matching `^0x[0-9a-f]{64}$` (HTTP 422) | Hornet zero-pads short ids instead of rejecting them (H6), so a malformed id would be checked against a different block and shown as `not_found` | `reports/hornet/20261006T152327Z/metadata_malformed.txt`; manual check: `0x1234` → 422, uppercase → 422, valid → 201 (pytest to follow in P2) | Before: `0x1234` → 201 (stored). After: 422. Explorer rebuilt and running against the real node |
