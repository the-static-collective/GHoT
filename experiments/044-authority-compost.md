# Experiment 044 — Expiry Reclamation / Authority Compost

## Question

Can stranded capacity from an expired lease be reclaimed without reviving the
expired authority, rewriting lineage, or silently treating expiry as return?

## Starting lineage

043 ends at cut 9 with:

~~~text
root quantity              60
consumed                   51
live-leaf remainder         4
expired-leaf remainder      5
                           --
accounted                  60
~~~

The expired 5 is no longer live authority.

But it has not yet returned to the Guild.

Thus:

> **EXPIRY != RETURN**

## Reclaim requires proof

044 does not reclaim from a lease object alone.

The Guild recomputes the complete 043 authority DAG from:

- root lease;
- descendants;
- surrender receipts;
- signed use receipts;
- observed cut.

Only a lease appearing in the verified DAG as:

~~~text
LEAF_EXPIRED
remaining_quantity > 0
~~~

can be reclaimed.

The reclaim receipt binds:

~~~text
Treasury snapshot
root lease
DAG id
history digest
expired lease id
expiry cut
observed cut
native unit
exact stranded quantity
Guild steward
~~~

This freezes:

> **RECLAIMED CAPACITY REQUIRES EVIDENCE**

## Hostile controls

The specimen refuses:

- reclaim at the expiry cut before the leaf is expired;
- reclaim of the still-live renewed leaf;
- reclaim by a non-steward identity;
- reclaim from incomplete lineage/use evidence;
- a second reclaim of the same expired leaf.

## Reclaim is not revival

The signed receipt contains:

~~~text
status = RECLAIMED
revival_requested = false
~~~

After reclaim, an attempt to execute through the old expired lease still fails.

The old lease remains:

~~~text
expired
historical
non-live
~~~

Thus:

> **RECLAIM != REVIVAL**

## Post-reclaim overlay

The original DAG remains unchanged.

044 overlays the separate reclaim evidence:

~~~text
consumed                  51
live remainder             4
expired remainder          5
reclaimed expired          5
unreclaimed expired        0
accounted                 60
~~~

The overlay does not pretend the original DAG had no expired leaf.

It says what later happened to that stranded remainder.

Thus:

> **COMPOST != HISTORY ERASURE**

## Fresh reissue

The reclaimed 5 may be used to create one new Guild-signed authority object:

~~~text
reclaimed capacity lease = 5
source reclaim = exact reclaim receipt
source expired lease = exact expired leaf
fresh node = Node C
fresh expiry
~~~

The new lease has a different lease id.

It carries:

~~~text
REISSUE != CONTINUATION
~~~

The expired lease never becomes active again.

A second reissue from the same reclaim is refused.

## Crossing

The reclaimed lease crosses through the normal sovereign boundary:

~~~text
RECEIVE -> HOLD -> explicit ADMIT
~~~

The crossing explicitly requests no:

~~~text
expired lease revival
automatic consumption
ownership transfer
~~~

Node C then successfully consumes 3 of the fresh 5-unit lease and retains 2.

## Treasury history

The original Treasury snapshot remains immutable.

A successor Treasury snapshot adds reclaim/reissue evidence as a receipt entry.

044 does not silently increase the source capability quantity inside the old
snapshot.

The fresh authority is grounded in the reclaim receipt, not in retroactive
mutation of the Treasury history.

## Laws

~~~text
EXPIRY != RETURN
RECLAIM != REVIVAL
STRANDED AUTHORITY != LIVE AUTHORITY
RECLAIMED CAPACITY REQUIRES EVIDENCE
COMPOST != HISTORY ERASURE
REISSUE != CONTINUATION
~~~

## Next aperture

044 recovers dead authority only after expiry.

The next useful question is whether the whole authority fabric can be
periodically summarized into a durable resource cycle:

~~~text
issue
-> partition
-> use
-> handoff
-> expire
-> reclaim
-> reissue
-> settle
~~~

That suggests:

~~~text
045 — Capacity Cycle / Authority Metabolism
~~~

The goal would be one bounded end-to-end invariant proving that no unit is ever
simultaneously:

- live in two leases;
- consumed twice;
- returned and consumed;
- expired and live;
- reclaimed twice;
- reissued without evidence.

Target seal:

> **AUTHORITY CHANGES FORM. ACCOUNTABILITY CONSERVES.**
