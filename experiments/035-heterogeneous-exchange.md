# Experiment 035 — Heterogeneous Exchange

## Question

Can two sovereign participants settle an exchange whose two sides are genuinely
different kinds of obligation without inventing a common scalar, universal
price, or exchange rate?

## Frozen path

```text
Dogram contribution history
        |
        v
Realm projection: 13 lumen
        |
        | orientation only
        v
heterogeneous offer
        |
        +-- artist promises: artifact access
        |
        +-- host promises: compute service
        |
        v
explicit acceptance
        |
        +-- OFFEROR performance attestation
        |
        +-- ACCEPTOR performance attestation
        |
        v
bilateral heterogeneous settlement
```

The 13-lumen projection exists and remains inspectable, but it is **not used as
a price** and is not converted into compute.

There is no equation of the form:

```text
artifact access = N lumen = M compute
```

The protocol records only that two participants voluntarily bound themselves to
two declared obligations and later supplied evidence that each obligation was
performed.

## Obligation objects

Each side is carried as a content-addressed typed obligation:

```text
offeror obligation
  type = artifact-access
  resource = license:<render address>
  terms = {
    scope,
    artifact_ref,
    revocation
  }

acceptor obligation
  type = compute-service
  resource = ghot-capability:ice-cube/v0
  terms = {
    work_family,
    requested_width,
    requested_height,
    verification
  }
```

The types and terms remain different all the way through settlement.

## Forbidden collapse

The 035 kernel fails closed on economic-conversion fields such as:

```text
price
exchange_rate
common_unit
currency
monetary_amount
equivalent_value
conversion_rate
```

This is not a claim that such things can never exist.

It means they cannot be smuggled into this protocol while pretending the
protocol itself derived them.

## Consent boundary

Acceptance binds the exact two obligations by a terms digest.

The hostile control changes the compute request after acceptance from one
declared width to another and re-addresses the altered offer.

The existing acceptance must then fail verification.

Thus:

> **ACCEPTANCE OF A RELATION DOES NOT AUTHORIZE LATER REWRITING OF ITS TERMS.**

## Performance boundary

Each participant signs only their own role:

```text
OFFEROR -> artifact-access performance evidence
ACCEPTOR -> compute-service performance evidence
```

Settlement with only one signature is refused.

No participant can unilaterally promote their own performance into a completed
bilateral exchange.

## Settlement

The final settlement preserves both obligations verbatim and references both
signed performance attestations.

It explicitly does not request:

```text
conversion_rate
common_unit
mint_authority
balance_mutation
ownership_transfer
```

Settlement authority remains:

```text
bilateral-evidence-only
```

## Generality control

035 also creates a second offer with no valuation projection at all:

```text
hosting-service
      <->
future-labor-writ
```

The same offer grammar accepts this pair.

That demonstrates the protocol is not special-cased to:

- lumen;
- Ice Cube;
- artifact licensing;
- compute;
- or even the existence of an upstream economic projection.

## Laws

```text
OBLIGATION A != OBLIGATION B
ORIENTATION != PRICE
NO COMMON UNIT REQUIRED
OFFER != ACCEPTANCE
ACCEPTANCE != PERFORMANCE
PERFORMANCE != SETTLEMENT
SETTLEMENT != CONVERSION
BILATERAL PERFORMANCE != GLOBAL VALUATION
```

## Result

The minimal economic substrate now supports:

```text
history
-> measurement
-> optional valuation
-> heterogeneous proposal
-> consent
-> role-local performance
-> bilateral settlement
```

without requiring:

```text
global coin
global price oracle
global balance ledger
global exchange rate
```

## Next aperture

The next interesting step is **036: Labor Writs**.

The old Lightwalker vocabulary already had the right object. A future promise of
bounded work should become a portable capability-like obligation with:

- issuer;
- scope;
- expiry;
- delegation policy;
- redemption conditions;
- performance receipt;
- exhaustion / replay refusal.

That would let the old Lightwalker **Labor Writ** return as an actual bounded
economic instrument rather than a token metaphor.
