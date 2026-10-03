# Owner-Local State Merge Receipts

Experiment 019 adds the first schema-specific local merge protocol over
**already ADMITTED** state parcels.

Core law:

> ADMISSION MAKES A FOREIGN FRAGMENT LOCALLY AVAILABLE. IT DOES NOT AUTHORIZE MERGE.

## First merge contract

The first concrete contract is deliberately observational:

```text
source:
  ghot.organ.state / v1
  selector = /body/offers

target:
  GHOT_HOME/knowledge/foreign-offers.v0.json
  ghot.foreign-offer-catalog / v0
```

It lets one body remember what another body reported it could do.

It does not grant:

```text
liveness
trust
authority
scheduling eligibility
execution permission
```

Therefore:

```text
FOREIGN OFFER CATALOG != LIVE OFFER SET
```

## Eligibility

A parcel is merge-eligible only when all of these hold:

1. the receiver has an inbox record for it;
2. that inbox record has terminal disposition `ADMIT`;
3. the retained raw parcel bundle still verifies;
4. the admitted materialization still matches the raw parcel;
5. an exact registered merge contract accepts the source state kind/version and selector.

A parcel that is merely `HOLD`, `REJECT`, or `SCAR` cannot be merged.

## Proposal

Create a proposal:

```bash
python3 ghot/state_merge.py eligible <parcel-id>
python3 ghot/state_merge.py propose <parcel-id>
```

The proposal binds:

```text
merge contract id
parcel id/address
payload address
admitted materialization address

local target path
local target kind/version
local target existed?

local BEFORE semantic address
proposed AFTER semantic address
```

The proposal is content-addressed as `ghot.state.merge.plan/v0`.

No state is changed by proposal.

```text
MERGE PROPOSAL != MERGE
```

## First target state

If no foreign-offer catalog exists, planning uses the canonical empty state:

```json
{
  "kind": "ghot.foreign-offer-catalog",
  "version": "0",
  "entries": [],
  "merged_parcels": []
}
```

The file is not created until APPLY.

## Merge function

The first merge function is deterministic.

Entries are keyed by:

```text
(source BODY particular, capability)
```

An incoming admitted snapshot updates that source/capability pair.

Capabilities from older parcels that are absent from a newer snapshot are not
deleted automatically. The catalog is a provenance-bearing memory surface, not
a direct mirror of current peer liveness.

Every entry records:

```text
source BODY particular
source node id
capability
reported availability
reported power class
parcel id
payload address
```

The catalog also records the set of merged parcel ids.

## Owner decision

List plans:

```bash
python3 ghot/state_merge.py plans
```

The owner then explicitly chooses:

```bash
python3 ghot/state_merge.py apply <plan-id>
```

or:

```bash
python3 ghot/state_merge.py reject <plan-id> --note "not useful here"
```

There is no network merge endpoint.

A foreign body cannot call APPLY.

## APPLY revalidation

Before writing, GHoT revalidates:

```text
parcel still ADMITTED
raw parcel still verifies
admitted materialization unchanged
parcel address unchanged
payload address unchanged
merge contract still registered
local target path unchanged
local BEFORE address unchanged
merge output still equals proposed AFTER address
```

If the local target changed after proposal:

```text
STALE PLAN -> REFUSE
```

No best-effort merge is attempted.

## Exact backup

When the local target already exists, APPLY preserves its exact bytes under:

```text
GHOT_HOME/state-merges/backups/
```

before replacing it.

The merge receipt binds the backup path.

## Atomic local write

Successful APPLY:

```text
ADMITTED PARCEL
   +
LOCAL BEFORE STATE
   ↓
registered merge function
   ↓
PROPOSED AFTER
   ↓
owner APPLY
   ↓
revalidate parcel + local state
   ↓
exact backup if needed
   ↓
atomic local write
   ↓
re-read + verify AFTER address
   ↓
BODY-signed MERGE RECEIPT
```

## Merge receipt

`ghot.state.merge.receipt/v0` binds:

```text
plan id
contract id
APPLY or REJECT
parcel id/address
payload address
admitted ref
local target path
local BEFORE address
local AFTER address
backup path
BODY particular
note
time
P-256 signature
```

A REJECT receipt has:

```text
local AFTER address == local BEFORE address
```

and no local target mutation.

Terminal decisions are exclusive.

## Crash reconciliation

019 carries forward the 017 crash rule.

Failure window:

```text
merged target written
   ↓
power loss
   ↓
merge receipt missing
```

On retry, if the current target semantic address exactly equals the plan's
proposed AFTER address, GHoT may recreate the missing receipt without rewriting
the target.

If current state matches neither BEFORE nor AFTER:

```text
REFUSE
```

## Duplicate parcel protection

A parcel already listed in `merged_parcels` cannot produce another merge
proposal for the same target contract.

## Why the first target is observational

019 intentionally does **not** merge foreign state into:

- the live liveness field;
- authority trust records;
- lease ownership;
- task dispatch;
- current organ execution state.

Those surfaces have independent authority and freshness laws.

The foreign-offer catalog can later inform a user or composer that a capability
was reported before, but any actual dispatch still requires current discovery,
offer revalidation, and the existing authority path.

## Operator surface

```bash
python3 ghot/state_merge.py eligible <parcel-id>
python3 ghot/state_merge.py propose <parcel-id>
python3 ghot/state_merge.py plans
python3 ghot/state_merge.py apply <plan-id>
python3 ghot/state_merge.py reject <plan-id>
python3 ghot/state_merge.py receipts
```

## Laws

- HOLD != ADMIT
- ADMIT != MERGE
- MERGE PROPOSAL != MERGE
- FOREIGN STATE != LOCAL AUTHORITY
- FOREIGN OFFER CATALOG != LIVE OFFER SET
- REMEMBERED CAPABILITY != CURRENT CAPABILITY
- MERGE RECEIPT != EXECUTION AUTHORITY
- STALE PLAN != PERMISSION TO RECOMPUTE SILENTLY
- SIGNED MERGE != SEMANTIC INFALLIBILITY
