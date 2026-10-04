# Experiment 050 — Federated Reroute / Substitution

## Question

Can a failed or abandoned sovereign capacity source be replaced without
rewriting the original customer promise, double-counting old authority, or
erasing the failed route?

## Original promise

Guild A creates one immutable 60-minute customer-facing service promise backed
by:

~~~text
Guild B = 30 compute-minute
Guild C = 30 compute-minute
~~~

The promise object is frozen before any failure occurs.

Its content address must remain unchanged throughout the reroute.

## Original reservations

B and C independently reserve their 30-minute shares.

At this point the original 049 backing is complete:

~~~text
B = 30 reserved
C = 30 reserved
total = 60
~~~

No substitute source is yet active.

## Reroute before release is forbidden

A attempts to replace B while B's reservation is still live.

The reroute is refused.

A substitute may not count merely because A prefers another provider.

The original source authority must first stop counting through signed source
evidence.

Thus:

> **OLD AUTHORITY MUST STOP COUNTING BEFORE SUBSTITUTE AUTHORITY COUNTS**

## Actual source failure

B's named executor attempts the reserved work.

The execution fails before consumption:

~~~text
success = false
consumed_measure = null
~~~

B's reservation finalizes:

~~~text
RELEASED
~~~

B's 30-minute capacity becomes unencumbered again.

The failed B path remains permanent history.

## Reroute object

Only after the B release does A sign a reroute.

The reroute binds:

- original immutable promise;
- customer acceptance;
- exact original B source slot;
- original B grant;
- original B reservation;
- signed B release finalization;
- exact substitute D Treasury snapshot;
- exact D remote-capacity proof;
- exact replacement measure.

It explicitly records:

~~~text
original_route_status = RELEASED
promise_rewritten = false
ownership_transfer = false
old_authority_counts = false
substitute_reserved = false
~~~

Thus:

> **SOURCE SUBSTITUTION != PROMISE REWRITE**

and:

> **REROUTE REQUIRES NEW EVIDENCE**

## Substitute request and reservation

The reroute itself does not reserve D.

A separately sends a substitute request to D.

Only D's sovereign steward may create:

~~~text
D-local proposal
-> D-local authorization
-> D-local reservation
-> D-signed substitute grant
~~~

The grant is tied to the original B source slot but carries D's distinct local
authority.

No ownership moves from B to D or from either source to A.

## No double counting

Before D reserves, the rerouted backing view is:

~~~text
C original grant = 30
B original grant = retired by reroute
D substitute = pending

effective reserved = 30
status = PARTIAL
~~~

The old B grant is intentionally absent from the effective grant set.

After D reserves:

~~~text
C original grant = 30
D substitute grant = 30

effective reserved = 60
status = COMPLETE
~~~

B's old 30 does not reappear.

The system therefore never produces:

~~~text
B 30 + C 30 + D 30 = 90
~~~

from one 60-minute promise.

## Route history versus service semantics

The customer service remains:

~~~text
60 compute-minute
~~~

The route history changes from:

~~~text
B + C
~~~

to:

~~~text
B failed/released
C original
D substitute for B slot
~~~

The customer-facing service semantics do not change.

Thus:

> **ROUTE HISTORY != SERVICE SEMANTICS**

## Completion

C completes its original 30-minute share successfully.

At that point:

~~~text
performed = 30
status = PARTIAL
~~~

A is refused if it tries to claim customer-facing performance.

D then executes the substitute 30-minute route successfully.

D signs a substitute completion tied to:

- exact reroute;
- D substitute grant;
- D reservation;
- D execution receipt;
- D finalization.

The rerouted completion view becomes:

~~~text
C original completion = 30
D substitute completion = 30
performed = 60
status = COMPLETE
~~~

The original promise remains byte-for-byte unchanged.

Thus:

> **SUBSTITUTE COMPLETION MAY SATISFY THE SAME DECLARED SERVICE**

## Failed source is not failed service

B failed.

The overall customer service still succeeds because a later D route satisfies
the same source slot.

Therefore:

> **FAILED SOURCE != FAILED SERVICE**

This does not erase B's failure.

The service result and route history are different layers.

## Settlement

Only the complete rerouted aggregate may support A's economic performance
attestation.

The customer independently performs their consideration obligation.

The downstream heterogeneous exchange then settles.

The final witness explicitly carries:

~~~text
promise_rewritten = false
route_history_preserved = true
ownership_aggregated = false
payment_inferred_from_route_execution = false
~~~

## Source-local consequences

B's failed route consumed nothing.

Its capacity remains B-local and available:

~~~text
B visible = 60
B reserved = 0
B unencumbered = 60
~~~

D's successful substitute execution belongs only to D's operational history.

D does not consume B's capacity.

B's failed execution is never rewritten into D's success.

## Crossing behavior

The reroute, substitute request, substitute completion, and final settlement
witness may cross through reLATTE.

Every crossing requests no:

~~~text
promise rewrite
automatic reservation
automatic execution
ownership transfer
~~~

Receiver semantics remain:

~~~text
RECEIVE -> HOLD -> explicit ADMIT
~~~

## Laws

~~~text
SOURCE SUBSTITUTION != PROMISE REWRITE
FAILED SOURCE != FAILED SERVICE
REROUTE REQUIRES NEW EVIDENCE
OLD AUTHORITY MUST STOP COUNTING BEFORE SUBSTITUTE AUTHORITY COUNTS
SUBSTITUTE COMPLETION MAY SATISFY THE SAME DECLARED SERVICE
ROUTE HISTORY != SERVICE SEMANTICS
~~~

## Result

The sovereign service mesh now has a first fault-tolerant routing primitive.

~~~text
original:
A promise
  -> B 30
  -> C 30

failure:
B fails + releases

reroute:
B slot -> D 30

completion:
C 30 + D 30
-> same A promise fulfilled
~~~

No original customer promise is rewritten.

No failed source history disappears.

No old and substitute authority count simultaneously.

## Next aperture

050 handles one substitution after one source failure.

The next difficult step is route policy:

~~~text
051 — Route Selection / Failover Policy
~~~

Instead of A manually naming D after B fails, A could carry a bounded,
non-authoritative route policy such as:

~~~text
preferred: B
fallback: D
fallback: E
constraints:
  same native unit
  minimum quantity
  proof freshness
  sovereign diversity
  maximum hops
~~~

The policy could recommend or select a next route while preserving:

~~~text
POLICY != AUTHORITY
RECOMMENDATION != RESERVATION
FAILOVER ORDER != GUARANTEE
SOURCE SELECTION MUST REMAIN EVIDENCE-BACKED
AUTOMATIC ROUTING MAY NOT ERASE OWNER-LOCAL ADMISSION
~~~

That would turn reroute from a one-off recovery mechanism into a bounded
fault-tolerant routing layer.
