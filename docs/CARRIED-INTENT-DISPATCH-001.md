# CARRIED INTENT DISPATCH 001 — Assignment Opens a New Crossing

An assignment is not permission to run.

CARRIED INTENT DISPATCH 001 adds a separate explicit crossing from a durable
`ASSIGNED_NOT_EXECUTED` receipt into one bounded capability attempt.

```text
admitted carried intent
  → explicit body + capability assignment
  → ASSIGNED_NOT_EXECUTED
  → explicit DISPATCH
  → signed reLATTE crossing
  → revalidate exact assigned pair
  → persist PREPARED
  → execute exactly one bounded capability attempt
  → GHoT task + execution receipt
  → signed receiver consequence receipt
  → EXECUTED | EXECUTION_ERROR
```

## Dispatch payload

The selected capability receives a receiver-owned payload:

```text
ghot.carried-intent-execution-payload/v0
```

It carries:

- carried-intent id;
- assignment id;
- source reseed and Field Return ids;
- the exact carried door snapshot;
- the human note;
- the already-selected body/capability pair.

The donor door remains evidence. It is not interpreted as a command.

## Signed crossing

Before execution, GHoT creates and verifies a signed
`relatte.crossing-envelope/v0` using the reLATTE P-256 identity profile.

The crossing binds:

- the exact assignment digest;
- the exact execution-payload digest;
- selected node id;
- selected capability;
- receiver selection provenance;
- GHoT's dispatch identity.

The crossing itself is persisted before any execution begins.

## Prepared means uncertain, not retryable

The durable state machine is:

```text
absent
  → prepared
  → completed
```

If a process stops after `prepared` but before a completed consequence can be
persisted, the next invocation returns:

```text
DISPATCH_OUTCOME_UNKNOWN
```

It does not automatically execute again.

This is deliberate. Duplicate execution is a larger authority error than
requiring an explicit recovery procedure after an ambiguous outcome.

Completed dispatch is idempotent: repeating the same explicit request returns
the original result and does not create another task.

## Revalidation

Immediately before preparing the dispatch crossing, GHoT re-discovers the exact
assigned body/capability pair.

Dispatch refuses if:

- the body disappeared;
- it is no longer awake;
- its cryptographic particular changed;
- the capability disappeared;
- the capability is no longer available.

It never silently assigns a replacement body or capability.

## Execution

For a local body, dispatch calls the existing bounded
`reference_node.execute()` surface.

For an already-assigned remote body, dispatch uses the existing LAN task route.
The signed dispatch crossing is carried in the task constraints so the remote
task retains the exact assignment provenance.

No arbitrary shell surface is added.

## Signed consequence receipt

After the bounded capability attempt returns, GHoT creates a signed
`relatte.receipt/v0` bound to the dispatch crossing.

The receipt records:

- selected node and capability;
- task id;
- GHoT execution-receipt id;
- execution status;
- output digest when available;
- execution error when present.

`kind: EXECUTED` means the bounded attempt occurred. It does not mean the
capability returned success; that remains explicit in the extension status.

## Laws

```text
ASSIGNMENT != EXECUTION
DISPATCH != SUCCESS
EXECUTION != RECEIPT
RECEIPT != TRUTH
PAYLOAD != AUTHORITY
DOOR != COMMAND
EXECUTOR CONSEQUENCE != DONOR AUTHORITY
AMBIGUOUS OUTCOME != SAFE RETRY
RETRY REQUIRES EXPLICIT RECOVERY AFTER UNKNOWN OUTCOME
```

## Proof

```bash
GHOT_HOME="$(mktemp -d)" python3 ghot/carried_intent_dispatch_sim.py
```

The proof builds the complete local chain through HOLD, admission, offer,
assignment, signed dispatch, bounded `system.hash` execution, and signed
consequence receipt. It then repeats the dispatch and proves no duplicate task
or receipt is created.

A second assigned intent is placed into prepared-but-incomplete state and proves
that automatic retry is refused.
