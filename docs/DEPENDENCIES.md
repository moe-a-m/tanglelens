# Dependencies

Versions are the ones installed in the images that ran against the real node on 2026-10-06.
Licences come from each package's installed metadata (`License-Expression`).

| Name | Version | Licence | Why |
|---|---|---|---|
| iotaledger/hornet (image) | 2.0 → HORNET 2.0.2, `sha256:01206f1b…` | Apache-2.0 (per iotaledger/hornet repo; not re-checked) | Tangle node named in the brief |
| iotaledger/inx-coordinator (image) | 1.0, `sha256:61ed1fc5…` | Apache-2.0 (per repo; not re-checked) | Milestones for the private tangle |
| iotaledger/inx-dashboard (image) | 1.0, `sha256:12c669cb…` | Apache-2.0 (per repo; not re-checked) | Node dashboard |
| postgres (image) | 16-alpine → 16.15 | PostgreSQL Licence | Parallel relational DB (recommended by the brief) |
| python (image) | 3.11-slim | PSF-2.0 | Base image for the services and tests |
| fastapi | 0.142.2 | MIT | Explorer REST API and OpenAPI docs |
| uvicorn[standard] | 0.54.0 | BSD-3-Clause | ASGI server |
| pydantic | 2.13.5 | MIT | Request validation (used directly: `Field(pattern=)`) |
| sqlalchemy | 2.1.3 | MIT | ORM; SQLite and PostgreSQL |
| psycopg[binary] | 3.3.6 | LGPL-3.0-only | PostgreSQL driver. Installed from PyPI at build time and used unmodified as a library; none of its code is copied into this repo |
| httpx | 0.28.1 | BSD-3-Clause | Hornet client in the explorer; `MockTransport` in tests |
| Flask | 3.1.3 | BSD-3-Clause | Messages API (same framework as upstream) |
| requests | 2.34.2 | Apache-2.0 | Messages API → Hornet / explorer (same as upstream) |
| pytest | 9.1.1 | MIT | Test runner (tests image only) |
| eclipse-mosquitto (image) | 2 → mosquitto 2.1.2, `sha256:38c0da4f…` | EPL-2.0 OR EDL-1.0 (Eclipse Mosquitto project; not re-checked from the image) | MQTT broker for UPV Idea #1 (DESIGN D12) |
| paho-mqtt | 2.1.0 | EPL-2.0 OR BSD-3-Clause | MQTT client in the Messages API (publish) and the explorer (subscribe, alerts) (DESIGN D12) |
