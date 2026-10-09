# THE RIFF-RAFT-002 — THE RUBE GOLDBERG TERRAFORMER

**Make the machine change the conditions under which the ground can help make its next machine.**

This is a **human-authorized, provenance-first, offline simulation**. It never excavates ground, shifts real rainwater, plants seeds, opens valves, signs reLATTE crossings, commands hardware, or certifies ecological recovery.

## Excavation record: material recovered rather than newly invented

The following authored Drive documents are the source ancestors, not a synthetic folklore of past conversations:

1. [Lay the Bones, Wake the Soil — A Little Field Guide to Terraforming](https://docs.google.com/document/d/1Ygeu66WTffxJEJxT_Dn5ILrgok8IkWKyM4Eha6NChfw/edit): reconstructed histories of stewardship, regenerative substrate, desert oasis field work, soils, seed arks, seasonal growth, and "one meter outward." Its literal sequence: **read the field; lay the bones; make ground; seed a nucleus; feed the field; add engines; let succession work**. Its repeated engineering primitives include water catchments, brush shade, mulch, compost pockets, native pioneers and protected moisture.
2. [MAKE GROUND — A Field Manual for Growing Possible Futures — Spine 001](https://docs.google.com/document/d/1EP2u0R1CqTVZL-gzDWAHMeltuF8_KDDg5phWkbc3zng/edit): noncollapse and the constraint that a coherent simulation cannot certify itself; Better Holes → NAV → Constant → Rehearsal → Independent Witness → Terraforming. "The book is not the apparatus; the field must answer."
3. [MAKE GROUND — BRIDGE LAYER 001](https://docs.google.com/document/d/1dc05HctY5PyWGPIzV2961iQOSWfarIEXV3Tso5qn6ME/edit): a Bridge Packet's ancestry, doors, witness, open berth and world-contact. Relevant loop: **SOURCE → BRIDGE PACKET → VIEWS → TRAVERSAL → RECEIPT → RETURN → NEW SOURCE**; receipt is a trace, not a score.
4. [BRIDGE PACKET 006 — MAKE GROUND — Grow the Field](https://docs.google.com/document/d/1bzHhTe4P3OeTA-5Wlgjmr58ioQSlBOZDB2vBekHzVnY/edit): its sharp challenge is whether apparent increased fertility merely **moved maintenance work somewhere less visible**. The ground receipt needs FIELD BEFORE, INTERVENTION, EXPECTED LOOP, OBSERVED LOOP, MAINTENANCE, FERTILITY DELTA, NEXT EDGE.

### Canonical law

> **DO NOT DESIGN THE FINISHED WORLD. CHANGE THE SUBSTRATE SO MORE GOOD WORLDS CAN GROW.**

Earlier neighboring work supplies the runtime: [GHoT ECOLOGY-ROUTER-001 PR #109](https://github.com/the-static-collective/GHoT/pull/109) and [THE RIFF-RAFT-001 PR #111](https://github.com/the-static-collective/GHoT/pull/111).

This branch is stacked on the exact Riff-Raft-001 draft head, not on unrelated GHoT main. It composes read-only with the predecessor's simulated orchard information route and inherits its non-actuation. No repository-wide authority model is rewritten.

## What makes it a Rube Goldberg *terraformer*?

Picture an absurd little mechanical chain on a permitted, non-living **bench model**:

```text
 WIND VANE RINGS A SMALL OBSERVATION BELL
             |
       read the field
             v
      BRUSH BAFFLE    <- reusable, mechanically mounted model
             |
          rain cup
             v
       TIPPER / FLOAT  --(overflow measured separately)--> runoff tray
             |
       pulley suggests shade
             v
          SHADE FLAP
             |
      banked-water wick
             v
     SOIL + COMPOST POCKET
             |
      native seed packet
             v
       planted-site attempt
             |
    biomass-to-mulch return
             |
      measuring dial asks
       "did it actually work?"
             |
     field witness and open berth
             |
        ONE METER OUTWARD
```

The *causal* magic is **not** that each lever automatically has permission to launch the next. The machine can expose a next cue after a prior one changes the modeled stock or condition, but GHoT never treats a cue as authority. The physical chain can eventually function mechanically with fail-safe design; its current *software* version requires a new explicit operator selection at every stage.

A real field needs a better question than "did the bell ring?":

- Did the soil retain moisture longer than a comparable untreated patch?
- Did the interventions avoid causing new erosion, runoff, invasive spread or contamination?
- Did native seedlings establish and survive, not merely get dispensed from a seed pocket?
- Did water/soil quality improve under independent measurement?
- Did maintaining the patch get easier without merely outsourcing work?
- Did an adjacent patch become possible as a **measured** consequence, rather than as simulation rhetoric?

## The nine-cue runtime

The fixed bounded sequence in `ghot/riff_raft_terraformer.py`:

| Cue | Consequence in the current simulation | What it **does not** certify |
|---|---|---|
| READ_FIELD | Mark one modeled scenario as read | Real site survey |
| LAY_BONES | Allocate 600 g of brush to a modeled rain pocket | Earthwork stability or permission |
| CATCH_WATER | Partition 1,200 mL modeled rain into 900 mL banked + 300 mL runoff | Real rain captured, runoff quality |
| MAKE_SHADE | Allocate 300 g additional brush to modeled shade | Measured evaporation reduction |
| MAKE_GROUND | Transfer 300 g compost to amended soil, 400 mL banked water to soil water | Living microbial function |
| SEED_NUCLEUS | Allocate five native seed counts to a sowing **attempt** | Germination or habitat success |
| FEED_FIELD | Partition 400 g imported biomass into 240 g mulch, 120 g compost, 40 g documented process loss | On-site production or fully calibrated composting |
| WITNESS_DELTA | Ask for an outside field witness, **without inventing one** | Independent measurement or restoration |
| ONE_METER_OUTWARD | Mark the next adjacent **candidate**, not a new planted site | Permission, suitability, expansion, improved fertility |

The 400 g biomass input is explicitly **imported**. No stage conjures compost from seedlings that were never verified to grow. Water, biomass and seed count are each conserved in the model. Material loss is recorded, not hidden.

The model is simplistic by construction: it lacks soil hydrology, evaporation, evapotranspiration, degradation, infiltration, species biology, nutrient chemistry, real plant growth, seasonality and risk of adverse unintended effects. Its stocks are scenario accounting, not calibrated ecosystems or physical mass/volume inventories.

## Real physical field sequencing matters

The recovered guide says **biology first; engines after useful biological loops**. We can build harmless sensor-driven test rigs at any point, but don't let a gadget dictate where to dig or irrigate. Before hydrological intervention on actual land, site-specific local review is necessary.

Land-based arid-site water-harvesting practices differ materially from tidal wetland shoreline practices. [USDA NRCS catchment guidance](https://www.nrcs.usda.gov/resources/guides-and-instructions/water-harvesting-catchment-no-636-conservation-practice-standard) emphasizes that national standards do not replace local field-office technical standards. [NOAA Living Shorelines](https://www.habitatblueprint.noaa.gov/living-shorelines/) recommends context-specific choices for sheltered coasts, not arbitrary deposition or floating debris structures. Neither should be ported blindly to another site's soils, watershed, ownership or habitat.

**Three terrain variants, with distinct requirements:**

- **Dryland ground**: read slope, existing native cover and rainfall first; compare minimally disturbed captured-water/organic-matter plots against controls; require landowner/site drainage clearance before altering flows.
- **River/shoreside**: habitat-first, site-specific authorized living-shoreline work. Do not redirect runoff into productive water or alter channels without approved design.
- **Floating experimental platform**: no claim of terraforming the seafloor or turning garbage into land. Treat it as a *mobile laboratory* for metered heat, solar/wave observation, sampling and landward reporting; cargo/salvage requires qualified analysis and safe disposal.

## The actual GHoT seam

```text
ECOLOGY-ROUTER-001
  -> RIFF-RAFT-001
       synthetic land/shore/river/floating transport proposals
  -> RIFF-RAFT-002
       orchard INFORMATION route offered?
                |
          field source hash pinned
                |
            stage door
                |
      owner explicitly chooses once
                |
       conserve field stock ledger
                |
      unsigned simulation receipt
                |
          next door shown
                X
             STOP
```

A stale or withdrawn information route refuses all next steps. So do missing land stewardship consent, absent scenario erosion/water-path review, contamination screening, non-native-seed origin review, insufficient modeled inputs, repeated cue turn ids, authority/admission smuggling, stage hopping, checksum drift and fabricated witness flags.

### Reproduce

```bash
python3 ghot/ecology_router_sim.py
python3 ghot/riff_raft_sim.py
python3 ghot/riff_raft_terraformer_sim.py
```

The test harness imports the two checked-in, **synthetic** upstream fixtures and proves nine sequential owner-selected steps with no automatic execution or external consequences. All steps issue receipt hashes; those hashes check consistency, **not** external truth, signatures, physical durability or tamper resistance.

## Engineering's hardest gate: who gets to declare improvement?

The simulator can check **RESOURCE BALANCE**, not **FERTILITY**.

The MAKE GROUND packet explicitly demands an outside observation and a maintenance comparison. A field return packet should include:

```text
field_before           = bounded measured prestate
intervention           = exact person, site, permission, mechanism and time
expected_loop          = measurable hypothesis
observed_loop          = independent observation(s), with uncertainty
maintenance_cost       = ongoing inputs and labor at the site and upstream
fertility_delta        = what new capability actually exists, not just aesthetics
unintended_effects     = erosion / contaminants / invasive spread / disease
next_edge              = proposed one-meter adjacent patch
evidence_class         = simulation | first-party observation | independent witness
reLATTE_crossing       = no, until actually signed by reLATTE
authority_to_expand    = owner/local regulators, not GHoT
```

**No independent field witness exists in this version. Accordingly the post-rehearsal status remains `fertility_delta_verified = false`.** This intentionally refuses to rename a simulation into a restored landscape.

## Future apparatuses

The **field Rube Goldberg** version could be a non-electrified tabletop gravity/water/float prototype with removable modules and contained clean water; a tree coil provides a *signal* rather than power; a meter logs water balance and captures before/after images. The *next* task is not an automatic botanical seed cannon. It is one instrumented physical bench with human review before living materials are introduced.

The **floating version** could later use wind/wave movement to report a buoy position and energy measurement, solar to power instruments, and the thermal bank to moderate a separate water experiment. No live aquaculture shares a test fluid with reclaimed-material processing, compost tea, soil leachate, glycol or process coolants.

## New seam law

```text
INPUT != GROWTH
SEED RELEASE != PLANT ESTABLISHMENT
RUBE GOLDBERG CUE != EXECUTION AUTHORITY
SIMULATED SUCCession != PHYSICAL SUCCESSION
BIOLOGICAL OUTPUT != FREE MATTER
MORE ACTIVITY != MORE FERTILITY
WITNESS DELTA != SELF-ATTESTED SCORE
ADJACENT CANDIDATE != REAL LAND CLAIM
MAKE GROUND != DESIGN EVERY CONSEQUENCE
```

**Field instruction: Make one bounded change. Leave a receipt. Start again one meter outward—only when the ground actually answers.**
