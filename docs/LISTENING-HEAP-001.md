# THE LISTENING HEAP — 001

Status: **draft, removable experimental GHoT slice**, stacked on
[INSTRUMENT-RACK-001](https://github.com/the-static-collective/GHoT/pull/69).
No normative reLATTE changes. No radio transmission. No live RF reception.

## Core proposition

GHoT supplies opted-in ears and locally authorized execution.
Autodisco v20 supplies the independently bound attention/interpretation doorway.
reLATTE carries signed dispatch and attributable evidence, not equipment ownership.

This experiment proves only the narrow path from simulated spectrum survey
to proposal-only attention choice, then separately authorized GHoT RX execution,
then portable result, then exact native Autodisco LOOK-TWICE preparation.

## Anatomy

    simulated survey (explicitly SOURCE=SIMULATION)
                  |
    GHoT native opted-in Instrument Rack cards
                  |
          attention PROPOSAL
                  |
        human/operator exact selection
                  |
       GHoT signed dispatch crossing
                  |
       replaceable simulated RX donor
                  |
     native GHoT receipt / portable seed packet
                  |
     locally content-addressed observed bins
                  |
    SVG SIMULATED RF BINS (exact SHA-256)
                  |
     native Autodisco v20 prepare request
                  |
        two fresh first-listen PACKETS

Not claimed or implemented: radio sampling hardware, an RF energy scan,
Autodisco real AI first responses, dialogue, automatic selection of instruments,
adaptive learned policy, RF transmission, public broadcast, reception by peers,
cryptographic RF transmitter authentication, human attention proof or physical truth.

## Existing contracts, not copies

- GHoT: native ghot.instrument-card/v0, exact-card revalidation,
  dispatch_instrument_card() signed relatte.crossing-envelope/v0, signed receipt,
  and ghot.portable-seed-packet/v0.
- Autodisco v20: native autodisco.look-twice-prepare-request/v0 over exact SVG bytes,
  passed through its real scripts/look-twice.mjs producer. This produces two
  distinct first-listen packets, not actual model responses.
- reLATTE: existing GHoT integration profile only; GHoT does not pretend that
  the radio artifact itself is a cryptographically authenticated transmission.

## Attention and tests

The simulator has two named candidate bands and an explicitly declared heuristic:

    score = 5*novelty + 3*uncertainty + activity - attention_cost

No hidden answer labels enter the planner. It returns a content-addressed
proposal, including a specific exact card, budget, and source cut.

The fixture later grades its selection against a fixed first-band schedule using
independently declared toy utility labels. Winning on this small fixture does not
establish scientific information gain, real spectral awareness, or generalization.
A future study needs preregistered baselines, independent trials, observations of
what the system missed, and a scoring method that resists overfitting.

The explicit_listen() gate requires an additional operator-supplied selection
binding the exact proposal and card, followed by the existing fresh Instrument
Rack revalidation. No attention score or signed observer claim produces authority.

## Run

    python3 ghot/listening_heap_sim.py

To execute Autodisco native LOOK-TWICE prepare action (rather than merely
construct its exact request), point the test at a checkout of v20:

    AUTODISCO_LOOK_TWICE_SCRIPT=/path/to/Autodisco-v20/scripts/look-twice.mjs \
      python3 ghot/listening_heap_sim.py

GitHub Actions uses the exact pinned Autodisco commit
1e06cee07061116eb31afbcdc60b34971ee5b130 so the second part proves native
preparation instead of assuming a compatible interface by name.

The simulation uses temporary GHOT_HOME and an explicitly opted-in temporary
GHOT_ADAPTER_MANIFESTS pointing to the local fake-RX donor. Its capabilities
are only radio.rx.simulated.weather and radio.rx.simulated.ism.
The donor refuses transmit requests and does no network or hardware IO.

## Hostile conditions

- malformed/physical-source survey claims refuse;
- stale survey cuts refuse;
- insufficient attention budget refuses;
- planning itself invokes no instrument;
- omission of explicit approval refuses;
- changed proposal/card selection refuses;
- modified card limits refuse at GHoT existing card freshness gate;
- exact replay retains the same signed dispatch, with no new attempt;
- SVG source is byte-bound and deliberately labeled SIMULATED;
- observation tampering refuses the Autodisco projection;
- transmit, mismatched band and extra payload fields refuse.

## The next real gates

**RADIO-EAR-002:** real receive-only SDR adapter: explicit driver and
antenna metadata, supported sample rate/bandwidth, raw IQ windows with exact
SHA-256, timestamps and uncertainty, clipping/overrun status, gaps, safe retention
and local privacy policy. Hardware/source evidence must remain separate from
decoded claims.

**RADIO-ATTENTION-003:** field scanning, competing listening candidates,
budgets, cold replay, preregistered baselines and multiple independent receivers.
Do not infer that unobserved frequencies were silent.

**RADIO-VOICE-004:** proposal-only communication strategy initially using a
fake transmitter. A separately reviewed hardware/radio-service control must
enforce frequency, power, timing, duty, privacy, authorization and an independent
kill switch. No radio-law permission is inferred from software authority.
Service-specific regulations apply.

**RADIO-ENCOUNTER-005:** real authorized RF packet, independent receiver,
operator consent, GHoT native receipt, reLATTE receiver HOLD and cold replay.
A radio message is not the same thing as a verified reLATTE crossing.

## Non-collapses

    HEARING != UNDERSTANDING
    SURVEY != OMNISCIENCE
    ATTENTION != OBSERVATION
    SIGNAL ENERGY != DECODED PAYLOAD
    DECODED PAYLOAD != VERIFIED SOURCE
    PROPOSAL != SELECTION
    SELECTION != DISPATCH
    DISPATCH != RECEIPT
    RECEIPT != PHYSICAL TRUTH
    RX PERMISSION != TX PERMISSION
    SIMULATED SIGNAL != PHYSICAL RECEPTION
    FIRST-LISTEN PACKET != AI FIRST LISTEN
    RADIO ORGANISM != UNIVERSAL RADIO AUTHORITY

Promotion to a common instrument contract requires materially different native
donors; do not make the current simulated-radio-specific shapes normative.
