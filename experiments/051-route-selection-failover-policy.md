# Experiment 051 — Route Selection / Failover Policy

## Question

Can a service mesh choose a next route automatically from signed evidence
without turning routing policy into reservation authority, execution authority,
or a guarantee that the selected source will admit the work?

## Starting service

The customer-facing promise remains the same immutable 60-minute service from
the 049–050 line.

Its original source slots are:

~~~text
Guild B = 30 compute-minute
Guild C = 30 compute-minute
~~~

The route policy is attached to B's 30-minute source slot.

## Signed route policy

Guild A signs a bounded policy:

~~~text
preferred / failover order:
1. Guild B
2. Guild D
3. Guild E

required capability = render.verified
required slot measure = 30 compute-minute
maximum proof age = 4 cuts
maximum failover hops = 2
~~~

The policy explicitly carries:

~~~text
reservation_authority = none
execution_authority = none
ownership_authority = none
~~~

Thus:

> **POLICY != AUTHORITY**

## Evidence-backed selection

A route candidate must provide:

- a signed remote Treasury snapshot;
- a valid remote-capacity proof;
- the correct native unit;
- at least the required source-slot quantity;
- the required capability tag;
- a proof inside the policy freshness window;
- a Guild explicitly named in the ordered route policy.

The selector recomputes the candidate set deterministically.

A selection receipt contains:

~~~text
authority = derived-routing-recommendation-only
reservation_authority = none
execution_authority = none
owner_admission_required = true
~~~

It is a recommendation over verified evidence.

Thus:

> **SOURCE SELECTION MUST REMAIN EVIDENCE-BACKED**

## Original route fails

Guild B's original reserved route executes and fails before consumption.

B's reservation becomes:

~~~text
RELEASED
~~~

B is excluded from the next selection because its route has already failed.

## First failover: D

At evaluation cut 5, D has a valid proof:

~~~text
visible proof = 60 compute-minute
capability = render.verified
proof age = 1 cut
~~~

The deterministic policy therefore correctly selects:

~~~text
Guild D
~~~

This is not a bug.

The proof truthfully says D's signed Treasury snapshot contained sufficient
capacity.

## Proof state is not owner-local availability

After D published that proof, D independently reserved all 60 minutes for
unrelated local work.

The signed proof remains valid history.

The current owner-local reservation state is now:

~~~text
visible = 60
reserved = 60
unencumbered = 0
~~~

D evaluates the selection locally and signs:

~~~text
disposition = REFUSED
reason = INSUFFICIENT_UNENCUMBERED_CAPACITY
reservation_created = false
execution_authority_granted = false
~~~

The selection was evidence-backed and correct under the policy.

It was still not a guarantee.

Thus:

> **FAILOVER ORDER != GUARANTEE**

and:

> **RECOMMENDATION != RESERVATION**

## Owner-local admission remains sovereign

A tries to turn the D selection into a reroute despite D's refusal.

The operation is refused.

The routing layer therefore cannot convert a recommendation into remote
authority.

D's local admission response must be:

~~~text
ADMITTABLE
~~~

before a policy-bound reroute may proceed.

Even ADMITTABLE still does not reserve anything.

Thus:

> **AUTOMATIC ROUTING MAY NOT ERASE OWNER-LOCAL ADMISSION**

## Second failover: E

A reruns the same signed policy while excluding:

~~~text
B = failed original route
D = owner-local refusal
~~~

The second bounded policy selection becomes:

~~~text
Guild E
failover_index = 2
~~~

E's signed proof satisfies the same evidence constraints.

E evaluates its owner-local state:

~~~text
visible = 60
reserved = 0
unencumbered = 60
~~~

and signs:

~~~text
disposition = ADMITTABLE
reservation_created = false
~~~

The separation still holds:

~~~text
policy selection
!=
owner admission
!=
reservation
~~~

## Policy-bound reroute

Only after all three layers exist:

~~~text
signed policy
derived verified selection
signed owner-local ADMITTABLE response
~~~

may A construct the ordinary 050 reroute to E.

The original signed 050 reroute remains untouched.

051 produces a separate derived linkage witness:

~~~text
policy
-> selection
-> owner admission
-> reroute
~~~

This avoids mutating or invalidating the signed reroute artifact.

The binding itself carries:

~~~text
reservation_authority = none
execution_authority = none
~~~

## Real reservation still happens later

After the policy-bound reroute exists, E has still reserved nothing.

The E owner-local state remains:

~~~text
reserved = 0
~~~

A then sends the normal 050 substitute request.

Only E's steward may create:

~~~text
E-local proposal
-> E-local authorization
-> E-local reservation
~~~

The policy layer never receives that authority.

## Completion

C completes its original 30-minute source slot.

E completes the substituted 30-minute B slot.

The final rerouted service becomes:

~~~text
C original completion = 30
E substitute completion = 30
performed = 60
status = COMPLETE
~~~

A may then prove customer-facing performance and the downstream exchange may
settle.

The original customer promise remains unchanged.

## Bounded failover depth

The policy allows at most two failover selections.

After:

~~~text
selection 1 = D
selection 2 = E
~~~

a third selection attempt is refused.

Thus policy recursion is bounded rather than silently open-ended.

## Laws

~~~text
POLICY != AUTHORITY
RECOMMENDATION != RESERVATION
FAILOVER ORDER != GUARANTEE
SOURCE SELECTION MUST REMAIN EVIDENCE-BACKED
AUTOMATIC ROUTING MAY NOT ERASE OWNER-LOCAL ADMISSION
~~~

## Result

The service mesh now has a bounded automatic routing layer:

~~~text
B fails
  |
  v
policy selects D
  |
  v
D owner-local refusal
  |
  v
policy selects E
  |
  v
E owner-local admission
  |
  v
normal sovereign reroute + reservation
  |
  v
completion
~~~

Selection can be automatic.

Authority remains local.

## Next aperture

051 chooses one candidate at a time from a static preference order.

The next useful pressure test is:

~~~text
052 — Route Scoring / Multi-Factor Selection
~~~

Candidate ordering could be derived from multiple non-authoritative evidence
dimensions:

~~~text
proof freshness
available native quantity
latency receipt
energy cost
reliability history
privacy / locality requirement
sovereign diversity
expected completion window
~~~

while preserving:

~~~text
SCORE != VALUE
SCORE != AUTHORITY
MEASUREMENT != PREFERENCE
PREFERENCE != ADMISSION
LOWER COST != UNIVERSALLY BETTER
POLICY WEIGHTS ARE LOCAL
~~~

That would let the routing mesh make richer decisions without smuggling one
global optimization function into the protocol.
