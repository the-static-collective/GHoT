# Experiment 063 — Recursive Continuation Kernel / Arbitrary-Depth Resume

## Question

Can the explicit multi-hop continuation proven in 062 become a reusable recursive
runtime without changing the meaning of the already-signed 062 artifacts?

The desired grammar is:

~~~text
root checkpoint
-> continuation node
-> checkpoint
-> stop
-> handoff
-> continuation node
-> checkpoint
-> stop
-> handoff
-> ...
-> completion
~~~

The depth must not create authority.

The root work measure must never reset.

Every edge must prove its immediate parent.

## Preserve 062 as the seed witness

063 does not rewrite the 062 continuation node format.

A valid 062 node is normalized once as the recursive seed.

After that, every descendant uses the same 063 recursive node grammar.

This keeps:

~~~text
062 = concrete second-hop proof
063 = arbitrary-depth recursive kernel
~~~

rather than silently changing the semantics of an existing signed artifact.

## Depth-9 specimen

The executable specimen uses a 100 compute-minute root job and ten sovereign
work owners:

~~~text
F
E
H
J
K
L
M
N
P
Q
~~~

The state progression is:

~~~text
F checkpoint 10%
-> E checkpoint 20%
-> H seed node at 20%
-> H checkpoint 30%
-> J node at 30%
-> J checkpoint 40%
-> K node at 40%
-> K checkpoint 50%
-> L node at 50%
-> L checkpoint 60%
-> M node at 60%
-> M checkpoint 70%
-> N node at 70%
-> N checkpoint 80%
-> P node at 80%
-> P checkpoint 90%
-> Q node at 90%
-> Q completion 100%
~~~

The recursive terminal node is:

~~~text
hop_index = 9
checkpoint ancestry count = 9
~~~

Thus the recursive structure is not special-cased for hop 2 or hop 3.

## Root measure stays invariant

The root work measure is:

~~~text
100 compute-minutes
~~~

Every continuation node carries the same root measure.

Progress is always measured against that root.

It never becomes:

~~~text
"percentage of the current reservation"
~~~

or:

~~~text
"a new local job beginning at zero"
~~~

Each hop adds exactly 10 root-relative compute-minutes.

The final accounting is:

~~~text
F = 10
E = 10
H = 10
J = 10
K = 10
L = 10
M = 10
N = 10
P = 10
Q = 10
----------------
total = 100
~~~

Therefore:

> **ROOT MEASURE MUST REMAIN INVARIANT**

and:

> **RECURSION != HISTORY COLLAPSE**

## Generic recursive node

Every 063 child node contains:

~~~text
continuation lineage id
root run id
root checkpoint id

parent node id
parent node kind
parent checkpoint id
parent handoff id

checkpoint ancestry
ancestry digest
hop index

prior root-relative progress
root source work measure
prior work measure
remaining work measure

new Guild
new reservation
new authorization
new steward
new executor

fresh execution gate
~~~

The node explicitly carries:

~~~text
service_complete = false
ownership_transfer = false
ancestor_work_reexecuted = false
settlement_authority = none
~~~

The hop number is descriptive lineage depth.

It is not an authority level.

> **DEPTH != AUTHORITY**

## Every checkpoint proves its node

A recursive checkpoint binds exactly one parent node.

It recomputes current temporal execution permission and records:

~~~text
parent node id
hop index
reservation id
ancestor checkpoint ids

total root-relative progress
cumulative root-relative work
new work contributed by this node
partial result
fresh continuation gate
~~~

The verifier recomputes the cumulative and new-work measures from the immutable
root measure.

A checkpoint therefore cannot choose a new denominator.

## Partial stop still settles real capacity

Each nonterminal recursive parent partially consumes its reservation.

For example, H starts at 20% with 80 units of remaining authority.

At 30%:

~~~text
new work = 10

H reservation = 80
consumed = 10
released = 70
~~~

The reservation finalization binds the recursive checkpoint as its
partial-evidence reference.

The same pattern repeats at every nonterminal hop.

Thus state lineage and operational-capacity history remain aligned recursively.

## One accepted child per checkpoint

A parent checkpoint can name one next reservation through a recursive handoff.

The parent store has an atomic accepted-handoff slot keyed by the checkpoint id.

The depth-9 simulation deliberately creates a second valid child reservation
for the first recursive checkpoint after the first child was accepted.

The second handoff is refused.

The rejected resource may then release its unused reservation normally.

Thus:

> **ONLY ONE LIVE LEAF PER ACCEPTED BRANCH**

A copied checkpoint does not inherently create many accepted descendants inside
one owner-local lineage.

## Every edge proves its parent

A recursive handoff binds:

~~~text
parent node
parent checkpoint
parent stop
parent partial finalization

full checkpoint ancestry
cumulative root-relative progress
cumulative root-relative work
remaining root-relative work

one exact next reservation
~~~

The child node must prove that handoff and must increment:

~~~text
child hop = parent hop + 1
~~~

Its ancestry must equal:

~~~text
parent ancestry
+ parent checkpoint
~~~

The lineage view rejects a child whose ancestry does not preserve that exact
prefix.

Thus:

> **EACH EDGE MUST PROVE ITS PARENT**

## Recursive lineage view

063 derives a read-only lineage observation over the ordered recursive edges.

For the green specimen it reports:

~~~text
status = ACTIVE
recursive_depth = 9
live_leaf_count = 1
tip = Q
root source measure = 100
~~~

before completion.

It verifies that:

~~~text
all resource reservation ids are distinct
each hop increments exactly once
each checkpoint extends ancestry exactly once
every descendant preserves the same root measure
every edge points to the current leaf
~~~

The view itself carries:

~~~text
execution_authority = none
global_consensus = false
history_collapsed = false
~~~

## Completion

Q begins at 90% with exactly 10 root units remaining.

Its completion consumes those 10 units and records:

~~~text
hop_count = 9
total progress = 100

ancestor work = 90
new work = 10
total work = 100

ancestor_work_reexecuted = false
ancestor_work_double_counted = false
full_ancestry_proven = true
service_complete = true
settlement_authority = none
~~~

The completed recursive view then reports:

~~~text
status = COMPLETED
live_leaf_count = 0
terminal leaf = Q completion
~~~

The complete smoke specimen proves total consumed work is exactly 100.

## Compact lineage proof

The full recursive view may become large.

063 therefore derives a compact proof containing:

~~~text
recursive view id
continuation lineage id
root run/checkpoint
root work measure
recursive depth
tip node
status

ancestry count
ancestry digest
resource reservation count
~~~

The green depth-9 compact proof records:

~~~text
ancestry_count = 9
history_erased = false
execution_authority = none
settlement_authority = none
sufficient_for_new_resume = false
~~~

This distinction is deliberate.

The compact proof is useful for transport, indexing, comparison, and later
expansion.

It does not replace the edge evidence required to authorize a new child.

Therefore:

> **COMPACTION MAY SHORTEN PROOF TRANSPORT WITHOUT ERASING ANCESTRY**

and:

~~~text
COMPACT PROOF != EXECUTION AUTHORITY
~~~

## Tamper control

The recursive view is content-addressed and independently verified.

The simulation mutates the reported recursive depth without changing the
underlying ancestry.

Verification fails.

The ancestry digest is also recomputed from:

~~~text
continuation lineage id
+ ordered checkpoint ancestry
~~~

rather than trusted as an opaque field.

## Laws

~~~text
DEPTH != AUTHORITY
RECURSION != HISTORY COLLAPSE
EACH EDGE MUST PROVE ITS PARENT
ROOT MEASURE MUST REMAIN INVARIANT
ONLY ONE LIVE LEAF PER ACCEPTED BRANCH
COMPACTION MAY SHORTEN PROOF TRANSPORT WITHOUT ERASING ANCESTRY
COMPACT PROOF != EXECUTION AUTHORITY
~~~

## Result

The continuation system is no longer a fixed-depth demonstration.

It is now a recursive execution grammar:

~~~text
state ancestry
        |
        v
local authority
        |
        v
checkpoint
        |
        v
partial consume + release
        |
        v
exact handoff
        |
        v
new local authority
        |
       ...
        |
        v
completion
~~~

The root remains invariant.

The owners remain local.

The history grows without collapsing.

The accepted live branch remains singular.

## Next aperture

063 enforces one accepted child inside one owner-local handoff registry.

The next distributed pressure point is the recursive analogue of 061:

~~~text
064 — Recursive Branch Claim / Fork Reconciliation
~~~

Two disconnected replicas of a deep parent may each accept a different child:

~~~text
depth 7 checkpoint
       /        \
 replica A    replica B
   -> P          -> Q
 ACTIVE        ACTIVE
~~~

When those histories meet, the system should derive a recursive branch fork,
block both descendants, and require an explicit parent-owner resolution over
the exact child set.

Likely laws:

~~~text
LOCAL SINGLE-CHILD != GLOBAL SINGLE-CHILD
RECURSIVE FORK != HISTORY DELETION
FORK DETECTION != CONSENSUS
RESOLUTION MUST NAME THE EXACT PARENT CHECKPOINT
LOSING DESCENDANT != NONEXISTENT DESCENDANT
ONLY THE RESOLVED LEAF MAY CONTINUE
~~~

That would extend 061's contradiction discipline to arbitrary continuation
depth without introducing a universal chain.
