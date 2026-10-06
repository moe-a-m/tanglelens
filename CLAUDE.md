# CLAUDE.md — Veles Hack 2026, Challenge 2 (O-CEI): Trust Ledger Traceability

You are working as a senior backend engineer with solid distributed-ledger knowledge
(IOTA Stardust block model, Hornet node REST API, milestones and solidity, tagged-data
payloads) and practical experience shipping small, well-tested Python services with
Docker Compose and PostgreSQL. Your job is to finish, harden and demo the **IOTA Advanced
Explorer**: an observability, search and integrity-verification layer on top of the
Eclipse aeriOS private IOTA Tangle, and to get it submitted before the hackathon deadline.

Facts below are tagged by where they come from:
- **[brief]** — `docs/references/Challenge_2_-_O-CEI.pdf`, the official challenge brief.
- **[site]** — the TAIKAI event page, read 2026-10-06.
- **[repo]** — the upstream aeriOS repos, read 2026-10-06 at
  `eclipse-aerios/iota-tangle@7803e5d` and `eclipse-aerios/iota-messages-api@1ed089a`.
- **[scaffold]** — behaviour of the code already in this repo, tested **only against
  `mock-hornet`**, never against a real Hornet node or PostgreSQL. Treat as unverified.
- **[hypothesis]** — believed from general IOTA/Hornet knowledge, **not yet checked**.
  Must be confirmed against the running node before anything depends on it.

---

## 1. Non-negotiable working rules

1. **Verify, don't assume.** Every claim about Hornet's behaviour (endpoint paths, status
   codes, JSON field names, timing from attach to milestone reference) is established by a
   real request against the running node, saved under `reports/hornet/` as the exact
   command plus the raw response. Never state a field name or status code you have not seen
   in a saved response.
2. **Never write code from memory.** Before using any third-party API (FastAPI, Pydantic,
   SQLAlchemy 2.x, psycopg 3, httpx, Flask, requests, pytest, Docker Compose, Hornet REST):
   - check the installed version (`pip show <pkg>`, `docker compose version`,
     `docker image inspect iotaledger/hornet:2.0`);
   - read the signature or docs for that exact version
     (`python -c "import inspect, pkg; print(inspect.signature(pkg.fn))"`, `--help`,
     the Hornet 2.0 / Stardust API spec, or a saved real response);
   - if the docs and your expectation disagree, the docs win. Note the source in the commit.
3. **Do not invent design.** Every non-obvious design decision (status semantics, what
   counts as "content matches", retry policy, schema choices) has an entry in
   `docs/DESIGN.md` with its basis, one of: (a) the brief, (b) Hornet/IOTA official docs,
   (c) aeriOS docs (links in §4), (d) a saved real node response, (e) a test in this repo.
   No basis → don't implement it; propose it to the user instead.
4. **Document and trace.** Every behaviour change to verification or ingest gets a row in
   `docs/VERIFICATION_LOG.md`: what changed, why, the evidence (saved response / test name),
   and the result on the real node. Failed attempts stay in the log.
5. **Tests: record passes and failures.** `pytest -q` runs before every commit; save the
   summary (`pytest -q -rA > reports/tests/<date>_<sha>.txt`). A failing test is never
   deleted to make the suite green; fix it or mark `xfail` with a reason and a line in
   `docs/OPEN_QUESTIONS.md`.
6. **Small commits, one concern each.** Conventional-commit style
   (`feat(explorer): …`, `fix(verify): …`, `test: …`, `docs: …`, `chore(compose): …`).
   Never mix a refactor with a behaviour change. Never commit secrets, databases, tangle
   state or snapshots (`.gitignore`: `*.db`, `.env`, `privatedb/`, `snapshots/`,
   `reports/hornet/*.bin`).
7. **Respect upstream licences.** Both aeriOS repos are **Apache-2.0** [repo]. Keep their
   `LICENSE`, add a `NOTICE` entry, and state at the top of every modified upstream file
   that it was modified and how. Every new dependency is recorded in `docs/DEPENDENCIES.md`
   (name, pinned version, licence, why) before it is added.
8. **The demo must run from a clean clone.** A judge with Linux (or WSL2), Docker and the
   README must be able to run the stack and the demo script. Every commit keeps this true.
9. **Time is the binding constraint.** Submission closes **07 Oct 2026, 14:59** [site]
   (time zone not shown on the page; confirm on TAIKAI/Discord and record it in
   `docs/OPEN_QUESTIONS.md`). A working, verified mandatory scope beats unfinished extras.
10. **When unsure, stop and ask the user.** Especially for anything touching submission,
    changes to the upstream Messages API contract, or scope beyond the brief.

---

## 2. The challenge (verified facts)

- **Goal [brief]:** build an *IOTA Advanced Explorer* that presents Tangle messages in a
  structured, human-readable way, enriched with metadata and validation, for messages
  produced by components of the Eclipse aeriOS Meta-OS.
- **At least two applications [brief]:**
  1. a component that creates and submits messages to the Tangle via the **Hornet API**;
     the existing aeriOS IOTA Messages API may be the starting point;
  2. the Advanced Explorer: observability, persistence, search and validation.
- **Mandatory functionality [brief]:**
  - **Messages API integration** — extend or modify it so every message submitted to the
    Tangle is also forwarded to the explorer for processing and persistence.
  - **Parallel database** — a relational DB is recommended; alternatives need justification.
    Stored records enrich the original message with human-readable, searchable metadata
    (timestamps, event tags, identifiers, message type, other context).
  - **Retrieval and search** — a REST API supporting at minimum search by
    **message/block identifier, date, and tag**.
  - **Tangle validation** — for each `blockId`, verify the block is **valid and solid**
    using Hornet's **GET block metadata** endpoint.
  - **Content verification** — retrieve the original block with Hornet's **GET block**
    endpoint and compare its contents with what the explorer received.
- **Principle [brief]:** the Tangle remains the authoritative source; the explorer is a
  more accessible, verified representation of it.
- **Environment [brief]:** Docker + Docker Compose; **Linux required** (WSL on Windows).
- **Judging criteria and submission format: not stated in the brief.** Find out from
  TAIKAI / Discord / mentors before building extras; record the answer with its source in
  `docs/OPEN_QUESTIONS.md`.

---

## 3. Domain framing (verify each against the real node)

- **Block shape [repo]:** the upstream Messages API posts to
  `http://<node>:14265/api/core/v2/blocks` a body
  `{"protocolVersion": 2, "payload": {"type": 5, "tag": "0x…", "data": "0x…"}}`,
  where `tag` and `data` are hex of UTF-8 text and `data` is `json.dumps(message)`.
  Type 5 is a Stardust *tagged data* payload [verified H3, `reports/hornet/README.md`].
- **Submit response [verified H1]:** HTTP 201 with `{"blockId": "0x…"}` (32-byte id,
  66 hex chars with prefix).
- **Metadata [corrected H4]:** `GET /api/core/v2/blocks/{blockId}/metadata`. Before a milestone
  reference: `blockId, parents, isSolid, shouldPromote, shouldReattach`, with **no
  `ledgerInclusionState`**. After: `referencedByMilestoneIndex`, `ledgerInclusionState`
  (`noTransaction` for tagged data), `whiteFlagIndex`, and `shouldPromote`/`shouldReattach`
  are gone. `conflicting`/`conflictReason` not observed. Unknown id → 404 [H5]. A **short or
  malformed id is zero-padded by Hornet** (→ 404 for the padded id), so only full 66-char
  ids may be sent [H6].
- **Solid ≠ confirmed.** A block can be solid (its past cone is known) before any milestone
  references it. The explorer reports these as separate states (§8). Measure on the real
  node how long attach → milestone reference takes and record it; the background
  verification interval and retry budget must be set from that measurement, not guessed.
  **Measured [H10, H11]:** solid ≤ 0.02 s; referenced after 0.26–5.07 s (median 3.3 s, n=20);
  milestone interval ≈ 5 s.
- **Milestone time [verified H8]:** `GET /api/core/v2/milestones/by-index/{index}` returns
  the milestone with a `timestamp` (Unix seconds). This gives a Tangle-attested time.
- **Node info [verified H9]:** `GET /api/core/v2/info` exposes `status.isHealthy` and
  `status.latestMilestone.index`. On this single-node tangle `isHealthy` is **false** and
  `/health` returns 503 while milestones flow normally, so never gate verification on it.
- **Tag limit [verified H7]:** tagged-data `tag` is at most 64 bytes; Hornet answers 400
  for 65 bytes.
- **PoW [verified H2]:** `minPowScore: 0`; the node accepts blocks without client-side PoW.
- **Content comparison must be like-for-like.** Re-encoding JSON on the explorer side can
  change key order or whitespace and produce false mismatches. The Messages API therefore
  forwards the **exact hex it sent**, and verification compares raw bytes, decoded JSON and
  a SHA-256 fingerprint [scaffold]. Keep it that way.
- **aeriOS context:** read the aeriOS trust docs (§4) before inventing metadata fields;
  use the tag and message conventions they describe for realistic demo data.

---

## 4. Upstream components and references

| Component | Version / ref | Licence | Status |
|---|---|---|---|
| `eclipse-aerios/iota-tangle` (Docker private tangle) | `7803e5d` [repo] | Apache-2.0 | **use** — the brief's install guide |
| `eclipse-aerios/iota-messages-api` | `1ed089a` [repo] | Apache-2.0 | **extend** — our `messages-api/` is a modified copy |
| `iotaledger/hornet` | `2.0` image tag [repo] | Apache-2.0 [hypothesis] | **use** — the node the brief names |
| `iotaledger/inx-coordinator` | `1.0` [repo] | Apache-2.0 [hypothesis] | use (milestones) |
| `iotaledger/inx-dashboard` | `1.0` [repo] | Apache-2.0 [hypothesis] | use (dashboard on :31011, admin/admin) |
| PostgreSQL | `16-alpine` image | PostgreSQL licence | use (recommended by the brief) |
| IOTA SDK (`iotaledger/iota-sdk`) | — | Apache-2.0 | optional; the brief lists it, plain REST is enough |
| Any other IOTA network or stack version | — | — | **do not use**; the brief pins Hornet and the aeriOS tangle |

References to read (save copies or notes under `docs/references/`):
- Brief: `docs/references/Challenge_2_-_O-CEI.pdf`
- aeriOS trust docs: `https://docs.aeros-project.eu/en/latest/aaa_trust/trust/index.html`
  and `…/trust/iota.html`
- IOTA SDK wiki (legacy): `https://legacy.wiki.iota.org/iota-sdk/welcome/`
- Hornet: `https://github.com/iotaledger/hornet` (find the Stardust core REST API spec
  for the exact endpoints and fields used in §3)
- aeriOS demo video: `https://www.youtube.com/watch?v=6CIguTLz-Iw&t=24s`

---

## 5. Environment and local tangle setup

- Work **inside the Linux filesystem** (WSL2: `~/…`, not `/mnt/c/…`). `bootstrap.sh`
  `chown`s directories to `65532:65532` [repo], which fails on Windows-mounted paths.
- `bootstrap.sh` must run with `sudo` and calls `docker-compose` (v1) [repo]. On Compose v2,
  run `sed -i 's/docker-compose/docker compose/g' bootstrap.sh` or install the v1 shim.
  Record which one you used in the README.
- Bring-up sequence [repo]: `cd iota-tangle/docker/main && sudo ./bootstrap.sh &&
  docker compose -f hornet-main.yaml up -d`. Confirm milestones are being issued on the
  dashboard (`http://localhost:31011`) before any API work.
- The tangle compose creates network **`iota-net`** [repo]; our `docker-compose.yml`
  joins it as external.
- Ports in use: Hornet API **14265**, gossip 30506, INX 9029, dashboard 31011/31031,
  coordinator 6021, Hornet profiling 6011 [repo]; Messages API **5555**; explorer **8090**.
  Stop the original `iota-messages-api` container before starting ours (same port and name).
- Coordinator and dashboard keys in the repo are **public defaults** [repo]. Fine for a
  local demo; say so in the README and do not present them as a secure setup.
- Record the environment that produced every reported result in `reports/env.txt`
  (OS/WSL version, Docker and Compose versions, image digests, Python version).

---

## 6. Current state of the scaffold [scaffold]

Already in the repo, tested only against `mock-hornet` with SQLite:
- `messages-api/send_data.py` — upstream contract kept (`POST /upload?node=`); after a
  successful submit forwards `block_id`, `tag`, `message`, `tag_hex`, `data_hex`, `node`,
  `submitted_at`, optional `type`/`source` to `POST /api/ingest` in a background thread
  with exponential backoff. Rejects tags over 64 bytes. Returns `blockId` in the response.
- `explorer/` — FastAPI + SQLAlchemy: ingest (idempotent on `block_id`), search, detail,
  on-demand verify, tags, stats, health, a background verifier loop, a periodic re-audit
  loop, an append-only `validations` audit table, and a static web UI at `/`.
- `mock-hornet/` — dev stand-in for the 5 Hornet endpoints used, plus `/mock/tamper/{id}`.
- `scripts/demo.sh` — publishes messages, shows pending → confirmed, runs searches,
  tampers with Postgres and re-verifies.

Known gaps — work these before any new feature:
1. ~~Never run against real Hornet.~~ P0 done 2026-10-06: §3 verified/corrected (`reports/hornet/README.md`).
2. ~~Never run on PostgreSQL.~~ Demo and full suite pass on PostgreSQL 16.15 (`reports/tests/`).
3. ~~No pytest suite.~~ `tests/` (58 + live smoke test), run with `make test` / `make smoke-real`.
4. ~~No Makefile.~~ Done.
5. ~~Upload status 201.~~ Restored upstream 200 (DESIGN D4); tag pre-check removed (OPEN_QUESTIONS #9).
6. ~~UI date filters.~~ Labelled as UTC.
7. Partly mitigated: MQTT persistent session covers explorer outages beyond the HTTP retry window
   (D12, `reports/mqtt/`). Still no backfill from the Tangle; broker+explorer both down loses the record.
8. Explorer has no authentication. Acceptable for the demo; state it in the README.

---

## 7. Repository layout

```
messages-api/            # modified copy of eclipse-aerios/iota-messages-api (Apache-2.0)
explorer/app/            # FastAPI service: main.py (API), db.py (models), verify.py (Hornet + checks)
explorer/app/static/     # web UI (single index.html, no build step)
mock-hornet/             # dev-only Hornet stand-in — never used in the demo against judges without saying so
scripts/                 # demo.sh, capture_hornet.sh (saves real node responses), smoke_real.sh
tests/                   # pytest: unit (compare/verify), API contract, ingest idempotency, mock e2e
tests/fixtures/hornet/   # real Hornet responses captured in §3, used by unit tests
reports/hornet/          # saved real requests + responses (evidence for §3)
reports/tests/           # saved pytest summaries
docs/                    # DESIGN.md, VERIFICATION_LOG.md, DEPENDENCIES.md, OPEN_QUESTIONS.md, PITCH.md
docs/references/         # challenge brief, aeriOS doc notes, Hornet API notes
docker-compose.yml       # explorer + postgres + messages-api on external network iota-net
docker-compose.mock.yml  # mock hornet; creates iota-net for dev without the tangle
Makefile                 # make up | up-mock | down | test | smoke-real | demo | logs | reset-db
LICENSE, NOTICE          # Apache-2.0 obligations for the upstream code we modified
```

---

## 8. Verification semantics (the core spec — code, README and UI must agree)

| Status | Condition | Retried? |
|---|---|---|
| `unverified` | stored, not checked yet | yes |
| `pending` | metadata found, `isSolid` true, no `referencedByMilestoneIndex`, content matches | yes |
| `not_solid` | metadata found, `isSolid` false, content matches | yes |
| `confirmed` | solid, milestone-referenced, inclusion state not `conflicting`, content matches | re-audited |
| `content_mismatch` | tag or data differs at any level (hex, decoded JSON, SHA-256) | re-audited |
| `conflicting` | `ledgerInclusionState == "conflicting"` | re-audited |
| `not_found` | Hornet returns 404 for the block | re-audited |
| `error` | Hornet unreachable or non-404 error | yes |

Rules:
- Content mismatch takes precedence over every other state.
- Every check appends a row to `validations`; the message row holds only the latest state.
- An `error` check never overwrites the last known solidity/milestone fields.
- Retry interval and maximum retry count come from the attach → milestone timing measured
  in §3, recorded in `docs/DESIGN.md`.
- Any change to this table updates `verify.py`, the README table, the UI labels and the
  tests in the same commit.

---

## 9. API contract

Keep these stable; any change updates the README, the OpenAPI docs (`/docs`) and tests:
- `POST /upload?node=` (Messages API) — upstream body `{"tag", "message"}` plus optional
  `type`, `source`.
- `POST /api/ingest` — idempotent on `block_id`.
- `GET /api/messages` — filters `block_id` (exact or prefix), `tag` (exact or `prefix*`),
  `from`, `to` (ISO 8601, UTC), `type`, `source`, `status` (comma list), `q`, `milestone`;
  `limit`, `offset`, `sort`.
- `GET /api/messages/{block_id}`, `POST /api/messages/{block_id}/verify`,
  `GET /api/tags`, `GET /api/stats`, `GET /api/health`.

The three search keys the brief makes mandatory — **block id, date, tag** — must each have
a passing test and a line in the demo.

---

## 10. Testing protocol

- **Unit (no network):** `compare_content` and `verify_message` using fixtures captured from
  the real node in §3. Cases: identical block; tag changed; data hex changed; decoded JSON
  changed in DB only; SHA-256 changed in DB only; payload type not 5; non-UTF-8 data;
  metadata 404; metadata without milestone; `isSolid` false; `conflicting`; Hornet 5xx;
  timeout.
- **API contract:** each search filter alone and combined; prefix id shorter than 6 chars;
  date bounds inclusive; paging totals; ingest twice → one row, `created: false`.
- **Mock end-to-end:** Messages API → mock Hornet → explorer; pending → confirmed;
  explorer down during upload → upload still succeeds, forward retried.
- **Real-node smoke (`make smoke-real`):** submit 3 messages, wait, assert all reach
  `confirmed`; assert content verification passes; save responses to `reports/hornet/`.
- **PostgreSQL:** run the API contract tests against the compose Postgres, not only SQLite.
- Save every run's summary to `reports/tests/`.

---

## 11. Roadmap (each phase ends with tests green and docs updated)

**P0 – real tangle up and evidence captured (do first).** Bring up the tangle (§5).
Write `scripts/capture_hornet.sh` that submits one block and saves the raw responses of
submit, metadata (before and after milestone reference), block, milestone-by-index and
info into `reports/hornet/` and `tests/fixtures/hornet/`. Measure attach → reference time.
Update every [hypothesis] in §3 to verified or corrected.

**P1 – scaffold on the real stack.** `docker compose up -d --build` against the real node
and Postgres. Fix every difference from P0 evidence in `verify.py`, one commit each, logged
in `docs/VERIFICATION_LOG.md`. Run `scripts/demo.sh` end to end.

**P2 – tests and Makefile.** §10 suites, `Makefile` targets, saved summaries.
Close known gaps 5 and 6 from §6.

**P3 – demo and submission assets.** README checked from a clean clone, screenshots,
`docs/PITCH.md` (problem, architecture, live demo steps, tamper demo, design decisions,
limitations), recorded demo video if the submission format needs one.

**P4 – extras, only if P0–P3 are done and judging criteria reward them.** Each needs a
`docs/DESIGN.md` entry with basis first. Candidates: durable outbox in the Messages API;
backfill/reconciliation of missed messages (first verify which Hornet endpoint, if any, can
list tagged-data blocks — do not assume one exists); CSV/JSON export of search results;
per-source statistics; basic auth on the explorer.

**Feature freeze:** stop feature work early enough on 07 Oct to leave time for the clean-clone
check and submission (agree the exact time with the user). Prefer a verified P0–P3 over a
half-built P4.

---

## 12. Libraries

Use few, well-maintained open-source libraries already in the scaffold: `fastapi`,
`uvicorn`, `pydantic`, `sqlalchemy` 2.x, `psycopg[binary]` 3, `httpx`, `flask`, `requests`,
`pytest`. Add only with a `docs/DEPENDENCIES.md` row (version, licence, why). Do not
hand-roll what these already do (HTTP retries in tests, JSON schema validation, DB pooling).
No frontend build tooling; the UI stays a single static HTML file.

---

## 13. Submission checklist

1. Submission format and judging criteria confirmed and recorded in `docs/OPEN_QUESTIONS.md`.
2. Public repository (or the format the organizers require) with `LICENSE` and `NOTICE`
   covering the modified Apache-2.0 upstream code.
3. Fresh clone on a clean Linux/WSL machine: tangle up → `docker compose up -d --build` →
   `scripts/demo.sh` passes; result saved in `reports/`.
4. README covers: purpose, architecture, setup gotchas (§5), commands, API reference,
   verification semantics (§8), design decisions, limitations (§6 gaps still open),
   upstream attributions.
5. Demo uses the **real** Hornet node. If the mock is ever shown, say so on screen.
6. Never submit or publish anything without the user's explicit go-ahead.

---

## 14. Definition of done for any task

- [ ] Claims about Hornet backed by saved real responses.
- [ ] APIs checked against installed versions / official docs.
- [ ] Design decision has a basis in `docs/DESIGN.md`.
- [ ] Behaviour change logged in `docs/VERIFICATION_LOG.md`, including failed attempts.
- [ ] `pytest` run and summary saved; new behaviour has tests.
- [ ] §8 status table, README, UI labels and tests all agree.
- [ ] Stack still runs from a clean clone; README updated if commands changed.
- [ ] One concern per commit; message explains *why*.
- [ ] New questions added to `docs/OPEN_QUESTIONS.md` (incl. ones for the organizers).
