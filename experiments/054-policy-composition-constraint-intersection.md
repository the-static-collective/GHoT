# Experiment 054 — Policy Composition / Constraint Intersection

## Question

Can several independently signed route policies constrain the same service
without being rewritten into one opaque super-policy?

And when those policies conflict, can the system preserve the conflict instead
of inventing precedence or silently relaxing a requirement?

## Independent source policies

054 uses three separate policy issuers:

~~~text
customer
promisor
project
~~~

Each signs its own policy fragment.

Each fragment separately declares:

- target promise;
- target route policy and source slot;
- trusted constraint assessor;
- trusted route measurer;
- allowed jurisdictions;
- minimum privacy class;
- renewable-evidence requirement;
- completion deadline;
- forbidden sovereign groups;
- evidence freshness window.

Every policy explicitly carries:

~~~text
override_authority = none
rewrite_authority = none
relaxation_authority = none
reservation_authority = none
~~~

Thus:

> **POLICY A != POLICY B**

The fact that several policies govern one route does not turn them into one
authority.

## Composition is derived

The three successful specimen policies are:

~~~text
Customer
  jurisdictions = {zone:a, zone:b}
  privacy >= 3
  renewable = not required
  completion <= 4
  forbid = {group:x}

Promisor
  jurisdictions = {zone:b, zone:c}
  privacy >= 4
  renewable = required
  completion <= 5
  forbid = {}

Project
  jurisdictions = {zone:b}
  privacy >= 2
  renewable = not required
  completion <= 4
  forbid = {group:blocked}
~~~

The derived intersection summary is:

~~~text
jurisdictions = {zone:b}
privacy >= 4
renewable = required
completion <= 4
forbid = {group:x, group:blocked}
~~~

But this summary is not a rewritten policy.

The intersection artifact keeps every original:

~~~text
policy id
issuer
issuer role
policy name
original constraint body
trusted evidence roots
~~~

and explicitly records:

~~~text
source_policies_rewritten = false
override_authority = none
relaxation_authority = none
~~~

Thus:

> **INTERSECTION != POLICY REWRITE**

## Independent verdicts survive evaluation

Each candidate is evaluated separately against each original policy.

Guild D demonstrates why provenance matters.

D's facts satisfy the customer policy but not the other two:

~~~text
customer -> PASS
promisor -> FAIL
project  -> FAIL
~~~

The composed result is:

~~~text
D = INELIGIBLE
~~~

The evaluation retains all three policy verdicts rather than flattening them
into an unexplained rejection.

Thus:

> **POLICY PROVENANCE MUST SURVIVE COMPOSITION**

## More restrictive is not more authoritative

The project policy happens to permit only:

~~~text
zone:b
~~~

while the customer and promisor policies each allow two jurisdictions.

The project policy is therefore narrower on that dimension.

That does not make the project issuer higher authority.

All policies remain independent requirements in the intersection.

Thus:

> **MORE RESTRICTIVE != MORE AUTHORITATIVE**

## Successful satisfying set

After all three policies are applied:

~~~text
E = ELIGIBLE
F = ELIGIBLE
H = ELIGIBLE
D = INELIGIBLE
~~~

The composed evaluation has:

~~~text
result = SATISFYING_ROUTES
winner = null
~~~

Hard composition still does not choose a winner.

## Pareto tradeoffs remain downstream

H is dominated by E.

E and F remain non-dominated tradeoffs.

~~~text
frontier = {E, F}
dominated = {H}
winner = null
~~~

Only after policy intersection and Pareto filtering does A apply a local
reliability / energy preference.

That selects:

~~~text
F
~~~

The preference did not modify any source policy.

## Owner-local authority still remains separate

F is selected only after:

~~~text
3 signed policies
-> derived intersection
-> independent per-policy verdicts
-> Pareto frontier
-> local preference
~~~

F must still separately answer:

~~~text
ADMITTABLE
reservation_created = false
~~~

Only after that does the ordinary sovereign reroute and F-local reservation
occur.

The composed-policy binding explicitly carries:

~~~text
source_policies_rewritten = false
override_authority = none
relaxation_authority = none
reservation_authority = none
execution_authority = none
~~~

## Conflict specimen

054 also creates two individually valid policies:

~~~text
Customer policy:
  allowed jurisdictions = {zone:a}

Project policy:
  allowed jurisdictions = {zone:b}
~~~

Their jurisdiction intersection is empty.

The composition therefore produces:

~~~text
status = CONFLICT
static_conflicts =
  ALLOWED_JURISDICTIONS_DISJOINT
~~~

Candidate evaluation produces:

~~~text
result = NO_SATISFYING_ROUTE
eligible routes = {}
~~~

The system does not:

- choose one issuer as superior;
- relax either policy;
- invent an exception;
- score candidates anyway;
- turn a conflict into permission.

The frontier stage is refused.

Thus:

> **CONFLICT != AUTOMATIC OVERRIDE**

and:

> **NO SATISFYING ROUTE != PERMISSION TO RELAX CONSTRAINTS**

## Source policies remain immutable

The simulator serializes the customer, promisor, and project policies before
composition.

After intersection, scoring, reroute, execution, and settlement, each original
policy remains byte-for-byte unchanged.

The customer-facing promise also remains unchanged.

## Completion

The successful route uses:

~~~text
C original completion = 30
F substitute completion = 30
                         ----
service                  60
status                   COMPLETE
~~~

The downstream exchange settles normally.

The settlement does not erase the policy lineage that authorized the route to
be considered.

## Laws

~~~text
POLICY A != POLICY B
INTERSECTION != POLICY REWRITE
CONFLICT != AUTOMATIC OVERRIDE
MORE RESTRICTIVE != MORE AUTHORITATIVE
NO SATISFYING ROUTE != PERMISSION TO RELAX CONSTRAINTS
POLICY PROVENANCE MUST SURVIVE COMPOSITION
~~~

## Result

The route brain can now answer:

~~~text
What does the customer require?
What does the promisor require?
What does the project require?

Which routes satisfy ALL of them?
~~~

without pretending those questions came from one sovereign.

## Next aperture

054 composes hard policies at one moment.

The next pressure test is:

~~~text
055 — Policy Versioning / Mid-Flight Change
~~~

A policy may change while a route is already being considered or reserved.

That should force distinctions such as:

~~~text
NEW POLICY != RETROACTIVE REWRITE
POLICY VERSION != POLICY IDENTITY
OLD ADMISSION != NEW COMPLIANCE
RESERVATION UNDER V1 != AUTOMATIC AUTHORITY UNDER V2
POLICY CHANGE MAY REQUIRE REVALIDATION
REVALIDATION != HISTORY ERASURE
~~~

That would let the service mesh survive changing rules without pretending the
past occurred under today's policy.
