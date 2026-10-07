# 5-minute final pitch: run sheet

Thu 08 Oct 2026, 09:30 UTC+2, Challenge 2 pitches (TangleLens is listed first). **Hard limit: 5 minutes.**
Deck: the Slides artifact (8 visible slides; 6 hidden backup slides at the end for questions).
Speaker notes on each slide hold the script below.

## Morning checklist (on the demo machine)

On this machine the explorer runs on port **8091**, so prefix the make targets with `EXPLORER_PORT=8091`.

| When | Do | Check |
|---|---|---|
| 08:30 | Tangle up: `cd iota-tangle/docker/main && docker compose -f hornet-main.yaml start` | `curl -s localhost:14265/api/core/v2/info` shows `latestMilestone.index` increasing |
| 08:35 | Stack up: `EXPLORER_PORT=8091 make up` | http://localhost:8091 loads, header says "Hornet HORNET reachable" |
| 09:15 | Fresh demo data: `EXPLORER_PORT=8091 make pitch-setup` (~45 s) | Ends with "Ready … then run: make pitch-tamper"; UI shows 5 confirmed messages |
| 09:20 | Browser on http://localhost:8091 at 125 % zoom; terminal in the repo with `EXPLORER_PORT=8091 make pitch-tamper` typed but **not run** | — |
| 09:20 | Fallback video open in a player, paused at 0:00: `docs/pitch/tanglelens_demo_fallback.mp4` | Plays |
| 09:25 | Deck in Present mode; Zoom: share the whole screen, so switching windows works | Notes visible on your side only |

If you need to run the demo again, run `make pitch-setup` again first (45 s). Running `pitch-tamper` twice is harmless: it raises no second alert.

## Script (300 s)

| Time | Slide | Say (short form; the full lines are in the speaker notes) |
|---|---|---|
| 0:00–0:15 | Cover | "ie-2's trust score is 0.61. Someone changes it to 0.95. Would anyone notice? With TangleLens: in seconds." |
| 0:15–0:40 | Problem | Tangle = immutable, but opaque: hex, 32-byte ids, no search, no receipt. |
| 0:40–1:20 | Architecture | The two apps the brief asks for; exact bytes forwarded over HTTP + MQTT; GET block metadata + GET block; Tangle stays the authority. "Let me show you." |
| 1:20–3:00 | Live demo (cue slide) | Browser: ie-2 trust score confirmed → trace verified → terminal `make pitch-tamper` → trace not verified, alert opens → click the red event → side by side, "Fields that differ: trust_score". **Max 100 s.** |
| 3:00–3:30 | Measured | Real node: 20 ms to solid, 3.3 s median to milestone, verifier every 3 s; two Hornet behaviours found by testing. |
| 3:30–4:10 | Beyond the brief | UPV ideas #3, #4, #1; outage tests: no record lost. |
| 4:10–4:40 | Quality | 115 tests, raw Hornet evidence, code review fixes tested, fresh clones. |
| 4:40–5:00 | Close | Repo, three commands, thank you. |

**If running long:** skip the Measured slide (saves 30 s). **If the demo fails:** play the fallback video (35 s) and narrate the same four steps.

## Likely questions (answers grounded in the repo)

- **How do you know a message is final, not just received?** Solid is not confirmed. A block counts as final only when a milestone references it (GET block metadata, `referencedByMilestoneIndex`). We measured 0.3–5.1 s on the real node (`reports/hornet/README.md`, H11).
- **What exactly is compared?** The stored tag and data against the block from GET block, at three levels: exact hex bytes, decoded JSON and a SHA-256 fingerprint. Editing either the raw or the readable copy is caught.
- **Why not put the metadata on-chain?** The aeriOS on-chain payload and the `/upload` contract stay unchanged, so existing aeriOS consumers keep working. Type, source and trace are explorer metadata.
- **What if the explorer misses a message?** HTTP forwarding retries; MQTT with a persistent session covers longer outages. We tested the explorer down for 25 s and the database down for 25 s, with no loss (`reports/mqtt/`). The honest limit: if the broker *and* the explorer are both down, a record is missed. A backfill from the Tangle is the next step.
- **Can someone tamper with the Tangle itself?** The Tangle is the authority: milestones are signed by the coordinator. TangleLens detects any divergence of its own copy from it.
- **conflicting / not_solid?** Never seen on a healthy single-node tangle (tagged data is `noTransaction`). They are covered by tests built from real responses.
- **Security?** There is no auth yet, and the broker runs without TLS: demo settings, stated in the README. Next steps: auth, TLS, multi-node peering, real coordinator keys.
- **Why PostgreSQL?** The brief recommends a relational DB: indexed search on block id, tag, date and trace, a JSON column for the message, and an append-only audit table.
- **How does it fit aeriOS?** Same `POST /upload` as the aeriOS Messages API; the Trust Manager is configured with an IOTA API URL, so its writes flow through it unchanged.
- **Scale?** It hasn't been load-tested. The verifier checks in batches of 50 every 3 s, and the audit loop re-checks the 1000 longest-unchecked messages every 5 minutes.
