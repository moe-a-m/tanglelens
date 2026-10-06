# Design decisions

Each entry has a **basis**: (a) the brief, (b) Hornet/IOTA official docs, (c) aeriOS docs,
(d) a saved real node response under `reports/hornet/`, or (e) a test in this repo.
Entries without a basis are proposals and are not implemented.

| # | Decision | Basis | Status |
|---|---|---|---|
| D1 | Validate solidity with `GET /api/core/v2/blocks/{id}/metadata` | (a) brief, "Tangle message validation" | implemented in the scaffold; field names unverified (pending P0 capture) |
| D2 | Verify content with `GET /api/core/v2/blocks/{id}` and compare it with what was received | (a) brief, "Message content verification" | implemented in the scaffold; unverified |
| D3 | The Messages API forwards the exact `tag_hex`/`data_hex` it sent, so content checks compare raw bytes | (a) brief + CLAUDE.md §3 (re-encoding can reorder keys) | implemented in the scaffold |
| D4 | `/upload` keeps the upstream HTTP 200 on success; Hornet's status code stays in the body as `status_code` | upstream `send_data.py@1ed089a` returns Flask's default 200; the user's decision of 2026-10-06 | being implemented |
| D5 | Verifier retry interval and retry budget | must come from the attach → milestone timing (P0) | **open**, waiting on the measurement |
