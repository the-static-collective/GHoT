# Experiment 007 — Power Field

## Question

Can one GHoT body change what it offers as battery, thermal, load, or renewable-surplus state changes without changing node identity or deleting installed executors?

## Trial A — deterministic policy simulation

```bash
python3 ghot/power_sim.py
```

The simulation verifies four conditions:

1. solar surplus -> abundant -> heavy offers remain;
2. battery 21% -> conserve -> heavy offers withdraw;
3. battery 8% -> critical -> only essential offers remain;
4. thermal 89C -> conserve even while plugged in.

Expected:

```json
{
  "simulation_passed": true
}
```

## Trial B — inspect a real body

```bash
python3 ghot/power_field.py
python3 ghot/reference_node.py probe
```

On Linux laptops/SBCs, inspect the automatic sysfs results.

On desktops/VMs, some battery/thermal fields may be unknown. Unknown measurement is preserved as unknown rather than guessed.

## Trial C — solar/manual hardware declaration

```bash
GHOT_POWER_SOURCE=solar \
GHOT_RENEWABLE_SURPLUS=1 \
GHOT_BATTERY_PERCENT=88 \
GHOT_CHARGING=1 \
python3 ghot/reference_node.py probe
```

Expected willingness: `abundant`, unless thermal or load pressure overrides it.

## Trial D — forced low battery

```bash
GHOT_POWER_SOURCE=battery \
GHOT_BATTERY_PERCENT=9 \
GHOT_CHARGING=0 \
python3 ghot/reference_node.py probe
```

Expected:

- willingness `critical`;
- non-essential offers have `available: false`;
- installed executor records remain present;
- node_id is unchanged.

## Trial E — composition

Run two bodies where one has a capability that has been power-withdrawn.

The Capability Composer should treat an unavailable power-withdrawn offer exactly as unavailable and choose another awake body if one exists.

## Pass

007 passes when:

- power state is visible and explainable;
- power policy changes OFFER availability;
- BODY identity remains stable;
- the composer never routes to a withdrawn offer;
- CI verifies the deterministic power-policy simulation.

## Mutation opened

008 should turn power awareness into **energy-aware selection** rather than only withdrawal:

- score renewable surplus;
- score plugged-in/charging state;
- estimate task energy class;
- prefer data-local work when moving bytes costs more;
- defer background heavy work until surplus;
- distinguish urgent from deferrable intent.

That is where the heap begins scheduling *when* as well as *where*.
