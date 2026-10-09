# THE RIFF-RAFT

> **A distributed commons built from rescued materials, honest energy, accountable crossings, and people who do not need permission to count as people.**

Name: **The Riff-Raft** (the musical *riff*, the floating *raft*, and an intentional reclaiming of *riffraff*).

**Current status: executable *simulation* only.** No claim is made of a floating structure, connected power/water infrastructure, structural approval, environmental clearance, actual wave generation, live equipment actuation, measured sensor readings, an operational settlement, or people occupying such a site.

## What it is

The Riff-Raft is not initially one huge artificial island. It is a network of independently governed nodes that may occupy **land, shore, river, and floating platforms**. The Riff-Raft is the infrastructure *between* them:

- A land orchard / reused-material yard.
- A shore-based heat, charging, water, repair or processing station.
- A river landing for approved transfers and contingency return.
- A modular floating node with its own safe power, water, food, wastewater, and shelter systems.
- A compute organ, present only if genuine energy surplus and local permission exist.

These are **potential community functions**, not interchangeable equipment or an invitation to build unsafe accommodation on floating rubbish.

The cultural reference is *Meteor City* in Hunter × Hunter; the engineering reference is measured recovery and durable reuse of resources in real land-based and marine systems. Neither a garbage patch nor unsorted discarded materials is an adequately characterized building foundation. Begin with **land-side repair, sorting, responsible recycling and supervised model-boat/bench experiments**.

## The executable seam, RIFF-RAFT-001

The older GHoT [ECOLOGY-ROUTER-001 draft](https://github.com/the-static-collective/GHoT/pull/109) asks whether a synthetic source may *propose* meeting a modeled load, respecting resource type, amount, freshness, consent, and life-support priority.

This extension asks **whether a path exists** across places under explicitly modeled constraints:

```text
             GHoT ECOLOGY-ROUTER-001
             owner-selected eligible offer
                           |
                           v
                  THE RIFF-RAFT 001
              anchored ecology state hash
                           |
                  link-by-link review:
                   - resource / unit
                   - local steward
                   - modeled reserve
                   - cable / pipe / cargo / radio
                   - proposed transfer capacity
                   - consent on both endpoints
                   - isolation / weather / permit
                           |
             +-------------+-------------+
             |                           |
       can model route               cannot model route
             |                           |
         PROPOSE                       HOLD
             |                           |
    no physical transfer          no physical transfer
             +-------------+-------------+
                           |
                  no authorization
                  no automatic dispatch
                  no destination admission
```

**Crucial rule: the network overlay may narrow an ECOLOGY PROPOSE to HOLD. It cannot promote an ECOLOGY HOLD into PROPOSE.** If a water crossing is safe in the cartoon but forbidden at the source, it remains forbidden.

### What is in code

- `ghot/riff_raft.py`: strict topology contract, signed-off only as a synthetic **scenario**, deterministic bounded shortest-hop search through offered directed links, origin/destination owner-grant checks, exact resource unit matching, weather/isolation/permit gates, shared link budget accounting, protected life-support route priority, and immutable plan output.
- `fixtures/riff-raft-001/topology.json`: connected orchard, shore, river and raft places, with an intentionally withheld salvage-cargo crossing and storm-unsafe wave candidate.
- `ghot/riff_raft_sim.py`: hostile tests including stale world pin, consent withdrawal, denied weather passage, missing dock, crossing budget collisions, resource mismatch, impossible claims of physical readiness, partial source authorization, and nonexecution of outputs.
- CI appends `python3 ghot/riff_raft_sim.py` to the existing GHoT smoke suite.

No network traffic, remote task execution, hardware communication, physical movement or reLATTE signing is performed.

### Four illustrative routes

| Route | First model result | Why |
|---|---|---|
| Solar platform → shore switch → fish aeration | PROPOSE | One source budget, two modeled cable segments, fish life support before compute |
| Shore heat store → separated fish thermal circuit | PROPOSE | Thermal joules stay thermal; isolated heat route, not fish-water mixing |
| Orchard sensor → local musical installation | PROPOSE | Signals are information events, **not** generated electricity |
| Material sorting yard → river landing → floating habitat | HOLD | Upstream qualification and downstream structural/permit gates not yet modeled as satisfied |

A PROPOSE is **not proof a cable can be laid, a permit exists or material is habitable**. Flags are scenario assumptions used for hostile testing.

### Laws of the Riff-Raft

```text
PLACE != PROPERTY
ARRIVAL != ADMISSION
SCRAP != STRUCTURAL MATERIAL
WAVE MOTION != USABLE POWER
RESOURCES != PEOPLE
WATER != COOLANT
MEASUREMENT != MEANING
CONNECTION != CONTROL
SOURCE CONSENT != DESTINATION CONSENT
PROPOSAL != TRANSPORT
TRANSPORT != TRUST
FLOATING != SAFE
SURVIVAL != OPTIONAL COMPUTATION
HOLD != ABANDONMENT
```

The land/river/floating habitats remain sovereign in their local operations. GHoT can offer feasibility and evidence; reLATTE alone may carry properly signed crossings through an owner-defined transport, and local authorities decide what is accepted. No central ledger acquires title to a raft, land, water, people, labor, or scrap through discovery.

## Running the simulation

```bash
python3 ghot/ecology_router_sim.py
python3 ghot/riff_raft_sim.py
```

Standalone demonstration from repository root:

```bash
PYTHONPATH=ghot python3 - <<'PY'
import json
from ecology_router import digest
from riff_raft import compose
ecology = json.load(open("fixtures/ecology-router-001/world.json"))
topology = json.load(open("fixtures/riff-raft-001/topology.json"))
result = compose(ecology, topology)
for row in result["routes"]:
    print(row["load_id"], row["decision"], row["route_link_ids"])
assert result["ecology_world_sha256"] == digest(ecology)
assert not result["physical_transfer_performed"]
PY
```

The topology binds the exact canonical hash of the synthetic ecology fixture, refusing changes not deliberately re-bound by the experiment owner.

## A proposed real-world build order

**First floor: LAND.** Cleanable salvage sorting and repair benches; metered solar/battery circuit; calibrated thermal reservoir experiment using non-pressurized water; no reclaimed material is presumed load-bearing. Record contaminants and material provenance.

**Second floor: SHORE.** Safe demonstration at a permitted site, with separate simulated bids for electric supply, cooling, communications, water, fish and plant life support. Test blackout, pump failure, storm/weather hold, and manual deactivation before touching live aquaculture.

**Third floor: FLOAT.** Start with a **small unoccupied instrumented platform or commercially engineered model buoy**, correctly designed for wind/wave/current, load/stability, buoyancy/compartmentation, anchor/mooring, retrieval, navigation restrictions, and environmental compliance. Never make a habitable structure from loose marine trash.

**Fourth floor: BRIDGE.** Separate carrier-specific routes: data by permitted radios or cables; electricity by appropriately engineered circuits; hot/cold by rated heat exchangers; freshwater in certified clean systems; hazardous wastewater isolated; reclaimable material through tested provenance and safe cargo handling.

**Fifth floor: COMMONS.** Source and destination independently approve resource sharing. Run each resource owner locally and preserve receipt trails for loss, refusal, transport and actual delivery. Non-rescuable weather or safety conditions require withdrawal, **not** forcing passage because a scheduler preferred the route.

## Physical safety boundary

The heat and wave inventions are appealing precisely because they are governed by physical limits. Soil electrode potential may consume electrodes; wave harvest is variable, and transmission losses occur. An inexpensive home experiment does not establish safety for fish, drinking water, boats, or occupied structures. This software has **no physical sensor or actuator drivers**, is not a certified safety controller, and offers no build approval.

## Next executable crossing

**RIFF-RAFT-002 — witnessed availability**: add read-only, source-specific provenance for shore solar electrical measurements, simulated thermal bank measurements, a weather and wave snapshot, and a float integrity inspection. Prove expired evidence always falls back to HOLD. Do not permit a remote processor to invent capacity or manufacture a safety permit.

Riff = creativity. Raft = transport. **The commons exists where accountable crossings actually happen.**
