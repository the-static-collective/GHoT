# Experiment 006 — Liveness Field

## Question

Can GHoT remember bodies across silence, distinguish awake/stale/departed state, record arrival/return events, and temporarily quarantine repeatedly failing bodies without deleting their history?

## Trial A — deterministic lifecycle

```bash
python3 ghot/liveness_sim.py
```

The simulation verifies:

```text
unknown
 -> awake
 -> stale
 -> departed
 -> returned/awake
 -> three failures
 -> quarantined
 -> heartbeat while quarantined
 -> quarantine expires
 -> awake
```

Expected:

```json
{
  "simulation_passed": true,
  "final_state": "awake"
}
```

## Trial B — real heartbeat field

On one or more remote bodies:

```bash
python3 ghot/lan_node.py serve --port 7788
```

On the observing body:

```bash
python3 ghot/liveness_field.py watch --interval 5
```

Stop one remote body.

Observe its state age without disappearing from the field:

```text
awake -> stale -> departed
```

Restart it.

Expected:

```text
departed -> awake
event: body.returned
same node_id
```

## Trial C — circuit breaker

Record failures manually for a known node during development:

```bash
python3 ghot/liveness_field.py failure <node-id> "test failure 1"
python3 ghot/liveness_field.py failure <node-id> "test failure 2"
python3 ghot/liveness_field.py failure <node-id> "test failure 3"
python3 ghot/liveness_field.py show
```

Expected state: `quarantined`.

The resilient composer is wired to report actual failed/successful attempts into this same field, so manual failure injection is only a test aid.

## Pass

006 passes when:

1. silence changes eligibility without deleting body memory;
2. a returning body keeps the same identity;
3. events reconstruct arrival/stale/departure/return;
4. three failures trip the V0 circuit breaker;
5. quarantine is bounded;
6. composers reject non-awake bodies.

## Mutation opened

007 should make **power an active field dimension**:

- real battery probing where supported;
- AC/USB/solar source;
- thermal pressure;
- willingness state;
- heavy-offer withdrawal;
- renewable-surplus scheduling.

That recovers the April 2024 energy-aware distributed-compute idea directly.
