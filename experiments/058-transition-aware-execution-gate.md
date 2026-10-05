# Experiment 058 — Transition-Aware Execution Gate / Durable Enforcement

## Question

Can the temporal reasoning produced by 057 become an actual execution boundary
rather than advisory metadata?

Execution should require current evidence for exactly one valid path:

~~~text
fresh legacy permission
current compliant revalidation
verified migration
~~~

and no-common-path must remain non-executable.

## Decision is not enforcement

057 can derive:

~~~text
LEGACY_PATH_OPEN
REVALIDATION_REQUIRED
MIGRATION_REQUIRED
NO_COMMON_TRANSITION_PATH
~~~

058 does not trust that stored decision by itself.

At execution time, the gate recomputes the temporal intersection from the
original signed transition bundles at the exact execution cut.

Thus:

> **DECISION != ENFORCEMENT**

## Freshness is part of authority

A legacy intersection derived at cut 7 says the old reservation may continue.

Execution is attempted at cut 8 using that cut-7 artifact.

058 refuses it.

The caller must derive the temporal intersection again at cut 8.

The fresh cut-8 result still says:

~~~text
LEGACY_PATH_OPEN
~~~

and only that fresh artifact may pass the execution gate.

Thus:

> **STALE TEMPORAL INTERSECTION != CURRENT AUTHORITY**

and:

> **LEGACY PERMISSION MUST BE PROVEN AT EXECUTION TIME**

## Legacy path

The legacy execution path requires:

~~~text
fresh temporal intersection
aggregate_action = LEGACY_PATH_OPEN
execution reservation = transition subject reservation
no revalidation evidence
no migration evidence
~~~

The successful gate emits:

~~~text
evidence_path = FRESH_LEGACY_PERMISSION
source_evidence_recomputed = true
temporal_freshness_required = true
permitted = true
~~~

The gate itself still carries:

~~~text
reservation_authority = none
execution_authority = none
~~~

Only after the gate is satisfied does the owner-local reservation store execute
the work.

## Revalidation path

The revalidation specimen composes:

~~~text
customer -> bounded grace
promisor -> immediate revalidation
~~~

The aggregate temporal result is:

~~~text
REVALIDATION_REQUIRED
~~~

Execution with no revalidation receipt is refused.

058 then independently recomputes:

- previous active policy set;
- current active policy set at the execution cut;
- current candidate compliance;
- exact revalidation receipt.

The supplied revalidation must be:

~~~text
status = COMPLIANT
future_execution_permitted = true
evaluated_at_cut = execution cut
~~~

A valid current receipt passes:

~~~text
evidence_path = CURRENT_REVALIDATION
~~~

The reservation then executes.

## Evidence types may not collapse

The revalidation path refuses a caller that attempts to provide migration
evidence alongside the revalidation receipt.

The evidence types are semantically distinct.

Thus:

> **REVALIDATION RECEIPT != MIGRATION RECEIPT**

A caller cannot satisfy one gate by presenting evidence intended for another.

## Migration path

Migration uses two different reservation objects.

The transition subject is the old F reservation:

~~~text
F reservation
authorized under older temporal state
~~~

The execution reservation is a new E reservation:

~~~text
E reservation
created under current policy state
~~~

Before migration can pass:

1. F must explicitly RELEASE its old reservation.
2. E must independently create a distinct reservation.
3. the current active policy set must recompute at the execution cut.
4. the individual migration transition decision must recompute.
5. the migration receipt must recompute from:
   - old reservation;
   - signed RELEASED finalization;
   - new reservation;
   - current policy set.

Trying to execute the old reservation is refused.

Only E's new reservation may pass:

~~~text
evidence_path = VERIFIED_MIGRATION
execution_reservation = E reservation
~~~

The new reservation then executes normally under E's owner-local authority.

## No-common-path is a hard stop

The conflict specimen combines:

~~~text
MIGRATE_BEFORE_EXECUTION
FINISH_IN_FLIGHT_ONLY
execution already started before v2
~~~

057 derives:

~~~text
NO_COMMON_TRANSITION_PATH
~~~

058 refuses execution unconditionally.

No revalidation receipt, migration receipt, stale permission, or existing
reservation can turn that result into execution authority.

The old reservation remains live because refusal itself does not mutate the
owner's ledger.

Thus:

> **NO COMMON PATH != EXECUTION AUTHORITY**

## Source evidence is recomputed

The gate does not merely verify that supplied receipts have valid shapes.

It recomputes from source evidence:

~~~text
signed transition bundles
-> fresh temporal intersection

signed policy fragments + signed versions
-> current policy set

candidate evidence
-> current revalidation

owner-local release + new reservation
-> migration receipt
~~~

Only then does execution proceed.

Thus:

> **ENFORCEMENT MUST RECOMPUTE FROM SOURCE EVIDENCE**

## Durable gate witness

A successful execution gate is content-addressed and binds:

~~~text
promise
route policy
source slot
fresh temporal intersection
transition-subject reservation
actual execution reservation
execution cut
aggregate temporal action
evidence path
revalidation id or migration id when applicable
current policy-set id when applicable
~~~

It explicitly records:

~~~text
permitted = true
source_evidence_recomputed = true
temporal_freshness_required = true
reservation_authority = none
execution_authority = none
~~~

The witness proves the prerequisites were satisfied.

It does not itself perform the execution.

## Four executable specimens

~~~text
1. LEGACY
   stale cut-7 evidence at cut 8 -> REFUSED
   fresh cut-8 evidence          -> EXECUTED

2. REVALIDATION
   missing receipt               -> REFUSED
   mixed evidence types          -> REFUSED
   fresh compliant receipt       -> EXECUTED

3. MIGRATION
   old reservation               -> REFUSED
   released old + new E reservation
   + recomputed migration        -> EXECUTED

4. NO COMMON PATH
   any execution attempt         -> REFUSED
~~~

## Laws

~~~text
DECISION != ENFORCEMENT
STALE TEMPORAL INTERSECTION != CURRENT AUTHORITY
LEGACY PERMISSION MUST BE PROVEN AT EXECUTION TIME
REVALIDATION RECEIPT != MIGRATION RECEIPT
NO COMMON PATH != EXECUTION AUTHORITY
ENFORCEMENT MUST RECOMPUTE FROM SOURCE EVIDENCE
~~~

## Result

The adaptive stack now has a real control boundary:

~~~text
policy
-> version
-> transition
-> multi-policy temporal intersection
-> fresh execution gate
-> owner-local execution
~~~

The reasoning layer can no longer be bypassed by holding an old reservation or
an old decision.

## Next aperture

058 proves the gate against one execution attempt.

The next useful pressure test is:

~~~text
059 — Long-Running Execution / Checkpoint Revalidation
~~~

A job may begin under valid authority and remain active across later policy
changes.

That creates a new temporal problem:

~~~text
execution start != execution lifetime
start authorization != perpetual authorization
checkpoint != restart
policy change during execution != automatic rollback
revocation boundary != history erasure
partial work != completed service
~~~

A long-running job could emit bounded execution checkpoints and require current
temporal evidence before crossing selected continuation boundaries.

That should preserve:

~~~text
START AUTHORITY != CONTINUATION AUTHORITY
CHECKPOINT REVALIDATION != REEXECUTION
PAUSE != FAILURE
STOP != HISTORY REWRITE
PARTIAL RESULT != SETTLEMENT
CONTINUATION MUST REMAIN OWNER-LOCAL
~~~

That would extend adaptivity from "before execution" into work that is already
alive.
