# Hold Queue / Wake Composer

Experiment 008 introduced HOLD as a legitimate scheduling result.

Experiment 009 makes HOLD operational.

A held task now has two simultaneous forms:

1. an append-only record proving that the hold was created;
2. a mutable local queue record representing the hold's current state.

This preserves history without pretending that queue state is immutable.

## Lifecycle

```text
ENERGY PLAN
    |
    | decides HOLD
    v
HELD
    |
    +---- field/power unchanged ----> RECHECKED ----> HELD
    |
    +---- conditions improve -------> CHILD ENERGY PLAN
    |                                      |
    |                                      v
    |                                  EXECUTION
    |                                      |
    |                                      v
    |                                  RELEASED
    |
    +---- operator cancels ----------> CANCELLED
    |
    +---- expiry reached ------------> EXPIRED
```

Terminal states do not return to `held` in V0.

## Active queue

Current queue state lives under:

```text
.ghot/holds/<hold-id>.json
```

The append-only trail remains under:

```text
.ghot/records/
```

Transitions emit:

- `hold.enqueued`
- `hold.rechecked`
- `hold.released`
- `hold.cancelled`
- `hold.expired`

## Wake Composer

Inspect active holds:

```bash
python3 ghot/wake_composer.py list
```

Inspect all terminal + active records:

```bash
python3 ghot/wake_composer.py list --all
```

Re-evaluate one hold:

```bash
python3 ghot/wake_composer.py recheck <hold-id>
```

Re-evaluate all active holds:

```bash
python3 ghot/wake_composer.py wake
```

Continuous local watcher:

```bash
python3 ghot/wake_composer.py watch --interval 5
```

The watcher fingerprints the current liveness/power/offer field and the active
hold set. It wakes work when those inputs change rather than blindly creating a
new plan every polling interval.

## Child-plan lineage

A released HOLD does not disappear into a new unrelated plan.

The child energy plan records:

```text
parent_hold_id
parent_energy_plan_id
trigger
```

The resulting trail is reconstructible:

```text
ENERGY PLAN 12
  -> HOLD 7
      -> hold.rechecked
          -> ENERGY PLAN 13
              action = hold

      -> field changes

      -> ENERGY PLAN 14
          parent_hold_id = HOLD 7
          parent_energy_plan_id = ENERGY PLAN 12
          trigger = hold.wake
              -> execution
                  -> RECEIPT
                      -> HOLD 7 released
```

## Cancellation

```bash
python3 ghot/wake_composer.py cancel <hold-id> "no longer needed"
```

A cancelled hold becomes inert.

A later wake pass reports it as inactive and does not execute it.

## Expiry

An optional bounded lifetime can be attached when scheduling:

```bash
python3 ghot/energy_scheduler.py render.video job.json \
  --urgency background \
  --deferrable \
  --hold-for-seconds 3600
```

The Wake Composer checks expiry before re-evaluation and again immediately
before beginning release execution.

V0 interprets this as:

> do not begin execution after the hold expires.

It does not attempt to terminate work that already began before expiry.

## Dry-run correction

`energy_scheduler.py --dry-run` now persists the ENERGY PLAN for inspection
but does **not** enqueue a live HOLD or execute work.

Planning is no longer confused with queue mutation.

## Current V0 concurrency assumption

The active queue is designed for one local Wake Composer process per GHoT home.

Multiple simultaneous Wake Composer processes are not yet coordinated by a
lease/claim protocol. A future experiment should add atomic claiming before
execution if multi-worker wake processing is required.

## Laws

- HOLD != FAILURE
- QUEUE STATE != EVENT HISTORY
- RECHECK != RELEASE
- RELEASE MUST HAVE A CAUSE
- CANCELLED WORK MUST NOT WAKE
- EXPIRED WORK MUST NOT START
- CHILD PLAN MUST NAME ITS PARENT
- PLANNING != QUEUE MUTATION
- WAITING IS A COMPUTATIONAL DECISION
