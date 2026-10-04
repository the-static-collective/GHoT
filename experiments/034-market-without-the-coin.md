# Experiment 034 — The Market Without the Coin

## Question

Can two sovereign participants complete an exchange using the Lightwalker
contribution/economic stack without requiring a canonical token ledger to define
what happened?

## Path

```text
verified useful work
      |
      v
immutable Workmark
      |
      v
Dogram measurement
      |
      v
Realm valuation projection          13 lumen
      |
      |  VALUATION != OFFER
      v
seller offer                        11 lumen
      |
      |  OFFER != ACCEPTANCE
      v
buyer acceptance
      |
      |  ACCEPTANCE != PERFORMANCE
      +-----------------------------+
      |                             |
      v                             v
seller DELIVERY              buyer CONSIDERATION
signed performance           signed performance
      |                             |
      +-------------+---------------+
                    |
                    v
          bilateral settlement
                    |
                    v
          portable settlement record
```

No global balance table is required to say that the bilateral performance
occurred.

## Why the offer is 11 when the projection is 13

This is deliberate.

The Realm projection is an interpretation of contribution history. It is not a
price oracle and does not compel a trade.

In the frozen specimen:

```text
Realm projection = 13 lumen
seller offer     = 11 lumen
```

That proves:

```text
VALUATION != OFFER
```

A participant can discount, premium-price, barter, refuse to sell, or use a
different unit entirely without rewriting the projection.

## Acceptance

Acceptance freezes the exact offered terms and references the exact offer.

It does not:

- transfer the deliverable;
- create a payment;
- mutate a balance;
- settle the exchange.

The acceptance crossing explicitly requests no automatic settlement.

## Performance

Settlement requires two separately signed attestations:

1. `DELIVERY` signed by the offeror.
2. `CONSIDERATION` signed by the acceptor.

The experiment attempts settlement with only the delivery attestation and
requires refusal.

Thus:

> **ONE PARTY CANNOT UNILATERALLY DECLARE A BILATERAL EXCHANGE SETTLED.**

## Settlement

Once both attestations verify, the settlement object is deterministically
derived from them.

Its authority is:

```text
bilateral-evidence-only
```

It records what the two parties attested happened. It does not itself create a
universal currency, universal ownership judgment, or hidden account mutation.

The portable settlement crossing explicitly carries:

```text
mint_authority_requested = false
balance_mutation_requested = false
ownership_transfer_inferred = false
```

## Frozen laws

```text
VALUATION != OFFER
OFFER != ACCEPTANCE
ACCEPTANCE != PERFORMANCE
PERFORMANCE != SETTLEMENT
SETTLEMENT != WORKMARK
SETTLEMENT DOES NOT CREATE UNIVERSAL MONEY
DELIVERY != PAYMENT
RECORDING SETTLEMENT != REPLAYING SETTLEMENT
```

## Why this is a market

A market does not fundamentally require one universal coin.

It requires at least:

- independently attributable goods/services;
- independently attributable proposals;
- voluntary acceptance;
- evidence of performance;
- durable settlement history.

Money can be one coordination instrument layered over those primitives.

Experiment 034 makes the primitives executable first.

## Next aperture

The next experiment should test **heterogeneous consideration**:

```text
artifact access
    <->
compute credit

repair work
    <->
hosting

rendering
    <->
future labor writ
```

That would test whether the market protocol remains invariant when the two sides
are not denominated in the same scalar unit at all.

The architectural target becomes:

> **EXCHANGE CAN BE COMPOSED BEFORE CURRENCY IS STANDARDIZED.**
