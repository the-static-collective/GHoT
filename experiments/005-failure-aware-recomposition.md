# Experiment 005 — Failure-Aware Recomposition

## Question

Can GHoT survive the selected body disappearing between plan and execution without erasing the failed attempt or requiring the human to manually choose a fallback?

## Trial A — deterministic simulation

No second machine required:

```bash
python3 ghot/recomposition_sim.py
```

The simulation creates:

- body A: higher score;
- body B: lower score;
- attempt 1: A selected, then simulated transport failure;
- plan 2: A excluded;
- attempt 2: B selected and succeeds.

Expected final line:

```json
{
  "simulation_passed": true
}
```

Inspect `.ghot/records` for ATTEMPT and COMPOSITION records.

## Trial B — real disappearing body

Use at least two serving bodies plus the requester when possible.

Start nodes:

```bash
python3 ghot/lan_node.py serve --port 7788
```

From the requester:

```bash
python3 ghot/resilient_composer.py runtime.ffmpeg.version \
  --no-prefer-local \
  --prefer-memory \
  --max-attempts 3
```

To deliberately hit the race, stop/disconnect the initially preferred remote body after planning/discovery but before its task arrives. A later test hook may make this timing deterministic.

Expected:

1. PLAN 1 selects A;
2. crossing to A fails;
3. ATTEMPT 1 preserves transport failure;
4. A enters `excluded_node_ids`;
5. GHoT rediscovers the heap;
6. PLAN 2 references PLAN 1 and carries a recomposition reason;
7. B is selected if still eligible;
8. ATTEMPT 2 succeeds;
9. COMPOSITION final status is `ok`.

## Trial C — executed failure

Request a capability/input combination that reaches an adapter but returns a non-ok receipt.

Expected:

- remote structured receipt is retained;
- ATTEMPT outcome is `execution-error` or equivalent;
- selected node is excluded;
- recomposition may try another eligible body.

## Trial D — exhaustion

Request a capability available on one body only, then make it disappear.

Expected:

- failed ATTEMPT for that body;
- next plan has no eligible remaining body;
- final status `no-eligible-body` rather than fabricated success.

## Pass

005 passes when the record alone is enough to reconstruct:

- what was requested;
- why A was selected;
- how A failed;
- why the next plan changed;
- why B was selected;
- which attempt finally succeeded;
- or why the composition stopped.

## Mutation opened

006 should make **liveness itself explicit** instead of depending only on discovery responses:

- offer TTL;
- heartbeats;
- last-seen;
- stale vs offline;
- temporary quarantine;
- circuit breaker;
- body arrival/departure events.

That makes the heap maintain a continuously revisable picture of which organs are awake.
