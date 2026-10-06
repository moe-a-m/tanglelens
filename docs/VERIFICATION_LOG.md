# Verification log

Every behaviour change to verification or ingest: what changed, why, the evidence, and the result on the real node.
Failed attempts stay in the log.

| Date (UTC) | Change | Why | Evidence | Result on the real node |
|---|---|---|---|---|
| 2026-10-06 15:30 | None: first run of the unmodified scaffold verifier on real Hornet 2.0.2 + PostgreSQL 16.15 | P1: check the scaffold against P0 evidence | `reports/demo/20261006T152950Z_demo_real.txt` (stamp approximate, see dir) | **pass**: 4/4 `confirmed` at ms 102; tag/source/q/date searches OK on Postgres (JSON, ILIKE, NULLS FIRST all OK); DB tamper → `content_mismatch` ("decoded message in the database differs") |
| 2026-10-06 15:30 | Observation (not a failure): demo step 2 printed `unverified`, never `pending` | Verifier loop runs every 3 s while milestone reference takes a median 3.3 s (H11), so the first automatic check often lands after the reference | same run | Demo now calls `POST /verify` right after upload; re-run showed `pending` (solid, no milestone, content match) → `confirmed` 8 s later |
