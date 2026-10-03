# BODY CHOICE 002 — REPLAY-SAFE ASSIGNMENT

## Problem

A body assignment is an execution authorization boundary.

If a caller loses the response after execution and retries the same assignment, GHoT must not silently execute the task twice.

## Rule

```text
RETRY != SECOND EXECUTION
```

An assignment identity is derived from:

- exact body-offer id;
- capability;
- requester node id;
- selected node id;
- payload digest;
- selection source.

The resulting assignment id is content-addressed.

## Durable state

Before execution, GHoT writes:

```text
state = prepared
assignment_id
request_sha256
assignment
```

After execution returns, GHoT writes:

```text
state = completed
assignment_id
request_sha256
assignment
result
```

A retry of a completed assignment returns the exact stored result and original GHoT receipt.

A retry that finds only a `prepared` state refuses automatic execution with `ASSIGNMENT_OUTCOME_UNKNOWN`.

That conservative refusal handles the crash window where GHoT cannot prove whether the selected body executed before local result persistence.

## Non-collapse

```text
PREPARED != EXECUTED
UNKNOWN OUTCOME != SAFE TO REPLAY
RETRY != NEW AUTHORITY
SAME REQUEST != SECOND EFFECT
```

A caller that receives `ASSIGNMENT_OUTCOME_UNKNOWN` must inspect/reconcile rather than automatically issuing the same execution again.
