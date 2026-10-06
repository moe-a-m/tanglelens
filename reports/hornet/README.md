# Hornet evidence (P0)

Captured against the real private tangle: HORNET 2.0.2, network `private_tangle1`
(environment in `../env.txt`). Each `*.txt` file holds the exact curl command and the raw response.

- `20261006T152327Z/` — `scripts/capture_hornet.sh`: one block through its full lifecycle, plus negative cases
- `20261006T152415Z_timing/` — `scripts/measure_confirmation.py 20`: attach → milestone timing

## Findings

| # | Claim (CLAUDE.md §3) | Result | Evidence |
|---|---|---|---|
| H1 | Submit `POST /api/core/v2/blocks` → 201 `{"blockId": "0x…"}` (66 chars) | **verified** | `20261006T152327Z/submit.txt`, 20/20 in `timing.csv` |
| H2 | No client PoW needed | **verified**: the body has no nonce and the node fills in `"nonce":"0"`; `/info` lists `features:["pow"]`, `minPowScore:0` | `block.json`, `info.json` |
| H3 | `GET …/blocks/{id}` returns `payload.type` 5 with lowercase-hex `tag` and `data`, identical to what was sent | **verified** | `block.json` vs `submit_request_body.json` |
| H4 | Metadata fields | **corrected**. *Before* a milestone references the block: `blockId, parents, isSolid, shouldPromote, shouldReattach`, with **no `ledgerInclusionState`**. *After*: `blockId, parents, isSolid, referencedByMilestoneIndex, ledgerInclusionState:"noTransaction", whiteFlagIndex`, with **no `shouldPromote`/`shouldReattach`**. `conflictReason` was never seen (no conflicting block) | `metadata_immediate.json`, `metadata_referenced.json`, `poll.log` |
| H5 | Unknown block → 404 | **verified** for both `/metadata` and the block. Body: `{"error":{"code":"404","message":"Not Found, error: block not found: 0x…"}}` | `metadata_unknown.txt`, `block_unknown.txt` |
| H6 | Malformed (short) id → error | **corrected**: Hornet **zero-pads** `0x1234` to 32 bytes and answers 404 for that padded id, not 400. Only full 66-char ids may be sent to Hornet | `metadata_malformed.txt` |
| H7 | Tag ≤ 64 bytes | **verified**: 64 bytes → 201; 65 bytes → 400 `…tagged data tag: slice length is too long: slice (len 65) exceeds max length of 64…` | `submit_tag64.txt`, `submit_tag65.txt` |
| H8 | `GET /api/core/v2/milestones/by-index/{i}` has `timestamp` in Unix seconds | **verified** (`"timestamp":1791300208` = 2026-10-06T15:23:28Z). The milestone's `parents` include our block | `milestone_by_index.json` |
| H9 | `/api/core/v2/info` has `status.isHealthy` and `status.latestMilestone.index` | **verified** field names. Note: `isHealthy` is **false** and `GET /health` → **503** while milestones are issued every ~5 s. Cause unknown (single node with no peers is a guess, unverified) | `info.json`, `health.txt` |
| H10 | Attach → solid | ≤ 0.019 s (20/20) | `timing.csv` |
| H11 | Attach → milestone reference | min 0.256 s, median 3.307 s, mean 3.179 s, max 5.072 s (n=20, polled every 0.25 s, random 0–6 s spacing). Milestone interval ≈ 5 s (index 22 → 25 in 15 s) | `20261006T152415Z_timing/summary.txt` |
