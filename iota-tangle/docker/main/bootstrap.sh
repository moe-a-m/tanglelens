#!/bin/bash
# MODIFIED for veles-c2-advanced-explorer (from eclipse-aerios/iota-tangle@7803e5d, Apache-2.0):
# replaced the Compose v1 "docker-compose" command with Compose v2 "docker compose". No other change.

if [[ "$OSTYPE" != "darwin"* && "$EUID" -ne 0 ]]; then
  echo "Please run as root or with sudo"
  exit
fi

# Cleanup if necessary
if [ -d "privatedb" ] || [ -d "snapshots" ]; then
  ./cleanup.sh
fi

# Create snapshot
mkdir -p snapshots/hornet
if [[ "$OSTYPE" != "darwin"* ]]; then
  chown -R 65532:65532 snapshots
fi
docker compose -f startup.yaml run create-snapshots

# Prepare database directory for hornet
mkdir -p privatedb/hornet
mkdir -p privatedb/state
if [[ "$OSTYPE" != "darwin"* ]]; then
  chown -R 65532:65532 privatedb
fi

# Bootstrap network (create hornet database, create genesis milestone, create coo state)
docker compose -f startup.yaml run bootstrap-network

if [[ "$OSTYPE" != "darwin"* ]]; then
  chown -R 65532:65532 snapshots
fi
