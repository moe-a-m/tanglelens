#!/usr/bin/env bash
# Demo for the pitch: publish aeriOS-style messages, search them, then prove tamper detection.
set -euo pipefail
API=${API:-http://localhost:5555}
EXP=${EXP:-http://localhost:8090}
NODE=${NODE:-iota-hornet}

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "1. Publishing messages through the extended Messages API"
for ie in 1 2 3; do
  curl -s "$API/upload?node=$NODE" -H 'Content-Type: application/json' -d "{
    \"tag\": \"trust.score\", \"type\": \"trust.update\", \"source\": \"aeriOS/IE-$ie\",
    \"message\": {\"ie\": \"IE-$ie\", \"score\": 0.9$ie, \"window\": \"5m\"}}" | python3 -c 'import sys,json;print(" ", json.load(sys.stdin)["blockId"])'
done
BLOCK=$(curl -s "$API/upload?node=$NODE" -H 'Content-Type: application/json' -d '{
  "tag": "self.reorchestration", "type": "orchestration", "source": "aeriOS/HLO",
  "message": {"service": "svc-7", "action": "migrate", "from": "IE-2", "to": "IE-3"}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["blockId"])')
echo "  $BLOCK"

say "2. Right after insertion (expect pending: solid but not yet milestone-referenced)"
sleep 2; curl -s "$EXP/api/stats"; echo

say "3. After the next milestones (expect confirmed)"
sleep 12; curl -s "$EXP/api/stats"; echo

say "4. Search: tag prefix, source, free text, date range"
curl -s "$EXP/api/messages?tag=trust*" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("  tag=trust*      ->", d["total"])'
curl -s "$EXP/api/messages?source=aeriOS/IE-2" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("  source=IE-2     ->", d["total"])'
curl -s "$EXP/api/messages?q=migrate" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("  q=migrate       ->", d["total"])'
curl -s "$EXP/api/messages?from=$(date -u -d '-1 hour' +%Y-%m-%dT%H:%M:%SZ)" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("  last hour       ->", d["total"])'

say "5. Tamper with the explorer's copy in Postgres, then verify against the Tangle"
docker exec explorer-db psql -U explorer -q -c \
  "update messages set payload='{\"service\":\"svc-7\",\"action\":\"migrate\",\"from\":\"IE-2\",\"to\":\"IE-9\"}'::json where block_id='$BLOCK'"
curl -s -X POST "$EXP/api/messages/$BLOCK/verify" | python3 -c '
import sys,json; d=json.load(sys.stdin)
print("  status:", d["verification"]["status"]); print("  why:   ", d["history"][0]["detail"])'

say "Open $EXP to browse, filter and inspect every message."
