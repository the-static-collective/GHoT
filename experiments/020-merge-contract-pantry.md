# Experiment 020 — Merge-Contract Pantry

## Question

Can GHoT discover multiple installed local merge grammars, explain exact
compatibility, persist explicit selection, and revalidate that selection before
creating a normal 019 merge plan?

## Deterministic proof

```bash
python3 ghot/merge_contract_pantry_sim.py
```

## Trial A — multiple installed grammars

Expected pantry:

```text
ghot.organ.offers->foreign-offer-catalog/v0
ghot.organ.presence->foreign-presence-catalog/v0
```

Each contract has a distinct content address and declares no authority or
freshness effect.

## Trial B — offers compatibility

ADMIT an organ-state `/body/offers` parcel.

Expected:

- only the offers grammar is compatible;
- presence grammar reports selector and payload-shape mismatch;
- selecting the incompatible presence grammar is refused.

SELECT must create no 019 plan and no local target file.

PROPOSE must then produce:

```text
selection
 -> selection-to-plan link
 -> 019 merge plan
```

Still no target mutation until normal 019 APPLY.

## Trial C — presence grammar

ADMIT an organ-state `/presence` parcel.

Expected:

- only presence grammar is compatible;
- SELECT creates no target;
- PROPOSE creates a linked 019 plan;
- APPLY creates `foreign-presence.v0.json`;
- resulting state contains no liveness, trust, or authority surface.

## Trial D — no generic fallback

ADMIT selector `/work`.

Expected:

```text
compatible contracts: []
selection refused
```

## Trial E — admitted-state drift

SELECT a valid offers parcel, mutate its admitted local materialization, then
PROPOSE.

Expected:

```text
REFUSE
```

The persisted selection cannot silently retarget changed local evidence.

## Trial F — contract drift

SELECT a valid presence grammar, then change the installed descriptor before
PROPOSE.

Expected:

```text
REFUSE
```

The selected contract address is part of the durable selection.

## Trial G — shared payload-shape rule

Create `/body/offers` with an object payload rather than an array.

Expected:

```text
pantry compatible contracts: []
019 engine eligible contracts: []
reason: payload-type-mismatch
```

## Pass

020 passes when the pantry simulation and the full 001–019 smoke chain are
green.

## Mutation opened

021 can make merge contracts installable as first-class **organ plugins**:

```text
contract package
  -> signed/local manifest
  -> schema refs
  -> bounded pure merge function
  -> conformance fixture
  -> install into pantry
  -> discover as compatible door
```

That would let GHoT grow new lawful composition grammars without hard-coding
every merge into the core runtime.
