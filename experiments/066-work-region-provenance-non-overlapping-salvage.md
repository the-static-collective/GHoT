# Experiment 066 — Work-Region Provenance / Non-Overlapping Salvage

## Question

065 preserved useful work from a losing recursive branch but deliberately gave
that work zero root-progress credit.

That was correct because aggregate progress could answer only:

~~~text
how much work happened?
~~~

It could not answer:

~~~text
which exact work happened?
~~~

066 introduces exact work-region provenance so a losing branch may contribute
only the regions that are both correct and genuinely absent from the accepted
lineage.

## Core distinction

The central law is:

> **PROGRESS PERCENT != WORK REGION**

For this specimen the root work is a deterministic Ice Cube render:

~~~text
10 x 10 pixels
= 100 exact pixel regions
~~~

Each region is content-addressed from:

~~~text
Ice Cube work address
pixel index
x coordinate
y coordinate
~~~

Each region claim also carries the deterministic pixel value produced by the
same Halley/Mandelbrot render semantics already used by the Ice Cube producer
and Dogram verifier.

The region layer therefore does not invent a second render identity.

It addresses pieces of the existing canonical work object.

## Region plan

The root region plan contains:

~~~text
work address
continuation lineage id
width = 10
height = 10
region count = 100

region 0
region 1
...
region 99
~~~

For this bounded 066 specimen only, the operational accounting policy maps:

~~~text
1 pixel region = 1 compute-minute
~~~

That mapping is explicitly specimen-local.

Thus:

~~~text
REGION IDENTITY != RESOURCE QUANTITY
~~~

in the general architecture even though the test uses a simple one-to-one
mapping.

## Aggregate progress is not enough

At the deep parent L:

~~~text
checkpoint progress = 60%
cumulative work = 60 compute-minutes
~~~

That does not prove which 60 pixels exist.

066 therefore requires L to sign an explicit region-coverage attestation for:

~~~text
regions 0..59
~~~

The attestation verifies:

~~~text
signed L continuation checkpoint
same continuation lineage
same Ice Cube work address
60 exact region ids
60 exact pixel values
60-unit cumulative work measure
~~~

A hostile attempt to present only 59 exact regions against the 60-unit
checkpoint is refused.

Thus:

> **COVERAGE ATTESTATION != EXECUTION RECEIPT**

and, more importantly:

> **PROGRESS PERCENT != WORK REGION**

## Forked branch geometry

After L reaches 60%, disconnected replicas produce children P and Q exactly as
in 064/065.

P reaches 75% and contributes 15 regions:

~~~text
P = regions 60..74
~~~

Q reaches 80% and contributes 20 regions:

~~~text
Q = regions 60..69
  + regions 75..84
~~~

So the two branch sets deliberately contain:

~~~text
overlap = regions 60..69
        = 10 regions
~~~

and each branch also contains regions the other did not compute.

P and Q each sign exact region-work receipts bound to their real:

~~~text
child node
checkpoint
stop
reservation
PARTIALLY_CONSUMED finalization
artifact reference
region set
pixel values
~~~

The region count must exactly match the checkpoint's new work measure.

A mutated pixel value fails verification.

## Resolution chooses lineage, not region truth

The ordinary 064 fork resolution still chooses one branch as the continuation
winner.

The region layer does not replace that authority decision.

For the green exact-tip specimen:

~~~text
winner = Q
loser = P
~~~

Therefore the accepted coverage before salvage is:

~~~text
L accepted regions = 0..59

Q accepted regions =
  60..69
  75..84
~~~

P's losing work is:

~~~text
60..74
~~~

## Exact non-overlap derivation

066 compares region identities as sets.

For the green specimen:

~~~text
P losing regions = 60..74

already accepted from L + Q =
  0..69
  75..84
~~~

Therefore:

~~~text
overlap =
  60..69
  = 10 regions

reusable =
  70..74
  = 5 regions
~~~

The overlapping ten regions remain valid historical evidence that P computed
them.

They receive no second credit.

The unique five regions are merely derived as reusable candidates.

At this stage:

~~~text
root region coverage credit = 0
continuation progress credit = 0
continuation authority = none
execution authority = none
~~~

Thus:

> **NON-OVERLAP MUST BE PROVEN**

and:

> **REUSE != DOUBLE CREDIT**

## Salvage is not authority

The non-overlap artifact cannot admit itself.

The exact L parent owner must sign a separate salvaged-region admission.

Before signing, the admission constructor recomputes the full evidence chain:

~~~text
L signed checkpoint
L exact coverage attestation
fork
signed fork resolution
winning signed region bundle
losing signed region bundle
derived exact non-overlap set
~~~

Only the proven reusable set may be admitted.

A hostile mutation that changes the reusable-region count is refused before
the parent can sign it.

The admission grants:

~~~text
root region coverage credit = reusable region count
~~~

but still grants:

~~~text
continuation progress credit = 0
execution authority = none
settlement authority = none
~~~

Thus:

> **SALVAGED REGION != SALVAGED AUTHORITY**

Region reuse is admitted coverage, not inherited execution authority.

## Missing work after salvage

Whichever branch wins, the chosen geometry leaves exactly 85 distinct root
regions covered after non-overlapping salvage.

If Q wins:

~~~text
L = 60
Q = 20
P reusable = 5
-------------
covered = 85
~~~

If P wins:

~~~text
L = 60
P = 15
Q reusable = 10
--------------
covered = 85
~~~

Therefore the exact missing set is always:

~~~text
15 regions
~~~

This is stronger than saying:

~~~text
15% remains
~~~

because the system now knows the exact region ids.

## Fresh execution only for the missing regions

Provider R receives a claim set naming those exact 15 missing pixel regions.

The claim-set identity is bound into the ordinary Guild proposal as the purpose
reference.

R then goes through the existing operational chain:

~~~text
Treasury capability
-> proposal for 15 compute-minutes
-> steward authorization
-> reservation
-> one execution attempt
-> signed execution receipt
-> CONSUMED finalization
~~~

The signed execution receipt names the exact region claim-set id as its result.

066 then derives region-execution evidence only after verifying the full:

~~~text
proposal
authorization
reservation
execution receipt
finalization
exact pixel claims
~~~

R consumes exactly:

~~~text
15 compute-minutes
~~~

for exactly:

~~~text
15 still-missing regions
~~~

No salvaged region is replayed.

## Exact render reconstruction

The final composition credits four disjoint region groups:

~~~text
1. L pre-fork accepted coverage
2. resolved winning branch regions
3. parent-admitted non-overlapping losing regions
4. R freshly executed missing regions
~~~

Every credited region id must appear exactly once.

Their union must equal all 100 root region ids.

The compositor then reassembles the 100 pixel values in canonical row-major
order into:

~~~text
P5 PGM
10 x 10
255
[pixel bytes]
~~~

The reconstructed bytes are compared with a fresh canonical Ice Cube render of
the same work object.

For the green run:

~~~text
render reconstructed exactly = true
authoritative region coverage = 100
root region double counted = false
salvaged regions reexecuted = 0
work complete = true
~~~

The resulting render address is the canonical render address.

Thus:

> **ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE**

and:

> **REGION COMPOSITION MAY COMPLETE WORK WITHOUT REEXECUTION**

## Useful work can exceed credited work

Both P and Q genuinely executed work before the fork was discovered.

The green specimen therefore observes:

~~~text
L accepted work = 60
P physical work = 15
Q physical work = 20
R fresh work = 15
--------------------
useful region work observed = 110
~~~

But authoritative root region coverage remains:

~~~text
100 unique regions
~~~

The duplicate ten-region P/Q overlap is truthful physical work but receives no
second root credit.

This makes the accounting distinction explicit:

~~~text
physical useful work observed
!=
unique authoritative root coverage
~~~

## Green specimen

The exact green run produced:

~~~text
root plan:
  10 x 10
  100 regions

L:
  60 exact accepted regions

P:
  15 exact regions

Q:
  20 exact regions

P/Q overlap:
  10 regions

resolution:
  Q wins
  P loses

P reusable non-overlap:
  5 regions

R fresh execution:
  15 regions

final authoritative region coverage:
  100

useful region work observed:
  110

salvaged regions reexecuted:
  0

canonical render reconstructed:
  true
~~~

## Laws

~~~text
PROGRESS PERCENT != WORK REGION
NON-OVERLAP MUST BE PROVEN
SALVAGED REGION != SALVAGED AUTHORITY
REUSE != DOUBLE CREDIT
ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE
REGION COMPOSITION MAY COMPLETE WORK WITHOUT REEXECUTION
~~~

## Result

The continuation runtime can now distinguish:

~~~text
how much work occurred
from
which exact work occurred
~~~

That makes a new form of salvage possible.

A losing branch can contribute exact useful regions to the final artifact
without:

~~~text
reviving the losing continuation
moving its execution authority
replaying those regions
double-crediting overlap
rewriting fork history
~~~

The result is composed from plural evidence while preserving singular
continuation authority.

## Next aperture

066 binds exact regions into evidence and indirectly into R's execution purpose
reference.

The next useful move is to make region authority first-class:

~~~text
067 — Exact Region Assignment / Sparse Work Lease
~~~

Instead of authorizing:

~~~text
15 compute-minutes
for purpose = region-claim-set
~~~

the authority artifact itself can name:

~~~text
exact region ids
exact root work address
exact accepted coverage cut
exact missing-set digest
~~~

Likely laws:

~~~text
QUANTITY != REGION AUTHORITY
REGION ASSIGNMENT != OWNERSHIP
ASSIGNMENT MUST NAME EXACT MISSING WORK
REGION LEASE != REGION RESULT
PARTIAL REGION EXECUTION MUST PRESERVE UNFINISHED IDS
REASSIGNMENT MAY NOT DUPLICATE LIVE REGION AUTHORITY
~~~

That would turn exact region provenance from a verification layer into a native
distributed work scheduler.
