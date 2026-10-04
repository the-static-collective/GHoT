# Experiment 052 — Route Scoring / Multi-Factor Selection

## Question

Can routing preference be derived from multiple signed measurements without
turning a score into universal value, remote authority, or owner-local
admission?

## Separation of layers

052 introduces four distinct artifacts:

~~~text
signed route measurements
-> signed A-local scoring policy
-> derived scored selection
-> ordinary owner-local admission / 050 reroute
~~~

No layer is allowed to silently acquire the authority of the next.

## Signed measurements

A trusted route probe measures D and E.

The measurement artifact contains only raw evidence:

~~~text
latency_ms
reliability_ppm
energy_mwh_per_compute_minute
expected_completion_cuts
~~~

It is bound to the candidate's:

- signed Treasury snapshot;
- remote-capacity proof;
- resource entry;
- sovereign Guild;
- observation cut.

The artifact explicitly carries:

~~~text
score = null
preference_authority = none
reservation_authority = none
execution_authority = none
~~~

Thus:

> **MEASUREMENT != PREFERENCE**

The measurement issuer describes observed conditions.

It does not decide what A should prefer.

## Candidate evidence

At evaluation cut 5:

~~~text
Guild D
  proof age = 1 cut
  proven quantity = 60
  latency = 10 ms
  reliability = 970000 ppm
  energy = 80 mWh / compute-minute
  completion window = 2 cuts

Guild E
  proof age = 3 cuts
  proven quantity = 60
  latency = 35 ms
  reliability = 999000 ppm
  energy = 20 mWh / compute-minute
  completion window = 3 cuts
~~~

Both satisfy the base 051 evidence eligibility rules.

Neither is universally superior.

D is faster and fresher.

E is more reliable and uses less measured energy.

## Local scoring policy

Guild A creates two different signed local preference profiles over the exact
same evidence.

### Speed-first profile

~~~text
freshness = 10
quantity headroom = 0
reliability = 1
latency = 20
energy = 0
completion window = 0
~~~

The deterministic local scores are:

~~~text
D = 800
E = 309
~~~

Selection:

~~~text
Guild D
~~~

### Efficiency / reliability profile

~~~text
freshness = 1
quantity headroom = 0
reliability = 2
latency = 1
energy = 10
completion window = 1
~~~

The same measurements now produce:

~~~text
D = 1131
E = 1761
~~~

Selection:

~~~text
Guild E
~~~

Nothing about D or E changed.

Only A's local declared preference changed.

Thus:

> **POLICY WEIGHTS ARE LOCAL**

and:

> **LOWER COST != UNIVERSALLY BETTER**

E's lower energy measurement does not make E universally best.

D can still be the legitimate preference under a latency-heavy policy.

## Score semantics

A score is an integer used only to compare eligible candidates under one
specific local policy.

The scoring policy and selection both explicitly carry:

~~~text
score_semantics = local-comparison-only
value_authority = none
reservation_authority = none
execution_authority = none
~~~

Thus:

> **SCORE != VALUE**

The number 1761 is not:

- money;
- human worth;
- resource ownership;
- universal utility;
- a transferable balance;
- a claim that E is objectively better.

It is only the output of one declared local weighting function over one
candidate set.

## Score is not authority

The speed profile selects D.

D then performs an owner-local admission check and returns:

~~~text
ADMITTABLE
~~~

Even then:

~~~text
reservation_created = false
~~~

D's reservation ledger remains unchanged.

A may choose not to act on the D recommendation at all.

Thus:

> **SCORE != AUTHORITY**

and:

> **PREFERENCE != ADMISSION**

## Trusted measurement boundary

The scoring policy names the measurement issuer A trusts.

052 refuses:

- a route measurement whose signed content is tampered after issuance;
- otherwise well-formed evidence signed by an untrusted measurement identity.

Therefore candidate ranking is derived from explicitly trusted evidence rather
than arbitrary score-shaped input.

## Acting on the efficiency profile

A chooses to act on the efficiency/reliability profile's recommendation of E.

E separately performs owner-local admission:

~~~text
disposition = ADMITTABLE
reservation_created = false
~~~

Only after that may the existing 050 machinery create the reroute.

052 adds a separate derived binding:

~~~text
base route policy
-> local scoring policy
-> scored selection
-> owner-local admission response
-> signed 050 reroute
~~~

The signed 050 reroute itself is not modified.

## Reservation remains source-local

Even after scoring, selection, admission, and reroute:

~~~text
E reservation = none
~~~

The normal substitute request still has to cross to E.

Only E can create:

~~~text
E-local proposal
-> E-local authorization
-> E-local reservation
~~~

The routing brain never receives execution power.

## Completion

C completes its original 30-minute slot.

E completes the substituted 30-minute slot selected by the efficiency policy.

The same original customer service becomes:

~~~text
C original completion = 30
E substitute completion = 30
performed = 60
status = COMPLETE
~~~

The customer-facing exchange settles normally.

The original customer promise remains unchanged.

## Hostile controls

052 proves:

~~~text
tampered signed measurement -> REFUSED
untrusted measurement issuer -> REFUSED
score -> no reservation
ADMITTABLE -> still no reservation
different local weights -> different valid recommendation
~~~

## Laws

~~~text
SCORE != VALUE
SCORE != AUTHORITY
MEASUREMENT != PREFERENCE
PREFERENCE != ADMISSION
LOWER COST != UNIVERSALLY BETTER
POLICY WEIGHTS ARE LOCAL
~~~

## Result

The routing mesh now has a bounded local optimization layer without a global
optimizer.

~~~text
signed reality measurements
          |
          v
    A-local weights
       /       \
 speed profile  efficiency profile
      |               |
      D               E
~~~

Both recommendations can be valid interpretations of the same evidence.

Neither recommendation is authority.

## Next aperture

052 assumes every scoring dimension is commensurable enough to participate in
one local weighted expression.

The next useful pressure test is:

~~~text
053 — Constraint-First Routing / Pareto Frontier
~~~

Some requirements should not be traded away for a better score.

Examples:

~~~text
must remain in allowed jurisdiction
must satisfy privacy class
must avoid a named sovereign
must use renewable-energy evidence
must finish before deadline
must retain source diversity
~~~

Only candidates satisfying all hard constraints would enter a Pareto / scoring
stage.

That would preserve:

~~~text
CONSTRAINT != PREFERENCE
INELIGIBLE != LOW SCORE
PARETO FRONTIER != WINNER
TRADEOFF != COLLAPSE
LOCAL POLICY != UNIVERSAL OPTIMUM
~~~

and would let GHoT distinguish a route that is merely less preferred from one
that is not permitted at all.
