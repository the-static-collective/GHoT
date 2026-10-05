# Experiment 057 — Multi-Policy Transition Composition

## Question

Can several sovereign policy transitions apply to the same live reservation at
the same time without flattening their temporal semantics into one rewritten
mode?

And when their allowed temporal paths do not intersect, can the system stop
rather than inventing a compromise?

## Independent temporal policies

057 composes separate transitions from:

~~~text
customer
promisor
project
~~~

Each source transition remains independently signed.

Each retains its own:

- policy lineage;
- previous policy version;
- current policy version;
- transition mode;
- issuer;
- individual transition decision.

Composition does not mutate any source transition.

Thus:

> **TRANSITION A != TRANSITION B**

## Temporal intersection

The composition artifact is derived from the individual 056 decisions.

It records full provenance:

~~~text
issuer role
issuer identity
policy lineage
previous policy version
current policy version
transition id
transition mode
individual decision id
individual action
individual legacy-path status
individual revalidation requirement
individual migration requirement
individual enforcement bound
~~~

The derived intersection explicitly carries:

~~~text
source_transitions_rewritten = false
mode_override_authority = none
relaxation_authority = none
reservation_authority = none
execution_authority = none
~~~

Thus:

> **TEMPORAL INTERSECTION != MODE REWRITE**

## Legacy execution requires unanimous permission

A legacy path remains open only if every active transition independently allows
that same old authority to continue.

This is not a vote.

One policy cannot donate its grace period to another policy.

## Mixed-mode specimen

At cut 7, the same v1 reservation is governed by:

~~~text
Customer:
  GRACE_UNTIL_CUT 10

Promisor:
  IMMEDIATE_REVALIDATION

Project:
  FINISH_IN_FLIGHT_ONLY
~~~

The work started at cut 6, before v2 became effective.

The individual decisions are:

~~~text
Customer:
  ALLOW_LEGACY_DURING_GRACE
  legacy_path_open = true

Promisor:
  REVALIDATE_NOW
  legacy_path_open = false

Project:
  ALLOW_FINISH_IN_FLIGHT
  legacy_path_open = true
~~~

The aggregate result is:

~~~text
result = COMMON_PATH
aggregate_action = REVALIDATION_REQUIRED
legacy_path_open = false
revalidation_required = true
~~~

The promisor transition is preserved as the blocking provenance.

Thus:

> **GRACE IN ONE POLICY != GRACE IN ALL POLICIES**

and:

> **ONE IMMEDIATE REQUIREMENT MAY CLOSE THE LEGACY PATH**

Customer grace remains real.

Project finish-in-flight permission remains real.

Neither can weaken the independent promisor requirement.

## Compatible legacy specimen

057 also composes:

~~~text
Customer:
  GRACE_UNTIL_CUT 10

Promisor:
  GRACE_UNTIL_CUT 8

Project:
  NEW_WORK_ONLY
~~~

The reservation was authorized before v2.

At cut 7 all three independently permit the legacy path.

The aggregate therefore becomes:

~~~text
aggregate_action = LEGACY_PATH_OPEN
legacy_path_open = true
~~~

But their temporal bounds differ.

The aggregate enforcement bound is:

~~~text
min(10, 8, reservation expiry 12)
= cut 8
~~~

So:

~~~text
cut 7:
  LEGACY_PATH_OPEN
  aggregate enforcement cut = 8

cut 9:
  REVALIDATION_REQUIRED
  legacy_path_open = false
~~~

The most permissive deadline does not win.

The common temporal path lasts only as long as every policy permits it.

## No common transition path

The conflict specimen combines:

~~~text
Customer:
  MIGRATE_BEFORE_EXECUTION

Project:
  FINISH_IN_FLIGHT_ONLY
~~~

But execution already started at cut 6, before v2 became effective at cut 7.

The project transition legitimately says:

~~~text
ALLOW_FINISH_IN_FLIGHT
~~~

The customer transition demands:

~~~text
MIGRATION_REQUIRED
before execution
~~~

That migration condition can no longer honestly be satisfied because execution
already began.

The derived result is:

~~~text
result = NO_COMMON_TRANSITION_PATH
aggregate_action = NO_COMMON_TRANSITION_PATH
legacy_path_open = false
revalidation_required = false
migration_required = false

conflict =
MIGRATION_BEFORE_EXECUTION_COLLIDES_WITH_ALREADY_STARTED_WORK
~~~

The composition artifact carries:

~~~text
mode_override_authority = none
relaxation_authority = none
~~~

It does not:

- reinterpret migration as post-start migration;
- reinterpret finish-in-flight as migration permission;
- choose one issuer as globally superior;
- invent a grace period;
- silently discard either transition.

Thus:

> **NO COMMON TRANSITION PATH != PERMISSION TO INVENT ONE**

## Temporal provenance survives composition

The aggregate result always preserves every individual transition and decision.

A downstream actor can determine:

~~~text
which policy allowed continuation
which policy blocked continuation
which policy required migration
which policy supplied a deadline
which source caused the aggregate path to close
~~~

without reconstructing that information from one collapsed mode.

Thus:

> **TEMPORAL PROVENANCE MUST SURVIVE COMPOSITION**

## Authority remains separate

057 changes no reservation state.

A temporal intersection can conclude:

~~~text
LEGACY_PATH_OPEN
REVALIDATION_REQUIRED
MIGRATION_REQUIRED
NO_COMMON_TRANSITION_PATH
~~~

but it cannot:

~~~text
release capacity
reserve capacity
execute work
rewrite policy
override transition mode
relax a conflict
~~~

Those remain separate sovereign actions.

## Laws

~~~text
TRANSITION A != TRANSITION B
TEMPORAL INTERSECTION != MODE REWRITE
GRACE IN ONE POLICY != GRACE IN ALL POLICIES
ONE IMMEDIATE REQUIREMENT MAY CLOSE THE LEGACY PATH
NO COMMON TRANSITION PATH != PERMISSION TO INVENT ONE
TEMPORAL PROVENANCE MUST SURVIVE COMPOSITION
~~~

## Result

The adaptive policy stack can now reason across both content and time:

~~~text
independent policy contents
          ↓
hard policy intersection
          ↓
independent policy versions
          ↓
independent transition modes
          ↓
temporal intersection
          ↓
current common path, if one exists
~~~

No single sovereign's transition semantics silently become everyone else's.

## Next aperture

057 composes temporal requirements for one live reservation.

The next useful pressure test is:

~~~text
058 — Transition-Aware Execution Gate / Durable Enforcement
~~~

The derived temporal intersection should become a mandatory execution input.

Execution would then require one of a bounded set of evidence paths:

~~~text
LEGACY_PATH_OPEN
  -> prove current temporal intersection still permits legacy execution

REVALIDATION_REQUIRED
  -> provide valid current revalidation

MIGRATION_REQUIRED
  -> provide valid migration receipt + current reservation

NO_COMMON_TRANSITION_PATH
  -> execution impossible
~~~

That should preserve:

~~~text
DECISION != ENFORCEMENT
STALE TEMPORAL INTERSECTION != CURRENT AUTHORITY
LEGACY PERMISSION MUST BE PROVEN AT EXECUTION TIME
REVALIDATION RECEIPT != MIGRATION RECEIPT
NO COMMON PATH != EXECUTION AUTHORITY
ENFORCEMENT MUST RECOMPUTE FROM SOURCE EVIDENCE
~~~

That would convert the temporal reasoning layer into an actual execution
boundary.
