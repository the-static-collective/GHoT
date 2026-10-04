# Experiment 041 — Capacity Leases / Partitioned Authority

## Question

Can a Guild reduce split-brain reservation conflicts by partitioning scarce
capacity into bounded node-local authority, without introducing global
consensus, transferring ownership, or collapsing lease into consumption?

## Initial Treasury

The frozen specimen begins with:

~~~text
120 compute-minute
~~~

The Guild steward issues two signed capacity leases:

~~~text
Node A lease = 60 compute-minute
Node B lease = 60 compute-minute
~~~

A third lease for even one additional compute-minute is refused.

This freezes:

> **SHARED CAPACITY != SHARED AUTHORITY**

The resource is shared at the Guild level, but execution authority is divided
into explicit bounded budgets.

## Lease object

Each lease binds:

~~~text
guild_id
treasury snapshot
resource entry
node identity
native unit
leased quantity
issue cut
expiry cut
~~~

Its authority is:

~~~text
guild-delegated-capacity-budget
~~~

The lease is not ownership of the underlying compute pool.

It does not claim that capacity has already been consumed.

~~~text
DELEGATED BUDGET != OWNERSHIP
LEASE != CONSUMPTION
~~~

## Portability

Each signed lease crosses through the normal reLATTE-shaped boundary.

The crossing explicitly requests no:

~~~text
automatic consumption
ownership transfer
global consensus
~~~

The receiving node still performs:

~~~text
RECEIVE -> HOLD -> explicit ADMIT
~~~

Admission gives the node a valid bounded authority instrument. It does not
rewrite the Guild Treasury or transfer the underlying resource.

## Node-local autonomy

Once the leases are admitted, Node A and Node B use separate local budget
ledgers.

There is no shared reservation lock between the two nodes.

The safety property now comes from partitioning:

~~~text
A may consume only from A's 60
B may consume only from B's 60
~~~

A node attempting to use another node's lease is refused.

Thus:

> **PARTITION != GLOBAL CONSENSUS**

The two nodes do not need to agree on every operation because their execution
budgets no longer overlap.

## Node A

Node A successfully consumes:

~~~text
50 compute-minute
~~~

Its local remainder becomes:

~~~text
10 compute-minute
~~~

An attempted additional use of 20 is refused.

Node A then signs a release receipt:

~~~text
consumed = 50
returned = 10
~~~

## Node B

Node B first attempts:

~~~text
20 compute-minute
~~~

and the operation fails before consumption.

The failed use receipt records:

~~~text
status = FAILED
consumed_measure = null
~~~

The lease budget remains 60.

Node B later successfully consumes:

~~~text
30 compute-minute
~~~

and releases:

~~~text
consumed = 30
returned = 30
~~~

Thus:

> **FAILED USE != CONSUMPTION**

## Guild close

The Guild does not trust caller-supplied consumption arithmetic.

Each node signs its release receipt.

The Guild verifies that receipt and produces a separate steward-signed close
record for the lease.

Each close preserves:

~~~text
leased amount
consumed amount
returned amount
node release receipt
original Treasury snapshot
original resource entry
~~~

The lease itself remains immutable.

The Treasury settlement also refuses duplicate close records or duplicate lease
closures, preventing the same consumption evidence from being counted twice.

## Successor Treasury

The two closed leases report:

~~~text
Node A consumed = 50
Node B consumed = 30

total consumed = 80
~~~

The original Treasury snapshot remains unchanged.

A successor snapshot is derived:

~~~text
120 - 80 = 40 compute-minute
~~~

The 10 returned by A and 30 returned by B are therefore present in the
successor resource capacity.

That 40 can then be issued as a fresh bounded lease to Node C.

A further lease is refused because the successor capacity is fully partitioned.

This freezes:

> **UNUSED LEASE CAPACITY MAY RETURN WITHOUT HISTORY REWRITE**

## Why this reduces 040 conflicts

Experiment 040 intentionally allowed both disconnected nodes to form tentative
80-minute claims against the same 120-minute shared capacity.

041 changes the authority topology before the nodes diverge:

~~~text
shared Treasury resource
        |
        +--> signed lease A: 60
        |
        +--> signed lease B: 60
~~~

As long as each node stays inside its own lease, ordinary node-local operations
cannot collide with the other node's partition.

No global ordering is required for those independent uses.

## Laws

~~~text
SHARED CAPACITY != SHARED AUTHORITY
DELEGATED BUDGET != OWNERSHIP
LEASE != CONSUMPTION
PARTITION != GLOBAL CONSENSUS
FAILED USE != CONSUMPTION
UNUSED LEASE CAPACITY MAY RETURN WITHOUT HISTORY REWRITE
~~~

## What 041 does not claim

041 does not eliminate all distributed coordination problems.

The Guild still needs an authoritative boundary for issuing leases whose total
does not exceed the source capacity.

It also does not solve lease renewal or transfer while nodes are disconnected.

The experiment proves a narrower property:

> scarce shared capacity can be partitioned into non-overlapping,
> independently usable local authority domains, reducing the need for
> cross-node consensus during ordinary execution.

## Next aperture

The next hard edge is **lease mobility and renewal**.

A node may need to:

- return only part of an unused lease;
- renew an expiring lease;
- transfer a remaining lease budget to another node;
- split one lease into child leases;
- merge returned capacity into a new Guild partition.

That suggests:

~~~text
042 — Lease Repartition / Handoff
~~~

with laws such as:

~~~text
RENEWAL != NEW OWNERSHIP
TRANSFER != DUPLICATION
CHILD LEASE SUM <= PARENT REMAINDER
HANDOFF != SIMULTANEOUS AUTHORITY
EXPIRY != HISTORY ERASURE
~~~

That would turn static partitions into a mobile sovereign capacity fabric.
