#!/usr/bin/env bash
# P0 evidence capture against a REAL Hornet node (CLAUDE.md §1.1, §11 P0).
# Submits one tagged-data block exactly like the upstream Messages API and saves, for every
# request, the exact command and the raw response (headers + body) under reports/hornet/.
# JSON bodies are also copied to tests/fixtures/hornet/ for the unit tests.
# Measures attach -> milestone-reference time by polling the block metadata.
#
# Usage: scripts/capture_hornet.sh            (HORNET=http://localhost:14265 by default)
set -euo pipefail
HORNET=${HORNET:-http://localhost:14265}
POLL_MAX=${POLL_MAX:-120}          # seconds to wait for a milestone reference
ROOT=$(cd "$(dirname "$0")/.." && pwd)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$ROOT/reports/hornet/$STAMP"
FIX="$ROOT/tests/fixtures/hornet"
mkdir -p "$OUT" "$FIX"

# capture NAME METHOD PATH [BODY]  -> writes $OUT/NAME.txt (command + raw response), $OUT/NAME.json (body)
capture() {
  local name=$1 method=$2 path=$3 body=${4:-}
  local args=(-sS -i -X "$method" "$HORNET$path" -H 'Accept: application/json')
  [[ -n $body ]] && args+=(-H 'Content-Type: application/json' --data-binary "$body")
  {
    echo "# captured: $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
    printf '# command: curl'; printf ' %q' "${args[@]}"; echo
    echo "# ---- raw response ----"
    curl "${args[@]}" || echo "# curl exit code $?"
  } > "$OUT/$name.txt"
  # body = everything after the first blank line of the response
  sed -n '/^# ---- raw response ----$/,$p' "$OUT/$name.txt" | tail -n +2 | tr -d '\r' \
    | awk 'f{print} /^$/{f=1}' > "$OUT/$name.json"
  echo "  $name: $(head -n 1 <(sed -n '/raw response/{n;p}' "$OUT/$name.txt") | tr -d '\r')"
}

field() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2], ""))' "$1" "$2"; }
hex() { printf '%s' "$1" | od -An -tx1 -v | tr -d ' \n'; }

echo "Hornet: $HORNET   output: $OUT"
capture info GET /api/core/v2/info

# Same encoding as upstream send_data.py: tag/data = "0x" + hex(utf-8), data = json.dumps(message)
TAG="veles.capture"
MSG=$(python3 -c 'import json; print(json.dumps({"probe": "capture_hornet", "stamp": "'"$STAMP"'"}))')
BODY=$(printf '{"protocolVersion": 2, "payload": {"type": 5, "tag": "0x%s", "data": "0x%s"}}' "$(hex "$TAG")" "$(hex "$MSG")")
echo "$BODY" > "$OUT/submit_request_body.json"

T0=$(date +%s.%N)
capture submit POST /api/core/v2/blocks "$BODY"
BLOCK=$(field "$OUT/submit.json" blockId)
[[ -n $BLOCK ]] || { echo "no blockId in submit response, see $OUT/submit.txt"; exit 1; }
echo "  blockId=$BLOCK"

capture metadata_immediate GET "/api/core/v2/blocks/$BLOCK/metadata"
capture block GET "/api/core/v2/blocks/$BLOCK"

# Poll until referencedByMilestoneIndex shows up; log every poll for the timing record
: > "$OUT/poll.log"
REF=""
while :; do
  NOW=$(date +%s.%N); EL=$(python3 -c "print(round($NOW-$T0,3))")
  M=$(curl -sS "$HORNET/api/core/v2/blocks/$BLOCK/metadata" -H 'Accept: application/json' || true)
  echo "$EL $M" >> "$OUT/poll.log"
  REF=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("referencedByMilestoneIndex",""))' "$M" 2>/dev/null || true)
  [[ -n $REF ]] && break
  python3 -c "import sys; sys.exit(0 if $EL < $POLL_MAX else 1)" || { echo "  not referenced after ${POLL_MAX}s"; break; }
  sleep 0.5
done
[[ -n $REF ]] && echo "  referenced by milestone $REF after ${EL}s (poll interval 0.5s)" | tee "$OUT/timing.txt"

capture metadata_referenced GET "/api/core/v2/blocks/$BLOCK/metadata"
[[ -n $REF ]] && capture milestone_by_index GET "/api/core/v2/milestones/by-index/$REF"

# Negative cases: unknown block id, malformed id, oversize tag (65 bytes)
capture metadata_unknown GET "/api/core/v2/blocks/0x$(printf '0%.0s' {1..64})/metadata"
capture block_unknown GET "/api/core/v2/blocks/0x$(printf '0%.0s' {1..64})"
capture metadata_malformed GET "/api/core/v2/blocks/0x1234/metadata"
LONGTAG=$(printf 'a%.0s' {1..65})
capture submit_tag65 POST /api/core/v2/blocks \
  "$(printf '{"protocolVersion": 2, "payload": {"type": 5, "tag": "0x%s", "data": "0x%s"}}' "$(hex "$LONGTAG")" "$(hex '{}')")"
TAG64=$(printf 'a%.0s' {1..64})
capture submit_tag64 POST /api/core/v2/blocks \
  "$(printf '{"protocolVersion": 2, "payload": {"type": 5, "tag": "0x%s", "data": "0x%s"}}' "$(hex "$TAG64")" "$(hex '{}')")"

for f in info submit metadata_immediate block metadata_referenced milestone_by_index metadata_unknown; do
  [[ -s $OUT/$f.json ]] && cp "$OUT/$f.json" "$FIX/$f.json"
done
echo "$BLOCK" > "$FIX/block_id.txt"
echo "done -> $OUT (fixtures refreshed in tests/fixtures/hornet/)"
