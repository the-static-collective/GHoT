# COMMONS MACHINE 001 — GHoT × tranchNOSE

**Status:** experimental, proposal-only, no hardware or live authority.  
**Formation:** "A Rube Goldberg civilization": one ordinary local action may yield several distinct downstream *candidate* benefits.

## Why this belongs in GHoT

tranchNOSE owns the experimental physics and evidence boundaries of physical relation/topology: see [hollow-copper research proposal](https://github.com/the-static-collective/tranchNOSE/pull/11) and the [water/flow/resonance note](https://github.com/the-static-collective/tranchNOSE/blob/main/RESEARCH_NOTE_WATER_FLOW_RESONANCE_RELATIONAL_CARRIER.md).

GHoT owns runtime bodies, discoverable capability offers, selection, owner-local execution, lease authority, liveness, power-aware refusal, and append-only work receipts. The Commons Machine is **not** a replacement for GHoT's capability composer or reLATTE's crossing authority. It is a small **physical observation → candidate relationship → proposed capability request** front end.

The immediate purpose is to represent a branching consequence graph without making false claims about a physical rig. All events are explicitly *synthetic*. The program neither observes sensors nor starts GHoT tasks, switches relays, opens valves, moves water, powers a coil, writes to a network, or claims a real result.

## Try the first machine

From GHoT's repository root:

~~~sh
python3 ghot/commons_machine.py experiments/commons-machine-001.json
python3 -m unittest discover -s tests -p 'test_commons_machine.py' -v
~~~

To append an **unsigned, non-authoritative** local simulation receipt, explicitly opt in:

~~~sh
GHOT_HOME=.ghot python3 ghot/commons_machine.py \
  experiments/commons-machine-001.json --write-receipt
~~~

Records are stored under \`GHOT_HOME/records\`; no previously written record is edited. The dry-run output contains the canonical scenario hash, a result hash, typed decisions, unvisited downstream relations, and machine-readable \`no_tasks_executed=true\`, \`no_dispatch=true\`, \`no_physical_observations_made=true\`.

## The one-lever walk

~~~text
SIMULATED LEVER
    |
    v
FIXTURE FLUSH (model only)
    |
    +-- observation candidate -> potable-supply meter
    |                                |
    |                                +-- demand estimate -> HOLD cooling review
    |                                |
    |                                +-- audit model -> HOLD capability request
    |
    +-- observation candidate -> pressure probe -> HOLD inspection request
    |
    +-- prohibited wastewater -> coolant fluid transfer -> REFUSE
~~~

No physical wastewater is connected to cooling equipment. The \`observation\` edge crosses informational domains only: it does not assert fluid continuity or pretend that the named sensor has actually reported.

**YES** = the relation is permissible as a *synthetic model step*. It is not an admission to run a real task.

**HOLD** = an action/capability proposal needs real readings, available offers, local selection, and authority. Downstream edges do not execute.

**REFUSE** = the particular model connection is prohibited (e.g., wastewater to independent coolant loop). REFUSE does not delete historical input or authorize a different crossing.

The fixture references capabilities such as \`sensor.water.flow.read\` as *candidate capability names*, **not claims that GHoT already advertises those offers**. The \`system.info\` proposal references an existing GHoT built-in capability, but even it is not invoked.

## First interoperation contract

Current simulated input:

~~~json
{
  "kind": "ghot.commons.scenario/v0",
  "source_event": {
    "node_id": "lever",
    "synthetic": true,
    "description": "Operator pulls a modeled flush lever"
  },
  "nodes": [],
  "edges": []
}
~~~

Future (not implemented) tranchNOSE source: a signed or otherwise attributable calibrated measurement bundle with explicit physical configuration, timestamps, observer cut, and uncertainty.

Proposal-only GHoT handoff after that future bridge:

~~~text
tranchNOSE observation / validated fixture
    -> typed physical domain and source provenance
    -> GHoT commons candidate
    -> GHoT discovery / capability composition
    -> energy/liveness/privacy/authority gates
    -> explicit local dispatch under existing rules
    -> local task execution
    -> native receipts
    -> a new attributable observation
~~~

**Do not make the return arrow automatic.** A receipt can be offered as an input to a later simulation or observation, but is not evidence that any physical event happened without the independent physical instrumentation.

## Hard boundaries

- Matter, energy, and information travel on separately typed edges.
- Potable, wastewater, greywater, process-water, and coolant quality distinctions are explicit. V0 refuses any cross-medium fluid-transfer edge, rather than guessing that treatment/isolation exists.
- Bare low-resistance copper coils require current limits, thermal limits, insulated turn separation, and an intentional electrical safety design; this prototype neither builds nor energizes them.
- V0 rejects cycles; feedback requires a new iteration bound, stopping criteria, authority model, and new receipts.
- Local planners may hold/refuse tasks, and infrastructure safety must never depend on an experimental inference.
- Simulated outcomes are not physical measurements or proof of decentralized cognition.
- No claim is made about perpetual motion, lost advanced historical infrastructure, or physical time tubes.
- No identity/consciousness conclusions are drawn from distributed signal processing.

## Bounded next steps

1. **GHoT:** Build an adapter that can consume real, authenticated tranchNOSE observations but only emits proposal cards; add an exact capability-offer check, then operator review.
2. **tranchNOSE:** Demonstrate one *dry, low-power* coil + a second receiver with a declared excitation/response test; capture a calibrated field/coupling receipt.
3. **reLATTE:** Define transport once a physical observation actually crosses owner boundaries; keep producer's measurement report distinct from receiver-local admission.
4. **Commons demo:** Connect a standalone lever/switch to a *sensor-only* signal for two independently instrumented downstream models; no pump/valve command until a separate approved safety review.
5. **Only after evidence:** Feed selected signed observations into GHoT capability planning, subject to real awake-body offers, power constraints, leases, and explicit local approval.

### Success criterion for 001

A deterministic offline simulation takes **one synthetic occurrence** and produces **at least three distinct candidate downstream routes**, including YES, HOLD, and REFUSE, with reproducible hashes and a durable optional receipt. No device is controlled and no historical state is rewritten.

> ONE LEVER MAY OPEN MANY CANDIDATE DOORS. NO DOOR CROSSES ITSELF.
