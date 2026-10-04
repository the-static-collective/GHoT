# Experiment 049 — Multi-Source Federated Service

## Question

Can one customer-facing service promise depend on multiple sovereign capacity
sources without turning partial reservation, partial completion, or aggregation
into full backing, full performance, or pooled ownership?

## Source plan

The specimen uses two sovereign capacity Guilds:

~~~text
Guild B = 60 compute-minute visible
Guild C = 60 compute-minute visible
~~~

Guild A promises one customer-facing service:

~~~text
60 compute-minute
~~~

The promise freezes an exact source plan:

~~~text
B share = 30
C share = 30
sum     = 60
~~~

The source plan must equal the promised native measure exactly.

A 20 + 20 plan for a 60-minute promise is refused.

Thus:

> **ONE PROMISE MAY DEPEND ON MULTIPLE SOVEREIGN SOURCES**

without allowing ambiguous under-backing.

## Promise semantics

The A-signed multi-source promise binds:

- the customer-facing offer;
- exact service obligation;
- exact remote source proofs;
- exact remote Treasury snapshots;
- one exact native share per source;
- source validity windows.

It explicitly starts with:

~~~text
sources_reserved = 0
full_backing_proven = false
local_execution_authority = false
ownership_aggregated = false
~~~

The source plan describes where backing may come from.

It does not reserve anything.

## Per-source requests

After customer acceptance, A emits one signed request per required source.

Each request names:

~~~text
promise
acceptance
source id
capacity Guild
remote proof
remote snapshot
resource entry
exact source share
~~~

The request carries:

~~~text
reservation_authority = none
ownership_transfer_requested = false
~~~

Each source may therefore accept or refuse independently.

## Partial reservation

Guild B reserves its 30-minute share first.

The derived backing view becomes:

~~~text
required = 60
reserved = 30
missing  = Guild C source
status   = PARTIAL
~~~

This state cannot become full backing.

Only after C separately creates its own 30-minute local reservation does the
derived backing view become:

~~~text
required = 60
reserved = 60
missing  = none
status   = COMPLETE
~~~

The aggregate carries:

~~~text
execution_authority = none
ownership_aggregated = false
~~~

Thus:

> **PARTIAL RESERVATION != FULL BACKING**

and:

> **AGGREGATION != OWNERSHIP**

## Independent sovereign authority

B's reservation remains B-local.

C's reservation remains C-local.

A does not receive one synthetic 60-minute execution authority.

A receives evidence that two distinct source reservations together cover the
promise.

The distinction is structural:

~~~text
coverage relation
!=
merged authority
~~~

## Partial completion

B executes successfully before C.

B signs one 30-minute source completion.

The derived completion state is:

~~~text
performed = 30
required  = 60
status    = PARTIAL
~~~

A is refused if it tries to turn this state into customer-facing performance.

Only after C independently completes its own 30-minute execution does the
aggregate become:

~~~text
performed = 60
required  = 60
status    = COMPLETE
~~~

A may then sign customer-facing performance evidence whose evidence reference
is the exact aggregate completion.

Thus:

> **PARTIAL COMPLETION != CUSTOMER PERFORMANCE**

and:

> **ALL REQUIRED SUBCONTRACTS MUST COMPLETE BEFORE DOWNSTREAM PERFORMANCE**

## Successful settlement

Once both sources complete:

~~~text
B completion 30
+
C completion 30
=
aggregate completion 60
~~~

A signs its customer-facing performance attestation.

The customer independently performs its own typed consideration obligation.

Only then does the heterogeneous exchange settle.

The final witness still states:

~~~text
source_ownership_aggregated = false
promisor_remote_execution_authority = false
payment_inferred_from_source_execution = false
~~~

## Source-local Treasury transitions

Successful execution changes each source independently.

After the first successful 60-minute service:

~~~text
Guild B: 60 -> 30
Guild C: 60 -> 30
~~~

There is no shared pooled Treasury state.

## Failure pressure test

A creates a second 60-minute promise using the successor states:

~~~text
B = 30
C = 30
~~~

Both source reservations succeed.

Execution then diverges:

~~~text
B executes 30 successfully
C fails before consuming 30
~~~

B's reservation becomes consumed.

C's reservation becomes released.

The aggregate completion becomes:

~~~text
performed = 30
failure   = C
status    = FAILED
~~~

A cannot create customer-facing performance evidence.

Even if the customer has performed their own consideration obligation, the
downstream exchange cannot settle.

## Failure remains source-local

B's successful 30 remains consumed.

C's failed 30 returns to C's unencumbered capacity.

Final source states are:

~~~text
Guild B remaining = 0
Guild C remaining = 30
~~~

The C failure does not roll B backward.

The B success does not consume C.

Thus:

> **SOURCE FAILURE RELEASES ONLY ITS OWN AUTHORITY**

and failure never rewrites sibling source history.

## Crossing behavior

Per-source requests may cross from A to each source.

Source grants, completions, and failures may cross back as role-local signed
evidence.

The final multi-source settlement witness may cross as audit evidence.

Every crossing requests no:

~~~text
automatic reservation
automatic execution
ownership aggregation
downstream performance inference
~~~

## Laws

~~~text
ONE PROMISE MAY DEPEND ON MULTIPLE SOVEREIGN SOURCES
PARTIAL RESERVATION != FULL BACKING
PARTIAL COMPLETION != CUSTOMER PERFORMANCE
SOURCE FAILURE RELEASES ONLY ITS OWN AUTHORITY
AGGREGATION != OWNERSHIP
ALL REQUIRED SUBCONTRACTS MUST COMPLETE BEFORE DOWNSTREAM PERFORMANCE
~~~

## Result

The service mesh can now compose capacity without composing sovereignty away.

~~~text
              Guild B 30
             /          \
Customer <- Guild A      aggregate -> performance
             \          /
              Guild C 30
~~~

The aggregate is a proof that all required relations completed.

It is not a new owner, Treasury, balance, lease, or executor.

## Next aperture

049 still freezes the source plan when the promise is created.

The next hard problem is dynamic recovery:

~~~text
050 — Federated Reroute / Substitution
~~~

If one source refuses or fails before performance, can A replace that source
with another sovereign provider without rewriting the original promise?

Target distinctions:

~~~text
SOURCE SUBSTITUTION != PROMISE REWRITE
FAILED SOURCE != FAILED SERVICE
REROUTE REQUIRES NEW EVIDENCE
OLD RESERVATION MUST BE RELEASED BEFORE SUBSTITUTE AUTHORITY COUNTS
SUBSTITUTE COMPLETION MAY SATISFY THE SAME DECLARED SERVICE
ROUTE HISTORY != SERVICE SEMANTICS
~~~

That would give the service mesh fault-tolerant routing while preserving every
failed and abandoned path as history.
