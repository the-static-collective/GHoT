# Experiment 065 — Recursive Branch Merge / Salvage of Losing Work

## Question

What happens when a recursive fork is discovered only after both descendants
have already performed legitimate useful work?

064 handled:

~~~text
L 60%
 /    \
P      Q
zero   zero
work   work
~~~

065 handles:

~~~text
L 60%
 /    \
P 75%  Q 80%
 \    /
 fork discovered
~~~

Both branch contributions are real.

Only one branch may remain authoritative for the original execution.

The losing branch must not become fictitious merely because it lost authority.

## Deep-parent setup

The specimen builds the ordinary recursive lineage:

~~~text
F -> E -> H -> J -> K -> L
~~~

At L:

~~~text
hop index = 5
root progress = 60%
root cumulative work = 60 compute-minutes
remaining root work = 40
~~~

Two disconnected L-owned replicas then independently produce:

~~~text
L -> P
L -> Q
~~~

Both P and Q own valid local 40-unit reservations.

The handoffs and child nodes are individually valid exactly as in 064.

## Both children do real work

Before the fork is discovered, P advances from 60% to 75%.

~~~text
new useful work = 15
reserved = 40
consumed = 15
released = 25
artifact = artifact:065-p-75
~~~

Q independently advances from 60% to 80%.

~~~text
new useful work = 20
reserved = 40
consumed = 20
released = 20
artifact = artifact:065-q-80
~~~

Both work records are signed checkpoint evidence backed by real
PARTIALLY_CONSUMED reservation finalizations.

Therefore:

> **LOSING BRANCH WORK != ZERO WORK**

A branch becoming non-authoritative later cannot retroactively make its
verified computation disappear.

## Fork discovery still blocks continuation

After the two descendant histories meet:

~~~text
status = FORK
global_consensus = false
history_deleted = false
~~~

Both descendants are blocked from making another continuation handoff.

This remains true even though both contain real useful output.

Useful work is not continuation authority.

## Resolution chooses lineage, not reality

L resolves the exact fork set under the existing 064 rule.

One child becomes:

~~~text
ELIGIBLE_RESOLVED
~~~

The other becomes:

~~~text
SUPERSEDED
~~~

The resolution chooses which descendant may define future root progress.

It does not claim that the other descendant never computed anything.

Thus:

~~~text
RESOLUTION SELECTS LINEAGE
!=
RESOLUTION CREATES OR DESTROYS WORK
~~~

## Resolved branch progress

065 derives a resolved-progress artifact from the winning child.

It binds the fork, resolution, exact parent checkpoint, winning handoff,
winning child, winning checkpoint, winning stop, and winning finalization.

It records:

~~~text
credited work measure
authoritative cumulative work
authoritative progress percentage

continuation_authority = none
execution_authority = none
settlement_authority = none
~~~

This is evidence explaining which already-performed work belongs to the
accepted root history. It does not create that work.

## Losing branch salvage

The losing child receives a separate salvage artifact.

The salvage verifies the losing child, checkpoint, stop, reservation, partial
finalization, exact fork, and exact resolution.

It preserves:

~~~text
artifact_ref
salvaged_work_measure
~~~

but explicitly assigns:

~~~text
root_progress_credit = 0
continuation_authority = none
execution_authority = none
settlement_authority = none

artifact_survives = true
history_deleted = false
~~~

Thus:

> **SALVAGE != CONTINUATION AUTHORITY**

and:

> **USEFUL OUTPUT MAY SURVIVE A LOSING BRANCH**

## Forged credit pressure test

The simulator copies the valid salvage record and changes:

~~~text
root progress credit = 0
~~~

to:

~~~text
root progress credit = losing branch work
~~~

Verification fails.

A salvage record therefore cannot quietly promote useful losing work into root
execution credit.

## The losing branch still cannot continue

After resolution, the losing descendant attempts another handoff.

It is refused by the branch gate.

This remains true even though its salvage artifact is retained.

~~~text
artifact survival
!=
continued execution authority
~~~

## Winner continues normally

The resolved branch has also stopped after its useful partial contribution.

It performs a normal recursive handoff to a new sovereign provider R with
exactly the remaining root-relative quantity.

If P won:

~~~text
L 60
+ P 15
= 75 authoritative

R receives 25
~~~

If Q won:

~~~text
L 60
+ Q 20
= 80 authoritative

R receives 20
~~~

R independently owns that reservation, passes fresh temporal gates, and
completes the authoritative root execution at 100%.

## Two different totals are meaningful

065 intentionally tracks two measurements.

### Authoritative root total

Only the accepted execution ancestry counts:

~~~text
pre-fork root work
+ winning branch work
+ terminal continuation work
= 100
~~~

For the first green specimen, Q won:

~~~text
60 + 20 + 20 = 100
~~~

### Useful work observed

The losing P branch also performed 15 real compute-minutes.

~~~text
authoritative root total = 100
losing salvage work = 15
useful work observed = 115
~~~

This is not an accounting error.

The system can truthfully say:

~~~text
115 units of useful work occurred
~~~

while also saying:

~~~text
only 100 units belong to this authoritative execution
~~~

Thus:

> **ROOT PROGRESS MAY COUNT EACH WORK UNIT AT MOST ONCE**

The losing work is real but receives zero root-progress credit.

## Artifact attachment

The losing artifact may be attached to the final authoritative result as:

~~~text
attachment_role = auxiliary-artifact
artifact_retained = true
merged_execution = false
root_progress_credit = 0
~~~

The attachment requires the actual terminal continuation node and verifies its
signed completion before linking the salvage.

Thus:

> **MERGEABLE ARTIFACT != MERGED EXECUTION**

The final result may carry, cite, inspect, remix, or otherwise preserve the
losing branch artifact.

That does not merge the two execution histories.

## Salvage accounting witness

065 derives a final read-only accounting witness containing:

~~~text
root source work
pre-fork cumulative work

winning branch credited work
terminal credited work

losing branch salvaged work
losing branch root credit = 0

authoritative root total
useful work observed including salvage
~~~

and explicitly records:

~~~text
root_progress_double_counted = false
artifact_destroyed = false
execution_merged = false
settlement_authority = none
~~~

For the green run:

~~~text
authoritative root total = 100
useful work observed = 115
double counted = false
~~~

The exact useful-work total can vary with which deterministic branch wins, but
the invariant does not:

~~~text
authoritative root total = 100
salvage root credit = 0
useful work observed > 100
~~~

## Laws

~~~text
LOSING BRANCH WORK != ZERO WORK
SALVAGE != CONTINUATION AUTHORITY
MERGEABLE ARTIFACT != MERGED EXECUTION
USEFUL OUTPUT MAY SURVIVE A LOSING BRANCH
ROOT PROGRESS MAY COUNT EACH WORK UNIT AT MOST ONCE
FORK RESOLUTION != ARTIFACT DESTRUCTION
~~~

## Result

Recursive contradiction no longer forces a false binary between:

~~~text
"this branch wins"
and
"the other branch was worthless"
~~~

Instead:

~~~text
fork
 |
 +-- resolved branch
 |     |
 |     +-- credited root progress
 |     +-- new local continuation
 |     +-- authoritative completion
 |
 +-- losing branch
       |
       +-- verified useful work
       +-- zero root progress credit
       +-- preserved artifact
       +-- no continuation authority
~~~

Authority remains singular.

Evidence remains plural.

Useful artifacts survive contradiction.

## Next aperture

065 salvages a losing branch as an auxiliary artifact while keeping its work
out of the root execution ledger.

The next deeper question is whether some losing work is structurally
non-overlapping with winning work and could legitimately replace future work.

~~~text
066 — Work-Region Provenance / Non-Overlapping Salvage
~~~

For example, if a render job names exact tiles, frames, pixels, ranges, or
subgraphs:

~~~text
winner computed regions A + B
loser computed region C
future still needs C
~~~

then C might be admissible into the authoritative result without replay.

That requires proving region identity and non-overlap rather than merely
trusting aggregate progress percentages.

Likely laws:

~~~text
PROGRESS PERCENT != WORK REGION
NON-OVERLAP MUST BE PROVEN
SALVAGED REGION != SALVAGED AUTHORITY
REUSE != DOUBLE CREDIT
ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE
REGION COMPOSITION MAY COMPLETE WORK WITHOUT REEXECUTION
~~~

That would connect recursive fork salvage directly back to the useful-work
kernel's exact evidence identities.
