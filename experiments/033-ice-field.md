# Experiment 033 — The Ice Field

033 turns the verified Ice Cube pantry into a bounded mathematical exploration field.

## One cube opens five neighboring WANTs

For every locally merged verified cube, the field derives at most five deterministic neighbors:

```text
lucas-next
c-real-minus
c-real-plus
c-imag-minus
c-imag-plus
```

The complex-parameter step is exactly `1/16`.

Each WANT contains:

```text
parent specimen id/address
relation
exact child work spec
exact child work address
status
last scheduling observation
```

The child work address is the deduplication key. If that work already exists in the verified pantry, the WANT becomes `satisfied` instead of causing more compute.

## Authority chain

```text
PANTRY
  -> WANT
  -> energy/capability scheduling
  -> selected GHoT body
  -> Ice Cube mining
  -> Dogram on worker
  -> 032 verified return crossing
  -> requester HOLD
  -> requester-local Dogram
  -> owner-local ADMIT
  -> explicit pantry merge
  -> field refresh
  -> adjacent WANTs
```

Preserve:

```text
PANTRY != WANT
WANT != SCHEDULE
SCHEDULE != EXECUTION
EXECUTION != RETURN
RETURN != VERIFICATION
VERIFICATION != ADMISSION
ADMISSION != MERGE
ONE CUBE != INFINITE FANOUT
```

## Power-aware prospecting

Field dispatch uses the existing `energy_scheduler.schedule` with:

```text
capability = ghot.ice-cube/v0
urgency = background
deferrable = true
prefer_surplus_for_background = true
```

No Ice-Field-specific placement algorithm exists.

A worker can receive an optional return destination inside the bounded Ice Cube capability request. After mining and worker-side Dogram verification, it packages the artifact through Experiment 032 and sends it to the requester's HOLD-only porch.

## Proof

CI runs:

```bash
python3 ghot/ice_field_sim.py --dogram-repo _dogram_ice
```

The simulation:

1. mines and admits one seed cube;
2. merges it into the verified pantry;
3. refreshes the field and observes exactly five first-generation WANTs;
4. exposes a normal-power local body and a surplus-power remote body;
5. proves the existing energy scheduler selects the remote body;
6. remotely mines the `lucas-next` child;
7. returns it through the 032 porch as HOLD;
8. independently reverifies it on the requester;
9. owner-locally ADMITs and explicitly merges it;
10. refreshes the field;
11. marks the completed WANT satisfied;
12. observes a second generation of adjacent WANTs.

That is the first closed Ice Field ecology.
