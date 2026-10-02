# Experiment 008 — Energy-Aware Scheduling

## Question

Can GHoT make an inspectable choice among RUN HERE, RUN THERE, and HOLD using capability, liveness, energy state, urgency, deferrability, and data locality?

## Trial A — deterministic simulation

```bash
python3 ghot/energy_sim.py
```

The simulation proves:

1. background + heavy + deferrable + battery-only heap => HOLD;
2. the same capability marked immediate => RUN now;
3. adding an abundant solar body => RUN THERE on solar;
4. under normal urgency, strong data locality can beat a non-local solar advantage;
5. a power-withdrawn but known capability can produce HOLD for deferrable work.

Expected:

```json
{
  "simulation_passed": true
}
```

## Trial B — live dry run

With one or more GHoT bodies serving:

```bash
python3 ghot/energy_scheduler.py runtime.ffmpeg.version \
  --urgency normal \
  --dry-run
```

Inspect the energy plan.

## Trial C — simulated solar node

Start a serving node with:

```bash
GHOT_POWER_SOURCE=solar \
GHOT_RENEWABLE_SURPLUS=1 \
GHOT_CHARGING=1 \
python3 ghot/lan_node.py serve --port 7788
```

Run an energy-aware request from another body and verify the candidate records the surplus.

## Trial D — hold heavy background work

Use a heavy capability once a real heavy adapter exists, or use the deterministic simulation until then.

Expected HOLD contains:

- one `energy_plan_id`;
- the original capability/payload;
- explicit urgency and deferrability;
- a human-readable reason;
- no invented wake/release time;
- release condition based on re-evaluation.

## Pass

008 passes when:

- immediate work is not silently delayed for energy optimization;
- deferrable heavy background work may HOLD;
- favorable power may change where work runs;
- data locality is visible in selection;
- HOLD persists enough intent to be re-evaluated later;
- CI runs the deterministic energy scheduler simulation.

## Mutation opened

009 should add a **Hold Queue / Wake Composer**:

- enumerate held work;
- re-evaluate holds on field/power events;
- release when conditions improve;
- preserve the old HOLD and create a new child energy plan;
- allow expiry/cancellation;
- never execute after expiry.

That would turn `HOLD UNTIL SURPLUS` from a record into an autonomous local scheduling loop.
