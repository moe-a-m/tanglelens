# aeriOS trust and IOTA: source notes

Facts only, quoted from the sources below. Anything that is not in a source is marked
**not stated**. Extrapolations are marked **[extrapolation]**.

## Sources (all read 2026-10-06)

- [S1] https://docs.aeros-project.eu/en/latest/aaa_trust/trust/index.html ("Trustworthiness")
- [S2] https://docs.aeros-project.eu/en/latest/aaa_trust/trust/iota.html ("aerOS IOTA")
- [S3] https://docs.aeros-project.eu/en/latest/aaa_trust/trust/calculator.html ("Trust Manager"), linked from S1
- [S4] Local PDF: `docs/references/IOTA Decentralized blockchain for the Cloud-Edge-IoT continuum.pdf`
  (UPV challenge slides, 10 pages; see section 5)

## 1. What publishes to the Tangle, and why

- Purpose [S1]: "The aerOS trustworthiness and decentralized trust management aim to evaluate the
  trust score of the domain's Infrastructure Elements (IEs) using trust monitor components and
  ensure secure information exchange through the IOTA distributed ledger technology."
- [S1]: "The IOTA mechanism securely handles trust information by using the Tangle, which allows
  for trustworthy data transactions between aerOS IEs. The trust profile is shared among all nodes
  within the Tangle, with the entry-point domain serving as the starting point of the Tangle network."
- [S2]: "IOTA is a core component used to share critical continuum-wide relevant information."
- **Trust Manager is the only component named as a writer.** Reliability flow, [S3]:
  1. "Self-Awareness collects resource usage data (e.g., CPU, memory) from the IE."
  2. "It updates the Orion Broker at a set interval."
  3. "Trust Manager retrieves the data periodically."
  4. "It uses the TOPSIS method to calculate scores and rankings."
  5. "Results are written back to Orion-LD and IOTA."
- Trust Manager config needs the IOTA endpoints [S3]: "orion_url, iota_api_url, and iota_node_ip:
  Ensure these values match your current cluster setup." `iota_api_url` suggests it writes via the
  Messages API (the "Custom API") rather than straight to Hornet. **[extrapolation]**; the S3 text
  does not say which.
- No other component (orchestrator HLO/LLO, Self-Security, Self-Healing) is said to write to
  IOTA in S1–S3. **Not stated.**

## 2. Concrete tag names, fields, types, frequency, payloads

- Upload format [S2], verbatim:
  ```
  curl --location 'http://API-IP:30635/upload?node=hornet-1' \
  --header 'Content-Type: application/json' \
  --data '{
     "tag": "whatever.tag.you.want",
     "message": {
        "Anything": "You want"
     }
  }'
  ```
- [S2]: "The contents need to be in JSON format with the two fields "tag" and "message". The
  contents of "message" can be whatever you want them to be."
- [S2]: "You can send the message to any hornet node, just replace the "…hornet-1" in the URL with
  either any other hornet node (e.g. hornet-4) or just input the IP of the hornet node in question."
- Tag style: the only example is `whatever.tag.you.want`, i.e. **dot-separated, lower case**.
  No real tag name used by aeriOS is given. **Concrete tags: not stated.**
- Message fields written by the Trust Manager to IOTA: **not stated.** The trust score structure
  is described [S3]: "The Trust Manager computes three sub-scores: Reliability Sub-score ...
  Security Sub-score ... Reputation Sub-score" and
  "TS = (Wrep × SBrep) + (Wsec × SBsec) + (Wrel × SBrel) − Penalty".
- Score range [S3]: "A higher score means a more trustworthy IE." Numeric range **not stated**
  (the `/calculate` example returns scores between 0 and 1, e.g. `0.7959914251761436`).
- Reliability inputs [S3], `[ReliabilityScore]` Orion-LD properties:
  `cpucores = 0.2`, `currentcpuusage = 0.2`, `ramcapacity = 0.1`, `availableram = 0.25`,
  `currentramusage = 0.25`.
- Config field names [S3]: `domain_name` ("Set this to your pilot's domain (same as used in
  Orion-LD)"), `scoreInterval` (minutes), `reliabilityInterval` (minutes), `reputationInterval`
  (days), `healthPenalty`, `ReliabilityWeight`, `SecurityWeight`, `ReputationWeight`,
  `priorityThreshold` ("Threshold at which a new trust score is recalculated due to security concerns").
- Frequency [S3]: "Trust scores are calculated periodically." Default interval values **not stated**.
- Message type field: **not stated** (our optional `type`/`source` fields are our own extension).

## 3. How aeriOS reads data back from the Tangle

- No read path is described in S1–S3. **Not stated.**
- Components that could serve reads [S2]: "inx-mqtt.yaml - extends the node endpoints to provide
  an Event API to listen to live changes happening in the Tangle." and "inx-poi.yaml - generate and
  verify Proof-of-Inclusion of blocks in the Tangle. Given a piece of data or transaction and the
  proof, you can verify whether it was included in the Tangle at any given time".
  (Neither is in the `eclipse-aerios/iota-tangle` Docker compose we run; check before relying on it.)

## 4. Terminology

- **IE (Infrastructure Element)** — used throughout S1/S3; [S3]: "monitoring and evaluating the
  trustworthiness of Infrastructure Elements (IEs)". Formal definition: **not stated** in S1–S3.
- **Domain** — [S3]: "calculate a trust score for all Infrastructure Elements within a domain";
  [S1]: "entry-point domain serving as the starting point of the Tangle network". Formal
  definition **not stated** in S1–S3.
- **Trust Manager** — [S3]: "integrates Orion Broker, Self-Awareness, Self-Security, and
  Self-Healing modules to calculate a trust score for all Infrastructure Elements within a domain";
  "a core component that assists the orchestrator in selecting the most trustworthy infrastructure elements."
- **Trust Monitoring / Trust Management component** — [S1]: "continuously evaluates the
  trustworthiness of individual Infrastructure Elements (IEs) ... works by collecting various
  attributes from each Infrastructure element (IE)."
- **Self-Awareness / Self-Security / Self-Healing** — [S3]: Self-Security "sends real-time alerts"
  and "provides historical security data"; Penalty is a "Deduction based on self-healing alerts frequency".
- **HLO / LLO** — **not mentioned** in S1–S3.
- **Custom API** — [S2] "With the Custom API installed you can upload a block into the Tangle";
  this is the IOTA Messages API (`iota_custom_api` package in S2's wget URL).

## 5. PDF [S4] (UPV slides, 10 pages; Cuñat Negueroles and Vaño Garcia)

- The **only concrete aeriOS-flavoured tag** in any source, p.8 (verbatim, typo kept):
  `{ "tag": "self.reorquestration", "message": { "format": "I just need a valid JSON",
  "be_creative": true } }`
- p.2: the Tangle "has all the information necessary to track messages and ensure traceability of payloads."
- p.3 diagram: Domain 1 and Domain 2, each with IEs running Hornet nodes; "Software calls API" →
  "New block is uploaded"; "Coordinator verifies messages"; "Verified messages are added to the ledger".
- p.4: "The versions of IOTA used here are the "Stardust" versions, latest official documentation
  will most likely not be compatible."
- p.6 Idea #3: "many sensors/users can insert messages in the Tangle ... track messages that
  correspond to the same flow of events / user / IoT sensor". Idea #4: "an Incident Explorer that
  reconstructs key trust-related events stored in the IOTA Tangle ... groups correlated events into a
  chronological timeline and verifies each one against its corresponding BlockID."
- p.6: "The jury will bear in consideration the level of complexity of the final product pitched on Thursday."
- Slide errata (do not copy): p.5 says the Hornet API is at `http://localhost:14625` (the compose
  port is 14265); p.8 lists `GET /api/core/v2/<block-id>` without the `/blocks/` segment (verified
  path: `/api/core/v2/blocks/{blockId}`, `reports/hornet/README.md`).
- The PDF names no message fields and no message types beyond the example above.

## 6. Implications for demo data

The sources give **no real production tag list or Trust Manager payload schema**. Grounded facts:
tags are dot-separated lower case (S2 `whatever.tag.you.want`, S4 `self.reorquestration`);
`message` is any JSON (S2); the Trust Manager writes trust-score results to IOTA (S3). Field names
below reuse S3 vocabulary; the exact payload shapes are **[extrapolation]**.

1. `self.reorquestration` / `{"format": "I just need a valid JSON", "be_creative": true}`:
   verbatim from S4 p.8. Use it unchanged as the "official example" message.
2. `trust.score` / `{"domain_name": "domain-1", "ie": "ie-1", "trust_score": 0.79,
   "reliability": 0.82, "security": 0.75, "reputation": 0.80, "penalty": 0.0}`.
   Basis: S3 "Results are written back to Orion-LD and IOTA" + sub-score and `domain_name` terms.
   Tag name and key layout **[extrapolation]**.
3. `trust.reliability` / `{"domain_name": "domain-1", "ie": "ie-2", "cpucores": 8,
   "currentcpuusage": 37.5, "ramcapacity": 16384, "availableram": 9120, "currentramusage": 44.3}`.
   Basis: S3 `[ReliabilityScore]` property names. Units and tag **[extrapolation]**.
4. `trust.security.alert` / `{"domain_name": "domain-1", "ie": "ie-2", "priority": 4,
   "source": "self-security"}`. Basis: S3 "Self-Security sends real-time alerts" and
   "average alert priority". Whether alerts go to IOTA is **not stated**: label as extrapolation.
5. `trust.selfhealing.alert` / `{"domain_name": "domain-2", "ie": "ie-1", "healthPenalty": 0.05}`.
   Basis: S3 "Penalty: Deduction based on self-healing alerts frequency". Publication to IOTA
   **not stated**; **[extrapolation]**.
6. Same `ie` across several messages, for the Idea #3/#4 timeline (S4 p.6) **[extrapolation]**.

Open: ask the mentors (UPV) for a real Trust Manager IOTA message or tag; record it in
`docs/OPEN_QUESTIONS.md` if they answer.
