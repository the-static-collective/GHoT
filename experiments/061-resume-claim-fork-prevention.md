# Experiment 061 — Resume Claim / Fork Prevention

## Question

Can the same stopped checkpoint be visible to multiple valid sovereign providers
without allowing the partial execution to fork into multiple live
continuations?

The checkpoint may be portable.

The continuation authority must not be.

## Candidate resume claims

Guild E and Guild G each independently hold:

- valid current capacity;
- an exact 18 compute-minute reservation;
- the same F source run;
- the same 40% F checkpoint;
- the same released source lineage.

Each may therefore sign a candidate resume claim.

The claim binds:

~~~text
source run
source reservation
source checkpoint
source stop
source partial result
source progress
candidate guild
candidate reservation
candidate authorization
candidate native measure
~~~

and explicitly carries:

~~~text
execution_authority = none
ownership_transfer = false
source_history_rewritten = false
~~~

Thus:

> **CLAIM != EXECUTION**

A valid claim says:

~~~text
I possess candidate authority that could continue this checkpoint.
~~~

It does not say:

~~~text
I am the continuation.
~~~

## One source-owner-local active claim

The stopped run remains part of F's lineage.

061 therefore gives F an owner-local atomic resume-claim registry keyed by the
source checkpoint.

E and G submit their claims concurrently.

The registry serializes the exact checkpoint key.

The result is always:

~~~text
ACTIVE claims = 1
LOSING claims = 1
~~~

never:

~~~text
ACTIVE claims = 2
~~~

inside one authoritative F-local registry.

Thus:

> **ONE CHECKPOINT -> AT MOST ONE ACTIVE RESUME CLAIM**

The winning claim is signed into an ACTIVE decision by F.

The losing claim receives a distinct signed LOSING decision.

## Losing does not erase the claim

The losing decision records:

~~~text
status = LOSING
active_resume_claim_id = winner
claim_deleted = false
execution_authority = none
global_consensus = false
~~~

The losing candidate's claim remains part of history.

Its independently valid local reservation also remains its own resource state
until that resource owner acts.

The losing provider cannot resume through the checkpoint claim gate.

Its owner may then explicitly release the unused reservation.

Thus:

> **LOSING CLAIM != HISTORY DELETION**

## Winning continuation

The ACTIVE claim still does not execute anything.

The winning provider must pass the existing 060 resume requirements:

- exact source checkpoint lineage;
- exact remaining-work measure;
- fresh current temporal gate;
- independent new reservation;
- owner-local resumed execution.

061 adds a derived claim-bound resume linkage:

~~~text
source checkpoint
+ winning resume claim
+ ACTIVE claim decision
+ resumed execution
-> claim-bound resume
~~~

The artifact carries:

~~~text
claim_is_execution = false
ownership_transfer = false
source_history_rewritten = false
~~~

The resumed execution continues under fresh policy gates exactly as in 060.

## Winning completion lineage

The winner resumes from total 40%, checkpoints at total 70%, and completes at
100%.

061 derives one final linkage:

~~~text
winning resume claim
-> claim-bound resume
-> resumed completion
~~~

The completion binding explicitly records:

~~~text
winning_continuation_named = true
losing_claims_deleted = false
execution_authority = none
settlement_authority = none
~~~

Thus:

> **COMPLETION MUST NAME THE WINNING CONTINUATION LINEAGE**

A completed continuation cannot detach itself from the claim that won the right
to continue the checkpoint.

## Disconnected replica pressure test

Owner-local atomicity solves one registry.

It does not pretend disconnected replicas can never exist.

061 therefore creates two disconnected F-owned registry replicas.

Replica E sees only E's claim:

~~~text
E -> ACTIVE
~~~

Replica G sees only G's claim:

~~~text
G -> ACTIVE
~~~

Each local receipt is individually valid.

When those receipts are exchanged, 061 derives:

~~~text
status = FORK
active claims = {E, G}
execution_authority = none
global_consensus = false
claim_deleted = false
~~~

Both continuations become blocked.

The fork observation does not decide a winner.

Thus:

> **FORK DETECTION != GLOBAL CONSENSUS**

Detection means only:

~~~text
two contradictory owner-local ACTIVE histories are now visible together
~~~

## Explicit fork resolution

The exact fork set is returned to the source lineage owner.

F signs an explicit v0 resolution over the complete active claim set.

The deterministic test rule is:

~~~text
lowest-claim-id
~~~

The resolution records:

~~~text
winning claim
losing claims
claim_deleted = false
global_consensus = false
execution_authority = none
~~~

After resolution:

~~~text
winner -> ELIGIBLE_RESOLVED
loser  -> SUPERSEDED
~~~

The losing ACTIVE receipt remains historical evidence that the split occurred.

Resolution does not rewrite either replica's past.

## Resumable state is not plural authority

The source checkpoint may be copied freely.

Many providers may independently prepare exact remaining capacity.

Many claims may exist.

But those facts do not multiply continuation authority.

Thus:

> **RESUMABLE STATE != MULTIPLE CONTINUATION AUTHORITY**

The portable thing is state lineage.

The singular thing is the currently accepted continuation branch.

## Authority layers

061 now separates:

~~~text
checkpoint
  = resumable state

candidate reservation
  = local resource authority

resume claim
  = candidate continuation request

ACTIVE claim decision
  = source-owner-local continuation selection

claim gate
  = proof that this claim is currently eligible

resume
  = new owner-local execution lineage

completion binding
  = proof that completion belongs to the winning continuation
~~~

None of those categories collapse into another.

## Laws

~~~text
RESUMABLE STATE != MULTIPLE CONTINUATION AUTHORITY
ONE CHECKPOINT -> AT MOST ONE ACTIVE RESUME CLAIM
CLAIM != EXECUTION
LOSING CLAIM != HISTORY DELETION
FORK DETECTION != GLOBAL CONSENSUS
COMPLETION MUST NAME THE WINNING CONTINUATION LINEAGE
~~~

## Result

The execution graph can now migrate without silently branching:

~~~text
F checkpoint 40%
       |
       +---- E claim
       |
       +---- G claim
             |
             v
     F-local claim selection
        /             \
   ACTIVE            LOSING
      |                 |
      v                 v
   RESUME             history
      |
      v
  COMPLETE 100%
~~~

And if disconnected replicas accidentally create:

~~~text
E ACTIVE
G ACTIVE
~~~

exchange produces:

~~~text
FORK
-> execution blocked
-> explicit F-local resolution
-> one eligible continuation
~~~

No global chain or universal ordering is introduced.

## Next aperture

061 prevents two active continuations of one checkpoint.

The next pressure point is what happens when the winning continuation itself
later pauses and migrates again:

~~~text
062 — Continuation DAG / Multi-Hop Resume Lineage
~~~

For example:

~~~text
F checkpoint 40%
-> E resume
-> E checkpoint 70%
-> pause
-> H resume
-> completion 100%
~~~

That should preserve:

~~~text
CONTINUATION LINEAGE != RESOURCE LINEAGE
MULTI-HOP RESUME != RESTART CHAIN
ANCESTOR CHECKPOINTS MAY NOT BE DOUBLE-COUNTED
EACH HOP REQUIRES NEW LOCAL AUTHORITY
ONLY ONE LIVE LEAF PER CONTINUATION BRANCH
COMPLETION MUST PROVE THE FULL RESUME ANCESTRY
~~~

That would turn one migration edge into a durable execution DAG.
