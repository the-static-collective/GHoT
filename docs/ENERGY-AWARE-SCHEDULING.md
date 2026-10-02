# Energy-Aware Scheduling

007 taught each body to answer:

> Can I afford this capability right now?

008 asks the organism:

> Given the bodies awake now, should this task run here, run there, or wait?

## Decisions

V0 has four explicit decisions:

- `run_here`
- `run_there`
- `hold`
- `no_eligible_body`

`hold` is not failure. It is a durable scheduling decision.

## Intent dimensions

A request may carry:

### Urgency

- `immediate` — execute on the best eligible body now;
- `normal` — ordinary deterministic selection;
- `background` — permits energy-window policy to matter strongly.

### Deferrability

A task must explicitly be deferrable before V0 will hold it for power reasons.

Urgency and deferrability are separate.

An urgent task is normally not marked deferrable.

### Data locality

A request may identify the node already holding the data.

V0 adds a large visible score for processing data where it already lives rather than assuming moving bytes is free.

## V0 scoring

For otherwise-eligible candidates:

- data already local: +120
- abundant power willingness: +60
- renewable surplus: +40
- external power / charging: +20
- normal willingness: +10
- requester-local execution: +5
- conserve willingness: -40
- critical willingness: -100

These numbers are policy constants, not measurements of joules.

## Background heavy work

If a task is all of:

- `background`;
- `deferrable`;
- `heavy`;

then V0 prefers a candidate with abundant/external power.

If every eligible candidate is merely running on battery without a favorable energy state, the scheduler returns:

```text
HOLD
reason:
background heavy work is deferrable and
no eligible body has abundant/external power
```

The hold record does not claim to know when solar or grid power will improve.

Its release condition is:

> re-evaluate when field/power state changes.

## Urgent work

V0 does not postpone an otherwise-runnable urgent task merely to wait for renewable energy.

That prevents energy optimization from silently overriding human urgency.

## Withdrawn capability

If every matching body currently has the capability power-withdrawn and the task is deferrable, V0 may HOLD rather than report ordinary absence.

This preserves the distinction:

```text
CAPABILITY DOES NOT EXIST
!=
CAPABILITY EXISTS BUT SHOULD NOT RUN NOW
```

## Data locality versus solar

Data locality may outweigh a moderate energy preference under normal urgency.

Example:

- body A owns a 40 GB source file and is on AC;
- body B has renewable surplus but would require moving the 40 GB file.

V0 can select A because data-locality score exceeds the additional solar bonus.

For background work, a favorable powered body is considered first; future versions should estimate actual transfer cost rather than use fixed scores.

## CLI

Plan without execution:

```bash
python3 ghot/energy_scheduler.py render.video job.json \
  --urgency background \
  --deferrable \
  --dry-run
```

Mark where the data lives:

```bash
python3 ghot/energy_scheduler.py render.video job.json \
  --urgency normal \
  --data-node <node-id>
```

Override the background-surplus preference:

```bash
python3 ghot/energy_scheduler.py render.video job.json \
  --urgency background \
  --deferrable \
  --allow-background-battery
```

## Laws

- NOT NOW != FAILURE
- HOLD != REJECTION
- URGENCY != POWER CLASS
- DATA MOVEMENT != FREE
- GREENEST BODY != ALWAYS BEST BODY
- ENERGY POLICY MUST NOT INVENT URGENCY
- DEFERRAL REQUIRES EXPLICIT PERMISSION
- TIME MAY BE COMPOSED, BUT NOT FABRICATED
