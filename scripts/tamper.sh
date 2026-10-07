#!/usr/bin/env bash
# Step 6 of the demo on its own: inflate ie-2's trust score in the explorer's database, then verify
# against the Tangle. Uses the block and trace saved by the last demo run (.demo-state).
set -euo pipefail
STATE="$(dirname "$0")/../.demo-state"
[ -f "$STATE" ] || { echo "No demo state: run 'make demo' or 'make pitch-setup' first." >&2; exit 1; }
# shellcheck disable=SC1090
. "$STATE"
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "6. Someone inflates ie-2's trust score in the explorer's database (0.61 -> 0.95)..."
docker exec explorer-db psql -U explorer -q -c \
  "update messages set payload='{\"domain_name\": \"domain-1\", \"ie\": \"ie-2\", \"trust_score\": 0.95, \"reliability\": 0.74, \"security\": 0.52, \"reputation\": 0.70, \"penalty\": 0.05}'::json where block_id='$B4'"
curl -s -X POST "$EXP/api/messages/$B4/verify" | python3 -c '
import sys,json; d=json.load(sys.stdin)
print("  status:", d["verification"]["status"]); print("  why:   ", d["history"][0]["detail"])'
curl -s "$EXP/api/traces/$IE2" | python3 -c '
import sys,json; t=json.load(sys.stdin); print("  trace", t["trace_id"], "verified:", t["verified"], "| problems:", t["problems"])'
curl -s "$EXP/api/alerts?limit=1" | python3 -c '
import sys,json; a=json.load(sys.stdin)["items"][0]; print("  newest alert:", a["kind"], a["previous_status"], "->", a["status"], "on", a["block_id"][:18]+"…")'

