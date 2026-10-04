# Experiment 042 — Lease Repartition / Handoff

## Question

Can delegated Guild capacity move between sovereign nodes without duplicating
authority, rewriting the parent lease, or pretending renewal is ownership?

## Parent lease

The specimen begins with a 041 lease:

~~~text
Node A lease = 60 compute-minute
~~~

Node A consumes:

~~~text
20 compute-minute
~~~

leaving:

~~~text
40 compute-minute
~~~

## Overpartition refusal

Before any handoff occurs, A attempts to repartition the 40-minute remainder
into children totaling 50.

The surrender is refused.

~~~text
CHILD LEASE SUM <= PARENT REMAINDER
~~~

## Atomic surrender

A then signs a valid surrender:

~~~text
remaining = 40

successor allocation:
  A = 10
  B = 30
~~~

The surrender is written under the same local budget lock used for lease
execution.

That write freezes the parent lease before successor children are materialized.

After surrender:

~~~text
parent use -> REFUSED
parent release -> REFUSED
~~~

The original parent remains immutable history, but it has no remaining
exercisable authority.

Thus:

> **HANDOFF != SIMULTANEOUS AUTHORITY**

## Child leases

The Guild verifies the signed surrender and emits two new steward-signed child
leases:

~~~text
child A = 10
child B = 30
~~~

Both reference:

~~~text
parent_lease_id
surrender_id
generation
Treasury snapshot
resource entry
~~~

The parent is not edited.

The children are new authority objects.

## Crossing

Child B crosses to Node B through the ordinary sovereign boundary:

~~~text
signed child lease
-> RECEIVE
-> HOLD
-> explicit ADMIT
~~~

The crossing requests no automatic consumption and explicitly refuses parent
reactivation.

## Independent successor authority

After handoff:

~~~text
A child consumes 5 of 10
B child consumes 20 of 30
~~~

A and B operate against separate child budgets.

The old parent cannot participate.

## Expiry discipline

A plain handoff may not extend the parent's expiry.

Attempting to create handoff children with a later expiry is refused unless the
Guild explicitly invokes renewal authority.

Thus:

~~~text
HANDOFF != RENEWAL
~~~

## Renewal

Node B has:

~~~text
child B = 30
consumed = 20
remaining = 10
expiry = cut 8
~~~

B surrenders that remaining 10.

The old child freezes immediately.

The Guild then explicitly materializes one renewal successor:

~~~text
renewed B lease = 10
new expiry = cut 12
renewal = true
~~~

The renewed lease is a new signed object.

The old lease retains its old expiry and remains in history.

Thus:

> **RENEWAL != NEW OWNERSHIP**

and:

> **EXPIRY != HISTORY ERASURE**

## Renewal scope

In v0, expiry extension may only renew the current holder.

A node may not combine:

~~~text
transfer to another node
+
expiry extension
~~~

inside one renewal operation.

That mixed operation is refused.

A normal cross-node handoff remains legal if it does not extend expiry.

## Laws

~~~text
TRANSFER != DUPLICATION
HANDOFF != SIMULTANEOUS AUTHORITY
CHILD LEASE SUM <= PARENT REMAINDER
RENEWAL != NEW OWNERSHIP
EXPIRY != HISTORY ERASURE
SURRENDER != CONSUMPTION
~~~

## Result

The authority lineage can now move as:

~~~text
Guild lease
   |
   | consume 20
   v
remaining 40
   |
   | surrender parent
   v
parent frozen
   |
   +--> child A 10
   |
   +--> child B 30
            |
            | consume 20
            v
         remaining 10
            |
            | surrender child
            v
       renewal child 10
       with later expiry
~~~

At no point do the parent and its successors simultaneously hold authority over
the same remainder.

## Next aperture

The next hard problem is **multi-generation lineage reconciliation**.

Once capacity can move through several child leases, the Guild needs a compact
way to answer:

- which leaves are still live;
- how much has been consumed;
- how much remains delegated;
- how much has returned;
- whether two descendants overlap;
- whether a proposed child descends from an already-frozen ancestor.

That suggests:

~~~text
043 — Lease Lineage / Authority DAG
~~~

with laws:

~~~text
ANCESTOR HISTORY != LIVE AUTHORITY
DESCENDANT != DUPLICATE
LEAF SET DEFINES CURRENT AUTHORITY
LINEAGE PROOF != OWNERSHIP
COMPACTION != HISTORY DELETION
~~~
