# Experiment 047 — Capacity-Backed Future Service

## Question

Can verified operational capacity support a future economic service promise
without turning capacity proof into a guarantee, promise into reservation, or
resource consumption into payment?

## Close the loop from 046

047 does not begin with arbitrary compute.

The Guild first acquires:

~~~text
60 compute-minute
~~~

through a real 046-style heterogeneous settlement.

The upstream provider performs a compute-capacity-delivery obligation.

The Guild performs its own typed consideration obligation.

After bilateral settlement, the Guild separately admits the exact delivered
capacity into Treasury.

Thus the starting capability already has economic lineage.

## Two promises, one capacity source

The signed Treasury snapshot contains:

~~~text
60 compute-minute available
~~~

The Guild then creates two separate future-service offers:

~~~text
Promise A = future service using 40 compute-minute
Promise B = future service using 40 compute-minute
~~~

Both promises are individually valid because each points to a real signed
Treasury source that visibly contains 60.

Neither promise encumbers anything.

~~~text
capacity_encumbered = false
execution_authority_granted = false
performance_proven = false
~~~

Therefore both may coexist before reservation even though they cannot both
later reserve 40.

This freezes:

> **CAPACITY PROOF != PROMISE**

and:

> **PROMISE != RESERVATION**

## Promise must name its authority source

The promise binds:

~~~text
Treasury snapshot
exact capability entry
resource subject
service offer
service obligation
promised native measure
executor
offer validity
Guild steward
~~~

A promise whose Treasury subject, quantity, unit, or offer window does not
match the signed source fails verification.

The future service therefore names where its operational plausibility comes
from without pretending that plausibility is already authority.

> **FUTURE SERVICE OFFER MUST NAME ITS AUTHORITY SOURCE**

## Acceptance is not reservation

Customers A and B may each accept their respective economic offers.

Acceptance still does not encumber compute.

The operational commitment begins only when the Guild creates an exact
resource proposal and the 039 reservation store atomically reserves the
capacity.

The proposal purpose is bound to:

~~~text
service-promise:<promise_id>
~~~

so an unrelated reservation cannot later be relabeled as fulfillment of this
promise.

## Competing reservation

Customer A's accepted promise reserves:

~~~text
40 compute-minute
~~~

The live state becomes:

~~~text
visible       = 60
reserved      = 40
unencumbered  = 20
~~~

Customer B's independently valid 40-minute promise then attempts reservation.

It is refused.

The refusal does not invalidate the historical promise.

It means only that the promise never became an operational encumbrance.

This demonstrates why promise and reservation must remain separate.

## Successful path

The accepted A promise now has:

~~~text
economic acceptance
-> Guild resource proposal
-> bounded authorization
-> ACTIVE reservation
-> service encumbrance witness
~~~

The executor performs the service successfully.

The reservation finalizes:

~~~text
CONSUMED
~~~

Only then may the Guild create the 035 economic performance attestation for its
future-service obligation.

That attestation must point to the exact successful execution receipt.

The customer separately performs their typed consideration obligation.

Only after both performance attestations exist does the heterogeneous exchange
settle.

Thus:

> **RESERVATION != PERFORMANCE**

## Consumption is not payment

The resulting capacity-backed service settlement witness explicitly says:

~~~text
service_performed = true
payment_inferred = false
execution_authority = none
~~~

Consumption proves operational work happened.

It does not itself prove payment, create payment, or infer monetary transfer.

Thus:

> **PERFORMANCE != PAYMENT**

and the earlier law remains:

> **CONSUMPTION != PAYMENT**

## Successor Treasury

The successful 40-minute execution does not rewrite the old Treasury snapshot.

A successor snapshot carries:

~~~text
20 compute-minute available
~~~

The old B promise remains valid historical evidence against the original
snapshot, but cannot be treated as a promise against this successor state.

Its attempt to reserve using the new snapshot is refused as stale.

## Failure path

The Guild creates a fresh promise C against the successor 20-minute capacity.

C is accepted and successfully reserves all 20.

Execution then fails before consumption.

The execution receipt says:

~~~text
success = false
consumed_measure = null
~~~

and the reservation finalizes:

~~~text
RELEASED
~~~

The full 20 becomes unencumbered again.

Critically, the Guild cannot create successful service-performance evidence
from that failed execution.

Without the service-side performance attestation, the heterogeneous exchange
cannot settle even if the customer has already performed their own
consideration obligation.

Thus failure releases operational capacity without pretending successful
economic performance occurred.

## Portable witness

A successful capacity-backed service settlement may cross via reLATTE as audit
evidence.

The crossing requests no:

~~~text
automatic execution
payment inference
ownership transfer
~~~

Receiver semantics remain:

~~~text
RECEIVE -> HOLD -> explicit ADMIT
~~~

## Laws

~~~text
CAPACITY PROOF != PROMISE
PROMISE != RESERVATION
RESERVATION != PERFORMANCE
PERFORMANCE != PAYMENT
FUTURE SERVICE OFFER MUST NAME ITS AUTHORITY SOURCE
ECONOMIC COMMITMENT MAY ENCUMBER CAPACITY WITHOUT CONSUMING IT
~~~

## Result

The Lightwalker loop is now bidirectional:

~~~text
economic settlement
-> acquired operational capacity
-> Treasury
-> capacity-backed future promise
-> acceptance
-> reservation
-> actual service
-> bilateral settlement
~~~

The return path does not collapse the distinctions established on the way in.

## Next aperture

047 still uses one Guild as both economic offeror and reservation steward.

The next hard problem is delegation across sovereign boundaries:

~~~text
048 — Federated Service Promise
~~~

A Guild could economically promise a service whose actual capacity authority is
held by another Guild or sovereign node.

That would require proving:

~~~text
PROMISOR != CAPACITY OWNER
REMOTE CAPACITY PROOF != LOCAL AUTHORITY
SUBCONTRACT != OWNERSHIP TRANSFER
UPSTREAM RESERVATION != DOWNSTREAM PERFORMANCE
DOWNSTREAM FAILURE MUST PROPAGATE WITHOUT HISTORY REWRITE
ONE SERVICE PROMISE MAY DEPEND ON MULTIPLE SOVEREIGN CAPACITY SOURCES
~~~

That would move the system from one sovereign economic loop to a composable
service network.
