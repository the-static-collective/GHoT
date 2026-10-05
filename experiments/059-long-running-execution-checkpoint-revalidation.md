# Experiment 059 — Long-Running Execution / Checkpoint Revalidation

## Question

Can a job remain alive across policy changes without treating its original start
authority as perpetual execution authority?

A long-running execution needs to preserve partial work, re-check current policy
at selected continuation boundaries, and stop safely without rewriting the work
that already happened.

## Start is a distinct event

059 introduces an owner-local long-running execution record.

A run may start only from:

~~~text
valid reservation
+ authorized executor
+ fresh 058 execution gate
~~~

The start record binds:

- reservation;
- authorization;
- owner/steward;
- executor;
- start cut;
- start gate;
- start evidence path.

It begins at:

~~~text
status = RUNNING
progress = 0
service_complete = false
settlement_authority = none
~~~

Thus:

> **START AUTHORITY != CONTINUATION AUTHORITY**

The start gate proves only that work may begin at that boundary.

## Future rules may be known without being effective

The specimen predeclares:

~~~text
v2 at cut 6, effective cut 7
v3 at cut 7, effective cut 8
~~~

Therefore the run can know that a future rule is coming without applying it
before its effective cut.

At cut 6 the active policy remains v1.

That preserves:

~~~text
DECLARED FUTURE POLICY != CURRENT POLICY
~~~

without adding a new authority class.

## Start under V1

F has a 30 compute-minute reservation.

At cut 6:

~~~text
v1 is current
v2 is future-effective
temporal intersection = LEGACY_PATH_OPEN
~~~

F starts a long-running execution.

No Guild execution receipt is created yet.

The reservation remains active and fully encumbered.

## Cut-7 checkpoint

At cut 7, v2 becomes current.

Both active policy transitions require:

~~~text
IMMEDIATE_REVALIDATION
~~~

The temporal intersection therefore becomes:

~~~text
REVALIDATION_REQUIRED
~~~

Attempting to checkpoint using the original cut-6 start evidence is refused.

Thus:

> **START AUTHORITY != CONTINUATION AUTHORITY**

A fresh cut-7 revalidation is derived.

F is still compliant under v2:

~~~text
status = COMPLIANT
future_execution_permitted = true
~~~

The owner-local checkpoint then records:

~~~text
checkpoint index = 1
progress = 40%
partial result = partial:059-f-40
continuation evidence = CURRENT_REVALIDATION
service_complete = false
settlement_authority = none
underlying_execution_attempted = false
~~~

That last field matters.

The checkpoint did not replay or execute the underlying Guild authorization.

It only authorized continued long-running work at the checkpoint boundary.

Thus:

> **CHECKPOINT REVALIDATION != REEXECUTION**

The reservation remains active after the checkpoint.

## V3 changes the rule during execution

At cut 8, customer policy v3 becomes effective.

V3 newly forbids:

~~~text
sovereign group = group:f
~~~

The run already has:

~~~text
start at cut 6
valid checkpoint at cut 7
40% partial result
~~~

Those facts remain unchanged.

The new cut-8 revalidation yields:

~~~text
status = NONCOMPLIANT
failure = SOVEREIGN_GROUP_FORBIDDEN
future_execution_permitted = false
~~~

A proposed checkpoint at 70% is refused.

Critically, refusal does not roll the run backward.

After refusal, durable state still says:

~~~text
checkpoint count = 1
progress = 40%
partial result = partial:059-f-40
~~~

The nonexistent 70% result is never recorded.

## Pause is not failure

F's owner records a pause:

~~~text
reason = CURRENT_POLICY_REVALIDATION_FAILED
failure = false
service_complete = false
reservation_released = false
history_rewritten = false
~~~

The reservation remains encumbered.

The 40% checkpoint remains intact.

No settlement semantics arise from the partial result.

Thus:

> **PAUSE != FAILURE**

and:

> **PARTIAL RESULT != SETTLEMENT**

Attempting another checkpoint while the run is paused is refused.

## Stop is separate from pause

At cut 9, F's owner chooses to stop the run.

Stop performs an explicit owner-local reservation release.

The stop record binds:

~~~text
run
last valid checkpoint
40% partial result
reservation finalization
status = RELEASED
service_complete = false
failure = false
settlement_authority = none
history_rewritten = false
~~~

The stop does not delete:

- the start;
- checkpoint 1;
- the pause;
- the partial result;
- the policy-change evidence.

Thus:

> **STOP != HISTORY REWRITE**

After stop:

~~~text
run state = STOPPED
reservation = RELEASED
progress history = 40%
service complete = false
~~~

## Continuation remains owner-local

All lifecycle records are issued by the reservation owner.

The executor is named by the original authorization, but continuation state is
not allowed to become a free-floating executor power.

The owner controls:

~~~text
start
checkpoint acceptance
pause
stop
reservation release
~~~

while every continuation checkpoint still needs current policy evidence.

Thus:

> **CONTINUATION MUST REMAIN OWNER-LOCAL**

## Durable event history

059 stores immutable signed events separately from mutable current-state
projection:

~~~text
start event
checkpoint event
pause event
stop event

        ↓

current state projection
~~~

The projection may change from:

~~~text
RUNNING
-> PAUSED
-> STOPPED
~~~

but prior events remain immutable.

## Laws

~~~text
START AUTHORITY != CONTINUATION AUTHORITY
CHECKPOINT REVALIDATION != REEXECUTION
PAUSE != FAILURE
STOP != HISTORY REWRITE
PARTIAL RESULT != SETTLEMENT
CONTINUATION MUST REMAIN OWNER-LOCAL
~~~

## Result

The execution model is no longer atomic in time.

~~~text
START
  |
  | work
  v
CHECKPOINT 40%
  |
  | policy changes
  v
CONTINUATION REFUSED
  |
  v
PAUSE
  |
  v
OWNER STOP / RELEASE
~~~

The system preserves partial reality without pretending partial work is either
nothing or finished service.

## Next aperture

059 can preserve and stop a paused run.

The next useful pressure test is:

~~~text
060 — Resume / Migration of Paused Execution
~~~

A paused partial execution could continue on another sovereign resource without
rewriting the original run.

For example:

~~~text
F run
  checkpoint 40%
  pause
  release F reservation
       |
       v
E new reservation
  resume from checkpoint lineage
  continue 40% -> 100%
~~~

That should preserve:

~~~text
RESUME != RESTART
PARTIAL STATE != EXECUTION AUTHORITY
MIGRATED CONTINUATION != OWNERSHIP TRANSFER
OLD RUN != NEW RESOURCE AUTHORITY
CHECKPOINT LINEAGE MUST SURVIVE MIGRATION
RESUMED COMPLETION MAY NOT DOUBLE-COUNT PRIOR WORK
~~~

That would let adaptive execution move, not merely stop.
