# Dependencies

| Name | Version | Licence | Why |
|---|---|---|---|
| iotaledger/hornet (image) | 2.0 → HORNET 2.0.2, sha256:01206f1ba89c… | Apache-2.0 (to verify) | Tangle node named in the brief |
| iotaledger/inx-coordinator (image) | 1.0 | Apache-2.0 (to verify) | Milestones for the private tangle |
| iotaledger/inx-dashboard (image) | 1.0 | Apache-2.0 (to verify) | Node dashboard |
| postgres (image) | 16-alpine | PostgreSQL licence | Parallel relational DB (recommended by the brief) |
| python (image) | 3.11-slim | PSF | Base image for the explorer and the Messages API |
| fastapi, uvicorn, sqlalchemy, psycopg[binary], httpx | unpinned in the scaffold → pin in P1 | MIT / BSD / MIT / LGPL-3.0 / BSD (to verify) | Explorer service |
| Flask, requests | unpinned in the scaffold → pin in P1 | BSD-3 / Apache-2.0 | Messages API (same libraries as upstream) |
