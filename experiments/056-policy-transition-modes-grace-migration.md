# Experiment 056 — Policy Transition Modes / Grace / Migration

## Question

Can a policy version change how enforcement attaches to already-existing work
without changing the policy content itself, rewriting history, or granting the
policy issuer control over remote resources?

## Transition is a separate artifact

056 introduces a signed temporal contract attached to one policy-version edge:

~~~text
policy v1
   |
   | transition declaration
   v
policy v2
~~~

The transition declaration names:

- previous policy version;
- current policy version;
- effective cut;
- transition mode;
- optional grace cut.

It explicitly carries:

~~~text
policy_content_changed = false
resource_owner_authority = none
reservation_authority = none
execution_authority = none
release_authority = none
~~~

Thus:

> **TRANSITION MODE != POLICY CONTENT**

The policy still says what is allowed.

The transition only says when the newer rule begins governing existing work.

## Five transition modes

056 proves five bounded modes:

~~~text
IMMEDIATE_REVALIDATION
GRACE_UNTIL_CUT
FINISH_IN_FLIGHT_ONLY
NEW_WORK_ONLY
MIGRATE_BEFORE_EXECUTION
~~~

All five operate over the same immutable v1 reservation history.

## Immediate revalidation

For:

~~~text
mode = IMMEDIATE_REVALIDATION
v2 effective cut = 7
~~~

the live v1 reservation evaluated at cut 7 yields:

~~~text
action = REVALIDATE_NOW
legacy_path_open = false
revalidation_required = true
~~~

No implicit grandfathering exists.

## Grace until a bounded cut

For:

~~~text
mode = GRACE_UNTIL_CUT
grace_until_cut = 8
~~~

the same reservation produces:

~~~text
cut 7:
  ALLOW_LEGACY_DURING_GRACE

cut 8:
  ALLOW_LEGACY_DURING_GRACE

cut 9:
  REVALIDATE_AFTER_GRACE
~~~

The artifact records the exact deferred-enforcement cut.

Thus:

> **GRACE != PERMANENT EXEMPTION**

and:

> **DEFERRED ENFORCEMENT != ABSENT ENFORCEMENT**

## Finish in flight only

The mode distinguishes work that actually started before v2 from work that was
merely reserved.

For a reservation with:

~~~text
authorized = cut 6
expires = cut 12
v2 effective = cut 7
~~~

if execution started at cut 6:

~~~text
cut 7:
  ALLOW_FINISH_IN_FLIGHT
~~~

If no execution had started:

~~~text
cut 7:
  BLOCK_NOT_IN_FLIGHT
  revalidation_required = true
~~~

Even legitimately in-flight work does not become immortal.

At cut 13, after the reservation's own expiry:

~~~text
legacy_path_open = false
revalidation_required = true
~~~

Thus:

> **IN-FLIGHT != UNBOUNDED GRANDFATHERING**

## New work only

This mode distinguishes work already authorized before v2 from work created
after v2 becomes effective.

For the old reservation:

~~~text
authorized = cut 6
v2 effective = cut 7

cut 7:
  ALLOW_PREEXISTING_RESERVATION
~~~

For a new reservation:

~~~text
authorized = cut 7

cut 7:
  CURRENT_POLICY_REQUIRED_FOR_NEW_WORK
~~~

The old reservation also loses the legacy path after its own expiry.

Thus NEW_WORK_ONLY is bounded by the actual preexisting authority object rather
than becoming a permanent exception for a participant.

## Migrate before execution

For:

~~~text
mode = MIGRATE_BEFORE_EXECUTION
~~~

the decision is:

~~~text
action = MIGRATION_REQUIRED
legacy_path_open = false
migration_required = true
~~~

The transition declaration itself cannot perform migration.

An attempted migration receipt before the old resource owner releases its
reservation is refused.

Only F may explicitly finalize:

~~~text
old F reservation
-> RELEASED
reason = TRANSITION_REQUIRES_MIGRATION
~~~

Then E independently creates a new reservation.

Only after those owner-local acts may 056 derive:

~~~text
old F reservation
+ F RELEASED finalization
+ distinct E reservation
+ current policy set
-> migration receipt
~~~

The migration receipt explicitly carries:

~~~text
old_history_rewritten = false
new_reservation_is_continuation = false
ownership_transfer = false
reservation_authority = none
execution_authority = none
~~~

Thus:

> **MIGRATION != HISTORY REWRITE**

The new E reservation is not a transformed F reservation.

They are distinct authority objects joined by evidence.

## Policy issuer is not resource owner

The transition is signed by the customer policy issuer.

The F release is signed by F's local steward.

The E reservation is created by E's local steward.

Those identities are deliberately distinct.

Therefore the policy issuer can define the temporal policy semantics without
gaining power to release F's capacity or reserve E's capacity.

Thus:

> **POLICY ISSUER != RESOURCE OWNER**

## Decision artifacts remain non-authoritative

Every derived transition decision contains:

~~~text
resource_owner_action_taken = false
reservation_rewritten = false
policy_content_changed = false
~~~

A decision may say:

~~~text
revalidate
allow bounded legacy path
finish in flight
require current policy
migrate
~~~

but it does not itself mutate the resource ledger.

## Laws

~~~text
TRANSITION MODE != POLICY CONTENT
GRACE != PERMANENT EXEMPTION
IN-FLIGHT != UNBOUNDED GRANDFATHERING
MIGRATION != HISTORY REWRITE
POLICY ISSUER != RESOURCE OWNER
DEFERRED ENFORCEMENT != ABSENT ENFORCEMENT
~~~

## Result

Policy adaptivity now has explicit temporal semantics:

~~~text
policy content:
  WHAT is permitted

policy version:
  WHICH immutable rule is current

transition mode:
  WHEN / HOW the new rule attaches to existing work

resource owner:
  WHETHER local capacity is actually released, reserved, or executed
~~~

Those concerns remain separate.

## Next aperture

056 declares one transition mode for one policy-version edge.

The next useful pressure test is:

~~~text
057 — Multi-Policy Transition Composition
~~~

Different sovereign policies may change at the same time with different
transition modes:

~~~text
customer:
  GRACE_UNTIL_CUT 10

promisor:
  IMMEDIATE_REVALIDATION

project:
  FINISH_IN_FLIGHT_ONLY
~~~

The route then needs a derived temporal intersection without letting the most
convenient mode erase a stricter requirement.

That should preserve:

~~~text
TRANSITION A != TRANSITION B
TEMPORAL INTERSECTION != MODE REWRITE
GRACE IN ONE POLICY != GRACE IN ALL POLICIES
ONE IMMEDIATE REQUIREMENT MAY CLOSE THE LEGACY PATH
NO COMMON TRANSITION PATH != PERMISSION TO INVENT ONE
TEMPORAL PROVENANCE MUST SURVIVE COMPOSITION
~~~

That would make adaptivity sovereign in both policy content and time.
