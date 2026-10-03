# FIELD RESEED RECEIVER 001

GHoT can now receive one proposal-only Static Workbench Field reseed through a
verified reLATTE opaque-organ round trip, preserve it in receiver-local HOLD,
and admit it only after a separate explicit human action.

```text
Workbench TAKE
  -> workbench.field-reseed/v0
  -> reLATTE opaque crossing
  -> RECEIVED
  -> R3_HOLD
  -> GHoT field-reseed inbox
  -> explicit ADMIT
  -> ghot.carried-intent/v0
```

## Receive boundary

The receiver accepts only:

- `workbench.field-reseed/v0` with a valid deterministic `reseed_id`;
- proposal-only status and `effect: none`;
- a `relatte.opaque-roundtrip-result/v0`;
- matching crossing / RECEIVE / HOLD receipt identities;
- `RECEIVED` with semantic effect `none`;
- `R3_HOLD` with semantic effect `none`;
- receiver world `world:ghot:field-reseed-inbox`;
- donor family `organ:static-workbench/field-return`;
- an exact SHA-256 payload ref for the carried reseed.

Receiving persists the donor snapshot and transport witness under
`GHOT_HOME/field-reseed-inbox/`. It does not interpret the donor door as a
GHoT task.

## Admission boundary

Admission requires the exact local HOLD id plus an explicit selection source.

It creates:

- `ghot.field-reseed-admission/v0`;
- `ghot.carried-intent/v0`;
- status `admitted-not-assigned`;
- effect `local-inbox-only`.

No executor, capability, node, shell command, or remote body is selected by
admission.

## Laws

```text
RECEIVE != ADMISSION
HOLD != EXECUTION
TRANSPORT != AUTHORITY
DONOR PROPOSAL != RECEIVER INTENT
ADMISSION != ASSIGNMENT
ASSIGNMENT != EXECUTION
CARRIED INTENT != DONOR AUTHORITY
RECEIVER CONSEQUENCE != DONOR CONSEQUENCE
```

## Deterministic proof

```bash
GHOT_HOME="$(mktemp -d)" python3 ghot/field_reseed_receiver_sim.py
```

The proof covers exact donor binding, idempotent HOLD, explicit admission,
durable inbox state, and the absence of an execution side effect.
