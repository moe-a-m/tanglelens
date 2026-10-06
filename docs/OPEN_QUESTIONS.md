# Open questions

| # | Question | Ask whom | Status / answer (source, date) |
|---|---|---|---|
| 1 | Submission deadline is "07 Oct 2026, 14:59" on TAIKAI. In which time zone? | Organizers (TAIKAI/Discord) | Open. Assuming the stricter 14:59 CEST until confirmed. |
| 2 | Judging criteria | Organizers | Open. The user is gathering this from TAIKAI/Discord. |
| 3 | Submission format (repo link, video, slides?) | Organizers | Open. The user is gathering this from TAIKAI/Discord. |
| 4 | Do existing aeriOS callers depend on `/upload` returning HTTP 200? | User | Answered by the user on 2026-10-06: keep upstream 200; Hornet's code stays in the body as `status_code`. |
| 5 | Port 8090 is already used by another service on the dev machine (freshrss). The explorer's host port needs to be configurable. | — | Make it configurable via `EXPLORER_PORT` (default stays 8090). |
