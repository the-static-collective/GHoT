# Experiment 019 — Owner-Local State Merge Receipts

## Question

Can GHoT compose an already-admitted foreign state fragment into a real local
durable state while keeping the mutation schema-specific, owner-approved,
race-safe, crash-recoverable, and separate from trust/execution authority?

## Deterministic proof

```bash
python3 ghot/state_merge_sim.py
```

The simulation creates a source BODY and a receiver BODY, uses the real 018
parcel/admission path, then exercises the first 019 merge contract.

## Trial A — first merge

Source exports:

```text
ghot.organ.state/v1
selector /body/offers
```

Receiver HOLDs and ADMITs it.

019 must identify exactly one eligible contract:

```text
ghot.organ.offers->foreign-offer-catalog/v0
```

PROPOSE must not mutate local state.

APPLY must create:

```text
GHOT_HOME/knowledge/foreign-offers.v0.json
```

with source-particular/capability provenance and a verified BODY-signed merge
receipt.

## Trial B — existing target + exact backup

A second admitted offer snapshot updates the same source.

Before APPLY, the existing catalog bytes are captured.

Expected:

- exact backup exists;
- backup bytes equal the pre-merge catalog bytes;
- updated capability values appear;
- capabilities from the prior remembered snapshot are preserved;
- both parcel ids are recorded.

## Trial C — stale local plan

Create a proposal, then change the local target before APPLY.

Expected:

```text
APPLY REFUSED
no merge receipt
```

The plan cannot silently recompute against a different local state.

## Trial D — explicit REJECT

Create a valid proposal and REJECT it.

Expected:

- signed REJECT merge receipt;
- local BEFORE == local AFTER;
- later APPLY of that plan is refused;
- local target remains unchanged.

## Trial E — HOLD is insufficient

Receive a valid parcel but leave it in HOLD.

Expected:

```text
not merge eligible
```

## Trial F — schema/selector mismatch

ADMIT a parcel from the same source schema but selector `/work`.

Expected:

```text
eligible contracts: []
proposal refused
```

No generic merge fallback exists.

## Trial G — interrupted receipt persistence

Create a valid proposal, manually materialize the exact proposed AFTER state,
but do not create its receipt.

Expected APPLY retry:

```text
current target == proposed AFTER
 -> reconcile receipt
 -> do not rewrite target
```

## Trial H — admitted materialization tamper

Create a proposal, then alter the retained admitted materialization.

Expected:

```text
APPLY REFUSED
local target unchanged
```

## Pass

019 passes when all new trials plus the complete 001–018 smoke suite are green.

## Mutation opened

020 can turn this from one merge contract into a **merge-contract pantry**:

```text
ADMITTED PARCEL
  -> inspect source schema + selector
  -> discover locally installed merge contracts
  -> present compatible merge possibilities
  -> explicit human/external selection
  -> proposal
  -> APPLY / REJECT
  -> receipt
```

The important next move is not automatic universal merging. It is making
multiple bounded merge grammars discoverable without collapsing selection into
authority.
