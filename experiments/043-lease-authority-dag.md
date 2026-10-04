# Experiment 043 — Lease Lineage / Authority DAG

## Question

After several generations of lease handoff and renewal, can the Guild derive the
current authority surface from immutable history without counting ancestors
twice, flattening lineage, or deleting expired branches?

## Specimen

The root lease begins with:

~~~text
60 compute-minute
~~~

The lineage evolves:

~~~text
root 60
  |
  | consume 20
  | surrender remaining 40
  |
  +--> child A 10
  |      |
  |      | consume 5
  |      | surrender remaining 5
  |      v
  |    residual child B 5
  |    expiry cut 8
  |
  +--> child B 30
         |
         | consume 20
         | surrender remaining 10
         v
       renewed B 10
       expiry cut 12
         |
         | consume 6
         v
       remaining 4
~~~

The authority view is derived at cut 9.

At that cut:

- the root is historical ancestry;
- child A is historical ancestry;
- child B is historical ancestry;
- residual child B has expired with 5 unconsumed;
- renewed B is the only live leaf with 4 remaining.

Thus:

> **ANCESTOR HISTORY != LIVE AUTHORITY**

## Exact child materialization

Every surrender contains an explicit allocation set.

043 requires the descendant child set to match that allocation set exactly.

A second signed child generated from the same surrender allocation is rejected,
even if each child object is individually well formed.

Thus:

> **DESCENDANT != DUPLICATE**

## Use-history binding

A surrender does not get to assert arbitrary consumption.

For every surrendered parent, the DAG verifier requires:

~~~text
surrender.use_ids
==
actual signed use receipts supplied for that parent
~~~

and:

~~~text
successful use consumption
==
surrender.consumed_before_surrender
~~~

A lineage with missing parent use evidence is refused.

## Rooted DAG

All descendants must be reachable from the declared root lease.

043 refuses:

- orphan child leases;
- children whose parent never surrendered;
- child leases referencing the wrong surrender;
- duplicate lease objects;
- multiple surrenders for one parent;
- cycles;
- descendants crossing Treasury snapshot, resource entry, or native unit.

The graph is therefore a rooted authority DAG over one bounded source lease.

## Renewal discipline

A child may extend its parent's expiry only when:

- it is explicitly marked as renewal;
- the surrender has exactly one successor;
- the successor holder is the same holder.

This preserves the 042 boundary:

~~~text
renewal
!=
cross-node transfer + indefinite extension
~~~

## Conservation

043 requires every root unit to land in exactly one current or historical
bucket:

~~~text
root quantity
=
consumed
+ explicitly returned to Guild
+ live-leaf remainder
+ expired-leaf remainder
~~~

For the specimen at cut 9:

~~~text
root                     60
consumed                 51
returned to Guild         0
live-leaf remainder       4
expired-leaf remainder    5
                         --
accounted                60
~~~

If even one unit disappears or appears twice, DAG derivation fails.

## Current authority surface

The derived live-leaf set is:

~~~text
renewed B lease
remaining = 4
expiry = 12
~~~

The residual 5-unit leaf is expired and therefore not current authority.

This freezes:

> **LEAF SET DEFINES CURRENT AUTHORITY**

## Compact view

The full DAG remains the auditable history.

A compact authority view may expose only:

- current live leaves;
- expired terminal leaves;
- aggregate conservation buckets;
- root lease;
- observed cut;
- a digest committing to the complete lineage history.

The compact view preserves the same history digest.

Thus:

> **COMPACTION != HISTORY DELETION**

## Hostile controls

The simulation requires refusal for:

- duplicate child materialization from one surrender slot;
- missing surrender evidence;
- missing parent use history;
- tampered child quantity/signature.

## Laws

~~~text
ANCESTOR HISTORY != LIVE AUTHORITY
LEAF SET DEFINES CURRENT AUTHORITY
DESCENDANT != DUPLICATE
LINEAGE PROOF != OWNERSHIP
COMPACTION != HISTORY DELETION
CONSERVATION != GLOBAL CONSENSUS
~~~

## What 043 does not claim

The authority DAG is a derived proof over supplied signed history.

It is not ownership adjudication.

It is not global consensus.

It does not claim an expired leaf's unused remainder has automatically returned
to the Guild; expired remainder is kept as its own bucket until a later policy
or receipt explicitly disposes of it.

## Next aperture

The next problem is disposal of **expired and stranded authority**.

At cut 9 this specimen contains:

~~~text
expired leaf remainder = 5
~~~

That authority is no longer live, but it has not yet been explicitly reclaimed.

The next experiment should therefore test:

~~~text
044 — Expiry Reclamation / Authority Compost
~~~

A Guild could prove an expired leaf, issue a reclaim receipt, and return that
stranded capacity into a successor Treasury or new partition without reviving
the expired lease.

Target laws:

~~~text
EXPIRY != RETURN
RECLAIM != REVIVAL
STRANDED AUTHORITY != LIVE AUTHORITY
RECLAIMED CAPACITY REQUIRES EVIDENCE
COMPOST != HISTORY ERASURE
~~~
