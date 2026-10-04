# Experiment 053 — Constraint-First Routing / Pareto Frontier

## Question

Can hard route requirements remain categorically different from preferences, so
an impermissible route cannot compensate for a violation with an excellent
score?

And after hard filtering, can the system preserve multiple non-dominated
tradeoffs instead of prematurely declaring one universal winner?

## Pipeline

053 inserts two stages before 052 scoring:

~~~text
signed route evidence
-> hard constraint evaluation
-> Pareto frontier
-> local preference scoring
-> owner-local admission
-> sovereign reroute / reservation
~~~

The order matters.

## Raw candidate field

The specimen has four failover candidates:

~~~text
D = extraordinary raw performance
E = faster, higher-energy tradeoff
F = slower, more reliable, lower-energy tradeoff
G = eligible but dominated
~~~

D is deliberately constructed to be irresistible to unconstrained scoring:

~~~text
latency = 1 ms
reliability = 1000000 ppm
energy = 1
completion = 1 cut
~~~

A normal latency-heavy 052 policy therefore selects D if all candidates are
treated as preference-eligible.

That establishes the pressure condition.

## Constraint evidence

A separate trusted compliance assessor signs evidence bound to each exact
remote capacity proof.

The attestation contains factual inputs only:

~~~text
jurisdiction
privacy class
renewable-evidence presence
sovereign group
~~~

It explicitly carries no eligibility, preference, or reservation authority.

Thus the evidence itself does not decide policy compliance.

## Hard constraint policy

Guild A signs a local hard-eligibility policy:

~~~text
allowed jurisdictions = zone:a, zone:b
minimum privacy class = 3
renewable evidence required = true
maximum completion window = 4 cuts
forbidden sovereign groups = group:forbidden
~~~

The policy also names the trusted route measurer and trusted compliance
assessor.

It explicitly carries:

~~~text
preference_authority = none
score_authority = none
reservation_authority = none
admission_authority = none
~~~

## D cannot buy its way back in

D's compliance evidence says:

~~~text
jurisdiction = zone:blocked
privacy class = 1
renewable evidence = false
~~~

D therefore receives:

~~~text
constraint_status = INELIGIBLE

failures:
- JURISDICTION_NOT_ALLOWED
- PRIVACY_CLASS_TOO_LOW
- RENEWABLE_EVIDENCE_REQUIRED

local_score = null
~~~

The important result is not that D receives a bad score.

D receives no preference score at all.

Thus:

> **INELIGIBLE != LOW SCORE**

No amount of latency, reliability, energy, or completion performance can offset
a failed hard requirement.

## Constraint evaluation has no winner

The constraint stage produces only:

~~~text
eligible
ineligible
~~~

It explicitly contains:

~~~text
winner = null
score_semantics = null
~~~

Thus:

> **CONSTRAINT != PREFERENCE**

Passing the hard gate means only that a route may be considered further.

It does not mean the route is preferred.

## Eligible set

After filtering:

~~~text
E = ELIGIBLE
F = ELIGIBLE
G = ELIGIBLE
D = INELIGIBLE
~~~

Now preference tradeoffs may begin.

## Pareto frontier

The frontier compares eligible candidates on four measured objectives:

~~~text
minimize latency
maximize reliability
minimize energy
minimize expected completion window
~~~

E and F trade strengths:

~~~text
E:
  latency = 15
  reliability = 980000
  energy = 60
  completion = 2

F:
  latency = 30
  reliability = 999000
  energy = 10
  completion = 3
~~~

Neither dominates the other.

E is faster.

F is more reliable and lower-energy.

G is worse than E across every Pareto objective and is therefore dominated.

The derived frontier becomes:

~~~text
frontier = {E, F}
dominated = {G}
winner = null
local_score = null
~~~

Thus:

> **PARETO FRONTIER != WINNER**

and:

> **TRADEOFF != COLLAPSE**

The frontier preserves the unresolved tradeoff rather than hiding it inside one
number.

## Local preference happens afterward

Only the Pareto survivors enter 052-style scoring.

A latency-heavy local profile selects:

~~~text
E
~~~

A reliability / energy-heavy local profile over the same frontier selects:

~~~text
F
~~~

Both are legitimate local interpretations of the same eligible tradeoff set.

Thus:

> **LOCAL POLICY != UNIVERSAL OPTIMUM**

## Owner-local authority remains after all of this

A chooses to act on the F recommendation.

F still performs an owner-local admission check:

~~~text
ADMITTABLE
reservation_created = false
~~~

Constraints, Pareto filtering, and scoring still create no reservation.

Only after:

~~~text
constraint evaluation
-> Pareto frontier
-> local scoring
-> owner admission
~~~

does the ordinary 050 reroute path begin.

F alone then creates its local substitute reservation.

## Signed linkage

053 derives a separate binding over:

~~~text
constraint evaluation
-> frontier
-> scoring policy
-> scored selection
-> 052 scored reroute binding
-> signed 050 reroute
~~~

The binding explicitly says:

~~~text
constraint_override_authority = none
value_authority = none
reservation_authority = none
execution_authority = none
~~~

The hard gate cannot be bypassed by a downstream preference score.

## Completion

C completes the original 30-minute source slot.

F completes the substitute 30-minute slot.

~~~text
C = 30
F = 30
----
service = 60
status = COMPLETE
~~~

The original customer promise remains unchanged and the downstream exchange
settles normally.

## Laws

~~~text
CONSTRAINT != PREFERENCE
INELIGIBLE != LOW SCORE
PARETO FRONTIER != WINNER
TRADEOFF != COLLAPSE
LOCAL POLICY != UNIVERSAL OPTIMUM
~~~

## Result

The route brain now has three distinct reasoning layers:

~~~text
1. MAY this route be considered?
   hard constraints

2. WHAT tradeoffs remain?
   Pareto frontier

3. WHICH tradeoff do I prefer here?
   local scoring policy
~~~

None of those layers owns the remote resource.

## Next aperture

053 still treats the hard policy as one A-local policy applied to one route
decision.

The next pressure test is:

~~~text
054 — Policy Composition / Constraint Intersection
~~~

A real crossing may need to satisfy several independent policies at once:

~~~text
customer policy
promisor policy
source policy
privacy policy
project policy
jurisdiction policy
~~~

The composition should preserve:

~~~text
POLICY A != POLICY B
INTERSECTION != POLICY REWRITE
CONFLICT != AUTOMATIC OVERRIDE
MORE RESTRICTIVE != MORE AUTHORITATIVE
NO SATISFYING ROUTE != PERMISSION TO RELAX CONSTRAINTS
POLICY PROVENANCE MUST SURVIVE COMPOSITION
~~~

That would let the service mesh reason about multiple sovereign requirements
without flattening them into one mysterious rulebook.
