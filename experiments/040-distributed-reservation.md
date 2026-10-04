# Experiment 040 — Distributed Reservation

## Question

What happens when two sovereign Guild nodes act from the same stale Treasury
snapshot before either has heard about the other's local reservation claim?

## Split-brain specimen

The shared signed Treasury snapshot contains:

~~~text
120 compute-minute
~~~

Node A independently sees:

~~~text
proposal A = 80
known foreign claims = none
~~~

Node B independently sees:

~~~text
proposal B = 80
known foreign claims = none
~~~

Each node may therefore produce a locally signed tentative reservation claim.

Locally, each history is internally consistent:

~~~text
80 claimed against 120 visible
status = NO_CONFLICT
~~~

The protocol does not pretend either node had information it did not possess.

Thus:

> **LOCAL KNOWLEDGE != GLOBAL KNOWLEDGE**

## Claim is not consensus

A distributed reservation claim has:

~~~text
authority = node-local-tentative-claim
status = LOCAL_TENTATIVE
~~~

It binds a specific:

- Guild;
- Treasury snapshot;
- capability entry;
- proposal;
- executor;
- native measure;
- node identity;
- claim window;
- locally known claim set.

But it explicitly carries:

~~~text
RESERVATION CLAIM != CONSENSUS
LOCAL CLAIM != EXECUTION AUTHORITY
~~~

Neither local claim can directly become a Treasury execution.

## Crossing

Each node packages its signed claim into a reLATTE-shaped crossing.

The crossing requests:

~~~text
consider-distributed-reservation-claim
~~~

and explicitly does not request:

~~~text
automatic consensus
automatic execution
remote history rewrite
~~~

The foreign claim arrives at the other node through replaceable parcel
transport.

Receiver semantics remain:

~~~text
RECEIVE -> HOLD -> explicit ADMIT
~~~

Admission means the foreign claim has entered local history.

It does not mean the receiver endorses the claim as globally canonical.

## Reconciliation

After exchange, each node now possesses both signed histories.

Reconciliation is deterministic over the same claim set, independent of input
ordering.

Both nodes derive:

~~~text
visible quantity       = 120
claim A                = 80
claim B                = 80
total claimed          = 160
overcommit              = 40
status                  = CONFLICT
~~~

The reconciliation object is:

~~~text
authority = derived-conflict-observation
~~~

It is not a vote and not a consensus result.

It states only that the known claims cannot all be simultaneously honored by
the referenced capacity.

Thus:

> **CONFLICT != SILENT OVERCOMMIT**

## No contradiction destruction

The conflict object contains both claim IDs.

Neither claim is mutated or deleted.

Both execution gates become:

~~~text
BLOCKED_CONFLICT
~~~

until an explicit resolution addresses the exact conflict set.

This follows the TranchNode law:

> **No contradiction destruction. Disagreement remains visible until explicitly resolved.**

and freezes:

> **RECONCILIATION != HISTORY REWRITE**

## Resolution

The Guild steward may sign a resolution over the exact verified reconciliation.

Experiment 040 deliberately uses a simple deterministic v0 rule:

~~~text
lowest-claim-id
~~~

The rule is not asserted as universally fair economics. It is a bounded test
instrument proving that a resolution can be:

- attributable;
- deterministic;
- scoped to an exact conflict set;
- independently verifiable;
- separate from the claims it resolves.

The selected claim becomes:

~~~text
ELIGIBLE_RESOLVED
~~~

The other becomes:

~~~text
SUPERSEDED
~~~

The losing claim remains signed historical fact.

Thus:

~~~text
RESOLUTION != CLAIM DELETION
~~~

## Hostile controls

040 requires refusal for:

- a non-steward attempting to resolve the conflict;
- a resolution whose selected claim set has been modified;
- a resolution not grounded in a recomputed reconciliation;
- materialization of the superseded claim.

The resolution verifier recomputes the conflict from the underlying signed
claims and proposals rather than trusting an arbitrary supplied conflict object.

## Materialization into 039

A selected distributed claim is still not execution authority.

Only after resolution may it enter the established 039 authoritative path:

~~~text
selected distributed claim
      |
      v
Guild authorization
      |
      v
ACTIVE reservation
      |
      v
execution
~~~

The superseded claim cannot materialize.

In the frozen specimen, the selected 80-minute claim executes successfully and
the next Treasury snapshot becomes:

~~~text
40 compute-minute
~~~

## History preservation

After reconciliation, resolution, materialization, and execution:

- the original Treasury snapshot remains unchanged;
- Node A's local claim remains unchanged;
- Node B's local claim remains unchanged;
- the conflict set retains both claim IDs;
- the resolution explicitly records the superseded claim;
- the new Treasury snapshot points forward from the original history.

The system settles action without pretending the split-brain interval never
happened.

## Laws

~~~text
LOCAL KNOWLEDGE != GLOBAL KNOWLEDGE
RESERVATION CLAIM != CONSENSUS
CONFLICT != SILENT OVERCOMMIT
RECONCILIATION != HISTORY REWRITE
RESOLUTION != CLAIM DELETION
LOCAL CLAIM != EXECUTION AUTHORITY
~~~

## What 040 does not claim

040 does **not** implement leaderless global consensus.

It does not prove that disconnected nodes can safely spend the same scarce
resource forever without an eventual coordination boundary.

Instead, it proves a narrower and more useful property:

> divergence can remain locally lawful, become explicitly contradictory when
> histories meet, block unsafe execution, and be resolved without rewriting
> either past.

This matches the reLATTE posture:

~~~text
many sovereign histories
may share verifiable crossings
without sharing one global state
~~~

## Next aperture

040 resolves a split-brain conflict only after the fact.

The next experiment should reduce how often such conflicts arise without
reintroducing global locking.

One candidate is **041 — Capacity Leases / Partitioned Authority**:

~~~text
Guild Treasury = 120 compute-minute

lease to Node A = 60
lease to Node B = 60

A may reserve only inside A's 60
B may reserve only inside B's 60
~~~

The leases could themselves cross via reLATTE and expire/release like the prior
authority instruments.

That would test:

~~~text
SHARED CAPACITY != SHARED AUTHORITY
DELEGATED BUDGET != OWNERSHIP
LEASE != CONSUMPTION
PARTITION != GLOBAL CONSENSUS
UNUSED LEASE CAPACITY MAY RETURN WITHOUT HISTORY REWRITE
~~~

It would move the architecture from conflict detection toward conflict
avoidance while keeping the nodes sovereign.
