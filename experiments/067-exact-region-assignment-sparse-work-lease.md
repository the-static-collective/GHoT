# Experiment 067 — Exact Region Assignment / Sparse Work Lease

## Question

066 proved exact work-region provenance and showed that a losing branch can
contribute non-overlapping regions to a canonical result without replay or
double credit.

But the final worker was still authorized operationally as:

~~~text
15 compute-minutes
purpose = exact-region-claim-set
~~~

The exact region set constrained evidence.

It did not yet exist as its own delegated work authority.

067 asks:

> Can exact missing work become first-class sparse assignment authority without
> collapsing that authority into compute capacity, ownership, or result proof?

The answer is yes.

## Core separation

067 introduces:

~~~text
exact missing work observation
        |
        v
sparse region work lease
        |
        +---- says WHICH regions may be worked
        |
        v
worker-local compute capacity
        |
        +---- says WHICH resources may be spent
        |
        v
exact region result
~~~

The central law is:

> **QUANTITY != REGION AUTHORITY**

A worker holding capacity for 15 compute-minutes does not thereby have
authority over any particular 15 regions.

A worker holding a lease for 15 particular regions does not thereby receive
compute capacity.

Therefore:

> **REGION ASSIGNMENT != COMPUTE CAPACITY AUTHORITY**

## Exact missing-region observation

067 re-derives the complete 066 evidence chain:

~~~text
root pixel-region plan
L parent checkpoint
L accepted coverage
fork
fork resolution
winning branch region receipt
losing branch region receipt
non-overlap derivation
parent-owner salvage admission
~~~

Only then does it derive an exact missing set.

For the executable specimen:

~~~text
root regions = 100
accepted after winner + salvage = 85
missing regions = 15
~~~

The observation contains:

~~~text
root work address
pixel-region plan id
continuation lineage id
exact parent checkpoint
fork resolution
salvage admission

accepted region ids
accepted coverage digest

missing region ids
missing region-set digest

missing work measure = 15 compute-minutes
~~~

It also names:

~~~text
assignment_owner_particular = exact parent steward
~~~

and explicitly grants:

~~~text
assignment_authority = none
execution_authority = none
settlement_authority = none
~~~

The missing set is evidence.

It is not itself a lease.

> **ASSIGNMENT MUST NAME EXACT MISSING WORK**

## Owner-local sparse lease

The exact assignment owner may issue a sparse region lease.

A lease binds:

~~~text
exact missing-region-set id
root pixel-region plan id
continuation lineage id
root work address

accepted coverage digest
missing region-set digest

assigner
worker node
worker particular

exact assigned region ids
region-set digest
assigned region count
assigned work measure

issuance cut
expiry cut
~~~

The lease explicitly records:

~~~text
compute_capacity_authority = none
ownership_transfer = false
settlement_authority = none
~~~

Thus:

> **REGION ASSIGNMENT != OWNERSHIP**

The assigner must be the exact assignment owner named by the missing-set
evidence.

A different signer cannot mint a valid lease over the same missing set.

## Quantity alone is insufficient

The green specimen leases all 15 missing regions to R.

The lease therefore happens to say:

~~~text
assigned regions = 15
assigned work measure = 15 compute-minutes
~~~

But those two facts are not interchangeable.

The lease also carries the exact region IDs and their region-set digest.

A request for another arbitrary region with the same scalar quantity would
not be equivalent.

Hence:

> **QUANTITY != REGION AUTHORITY**

## Owner-local anti-overlap

The sparse assignment ledger is atomic inside one owner-local store.

While R holds the 15-region lease, the issuer attempts to lease one of those
same regions to S.

Refused.

Thus a local ledger guarantees:

~~~text
one exact region
-> at most one live sparse lease
~~~

within that ledger.

> **REASSIGNMENT MAY NOT DUPLICATE LIVE REGION AUTHORITY**

## Region lease is not result proof

R cannot merely return region values because it has a sparse lease.

To record region execution, R must also prove a separate local capacity chain:

~~~text
R Treasury capability
-> proposal
-> steward authorization
-> reservation
-> execution receipt
-> consumed finalization
~~~

The proposal must name the sparse lease id.

The execution result must name the exact deterministic region-claim-set id.

The sparse use receipt then binds both worlds:

~~~text
sparse lease
exact consumed region ids
exact deterministic pixel claims

capacity proposal
capacity authorization
capacity reservation
capacity execution receipt
capacity finalization
~~~

Therefore:

> **REGION LEASE != REGION RESULT**

and:

> **REGION ASSIGNMENT != COMPUTE CAPACITY AUTHORITY**

## Outside-region pressure test

R holds authority over the 15 missing regions.

The simulator attempts to record work on a region already belonging to the
accepted parent coverage.

Refused before capacity evidence can matter.

A valid compute budget cannot expand the sparse region lease.

## Partial sparse execution

R does not finish the entire lease.

It computes exactly nine of the fifteen assigned regions.

The sparse use receipt records:

~~~text
assigned regions = 15
consumed regions = 9
~~~

The node-local sparse budget refuses replay of those same nine regions.

Thus:

~~~text
same lease
same region
second consumption attempt
-> REFUSED
~~~

## Exact unfinished-ID preservation

R then releases the lease.

The release does not say merely:

~~~text
6 units unused
~~~

It carries the exact partition:

~~~text
consumed region ids = 9 exact ids
returned region ids = 6 exact ids
~~~

with corresponding work measures.

The owner closes the lease while preserving the exact node release.

067 verifies:

~~~text
consumed ids
+ returned ids
= exact original assigned set

consumed ∩ returned = empty
~~~

The close also preserves:

~~~text
history_deleted = false
~~~

Thus:

> **PARTIAL REGION EXECUTION MUST PRESERVE UNFINISHED IDS**

## Consumed work cannot be reassigned

After R closes its lease, the assignment owner attempts to issue one of R's
already-consumed regions to S.

Refused.

Consumed region authority is exhausted for that exact missing-set observation.

Returning unused authority does not make consumed authority reusable.

## Returned work can be reassigned

The six exact region IDs that R returned are still unfinished.

Those exact six may therefore be leased to S.

S receives:

~~~text
assigned regions = exact R returned set
assigned count = 6
~~~

No other region is silently added.

S supplies its own local compute-capacity chain and consumes all six.

Its release then contains:

~~~text
consumed regions = 6
returned regions = 0
~~~

The final state is:

~~~text
R consumed 9
S consumed 6
--------------
missing set satisfied = 15
~~~

## Exact sparse execution witness

067 derives a combined execution witness only after re-verifying every lease
bundle.

For each lease, it verifies:

~~~text
sparse lease signature
sparse use signature
node release signature
owner close signature

exact use/release/close region partition

capacity proposal
capacity authorization
capacity reservation
capacity execution receipt
capacity finalization

proposal purpose = exact sparse lease id
execution result = exact region claim-set id
use receipt ids = exact capacity evidence ids
use work measure = exact capacity consumed measure
~~~

V0 requires each represented closed sparse lease to have exactly the one use
receipt carried in its execution bundle.

This prevents a close receipt from hiding additional consumed work that the
aggregate witness did not inspect.

The combined witness then requires:

~~~text
all consumed region ids pairwise disjoint

union(consumed region ids)
=
exact missing region set

total local compute consumption
=
missing work measure
~~~

For the green specimen:

~~~text
sparse leases = 2
R regions = 9
S regions = 6
exact missing regions satisfied = 15
compute capacity consumed = 15
region authority duplicated = false
~~~

## Canonical result reconstruction

The final composition does not trust a cached missing-set or aggregate sparse
execution object.

It re-derives:

~~~text
exact missing region set
exact sparse execution evidence
~~~

from the full upstream evidence.

Then it composes four disjoint sources:

~~~text
L accepted regions
resolved winning branch regions
admitted non-overlapping salvage regions
sparse-executed missing regions
~~~

Every root pixel must appear exactly once.

The 100 pixel claims reconstruct the same canonical Ice Cube PGM bytes.

The green result proves:

~~~text
authoritative region coverage = 100
sparse executed regions = 15
root region double counted = false
work complete = true
canonical render reconstructed exactly = true
~~~

## Authority map

The resulting authority structure is:

~~~text
fork parent owner
    |
    +-- admits non-overlapping salvage
    |
    +-- owns exact missing-work assignment surface
            |
            +-- sparse lease R: exact region ids
            |       |
            |       +-- R independently supplies local compute authority
            |       +-- R computes 9
            |       +-- R returns 6 exact ids
            |
            +-- sparse lease S: exact returned ids
                    |
                    +-- S independently supplies local compute authority
                    +-- S computes remaining 6
~~~

No sparse assignment transfers ownership.

No sparse assignment mints compute capacity.

No scalar quantity is allowed to stand in for an exact region set.

## Laws

~~~text
QUANTITY != REGION AUTHORITY
REGION ASSIGNMENT != OWNERSHIP
REGION ASSIGNMENT != COMPUTE CAPACITY AUTHORITY
ASSIGNMENT MUST NAME EXACT MISSING WORK
REGION LEASE != REGION RESULT
PARTIAL REGION EXECUTION MUST PRESERVE UNFINISHED IDS
REASSIGNMENT MAY NOT DUPLICATE LIVE REGION AUTHORITY
~~~

## Result

066 made exact region identity visible.

067 makes exact region identity assignable.

The system can now say:

~~~text
R may work on THESE 15 regions
~~~

rather than only:

~~~text
R may spend 15 units of capacity
~~~

and it can preserve the exact unfinished set through partial execution and
reassignment.

That turns exact provenance into a real sparse distributed work scheduler.

## Next aperture

067 prevents overlapping live region leases inside one owner-local assignment
ledger.

The distributed analogue is now the obvious pressure point:

~~~text
068 — Distributed Sparse Region Claim / Assignment Fork
~~~

Two disconnected copies of the same assignment owner could each lease the
same missing region to different workers:

~~~text
missing region C
      /       \
 replica A   replica B
    -> R       -> S
~~~

Both leases may be locally valid.

When those histories meet, the system must not silently credit both.

Likely laws:

~~~text
LOCAL NON-OVERLAP != GLOBAL NON-OVERLAP
REGION ASSIGNMENT FORK != REGION RESULT FAILURE
FORK DETECTION != GLOBAL CONSENSUS
CONFLICTED REGION AUTHORITY MUST BLOCK RESULT ADMISSION
RESOLUTION MUST NAME THE EXACT REGION SET
LOSING REGION RESULT MAY SURVIVE AS EVIDENCE
ONLY RESOLVED REGION AUTHORITY MAY RECEIVE ROOT COVERAGE CREDIT
~~~

That would extend the contradiction discipline from recursive continuation
lineages all the way down to exact sparse work regions.
