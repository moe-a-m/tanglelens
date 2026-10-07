# IOTA Advanced Explorer — common tasks. The tangle itself is started separately (README, step 1).
SHELL        := /bin/bash
.SHELLFLAGS  := -o pipefail -c
COMPOSE      := docker compose
RUN          := $(COMPOSE) --profile test run --rm --no-deps
PG_TEST_URL  := postgresql+psycopg://explorer:explorer@explorer-db:5432/explorer_test
STAMP        := $(shell date -u +%Y%m%d)_$(shell git rev-parse --short HEAD 2>/dev/null || echo nogit)

.PHONY: up up-mock down test test-sqlite test-postgres smoke-real e2e-mock demo pitch-setup pitch-tamper logs reset-db mqtt-watch

up:            ## explorer + Postgres + Messages API on the real tangle's network (iota-net)
	$(COMPOSE) up -d --build

up-mock:       ## development only: fake Hornet on its own network (iota-mock-net), then the stack
	$(COMPOSE) -f docker-compose.mock.yml up -d --build
	HORNET_NETWORK=iota-mock-net $(COMPOSE) up -d --build

down:
	$(COMPOSE) down
	-$(COMPOSE) -f docker-compose.mock.yml down

test: test-sqlite test-postgres   ## unit + API contract + Messages API tests, saved to reports/tests/

test-sqlite:
	$(COMPOSE) --profile test build tests
	$(RUN) tests pytest -q -rA | tee reports/tests/$(STAMP)_sqlite.txt

test-postgres:  ## needs the explorer-db container (make up)
	$(COMPOSE) up -d explorer-db
	$(RUN) -e TEST_DATABASE_URL=$(PG_TEST_URL) tests pytest -q -rA | tee reports/tests/$(STAMP)_postgres.txt

smoke-real:    ## live test against the running stack + REAL Hornet; records in reports/smoke/
	$(RUN) tests pytest -q -rA -m live | tee reports/tests/$(STAMP)_smoke_real.txt

e2e-mock:      ## same live test, but against the mock (make up-mock first)
	HORNET_NETWORK=iota-mock-net $(RUN) -e SMOKE_TIMEOUT=30 tests pytest -q -rA -m live | tee reports/tests/$(STAMP)_e2e_mock.txt

demo:
	./scripts/demo.sh

pitch-setup:   ## before a live pitch: fresh DB, publish + confirm the demo messages, stop before tampering
	$(MAKE) reset-db
	sleep 5
	STOP_BEFORE_TAMPER=1 ./scripts/demo.sh

pitch-tamper:  ## the one live step: inflate ie-2's trust score in the DB and verify against the Tangle
	./scripts/tamper.sh

mqtt-watch:    ## live MQTT feed: block records from the Messages API and alerts from the explorer
	docker exec -it mqtt-broker mosquitto_sub -h localhost -t 'aerios/#' -v

logs:
	$(COMPOSE) logs -f --tail=100

reset-db:      ## wipe the explorer database (Tangle data is untouched)
	$(COMPOSE) stop advanced-explorer
	$(COMPOSE) exec explorer-db psql -U explorer -c "drop schema public cascade; create schema public;"
	$(COMPOSE) start advanced-explorer
