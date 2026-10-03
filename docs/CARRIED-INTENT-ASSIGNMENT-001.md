# CARRIED INTENT ASSIGNMENT 001 — ASSIGNMENT != EXECUTION

An admitted `ghot.carried-intent/v0` can now enter GHoT's native body/capability
field without becoming a task.

```text
ADMITTED CARRIED INTENT
        ↓
receiver-owned assignment offer
        ↓
current body × capability field
        ↓
human names one body + one capability
        ↓
revalidate exact pair
        ↓
ASSIGNED_NOT_EXECUTED
```

## Offer

The assignment offer contains the current discovered bodies and their declared
capability offers. It deliberately contains:

- no selected body;
- no selected capability;
- no recommendation;
- no score.

Bodies and capabilities are presented in deterministic lexical order. Eligibility
means only that the body is currently awake and the capability currently reports
`available: true`.

The offer is bound to the exact admitted intent snapshot and admission id.

## Assignment

The caller must return:

- the exact current assignment offer;
- one `selected_node_id`;
- one `capability` that was eligible on that body;
- an attributable `selection_source`.

GHoT re-discovers the selected body and refuses assignment when the body
disappeared, stopped being awake, changed cryptographic particular, withdrew
the capability, or changed availability.

Successful assignment persists:

```text
schema: ghot.carried-intent-assignment/v0
status: ASSIGNED_NOT_EXECUTED
semantic_effect: assignment-only
```

One carried intent has one assignment in this slice. A different later choice is
refused rather than silently replacing the first assignment.

## What does not happen

This surface does **not** call `body_choice.assign()`, because that older surface
continues directly into execution.

It also does not:

- create `ghot.task`;
- create `ghot.receipt`;
- call `reference_node.execute()`;
- call an external adapter;
- make a LAN request;
- dispatch to a remote body;
- interpret the donor door as executable instructions.

## Laws

```text
ADMISSION != ASSIGNMENT
OFFER != ASSIGNMENT
CAPABILITY != AUTHORITY
BODY AVAILABILITY != SELECTION
ASSIGNMENT != EXECUTION
ASSIGNMENT != TASK
SELECTED BODY != AUTHORITY OWNER
CAPABILITY != EXECUTION
DISPATCH REQUIRES A NEW EXPLICIT CROSSING
```

## Proof

```bash
GHOT_HOME="$(mktemp -d)" python3 ghot/carried_intent_assignment_sim.py
```

The simulation builds a real receiver HOLD and admission first, opens the live
GHoT body/capability field, explicitly assigns the intent to the local
`system.hash` offer, and proves that no task or execution receipt appears.
