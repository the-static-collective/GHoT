# Experiment 033 — Time Assays the Ore

## Question

Can one verified useful-work contribution acquire later attributable consequences,
be re-measured by Dogram, and receive a new Realm-local economic projection
without rewriting either the original Workmark or the original projection?

## Composition

This experiment composes three already-existing layers rather than inventing a
new chain:

```text
GHoT Ice Cube useful work
        |
        v
Dogram bounded Ice Cube verification
        |
        v
Dogram CONTRIBUTION-FIELD-001 birth event
        |
        v
immutable Dogram Workmark
        |
        +------ cut 0 measurement ------> Lantern lens ------> 7 lumen
        |
        +------ later attributable events
                         |
                         v
                  cut 1 measurement
                         |
                         v
                    same lens
                         |
                         v
                      13 lumen
```

The `7 lumen` projection is not edited into `13 lumen`.

They are two different content-addressed projections over:

- the same immutable Workmark;
- the same declared Realm lens;
- two different Dogram measurement receipts.

## Frozen specimen

The Ice Cube specimen becomes the contribution root.

At cut 0:

```text
worker --CREATED--> Ice Cube
descendant_count = 0
```

At cut 1 the declared finite specimen additionally contains:

```text
Ice Cube --ENABLED--> artifact use
artifact use --CARRIED--> derived study
reviewer --CHALLENGED--> Ice Cube
```

Dogram therefore reports two reachable descendants from the original
contribution root.

This is a structural measurement. It is not value.

## Realm assay lens

Lantern Realm declares:

```text
unit = lumen
basis = base-plus-descendants
base_amount = 7
per_descendant = 3
```

Therefore:

```text
cut 0: 7 + (0 * 3) = 7 lumen
cut 1: 7 + (2 * 3) = 13 lumen
```

Those numbers are not emitted by Dogram. They are the output of a separately
identified Realm-local lens.

## Anti-retroactivity

Experiment 033 explicitly freezes the original serialized Workmark and original
cut-0 projection before creating the cut-1 projection.

After cut 1:

```text
birth Workmark bytes: unchanged
cut-0 projection bytes: unchanged
cut-1 projection: new address
```

Thus:

> **LATER CONSEQUENCE MAY CHANGE A LATER ECONOMIC PROJECTION. IT MAY NOT CHANGE THE PAST.**

## Crossing boundary

Only the newer projection is sent through the crossing in this experiment.

The signed request says:

```text
operation = consider-assay-projection
mint_authority_requested = false
retroactive_repricing_requested = false
```

The receiver first HOLDs the packet with semantic effect `none`, then makes an
explicit owner-local ADMIT decision.

Admission remains information admission, not automatic settlement.

## Historical Dogram isolation

The Ice Cube verifier and CONTRIBUTION-FIELD-001 currently live on different
historical Dogram branches.

Experiment 033 therefore runs the contribution-field code through an isolated
subprocess bridge. This is intentional: each historical instrument is used from
its own repository state, with no import-path blending.

## Laws

```text
WORKMARK != MEASUREMENT != VALUATION
LATER HISTORY MAY ENRICH THE FIELD
LATER HISTORY MAY NOT REWRITE BIRTH
MEASUREMENT != VALUATION
NEW MEASUREMENT MAY CREATE NEW PROJECTION
NEW PROJECTION MAY NOT REWRITE OLD PROJECTION
DELIVERY != PAYMENT
```

## Economic interpretation

This is the first executable form of:

> **WORK MINES THE MARKER. TIME ASSAYS THE ORE. COMMUNITY NAMES AN EXCHANGE RATE.**

"Time" here is not passive clock time. It means later attributable evidence
entering a new declared cut of contribution history.

The Workmark still has no universal price.

A different Realm can use the same measurements differently, use other
measurements, or decline economic interpretation entirely.

## Next aperture

The next honest move is to make **settlement itself a separate local act**:

```text
projection -> offer -> acceptance -> settlement receipt
```

That would let us distinguish:

```text
VALUATION != OFFER
OFFER != ACCEPTANCE
ACCEPTANCE != SETTLEMENT
SETTLEMENT != WORKMARK
```

At that point Lightwalker economics begins to look like an actual plural
exchange protocol rather than a token system.
