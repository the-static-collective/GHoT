# Experiment 060 — Resume / Migration of Paused Execution

## Question

Can a paused partial execution move onto a different sovereign resource without
restarting from zero, inheriting the old reservation, rewriting the old run, or
double-counting work already represented by the checkpoint?

## The source history

Guild F owns a 30 compute-minute reservation.

Its long-running execution reaches:

~~~text
checkpoint progress = 40%
partial result = partial:060-f-40
~~~

For an exactly divisible 30-unit source measure:

~~~text
30 * 40% = 12 compute-minutes
~~~

Those 12 units are represented by the checkpoint lineage.

When policy v3 makes F noncompliant, F preserves that checkpoint, pauses, and
explicitly stops/releases the old reservation.

The source history remains:

~~~text
F start
-> F checkpoint 40%
-> F pause
-> F stop
-> F reservation RELEASED
~~~

No source event is rewritten.

## Resume is a new run

060 does not reopen the F run.

Guild E must independently hold:

- its own treasury;
- its own proposal;
- its own authorization;
- its own reservation;
- its own current policy evidence;
- its own fresh execution gate.

The resume artifact links these new authority objects to the old checkpoint
lineage.

Thus:

> **RESUME != RESTART**

The new run begins at the checkpoint's total progress:

~~~text
prior progress = 40%
new work progress = 0%
total progress = 40%
~~~

It does not begin at zero.

## Partial state is not authority

The F checkpoint contributes:

~~~text
partial state
progress lineage
partial result reference
~~~

but carries:

~~~text
checkpoint_state_authority = none
~~~

E cannot execute merely because it possesses F's checkpoint.

E needs independent current authority.

Thus:

> **PARTIAL STATE != EXECUTION AUTHORITY**

## Exact remaining work

060 binds the checkpoint percentage to the original native work measure.

The source authorization is:

~~~text
30 compute-minutes
~~~

The source checkpoint is:

~~~text
40%
~~~

Therefore:

~~~text
prior work     = 12 compute-minutes
remaining work = 18 compute-minutes
~~~

E's new reservation must be exactly:

~~~text
18 compute-minutes
~~~

A fresh E reservation for the original 30 compute-minutes is deliberately
constructed.

Resume refuses it.

This prevents:

~~~text
12 prior units
+ 30 new units
= 42 units attributed to a 30-unit job
~~~

before a resumed run can even be created.

Thus:

> **RESUMED COMPLETION MAY NOT DOUBLE-COUNT PRIOR WORK**

## New resource authority is distinct

The valid E resume records:

~~~text
old reservation = F reservation
new reservation = E reservation

old reservation != new reservation
~~~

It explicitly carries:

~~~text
ownership_transfer = false
old_run_rewritten = false
~~~

The old F authority was released.

The new E authority was independently created.

Thus:

> **MIGRATED CONTINUATION != OWNERSHIP TRANSFER**

and:

> **OLD RUN != NEW RESOURCE AUTHORITY**

## Checkpoint lineage survives migration

The resume artifact binds:

~~~text
old run id
source checkpoint id
source pause id
source stop id
source partial result
prior progress
prior native work measure
remaining native work measure
~~~

Those references persist into resumed checkpoints and final completion.

E cannot present the resumed execution as though it independently generated the
first 40%.

Thus:

> **CHECKPOINT LINEAGE MUST SURVIVE MIGRATION**

## Resume still requires current policy

At cut 9, E is compliant under current v3.

Its new reservation passes a fresh transition-aware execution gate.

Only then is the resumed run created.

The checkpoint is not the gate.

The resume record binds:

~~~text
resume_execution_gate_id
resume_evidence_path
~~~

alongside the source checkpoint lineage.

## Adaptivity continues after resume

Resume does not create perpetual authority either.

At cut 10, before E may checkpoint at 70%, current policy is recomputed again.

The resumed checkpoint records:

~~~text
prior progress      = 40%
new work progress   = 30%
total progress      = 70%
prior work replayed = false
~~~

It also binds a fresh continuation gate.

Thus migration does not escape the 059 continuation model.

## Completion

At cut 11, E must pass another fresh current-policy gate before final execution.

The resumed completion binds:

~~~text
prior progress         = 40%
remaining work         = 60%
total progress         = 100%

source work measure    = 30 compute-minutes
prior work measure     = 12 compute-minutes
new work counted       = 18 compute-minutes
~~~

The arithmetic is therefore:

~~~text
12 prior
+18 new
-------
30 total
~~~

not:

~~~text
12 prior
+30 replayed
-------
42
~~~

The completion explicitly records:

~~~text
prior_work_reexecuted = false
prior_work_double_counted = false
ownership_transfer = false
old_run_rewritten = false
service_complete = true
settlement_authority = none
~~~

The new E reservation is consumed only once at completion.

## Completion is still not settlement

060 can prove that the resumed work reached 100%.

It does not infer payment, customer acceptance, or economic settlement.

Thus the completion retains:

~~~text
settlement_authority = none
~~~

Service evidence may later enter the economic settlement layer through the
existing explicit exchange path.

## Durable lineage

The full history is now:

~~~text
F reservation 30
  |
  v
F start
  |
  v
F checkpoint 40% / 12 units
  |
  v
F pause
  |
  v
F stop + RELEASE
  |
  | checkpoint lineage only
  v
E independent reservation 18
  |
  v
E RESUME at total 40%
  |
  v
E checkpoint total 70%
  |
  v
E completion total 100%
~~~

At no point does the old reservation become E's reservation.

At no point does the partial result become execution authority.

At no point is the first 40% counted again.

## Laws

~~~text
RESUME != RESTART
PARTIAL STATE != EXECUTION AUTHORITY
MIGRATED CONTINUATION != OWNERSHIP TRANSFER
OLD RUN != NEW RESOURCE AUTHORITY
CHECKPOINT LINEAGE MUST SURVIVE MIGRATION
RESUMED COMPLETION MAY NOT DOUBLE-COUNT PRIOR WORK
~~~

## Result

The execution layer can now preserve work across a sovereign resource change.

The three independent things remain separate:

~~~text
state lineage
authority lineage
work accounting
~~~

A checkpoint can move while authority does not.

New authority can arise while ownership does not transfer.

Completion can compose prior and new work without replaying either.

## Next aperture

060 permits one legitimate continuation from one stopped checkpoint.

The next pressure test is the obvious distributed race:

~~~text
061 — Resume Claim / Fork Prevention
~~~

What prevents the same 40% checkpoint from being resumed simultaneously by:

~~~text
E
and
G
~~~

both of which independently possess valid fresh resource authority?

The checkpoint itself cannot decide.

That should force:

~~~text
RESUMABLE STATE != MULTIPLE CONTINUATION AUTHORITY
ONE CHECKPOINT -> AT MOST ONE ACTIVE RESUME CLAIM
CLAIM != EXECUTION
LOSING CLAIM != HISTORY DELETION
FORK DETECTION != GLOBAL CONSENSUS
COMPLETION MUST NAME THE WINNING CONTINUATION LINEAGE
~~~

That would give resumed work the same anti-double-spend discipline already
developed for reservations and Labor Writs, without turning checkpoint state
into a currency.
