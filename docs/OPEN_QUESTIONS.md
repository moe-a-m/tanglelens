# Open questions

| # | Question | Ask whom | Status / answer (source, date) |
|---|---|---|---|
| 1 | Submission deadline is "07 Oct 2026, 14:59" on TAIKAI. In which time zone? | Organizers (TAIKAI/Discord) | **Spain time** (user, 2026-10-06): 07 Oct 2026 14:59 CEST = **12:59 UTC**. |
| 2 | Judging criteria | Organizers | Open. The user is gathering this from TAIKAI/Discord. |
| 3 | Submission format (repo link, video, slides?) | Organizers | Open. The user is gathering this from TAIKAI/Discord. |
| 4 | Do existing aeriOS callers depend on `/upload` returning HTTP 200? | User | Answered by the user on 2026-10-06: keep upstream 200; Hornet's code stays in the body as `status_code`. |
| 5 | Port 8090 is already used by another service on the dev machine (freshrss). The explorer's host port needs to be configurable. | — | Make it configurable via `EXPLORER_PORT` (default stays 8090). |
| 6 | Which licence must the repository use? | Organizers | **Apache-2.0 is accepted** (Rafa Vaño, UPV, on Discord, 2026-10-06 16:18). The Rules say repos without the correct licence file are ineligible, so the root `LICENSE` is Apache-2.0. |
| 7 | Project category on TAIKAI | Organizers | **Select "Challenge 2"** as the project category (Rafa Vaño, UPV, on Discord, 2026-10-06). The user does this at submission. |
| 8 | Why is Hornet `isHealthy=false` / `/health` 503 on the single-node tangle while milestones flow? | Hornet docs/source | Open. Doesn't block anything: verification never depends on node health. The UI must not present it as "node down". |
