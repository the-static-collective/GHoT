# Experiment 064 — Recursive Branch Claim / Fork Reconciliation

## Question

Can an arbitrary-depth recursive continuation remain owner-local without
pretending that disconnected replicas can never contradict one another?

063 proves:

~~~text
one local checkpoint store
-> at most one accepted child handoff
~~~

064 asks the distributed version:

~~~text
what if two disconnected copies of the same stopped parent history
each locally accept a different child?
~~~

The answer must not be:

~~~text
pick one silently
delete the other
pretend consensus happened
~~~

## Deep-parent specimen

The executable specimen builds a 100 compute-minute continuation lineage:

~~~text
F -> E -> H -> J -> K -> L
~~~

L is:

~~~text
hop_index = 5
prior progress = 50%
~~~

L advances to:

~~~text
checkpoint = 60%
~~~

and partially finalizes its local authority:

~~~text
L new work = 10
L consumed = 10
L released = 40
~~~

The exact L checkpoint is then replicated as terminal evidence to two
disconnected L-owned continuation stores.

The replica operation carries:

~~~text
replicated terminal evidence
execution_authority = none
~~~

Copying the stopped evidence does not create new work authority.

## Two locally correct histories

Replica A sees candidate P.

Replica B sees candidate Q.

Both candidates independently own:

~~~text
40 compute-minutes
~~~

which is the exact remaining root-relative work after L reaches 60%.

Replica A signs:

~~~text
L checkpoint -> P handoff
~~~

Replica B signs:

~~~text
L checkpoint -> Q handoff
~~~

Both handoffs are valid.

Both are signed by the exact L parent owner.

Both name the exact same L recursive checkpoint.

Each child then independently creates a valid hop-6 recursive node.

Thus the system contains:

~~~text
                 L checkpoint 60%
                    /      \
                   /        \
              handoff P    handoff Q
                 |             |
                 v             v
              child P       child Q
               hop 6         hop 6
~~~

There is no invalid signature to reject.

There is no malformed resource authority.

The contradiction is relational.

Therefore:

> **LOCAL SINGLE-CHILD != GLOBAL SINGLE-CHILD**

063 remains correct locally.

064 handles the newly visible distributed contradiction.

## Fork derivation

064 verifies every branch against the same immutable parent evidence:

~~~text
parent recursive node
parent checkpoint
parent stop
parent partial finalization
candidate next reservation
signed recursive handoff
signed child node
~~~

It derives a content-addressed observation:

~~~text
kind = recursive-branch-fork
status = FORK
parent node = L
parent checkpoint = exact L 60% checkpoint
branches = {P, Q}

global_consensus = false
history_deleted = false
execution_authority = none
~~~

The observation does not choose a winner.

Thus:

> **FORK DETECTION != CONSENSUS**

## Known fork blocks both descendants

Before resolution:

~~~text
P gate -> BLOCKED_FORK
Q gate -> BLOCKED_FORK
~~~

The simulation attempts branch-guarded completion on both real child nodes.

Both are refused.

This distinction is important.

Before the histories meet, each disconnected replica can honestly regard its
single child as locally accepted.

After the contradictory histories are known together, local validity is no
longer enough to continue.

The fork evidence changes the admissible continuation view.

It does not rewrite either past.

## Resolution authority

Only the exact parent owner may resolve the fork.

The resolution is signed by L and binds:

~~~text
recursive branch fork id
continuation lineage id
L parent node id
exact L parent checkpoint id

complete handoff set
complete child-node set

winner handoff
winner child
losing handoffs
losing children
~~~

V0 uses the deterministic test rule:

~~~text
lowest-handoff-id
~~~

The rule is not presented as universal merit.

It is simply a deterministic local resolution rule for the specimen.

Thus:

> **RESOLUTION MUST NAME THE EXACT PARENT CHECKPOINT**

A resolution copied from another checkpoint cannot be used here.

The simulation mutates the resolution's parent checkpoint reference.

Verification fails.

## Winner and loser remain different histories

After resolution:

~~~text
winner -> ELIGIBLE_RESOLVED
loser  -> SUPERSEDED
~~~

The losing child is not erased.

Its node, handoff, reservation, and supersession remain durable evidence that
the fork happened.

Thus:

> **RECURSIVE FORK != HISTORY DELETION**

and:

> **LOSING DESCENDANT != NONEXISTENT DESCENDANT**

## Closing the losing child

The losing child has not yet performed local work.

064 therefore closes it as:

~~~text
CLOSED_UNSTARTED
~~~

and releases its complete 40-unit reservation.

The supersession linkage records:

~~~text
resolution id
losing child node
reservation id
release finalization id

reservation_status = RELEASED
history_deleted = false
execution_authority = none
~~~

This prevents the superseded branch from continuing while preserving its
historical existence.

## Only the winner may complete

The winning child remains at:

~~~text
prior progress = 60%
remaining work = 40
~~~

Its branch-guarded completion rechecks the exact fork and exact resolution.

Only then does the ordinary 063 completion path execute.

The winner consumes:

~~~text
40 compute-minutes
~~~

and reaches:

~~~text
total progress = 100%
full_ancestry_proven = true
~~~

The total root accounting is:

~~~text
F = 10
E = 10
H = 10
J = 10
K = 10
L = 10
winner = 40
------------
total = 100
~~~

The losing child consumes:

~~~text
0
~~~

and releases:

~~~text
40
~~~

Thus:

> **ONLY THE RESOLVED LEAF MAY CONTINUE**

## Authority model

The layers are now:

~~~text
063 local handoff slot
    = one-child atomicity inside one owner-local store

064 fork observation
    = derived contradiction evidence across stores

064 resolution
    = exact parent-owner-local choice over the known fork set

child resource authority
    = still owned independently by each child Guild

branch gate
    = whether a known descendant may continue after reconciliation
~~~

None collapses into global consensus.

## Laws

~~~text
LOCAL SINGLE-CHILD != GLOBAL SINGLE-CHILD
RECURSIVE FORK != HISTORY DELETION
FORK DETECTION != CONSENSUS
RESOLUTION MUST NAME THE EXACT PARENT CHECKPOINT
LOSING DESCENDANT != NONEXISTENT DESCENDANT
ONLY THE RESOLVED LEAF MAY CONTINUE
~~~

## Result

The arbitrary-depth continuation runtime now has contradiction discipline.

A distributed fork can exist honestly:

~~~text
local history A: L -> P
local history B: L -> Q
~~~

When the two are compared:

~~~text
FORK
-> block both
-> exact parent-owner resolution
-> close losing child without erasure
-> resolved child may continue
~~~

No universal chain was introduced.

No losing history was destroyed.

No resource authority silently moved between owners.

## Next aperture

064 resolves a known fork after contradictory descendants have already been
created.

The next useful pressure point is:

~~~text
065 — Recursive Branch Merge / Salvage of Losing Work
~~~

What if both descendants performed legitimate useful work before the fork was
discovered?

For example:

~~~text
L 60%
 /    \
P 75%  Q 80%
 \    /
  fork discovered
~~~

Simply superseding one child would discard useful verified computation.

065 should ask whether non-winning branch work can be salvaged as evidence or
artifacts without being counted twice toward the original execution.

Likely laws:

~~~text
LOSING BRANCH WORK != ZERO WORK
SALVAGE != CONTINUATION AUTHORITY
MERGEABLE ARTIFACT != MERGED EXECUTION
USEFUL OUTPUT MAY SURVIVE A LOSING BRANCH
ROOT PROGRESS MAY COUNT EACH WORK UNIT AT MOST ONCE
FORK RESOLUTION != ARTIFACT DESTRUCTION
~~~

That would connect the continuation runtime back to the broader GHoT principle:
contradictions may preserve useful artifacts even when only one execution
lineage remains authoritative.
