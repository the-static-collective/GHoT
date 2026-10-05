# Experiment 062 — Continuation DAG / Multi-Hop Resume Lineage

## Question

Can a partially completed execution migrate more than once while preserving:

- one root-relative work denominator;
- exact consumed and released capacity at every hop;
- distinct local authority for every resource owner;
- one live continuation leaf per branch;
- full checkpoint ancestry at completion?

The specimen is:

~~~text
F checkpoint 40%
-> E resume
-> E checkpoint 70%
-> E stop / handoff
-> H resume
-> H completion 100%
~~~

## Root-relative work accounting

The original work measure is:

~~~text
30 compute-minutes
~~~

All progress percentages remain percentages of that original 30-unit job.

They do not reset when the job moves between resources.

Thus:

~~~text
F checkpoint 40%
= 12 compute-minutes cumulative

E checkpoint 70%
= 21 compute-minutes cumulative
= 9 additional compute-minutes after F

H remainder
= 30 - 21
= 9 compute-minutes
~~~

This gives the final accounting:

~~~text
F consumed = 12
E consumed =  9
H consumed =  9
----------------
total      = 30
~~~

Thus:

> **ANCESTOR CHECKPOINTS MAY NOT BE DOUBLE-COUNTED**

## Partial stop now settles real capacity

062 exposed a gap in the earlier long-running model.

A checkpoint could represent partial work while a stop merely released the full
reservation. That preserved state history but undercounted operational capacity.

062 extends reservation finalization with:

~~~text
status = PARTIALLY_CONSUMED

consumed_measure
released_measure
partial_evidence_ref
~~~

with the invariant:

~~~text
consumed + released = reserved
~~~

For F:

~~~text
reserved = 30
checkpoint = 40%

consumed = 12
released = 18
~~~

For E:

~~~text
reserved = 18
root-relative progress:
40% -> 70%

new contribution = 30% of root 30
                 = 9

consumed = 9
released = 9
~~~

The existing 059, 060, and 061 simulations remain green under this stronger
accounting.

## Hop 0 — F

F starts with its own 30-unit reservation.

At 40%:

~~~text
checkpoint = 40%
partial result = partial:062-f-40
~~~

F pauses and stops.

The stop finalizes the reservation as:

~~~text
PARTIALLY_CONSUMED
consumed = 12
released = 18
~~~

The checkpoint remains immutable lineage.

## Hop 1 — E

E independently creates:

~~~text
reservation = 18 compute-minutes
~~~

That quantity is the exact root-relative remainder after F's 40%.

E resumes from F's checkpoint.

This is still 060-style continuation:

~~~text
prior progress = 40%
new authority = E reservation 18
~~~

E later reaches:

~~~text
total progress = 70%
new root-relative progress = 30%
~~~

Because the root measure is 30:

~~~text
30% of 30 = 9
~~~

E then stops for another handoff.

Its 18-unit reservation finalizes:

~~~text
PARTIALLY_CONSUMED
consumed = 9
released = 9
~~~

The E run becomes durably STOPPED.

An attempted E checkpoint after stop is refused.

Thus the old E node cannot remain a live continuation after handoff.

## Handoff artifact

E signs a continuation handoff binding:

~~~text
root F run
root F checkpoint
E resume
E checkpoint
E stop
E partial finalization
chosen next reservation
root-relative cumulative work
root-relative remaining work
~~~

The handoff says:

~~~text
cumulative progress = 70%
cumulative work = 21
remaining work = 9
parent_leaf_closed = true
execution_authority = none
ownership_transfer = false
history_rewritten = false
~~~

The handoff names one exact next reservation.

A valid G reservation for 9 units is deliberately tested against the H-bound
handoff.

It is refused.

Thus:

> **ONLY ONE LIVE LEAF PER CONTINUATION BRANCH**

The handoff does not make H authoritative by itself.

It only closes E's branch and names the specific candidate authority for the
next branch.

## Hop 2 — H

H independently holds:

~~~text
reservation = 9 compute-minutes
~~~

H must also pass a fresh current temporal execution gate.

The continuation node then records:

~~~text
hop_index = 2
prior progress = 70%
prior work = 21
remaining work = 9

checkpoint ancestry:
  F checkpoint 40%
  E checkpoint 70%
~~~

The three resource reservations are distinct:

~~~text
F reservation
!= E reservation
!= H reservation
~~~

Thus:

> **CONTINUATION LINEAGE != RESOURCE LINEAGE**

The execution lineage is one ancestry graph.

The operational authority is three separate owner-local histories.

## Multi-hop resume is not restart chaining

H does not begin a new 9-unit job.

It begins the final continuation of the original 30-unit job.

Its node preserves:

~~~text
root run
root checkpoint
parent resume
parent checkpoint
parent handoff
full checkpoint ancestry
root work measure
cumulative ancestor work
remaining root-relative work
~~~

Thus:

> **MULTI-HOP RESUME != RESTART CHAIN**

The denominator remains 30 from F through H.

## Live-leaf view

Before H completes, the derived DAG view reports:

~~~text
status = ACTIVE
live_leaf_count = 1
live_leaf = H continuation node
~~~

A view containing multiple live child nodes for the same handoff is refused.

The DAG observation itself has:

~~~text
execution_authority = none
global_consensus = false
~~~

It is a derived lineage view, not an authority source.

## Completion

At cut 11, H passes another fresh temporal gate.

H executes its exact 9-unit reservation.

The completion records:

~~~text
ancestor work = 21
new work = 9
total work = 30
total progress = 100%

ancestor_work_reexecuted = false
ancestor_work_double_counted = false
full_ancestry_proven = true
service_complete = true
settlement_authority = none
~~~

The final DAG becomes:

~~~text
status = COMPLETED
live_leaf_count = 0
terminal_leaf = H completion
~~~

Thus:

> **COMPLETION MUST PROVE THE FULL RESUME ANCESTRY**

Completion is not allowed to cite only H's local work.

It must prove the complete F -> E -> H checkpoint lineage.

## Every hop receives new authority

The full authority path is:

~~~text
F local reservation 30
  -> consume 12 / release 18

E local reservation 18
  -> consume 9 / release 9

H local reservation 9
  -> consume 9
~~~

No reservation moves between Guilds.

No owner is inherited.

No checkpoint grants capacity.

Thus:

> **EACH HOP REQUIRES NEW LOCAL AUTHORITY**

## Laws

~~~text
CONTINUATION LINEAGE != RESOURCE LINEAGE
MULTI-HOP RESUME != RESTART CHAIN
ANCESTOR CHECKPOINTS MAY NOT BE DOUBLE-COUNTED
EACH HOP REQUIRES NEW LOCAL AUTHORITY
ONLY ONE LIVE LEAF PER CONTINUATION BRANCH
COMPLETION MUST PROVE THE FULL RESUME ANCESTRY
~~~

## Result

Long-running execution can now migrate repeatedly while preserving both state
and operational accounting:

~~~text
                    continuation lineage
F 40% ----------------> E 70% ----------------> H 100%
 |                       |                        |
 |                       |                        |
12 consumed              9 consumed               9 consumed
18 released              9 released               0 remaining
 |                       |                        |
F authority              E authority              H authority
~~~

The lineage is continuous.

The authority is local.

The accounting is conserved.

## Next aperture

062 proves a two-hop continuation DAG.

The next useful move is:

~~~text
063 — Recursive Continuation Kernel / Arbitrary-Depth Resume
~~~

The current 062 node intentionally proves the second hop explicitly.

063 can generalize that into one recursive continuation grammar:

~~~text
root checkpoint
-> continuation node
-> checkpoint
-> continuation node
-> checkpoint
-> ...
-> completion
~~~

with no hardcoded hop count.

That should preserve:

~~~text
DEPTH != AUTHORITY
RECURSION != HISTORY COLLAPSE
EACH EDGE MUST PROVE ITS PARENT
ROOT MEASURE MUST REMAIN INVARIANT
ONLY ONE LIVE LEAF PER ACCEPTED BRANCH
COMPACTION MAY SHORTEN PROOF TRANSPORT WITHOUT ERASING ANCESTRY
~~~

That would turn the demonstrated DAG into a reusable continuation runtime.
