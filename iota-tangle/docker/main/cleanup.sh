#!/bin/bash
# MODIFIED for veles-c2-advanced-explorer (from eclipse-aerios/iota-tangle@7803e5d, Apache-2.0):
# replaced the Compose v1 "docker-compose" command with Compose v2 "docker compose". No other change.

if [[ "$OSTYPE" != "darwin"* && "$EUID" -ne 0 ]]; then
  echo "Please run as root or with sudo"
  exit
fi

docker compose -f hornet-main.yaml down --remove-orphans
docker compose -f startup.yaml down --remove-orphans

rm -Rf privatedb
rm -Rf snapshots