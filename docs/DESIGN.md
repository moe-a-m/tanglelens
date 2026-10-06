# Design decisions

Each entry has a **basis**: (a) the brief, (b) Hornet/IOTA official docs, (c) aeriOS docs,
(d) a saved real node response under `reports/hornet/`, or (e) a test in this repo.
Entries without a basis are proposals and are not implemented.

| # | Decision | Basis | Status |
|---|---|---|---|
| D1 | Validate solidity with `GET /api/core/v2/blocks/{id}/metadata` | (a) brief, "Tangle message validation" | implemented in the scaffold; field names verified/corrected in H4 (`reports/hornet/README.md`) |
| D2 | Verify content with `GET /api/core/v2/blocks/{id}` and compare it with what was received | (a) brief, "Message content verification"; (d) H3: the node returns the submitted hex unchanged | implemented in the scaffold |
| D6 | Ingest accepts only full lowercase 66-char block ids (`^0x[0-9a-f]{64}$`) | (d) H6 (Hornet zero-pads short ids) and H1 (Hornet returns lowercase 66-char ids) | implemented |
| D3 | The Messages API forwards the exact `tag_hex`/`data_hex` it sent, so content checks compare raw bytes | (a) brief + CLAUDE.md §3 (re-encoding can reorder keys) | implemented in the scaffold |
| D4 | `/upload` keeps the upstream HTTP 200 on success; Hornet's status code stays in the body as `status_code` | upstream `send_data.py@1ed089a` returns Flask's default 200; the user's decision of 2026-10-06 | implemented (62d6973) |
| D5 | Verifier loop every `VERIFY_INTERVAL`=3 s, at most `MAX_CHECKS`=60 checks (180 s) for retryable states | (d) H11: referenced after ≤ 5.07 s, milestone interval ≈ 5 s. 3 s < one milestone interval, so a block becomes `confirmed` ≤ ~8 s after attach; 180 s ≈ 35× the worst case observed | scaffold values kept, now with a basis |
