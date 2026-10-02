# Experiment 009 — Hold Queue / Wake Composer

## Question

Can GHoT preserve deferrable work across time, re-evaluate it when the world
changes, release it with full lineage, and guarantee that cancelled or expired
work is not started by the Wake Composer?

## Trial A — deterministic lifecycle

```bash
python3 ghot/wake_sim.py
```

The simulation proves:

1. background heavy work is held under a battery-only field;
2. a recheck keeps it held without executing;
3. a later solar-surplus field creates a child ENERGY PLAN;
4. the child plan names the original HOLD and ENERGY PLAN;
5. the released task executes exactly once;
6. a cancelled hold never executes;
7. an expired hold never executes.

Expected:

```json
{
  "simulation_passed": true,
  "execution_count": 1
}
```

## Trial B — create a real bounded HOLD

Once a real heavy capability exists:

```bash
python3 ghot/energy_scheduler.py render.video job.json \
  --urgency background \
  --deferrable \
  --hold-for-seconds 3600
```

If current energy policy says wait, inspect:

```bash
python3 ghot/wake_composer.py list
```

## Trial C — change the field

Start or alter a serving body so its BODY advertises favorable power:

```bash
GHOT_POWER_SOURCE=solar \
GHOT_RENEWABLE_SURPLUS=1 \
GHOT_CHARGING=1 \
python3 ghot/lan_node.py serve --port 7788
```

Then:

```bash
python3 ghot/wake_composer.py wake
```

Expected:

- original HOLD remains in history;
- child energy plan references the HOLD and parent energy plan;
- work executes only if the new plan says run;
- HOLD becomes `released` on successful execution.

## Trial D — cancel

```bash
python3 ghot/wake_composer.py cancel <hold-id> "operator changed intent"
python3 ghot/wake_composer.py recheck <hold-id>
```

Expected: no execution.

## Trial E — expiry

Create a short-lived HOLD using `--hold-for-seconds`, allow it to expire, then
run:

```bash
python3 ghot/wake_composer.py wake
```

Expected:

- status becomes `expired`;
- event `hold.expired` is emitted;
- no task starts.

## Trial F — watcher

```bash
python3 ghot/wake_composer.py watch --interval 5
```

With the field unchanged, the watcher should not continuously create child
plans.

Change one of:

- body arrival/departure;
- offer availability;
- power willingness;
- power source;
- renewable surplus;
- active hold membership.

Expected: the watcher performs a wake pass.

## Pass

009 passes when the durable trail can answer:

- what was originally requested;
- why it was held;
- each time it was reconsidered;
- what changed before release;
- which child energy plan released it;
- what receipt completed it;
- or why it was cancelled/expired instead.

## Mutation opened

010 should add an **atomic claim / work lease** for multi-worker wake processing:

- one wake worker claims a HOLD before execution;
- concurrent workers cannot double-run it;
- lease timeout recovers after a crashed worker;
- cancellation wins before claim;
- expiry wins before claim;
- claims and recoveries are receipt-bearing.

That would allow multiple GHoT bodies/processes to service the same durable work
queue without duplicate execution.
