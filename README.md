# IOTA Advanced Explorer for Eclipse aeriOS

Veles Hack 2026, Challenge 2 (O-CEI): Trust Ledger Traceability.

An observability and traceability layer on top of the aeriOS private IOTA Tangle. Every message
published through the Messages API is also stored in a searchable PostgreSQL database, enriched
with human-readable metadata, and continuously verified against the Tangle through the Hornet API.
The Tangle stays the source of truth; the explorer makes it searchable and proves its copy is faithful.

```
 your app ──► Messages API (extended) ──► Hornet ──► Tangle
                     │                       ▲
                     │ forward (blockId,     │ GET block metadata  (solid? milestone?)
                     │ exact tag/data hex)   │ GET block           (same bytes?)
                     ▼                       │
              Advanced Explorer ─────────────┘
              REST API + web UI + PostgreSQL
```

## Components

| Path | What it is |
|---|---|
| `messages-api/` | The aeriOS IOTA Messages API, extended. Same `POST /upload?node=` contract; after Hornet accepts a block it forwards the blockId and the exact bytes sent to the explorer (background thread, retries with backoff, never fails the upload). Adds optional `type` and `source` fields and rejects tags over the 64-byte Stardust limit. |
| `explorer/` | FastAPI service: ingest, search, verification, web UI. PostgreSQL by default, SQLite for local runs. |
| `mock-hornet/` | Development stand-in for Hornet 2.0 implementing only the endpoints used. Not part of the solution. |
| `scripts/demo.sh` | End-to-end demo, including tamper detection. |

## Run it against the real private tangle

1. Start the aeriOS tangle (Linux or WSL2, inside the Linux filesystem rather than `/mnt/c`):
   ```bash
   git clone https://github.com/eclipse-aerios/iota-tangle && cd iota-tangle/docker/main
   sudo ./bootstrap.sh
   docker compose -f hornet-main.yaml up -d
   ```
   `bootstrap.sh` calls `docker-compose` (v1). On Compose v2 either install the shim or run
   `sed -i 's/docker-compose/docker compose/g' bootstrap.sh` first.
   Wait until the dashboard on http://localhost:31011 (admin/admin) shows milestones being issued.
2. Stop the original Messages API if it is running (it uses port 5555), then from this repo:
   ```bash
   docker compose up -d --build
   ```
3. Open http://localhost:8090 and run `./scripts/demo.sh`.

## Run it without the tangle (development)

```bash
docker compose -f docker-compose.mock.yml up -d --build   # fake Hornet + creates network iota-net
docker compose up -d --build
```

## REST API

Interactive docs: http://localhost:8090/docs

| Method and path | Purpose |
|---|---|
| `POST /api/ingest` | Called by the Messages API. Idempotent on `block_id`, so retries and backfills are safe. |
| `GET /api/messages` | Search. Filters: `block_id` (exact or prefix), `tag` (exact, or `trust*` for prefix), `from`, `to` (ISO 8601), `type`, `source`, `status` (comma-separated), `q` (free text in the message), `milestone`. Paging: `limit`, `offset`. `sort`: `-submitted_at`, `milestone_index`, `tag`. |
| `GET /api/messages/{block_id}` | Full record with verification history. |
| `POST /api/messages/{block_id}/verify` | Re-verify against Hornet now. |
| `GET /api/tags` | Tags with counts and last-seen time. |
| `GET /api/stats` | Counts per verification status. |
| `GET /api/health` | Explorer and Hornet node health. |

## How verification works

For each stored message the explorer calls:

1. `GET /api/core/v2/blocks/{blockId}/metadata` for `isSolid`, `referencedByMilestoneIndex` and `ledgerInclusionState`.
2. `GET /api/core/v2/blocks/{blockId}` and compares the on-chain `payload.tag` and `payload.data` with what it stored, at three levels: the exact hex bytes, the decoded JSON, and a SHA-256 fingerprint. Tampering with either the raw or the human-readable copy in the database is detected.
3. `GET /api/core/v2/milestones/by-index/{index}` to record the milestone timestamp, a Tangle-attested time for the message.

| Status | Meaning |
|---|---|
| `unverified` | Stored, not checked yet |
| `pending` | On the Tangle and solid, not yet referenced by a milestone |
| `not_solid` | Node has the block but not its full past cone yet |
| `confirmed` | Solid, milestone-referenced, contents identical |
| `content_mismatch` | Stored copy and Tangle differ (details say which field) |
| `not_found` | Hornet has no such block |
| `conflicting` | Ledger marks the block as conflicting |
| `error` | Hornet unreachable during the check |

A background loop rechecks `unverified`, `pending`, `not_solid` and `error` messages every few
seconds until they settle. A second loop re-audits all messages every 5 minutes, so tampering after
confirmation is still caught. Every check is appended to an audit trail (`validations` table), never
overwritten.

## Design decisions

- **Solid is not the same as confirmed.** A block is usually solid as soon as it is attached, but it
  only becomes final once a milestone references it. Reporting those separately is what makes the
  status trustworthy.
- **The Messages API forwards the exact bytes it sent**, so content verification compares like
  with like rather than re-encoding JSON (key order or whitespace changes would cause false mismatches).
- **Enrichment metadata (`type`, `source`, timestamps) lives only in the explorer**, so the
  on-chain payload format of aeriOS is unchanged and existing consumers keep working.
- **Explorer downtime never loses or blocks a message.** The upload succeeds regardless; forwarding
  retries, and ingest is idempotent for backfills.

## Configuration

| Variable | Service | Default |
|---|---|---|
| `EXPLORER_URL` | messages-api | `http://advanced-explorer:8090` |
| `HORNET_NODE` | messages-api | `iota-hornet` (used when `?node=` is omitted) |
| `DATABASE_URL` | explorer | `sqlite:///./explorer.db` (compose sets PostgreSQL) |
| `HORNET_URL` | explorer | `http://iota-hornet:14265` |
| `VERIFY_INTERVAL` / `AUDIT_INTERVAL` | explorer | `3` / `300` seconds |
| `EXPLORER_PORT` | compose, demo.sh | `8090` (host port of the explorer; set it if 8090 is taken, e.g. `EXPLORER_PORT=8091 docker compose up -d`) |
