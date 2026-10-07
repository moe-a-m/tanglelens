#!/usr/bin/env bash
# Demo for the pitch, against the REAL Hornet node: publish aeriOS-style trust messages, watch them
# become confirmed, search by the brief's three keys, follow a trace timeline, then prove tamper
# detection (and the alert it raises).
#
# Demo data is illustrative: the aeriOS docs publish no official Trust Manager message schema.
# Field names come from the Trust Manager docs; "self.reorquestration" and its message are the
# verbatim example from the UPV challenge slides (docs/references/aerios_trust_notes.md).
set -euo pipefail
API=${API:-http://localhost:5555}
EXP=${EXP:-http://localhost:${EXPLORER_PORT:-8090}}
NODE=${NODE:-iota-hornet}
RUN=$(date +%H%M%S)                  # makes this run's traces unique
IE1="domain-1-ie-1-$RUN" IE2="domain-1-ie-2-$RUN"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
publish() {   # publish TAG SOURCE TRACE MESSAGE_JSON -> prints blockId
  curl -s "$API/upload?node=$NODE" -H 'Content-Type: application/json' \
    -d "{\"tag\": \"$1\", \"source\": \"$2\", \"trace\": \"$3\", \"message\": $4}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["blockId"])'
}
count() { python3 -c 'import sys,json; print(json.load(sys.stdin)["total"])'; }
wait_stored() {   # the record reaches the explorer asynchronously (HTTP thread / MQTT): wait up to 10 s
  for _ in $(seq 1 40); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' "$EXP/api/messages/$1")" = 200 ] && return 0
    sleep 0.25
  done
  echo "  explorer has not stored $1 after 10 s; check 'make logs'" >&2; return 1
}

say "1. Publishing through the extended Messages API (same /upload contract as aeriOS)"
B1=$(publish trust.reliability aeriOS/self-awareness "$IE1" \
  '{"domain_name": "domain-1", "ie": "ie-1", "cpucores": 8, "currentcpuusage": 37.5, "ramcapacity": 16384, "availableram": 9120, "currentramusage": 44.3}')
B2=$(publish trust.score aeriOS/trust-manager "$IE1" \
  '{"domain_name": "domain-1", "ie": "ie-1", "trust_score": 0.82, "reliability": 0.86, "security": 0.79, "reputation": 0.80, "penalty": 0.0}')
B3=$(publish trust.security.alert aeriOS/self-security "$IE2" \
  '{"domain_name": "domain-1", "ie": "ie-2", "priority": 4}')
B4=$(publish trust.score aeriOS/trust-manager "$IE2" \
  '{"domain_name": "domain-1", "ie": "ie-2", "trust_score": 0.61, "reliability": 0.74, "security": 0.52, "reputation": 0.70, "penalty": 0.05}')
B5=$(curl -s "$API/upload?node=$NODE" -H 'Content-Type: application/json' \
  -d '{"tag": "self.reorquestration", "message": {"format": "I just need a valid JSON", "be_creative": true}}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["blockId"])')
printf '  %s  trust.reliability     (%s)\n  %s  trust.score           (%s)\n  %s  trust.security.alert  (%s)\n  %s  trust.score           (%s)\n  %s  self.reorquestration\n' \
  "$B1" "$IE1" "$B2" "$IE1" "$B3" "$IE2" "$B4" "$IE2" "$B5"

say "2. Verify the last trust score on demand, right after insertion"
echo "  (solid within ~20 ms; a milestone references it after 0.3-5 s, reports/hornet/README.md H11:"
echo "   'pending' if no milestone has arrived yet, otherwise already 'confirmed')"
wait_stored "$B4"
curl -s -X POST "$EXP/api/messages/$B4/verify" | python3 -c '
import sys,json; v=json.load(sys.stdin)["verification"]
print("  status:", v["status"], "| solid:", v["is_solid"], "| milestone:", v["milestone_index"], "| content match:", v["content_match"])'

say "3. After the next milestones (expect confirmed)"
sleep 8; curl -s "$EXP/api/stats"; echo
echo "  delivery path that arrived first (HTTP forward or MQTT, the other is a no-op):"
for B in $B1 $B2 $B3 $B4 $B5; do
  wait_stored "$B"
  curl -s "$EXP/api/messages/$B" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("   ", d["block_id"][:18]+"…", d["tag"], "->", d["received_via"])'
done

say "4. Search by the brief's three keys, plus metadata"
FROM=$(date -u -d '-2 minutes' +%Y-%m-%dT%H:%M:%SZ) TO=$(date -u -d '+1 minute' +%Y-%m-%dT%H:%M:%SZ)
echo "  block id  $B4            -> $(curl -s "$EXP/api/messages?block_id=$B4" | count)"
echo "  block id prefix ${B4:0:12}                -> $(curl -s "$EXP/api/messages?block_id=${B4:0:12}" | count)"
echo "  date      from=$FROM to=$TO -> $(curl -s "$EXP/api/messages?from=$FROM&to=$TO" | count)"
echo "  tag       trust.score                     -> $(curl -s "$EXP/api/messages?tag=trust.score&from=$FROM" | count) (this run)"
echo "  tag       trust*                          -> $(curl -s "$EXP/api/messages?tag=trust*&from=$FROM" | count) (this run)"
echo "  source    aeriOS/trust-manager            -> $(curl -s "$EXP/api/messages?source=aeriOS/trust-manager&from=$FROM" | count) (this run)"
echo "  text      be_creative                     -> $(curl -s "$EXP/api/messages?q=be_creative&from=$FROM" | count) (this run)"

say "5. Trace timeline for $IE2 (related events, each verified against its own block id)"
curl -s -X POST "$EXP/api/traces/$IE2/verify" | python3 -c '
import sys,json; t=json.load(sys.stdin)
print("  verified:", t["verified"], "| events:", t["events"], "| problems:", t["problems"])
for e in t["timeline"]:
    v=e["verification"]; print("  #%s %s %-22s %-10s milestone %s" % (e["seq"], e["submitted_at"], e["tag"], v["status"], v["milestone_index"]))'
echo "  open alerts: $(curl -s "$EXP/api/alerts?unacknowledged=true" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["open"], "-", ", ".join(sorted({a["kind"]+":"+a["tag"] for a in d["items"]})))')"

# Remember what step 6 needs, so the tamper can also be run on its own (make pitch-tamper)
printf 'B4=%s\nIE2=%s\nEXP=%s\n' "$B4" "$IE2" "$EXP" > "$(dirname "$0")/../.demo-state"
if [ "${STOP_BEFORE_TAMPER:-0}" = 1 ]; then
  say "Ready. Open $EXP (trace $IE2), then run: make pitch-tamper"
  exit 0
fi
"$(dirname "$0")/tamper.sh"

say "Open $EXP to browse, follow the trace $IE2 and inspect every message."
