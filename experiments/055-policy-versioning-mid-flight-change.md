# Experiment 055 — Policy Versioning / Mid-Flight Change

## Question

Can policy change after a route has already been admitted and reserved without
rewriting the past or accidentally grandfathering stale authority into the
future?

## Policy identity versus policy version

055 separates two concepts:

~~~text
policy lineage
!=
policy fragment
!=
policy version
~~~

The lineage is stable across revisions.

Each immutable fragment has its own content address.

Each signed policy version points to exactly one fragment.

For the customer policy:

~~~text
lineage = same
v1 fragment id != v2 fragment id
v1 version id  != v2 version id
~~~

Thus:

> **POLICY VERSION != POLICY IDENTITY**

## Version declarations

Version declarations are signed by the policy issuer.

They bind:

- stable policy lineage;
- immutable policy fragment;
- monotonically increasing version number;
- previous version id;
- declared cut;
- effective cut.

They explicitly carry:

~~~text
retroactive_rewrite = false
history_rewrite = false
automatic_authority_carry_forward = false
~~~

Thus:

> **NEW POLICY != RETROACTIVE REWRITE**

## V1 route

At cut 6 the active policy set contains:

~~~text
customer v1
promisor v1
project v1
~~~

Under that policy set, F survives:

~~~text
policy intersection
-> Pareto frontier
-> local preference
-> F selected
-> F ADMITTABLE
-> F reservation created
~~~

A derived versioned route binding records the exact active policy version ids
that governed the route.

The binding itself carries no authority.

## V2 arrives

Customer v2 becomes effective at cut 7.

It keeps the same stable customer-policy lineage but changes one immutable
constraint:

~~~text
v1 forbids:
  group:x

v2 forbids:
  group:x
  group:f
~~~

The active policy set now contains:

~~~text
customer v2
promisor v1
project v1
~~~

Customer v1 becomes superseded for future evaluation.

It is not deleted.

## Old admission remains history

After v2 becomes active, the original F artifacts still verify:

~~~text
old F admission = valid signed history
old F reservation = valid signed history
old v1 binding = unchanged
customer v1 = unchanged
customer v2 = unchanged
~~~

Nothing is rewritten to pretend F was never permitted under v1.

Thus:

> **REVALIDATION != HISTORY ERASURE**

and:

> **OLD ADMISSION != NEW COMPLIANCE**

The historical statement:

~~~text
F was admitted and reserved under v1
~~~

remains true.

The new question is different:

~~~text
May that still-live reservation execute under v2?
~~~

## Current-policy revalidation

055 derives a revalidation receipt from:

- previous active policy set;
- current active policy set;
- exact F reservation;
- exact prior policy-bound route binding;
- exact prior admission;
- current signed measurements;
- current signed policy evidence.

The v2 result for F is:

~~~text
status = NONCOMPLIANT
customer v2 = FAIL
failure = SOVEREIGN_GROUP_FORBIDDEN
future_execution_permitted = false
~~~

The receipt explicitly states:

~~~text
old_admission_rewritten = false
reservation_rewritten = false
history_erased = false
automatic_release = false
~~~

The revalidation result does not itself mutate the reservation.

## Execution gate

Two execution attempts are refused:

~~~text
live v1 reservation + no v2 revalidation
-> REFUSED

live v1 reservation + failing v2 revalidation
-> REFUSED
~~~

Thus:

> **RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2**

and:

> **POLICY CHANGE MAY REQUIRE REVALIDATION**

The reservation existed legitimately.

Its future use is no longer automatically legitimate.

## Release is still source-local

A failed policy revalidation does not silently cancel remote authority.

F's sovereign steward explicitly releases the reservation:

~~~text
reason = POLICY_V2_REVALIDATION_FAILED
status = RELEASED
~~~

Only then does F's local capacity become unencumbered again.

Thus policy evaluation remains separate from source-local resource mutation.

## Adaptive reroute under V2

The routing field is recomputed under the current policy versions.

Now:

~~~text
F = INELIGIBLE
E = ELIGIBLE
H = ELIGIBLE
~~~

E dominates H in the current frontier.

The new path becomes:

~~~text
customer v2 + promisor v1 + project v1
-> policy intersection
-> E
-> owner-local admission
-> new reroute
-> E-local reservation
-> E execution
~~~

A second versioned route binding records that E was created under the v2 active
policy set.

The service therefore adapts without mutating the v1 route history.

## Completion

The final service uses:

~~~text
C original completion = 30
E v2 substitute       = 30
                       ----
service                = 60
status                 = COMPLETE
~~~

The customer-facing promise remains unchanged.

The earlier F attempt remains visible as:

~~~text
v1-valid admission
v1-valid reservation
v2 NONCOMPLIANT revalidation
source-local RELEASED finalization
~~~

## Laws

~~~text
NEW POLICY != RETROACTIVE REWRITE
POLICY VERSION != POLICY IDENTITY
OLD ADMISSION != NEW COMPLIANCE
RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2
POLICY CHANGE MAY REQUIRE REVALIDATION
REVALIDATION != HISTORY ERASURE
~~~

## Result

The service mesh can now change rules while preserving time:

~~~text
past:
  judged under the policy actually active then

present:
  judged under the policy active now

future authority:
  must satisfy the current policy before use
~~~

That is the first real adaptive policy lifecycle.

## Next aperture

055 handles a stricter policy update that invalidates one live route.

The next pressure test is:

~~~text
056 — Policy Transition Modes / Grace / Migration
~~~

Not every policy change should necessarily have the same transition semantics.

A future version could explicitly declare one bounded transition mode:

~~~text
IMMEDIATE_REVALIDATION
GRACE_UNTIL_CUT
FINISH_IN_FLIGHT_ONLY
NEW_WORK_ONLY
MIGRATE_BEFORE_EXECUTION
~~~

while preserving:

~~~text
TRANSITION MODE != POLICY CONTENT
GRACE != PERMANENT EXEMPTION
IN-FLIGHT != UNBOUNDED GRANDFATHERING
MIGRATION != HISTORY REWRITE
POLICY ISSUER != RESOURCE OWNER
DEFERRED ENFORCEMENT != ABSENT ENFORCEMENT
~~~

That would turn policy adaptivity from one hard switch into an explicit,
auditable temporal contract.
