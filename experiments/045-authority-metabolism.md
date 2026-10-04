# Experiment 045 — Authority Metabolism

## Question

Can the complete authority lifecycle be audited as one conservation system even
when authority changes form across issue, partition, use, handoff, expiry,
reclaim, reissue, and use again?

## Principle

The target law is:

> **AUTHORITY CHANGES FORM. ACCOUNTABILITY CONSERVES.**

045 is not a new spending instrument.

It is a derived audit over the signed artifacts already created by 041–044.

## Source cycle

The specimen begins with one 60-minute root lease.

Its original lineage reaches cut 9 as:

~~~text
root authority              60
source consumption          51
source live remainder        4
expired stranded remainder   5
                            --
accounted                   60
~~~

The expired five-minute leaf is then reclaimed using the 044 proof path.

## Temporal split

The reclaim receipt is bound to the exact 043 DAG observation cut that proved
expiry:

~~~text
source_observed_cut = 9
~~~

The later metabolic audit happens after reissue and reuse:

~~~text
observed_cut = 10
~~~

These cuts are intentionally distinct.

The later audit does not weaken or recompute the reclaim against a different
historical observation.

## Reclaimed but unissued

Before fresh authority is created, the five reclaimed minutes occupy a separate
state:

~~~text
source consumed             51
source live                  4
reclaimed but unissued       5
                            --
accounted                   60
~~~

This proves reclamation alone does not imply a new lease.

## Reissue and reuse

The five reclaimed minutes become one fresh Guild-signed lease for Node C.

Node C then consumes three minutes.

The final metabolic state becomes:

~~~text
source consumed             51
source live                  4
source unreclaimed expired   0
reclaimed but unissued       0
recycled consumed            3
recycled live                2
                            --
accounted                   60
~~~

The original expired five is not counted in addition to the reclaimed five.

Thus:

> **EXPIRED + RECLAIMED MAY NOT BE DOUBLE COUNTED**

## Evidence chain

The metabolism verifier recomputes and verifies:

1. the original 043 authority DAG;
2. every supplied 044 reclaim receipt;
3. every reclaimed-capacity lease;
4. every recycled lease-use receipt;
5. the one-to-one relation between reclaim and fresh lease;
6. the final conservation equation.

A fresh lease without its reclaim evidence is refused.

A reclaim may materialize at most one fresh lease in v0.

## Hostile controls

The simulation requires refusal for:

- a reissued lease with no supplied reclaim receipt;
- duplicate reissue from one reclaim;
- duplicate recycled use evidence;
- a tampered reissued lease quantity/signature;
- missing original lineage use history.

## Derived witness

The output is:

~~~text
authority = derived-end-to-end-conservation-audit
spending_authority = none
conservation_status = BALANCED
~~~

The witness carries a digest over:

- the source DAG;
- source history digest;
- reclaim IDs;
- reissued lease IDs;
- recycled use IDs.

It does not grant permission to execute anything.

## Crossing

The witness can cross through reLATTE as portable audit evidence.

The crossing explicitly requests no:

~~~text
automatic execution
mint authority
history rewrite
~~~

Receiver semantics remain:

~~~text
RECEIVE -> HOLD -> explicit ADMIT
~~~

Admission accepts the audit as evidence only.

## Laws

~~~text
AUTHORITY CHANGES FORM; ACCOUNTABILITY CONSERVES
EXPIRED + RECLAIMED MAY NOT BE DOUBLE COUNTED
RECLAIM != REVIVAL
REISSUE != CONTINUATION
METABOLISM WITNESS != SPENDING AUTHORITY
CONSERVATION != GLOBAL CONSENSUS
~~~

## What 045 proves

The experiments from 041 onward are no longer merely adjacent mechanisms.

They form one accountable resource cycle:

~~~text
issue
-> partition
-> use
-> handoff
-> expire
-> reclaim
-> reissue
-> use again
~~~

Every state transition may change the form of authority while the root quantity
remains conserved by evidence.

## Next aperture

The next useful threshold is to compose this authority metabolism with the
earlier economic layer.

A Guild now knows both:

- how capacity authority moves and conserves;
- how heterogeneous exchange and Labor Writs settle.

That suggests:

~~~text
046 — Metabolic Exchange
~~~

A settlement could acquire capacity, place it into Treasury, lease it into the
authority fabric, consume or return it, and later prove the whole economic +
operational lineage without collapsing price, authority, ownership, or work.

Candidate laws:

~~~text
SETTLEMENT != CAPACITY
ACQUISITION != EXECUTION AUTHORITY
ECONOMIC VALUE != OPERATIONAL CAPACITY
TREASURY ENTRY != LEASE
CONSUMPTION != PAYMENT
ECONOMIC HISTORY + AUTHORITY HISTORY MAY CROSS WITHOUT COLLAPSE
~~~
