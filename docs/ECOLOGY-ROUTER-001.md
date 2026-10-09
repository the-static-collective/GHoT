# ECOLOGY-ROUTER-001 — TERRA / WATER / HEAP

> **GHoT proposes where useful resources might go. Resource owners decide whether they move.**

**Status:** deterministic offline *simulation*. No physical sensing, energy metering, wave converter, live fish tank, waste inventory, copper electrode, tree coil, Tesla transformer, seastead, or network transport was observed. No actual compute, electric transfer, pumps, valves, heat pumps, material certification, or reLATTE signature executed.

## Why here?

GHoT already owns the runtime's energy-aware capability scheduling: `docs/ENERGY-AWARE-SCHEDULING.md`, `ghot/energy_scheduler.py`. GHoT's LIGHTWALKER-053 draft PR #50 explored **hard constraints before preference** and Pareto frontiers for compute routing. This experiment introduces an upstream, typed, **non-executing external-resource proposal adapter**, without copying LIGHTWALKER's stacked code or pretending cross-repo thermal contracts are installed.

The exact neighboring draft artifacts to inspect for later integration are:

- STATIC OS [KETTLENODE-001 PR #78](https://github.com/the-static-collective/static-os/pull/78) — simulated electrical allowance, distinct from measured electrical energy.
- STATIC OS [KETTLENODE-002 PR #81](https://github.com/the-static-collective/static-os/pull/81) — thermal-only, isolated fluid proposal.
- GHoT [LIGHTWALKER-053 PR #50](https://github.com/the-static-collective/GHoT/pull/50) — hard-eligibility-before-Pareto modeling.
- Existing GHoT Power Field and Energy Scheduler on main — actual host computational willingness, not physical pump or generator authority.

This is a **separate proof**, not a claim of installed interoperability. Future composition should consume **verified owner-defined** source observations, frozen manifests, no unbounded inference, and acceptance by local owner.

## One map for six resource kinds

```text
              solar PV           waves          hot-water bank
                |                  |                 |
       measured-power gate   verified PTO gate  isolated HX gate
                |                  |                 |
               electricity                        heat
                  |                                 |
            GHoT field snapshot     soil/tree sensing --> information
                  |                    compost ----> nutrients [subject to treatment]
             hard constraints
                  |
        [LIFE SUPPORT FIRST]
               /       \
      fish aeration    safe root zone
               \\       /
          explicitly permitted surplus
                  |
        optional compute / GHoT work
                  |
           receipt proposal only
                  X
          NO AUTOMATIC ACTUATION
```

### Explicit non-collapses

1. `SOIL POTENTIAL != RENEWABLE POWER`: a Cu/Zn ground cell may be a galvanic battery that consumes an electrode. Test separate electrode mass, chemistry, plant impact, electrical output and an independent non-galvanic control. Avoid bare-metal experiments near productive root zones; elevated copper concentrations can damage roots.
2. `TREE SIGNAL != ELECTRICITY`: a suspended magnet/coil that emits a wind-triggered signal or sound is a *sensor/data source*, not measured continuous generation. Reuse the historical "Tesla in the orchard, Tesla in the trees" motif without overstating output.
3. `RESONANCE != POWER CREATION`: a passive copper pyramid, Tesla-style geometry, or tuned coil may concentrate/couple an **existing** EM field under certain circumstances, but geometry does not provide energy without an input. Any proposal requires actual input/output metering, control geometry, and verified frequency-dependent performance.
4. `OCEAN MOTION != ELECTRICAL DELIVERY`: marine wave energy depends on actual water motion, a mechanical power take-off, power conversion, storage/grid interface, storm loads and permitting. Unverified wave power is withheld.
5. `HEAT != ELECTRICITY`: prohibit silently exchanging thermal joules for mWh. A real conversion organ must meter thermal input, heat rejection, electricity output and loss.
6. `RECLAIMED MATERIAL != CERTIFIED STRUCTURE`: discarded HDPE/plastics may be feedstock; sorted, cleaned, tested and properly designed parts could later serve some marine functions. Raw trash cannot serve as a stable floating-city foundation. Water intrusion, UV, plastic release, load paths, buoyancy, mooring, storms and ownership require engineering and approval.
7. `FISH SURVIVAL != DEFERRABLE COMPUTE`: aeration/pumping redundancy, water quality and temperature safety take precedence over background rendering.
8. `OBSERVATION != OFFER != SELECTION != EXECUTION`: an external thermal, wave or materials offer is not a signed physical crossing or remote actuator instruction.

## How the specimen works

- `ghot/ecology_router.py` accepts exact `ghot.ecology-field/v0` synthetic sources, loads and routing paths.
- Each offer carries an exact typed unit: electricity mWh; heat J; freshwater mL; nutrients mg; information events; material mass g. There is **no implicit conversion** among categories.
- Source reserves stay protected; capacity cannot go negative; one source cannot fund two loads from the same modeled allowance.
- One path cannot be shared beyond its modeled limit.
- Hard gates: synthetic scenario evidence only, current sample step, permitted path, owner-reviewed path, environment, isolation, withdrawn or quarantined nodes, explicit owner selection.
- No permit/structural clearance = HOLD, independently of abundance.
- Life support gets capacity before noncritical loads; when life support of a given resource is unfunded, less-critical demands in that resource domain HOLD.
- Ranking among *eligible* paths is deterministic and illustrative, **not** physical efficiency optimization.
- The plan is immutable to the input and reproducible by cold replay.
- Plan `PROPOSE` never actuates. `HOLD` never implies refusal by an equipment owner; `physical_effects`, `owner_admission`, `signed_crossing` and `automatic_dispatch` remain **false**.

Limitations: this is an intentionally idealized resource-accounting sandbox with no temperature gradients, pipe losses, electrode corrosion model, wave statistics, ocean structural analysis, or timed storage state. Spatial network routing is direct one-hop and not optimized. The sensor confidence model is only a flag and **not** authentication. It is not safe as a controller.

## Run

```sh
python3 ghot/ecology_router_sim.py
```

Or from repository root (no network, no effect):

```sh
python3 - <<'PY'
import json
from ghot.ecology_router import plan, cold_replay
p = "fixtures/ecology-router-001/world.json"
world = json.load(open(p))
assert cold_replay(world)
print(json.dumps(plan(world), indent=2))
PY
```

Expected from fixture: solar supplies proposed fish aeration before optional rendering; heat bank offers isolated thermal heat; tree coil supplies information events only; unverified wave and soil-cell output cannot back computation; salvaged floating-structure material stays HOLD pending independent isolation, engineering and permits. These are model choices, not operating safety cases.

## The human landscape

The fiction reference is **Meteor City**, origin of the Phantom Troupe in *Hunter × Hunter*: a place where discarded things and disregarded people develop a culture and new systems of meaning. The real-region thread is the New Jersey Meadowlands' reclaimed landfill/garbage island and Staten Island's Freshkills transformation. Their lessons are **waste accountability and habitat restoration**, not permission to dump into waterways.

A future floating commons could combine: tested pontoon modules, freshwater and wastewater processing, PV plus experimental wave PTO, autonomous freshwater-safe thermal circuits, modular food production and GHoT nodes operating on surplus. Feasibility depends on real sites, wave climate, stability, structural load paths, environmental compliance, and community consent. Begin with a land-based sorting + tank experiment, not an ocean residence.

## Proposed next test

**ECOLOGY-ROUTER-002:** integrate *read-only* KETTLENODE thermal candidates through explicit external adapters. Record **origin SHA, timestamp, evidence class, expiry, physical unit, sink eligibility and owner consent**. Prove:

1. stale/corrupt/withdrawn readings cannot change source eligibility;
2. proposed fish aeration survives simulated loss of wave harvest by switching only when an independently approved reserve exists;
3. background compute cannot consume the oxygenation reserve;
4. simulated copper-soil signal cannot be magically classed as electrical output;
5. independent trusted measurement before any physical energy claim;
6. exact receipts stay HELD until source/destination-local decision.

Other research anchors: [NLR marine resource modelling](https://sam.nlr.gov/marine-energy.html), [NOAA garbage patches explanation](https://oceanservice.noaa.gov/facts/garbagepatch.html), [Princeton galvanic cell example](https://www.princeton.edu/~maelabs/mae324/12/galvaniccell.htm), [University of Minnesota soil copper caution](https://extension.umn.edu/agriculture/crop-production/nutrient-management-for-minnesota-crops/copper-for-crop-production).

**No available capability, donated thing, person, or energy source is automatically surrendered to GHoT.**
