# Failure-Aware Recomposition

A plan is a snapshot of a moving world.

Between selection and execution:

- a laptop can close;
- Wi-Fi can disappear;
- a battery can die;
- an executable can fail;
- an offer can become stale;
- a borrowed body can leave.

GHoT therefore treats a failed selection as evidence for the **next** plan, not as collapse of the request.

## Loop

```text
INTENT / CAPABILITY
      |
      v
PLAN 1
  select A
      |
      v
ATTEMPT 1
  A disappears
      |
      +--> preserve failure
      |
      +--> exclude A for this composition
      |
      v
PLAN 2
  parent = PLAN 1
  reason = A failed crossing
  select B
      |
      v
ATTEMPT 2
  B succeeds
      |
      v
RECEIPT
      |
      v
COMPOSITION
  final_status = ok
```

## New records

### ATTEMPT

An attempt says what happened when one selected plan met reality.

It records:

- composition id;
- ordinal;
- plan id;
- selected node;
- start/end;
- outcome;
- receipt id/status where available;
- transport/execution error;
- whether to stop or recompose.

### COMPOSITION

A composition is the envelope for the whole resilient request.

It records:

- one stable composition id;
- capability requested;
- ordered attempts;
- nodes excluded after failure;
- final status;
- final plan and receipt.

## Failure is not erased

If A fails and B succeeds, the final record does **not** say merely:

> B completed the task.

It says:

> A was selected under PLAN 1, failed under ATTEMPT 1, that failure caused PLAN 2 to exclude A, B was selected, and ATTEMPT 2 succeeded.

This preserves causality.

## Transport failure vs execution failure

These are intentionally different.

**Transport failure**

The selected body could not complete the crossing:

- connection refused;
- timeout;
- route disappeared;
- body shut down.

There may be no remote receipt.

**Execution failure**

The body received and attempted the task but returned a structured non-ok receipt.

That receipt is preserved.

The LAN layer now returns structured remote error receipts instead of collapsing them into a generic HTTP exception.

## V0 retry policy

On either transport failure or non-ok execution:

1. preserve an ATTEMPT;
2. exclude the selected node from this composition;
3. rediscover bodies;
4. create a new PLAN linked to the previous plan;
5. select among remaining eligible nodes;
6. stop on success, no eligible body, or max attempts.

Default maximum: 3 attempts.

This is intentionally bounded. Resilience must not become an infinite retry storm.

## Law

- PLAN != WORLD
- FAILURE != ERASURE
- RETRY != REPETITION
- RECOMPOSITION MUST CARRY CAUSE
- NODE LOSS != ORGANISM LOSS

## Future policy questions

005 keeps policy deliberately simple. Later experiments can distinguish:

- retryable vs permanent capability errors;
- backoff;
- temporary quarantine instead of composition-local exclusion;
- stale-offer TTL;
- circuit breakers;
- queue pressure;
- power transitions;
- partial work/checkpoint continuation;
- replicated/multi-body execution.
