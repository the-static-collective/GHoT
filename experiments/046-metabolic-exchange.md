# Experiment 046 — Metabolic Exchange

## Question

Can a heterogeneous bilateral settlement become usable operational capacity
without collapsing payment, settlement, Treasury inventory, lease authority, or
consumption into one state?

## Economic side

The specimen begins with a 035 heterogeneous exchange.

The provider promises:

~~~text
compute-capacity-delivery
60 compute-minute
capability = render.verified
~~~

The Guild promises:

~~~text
documentation-service
one documentation pass
~~~

The obligations remain typed and incommensurate.

There is no common unit and no exchange rate.

Both sides perform and sign role-local evidence.

The exchange becomes:

~~~text
SETTLED
authority = bilateral-evidence-only
~~~

## Settlement is not capacity

046 deliberately refuses to treat the settlement object itself as an
operational resource.

The Guild must perform a separate steward-signed admission step.

The admission binds:

~~~text
settlement id
offer + acceptance
exact capacity obligation
exact capacity performance attestation
native unit
native quantity
Guild steward
admission cut
~~~

and explicitly says:

~~~text
execution_authority_granted = false
ownership_inferred = false
~~~

Thus:

> **SETTLEMENT != CAPACITY**

and:

> **ACQUISITION != EXECUTION AUTHORITY**

## Economic hostile controls

The specimen refuses:

- capacity admission from an incomplete bilateral settlement;
- capacity admission from a valid settlement whose delivered obligation is
  artifact access rather than compute;
- direct leasing from a settlement ID.

The third control is important.

Even a valid settled exchange cannot be handed directly to the 041 lease
issuer.

## Treasury bridge

The Guild admission produces one capability entry:

~~~text
category = capability
position = available
native measure = 60 compute-minute
source = acquisition receipt
evidence =
  settlement
  capacity obligation
  provider performance
  acquisition receipt
~~~

The Treasury separately carries the settlement as economic evidence.

The two entries remain distinct.

Thus:

> **TREASURY ENTRY != LEASE**

## Operational side

Only after the signed Treasury snapshot exists can the 041 authority machinery
begin.

The acquired 60-minute capability enters the existing authority metabolism:

~~~text
Treasury capacity = 60
-> root lease 60
-> use
-> handoff
-> child leases
-> renewal
-> expiry
-> reclaim
-> fresh reissue
-> use again
~~~

The final 045 metabolism remains:

~~~text
source consumed       51
source live             4
recycled consumed       3
recycled live           2
                       --
accounted              60
~~~

## Consumption is not payment

Nothing about consuming the acquired capacity rewrites the economic settlement.

The provider was not paid again when a node used compute.

The Guild did not settle an obligation merely because a lease consumed
capacity.

The combined witness therefore freezes:

> **CONSUMPTION != PAYMENT**

## Recomputed operational history

046 does not trust a supplied metabolism witness by identifier.

When creating the combined economic-operational witness, the verifier
recomputes the complete 045 metabolism from:

- root lease;
- descendant leases;
- surrenders;
- original use receipts;
- reclaim receipts;
- reissued leases;
- recycled use receipts;
- historical source observation cut;
- later metabolism observation cut.

The supplied metabolism must exactly equal that recomputation.

This prevents a balanced-looking but fabricated operational report from being
linked to a real economic settlement.

## Combined witness

The derived object binds:

~~~text
settlement
-> Guild acquisition
-> Treasury snapshot
-> exact capability entry
-> authority metabolism
~~~

Its authority is:

~~~text
derived-economic-operational-linkage
~~~

It explicitly carries:

~~~text
economic_authority = bilateral-evidence-only
operational_authority = separate-derived-history
execution_authority = none
ownership_inferred = false
payment_inferred_from_consumption = false
~~~

## Bridge hostile controls

The simulation also refuses:

- a Treasury snapshot missing the exact acquired capability entry;
- an acquisition whose quantity was changed after signature;
- a metabolism witness whose operational totals were altered.

## Portable audit

The combined witness may cross through reLATTE.

The crossing requests no:

~~~text
automatic execution
payment inference
ownership transfer
mint authority
~~~

Receiver semantics remain:

~~~text
RECEIVE -> HOLD -> explicit ADMIT
~~~

Admission means the receiver accepts the combined economic + operational audit
as evidence.

It grants no authority to consume the resource.

## Laws

~~~text
SETTLEMENT != CAPACITY
ACQUISITION != EXECUTION AUTHORITY
ECONOMIC VALUE != OPERATIONAL CAPACITY
TREASURY ENTRY != LEASE
CONSUMPTION != PAYMENT
ECONOMIC HISTORY + AUTHORITY HISTORY MAY CROSS WITHOUT COLLAPSE
~~~

## Result

The old Lightwalker economic line and the newer authority-metabolism line are
now one composable system without becoming one semantic blob.

The full path is:

~~~text
heterogeneous offer
-> acceptance
-> bilateral performance
-> settlement

        economic / operational boundary

-> Guild capacity admission
-> Treasury capability
-> bounded lease authority
-> distributed use / handoff
-> expiry / reclaim / reissue
-> metabolic conservation audit

        audit boundary

-> combined metabolic-exchange witness
~~~

Each boundary requires its own evidence and authority.

## Next aperture

046 proves one acquisition entering one authority cycle.

The next useful pressure test is the reverse direction:

~~~text
047 — Capacity-backed Offer / Future Service
~~~

A Guild might offer a bounded future compute service because its Treasury and
authority DAG prove that capacity exists.

But the operational evidence must not become a guarantee that future service
will succeed.

That would test:

~~~text
CAPACITY PROOF != PROMISE
PROMISE != RESERVATION
RESERVATION != PERFORMANCE
PERFORMANCE != PAYMENT
FUTURE SERVICE OFFER MUST NAME ITS AUTHORITY SOURCE
ECONOMIC COMMITMENT MAY ENCUMBER CAPACITY WITHOUT CONSUMING IT
~~~

That would close the loop:

~~~text
economic exchange
-> operational capacity
-> evidence-backed future economic offer
~~~
