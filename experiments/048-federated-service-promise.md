# Experiment 048 — Federated Service Promise

## Question

Can one sovereign Guild make a customer-facing economic service promise while a
different sovereign Guild retains the actual operational capacity authority?

## Sovereign roles

048 separates three roles:

~~~text
Guild A = customer-facing promisor
Guild B = capacity holder / reservation steward
Customer = downstream economic counterparty
~~~

Guild A does not own or control Guild B's capacity.

Guild B does not become the customer-facing economic promisor.

This freezes:

> **PROMISOR != CAPACITY HOLDER**

## Remote capacity proof

Guild B begins with a signed Treasury containing:

~~~text
60 compute-minute
~~~

B publishes a separate signed remote-capacity proof naming:

- B's Treasury snapshot;
- exact capability entry;
- resource subject;
- native measure;
- observation cut;
- proof validity window;
- B's steward identity.

The proof explicitly carries:

~~~text
capacity_reserved = false
execution_authority_granted = false
ownership_transfer = false
~~~

The proof crosses to A through reLATTE:

~~~text
B-signed proof
-> RECEIVE
-> HOLD
-> explicit ADMIT
~~~

Only B may sign the crossing for B's proof.

Thus:

> **REMOTE CAPACITY PROOF != LOCAL AUTHORITY**

## A's customer promise

Guild A creates a 40-minute future-service offer to the customer.

A's promise references the exact B proof and B Treasury snapshot.

The promise names:

~~~text
A as promisor
B as capacity Guild
B's exact snapshot
B's exact resource entry
B's steward identity
40 compute-minute
~~~

but still says:

~~~text
capacity_reserved = false
local_execution_authority = false
ownership_transfer = false
~~~

A can therefore make an evidence-backed economic promise without pretending it
already controls B's machine.

## Customer acceptance

The customer accepts A's economic offer.

Acceptance still does not touch B's capacity.

Only after acceptance does A sign a subcontract request.

That request has:

~~~text
reservation_authority = none
ownership_transfer_requested = false
~~~

and crosses to B through:

~~~text
RECEIVE -> HOLD -> explicit ADMIT
~~~

The request asks B to consider reserving capacity.

It does not reserve capacity by itself.

## B-local reservation

A cannot reserve B's Treasury.

The simulation explicitly refuses A when A is supplied as the capacity steward.

Only B can convert the accepted request into:

~~~text
B-local resource proposal
-> B-local authorization
-> B-local reservation
-> B-signed subcontract grant
~~~

The proposal purpose is bound to:

~~~text
federated-subcontract:<request_id>
~~~

The grant crosses back to A as evidence.

It explicitly says:

~~~text
promisor_execution_authority = false
ownership_transfer = false
~~~

Thus:

> **SUBCONTRACT != OWNERSHIP TRANSFER**

## A cannot execute B's grant

Even after A receives the signed grant, A cannot execute the reserved capacity.

The authorization names B's executor.

An attempt by A to execute is refused.

Only B's named executor may consume the reservation.

## Successful remote execution

B's executor successfully performs the reserved 40-minute operation.

B's reservation becomes:

~~~text
CONSUMED
~~~

B then signs a subcontract completion binding:

- A's request;
- B's grant;
- B's reservation;
- exact execution receipt;
- finalization;
- performed measure.

The completion explicitly says:

~~~text
downstream_settlement_created = false
ownership_transfer = false
~~~

B's execution is therefore not automatically A's customer-facing settlement.

Thus:

> **UPSTREAM RESERVATION != DOWNSTREAM PERFORMANCE**

## Completion returns to A

B's signed completion crosses back to A.

Only after A verifies that remote completion may A create its own economic
performance attestation for the customer-facing obligation.

That A-side attestation uses:

~~~text
evidence_ref = B completion id
~~~

The customer separately performs their consideration obligation.

Only then does the downstream heterogeneous exchange become:

~~~text
SETTLED
~~~

## Federated settlement witness

048 derives one final linkage witness that independently verifies:

~~~text
B Treasury
-> B capacity proof
-> A promise
-> customer acceptance
-> A request
-> B proposal
-> B authorization
-> B reservation
-> B execution
-> B completion
-> A performance attestation
-> customer performance
-> downstream settlement
~~~

The witness explicitly carries:

~~~text
capacity_ownership_transferred = false
promisor_remote_execution_authority = false
payment_inferred_from_remote_execution = false
~~~

## Successor remote Treasury

B's successful 40-minute execution produces a successor B Treasury:

~~~text
60 - 40 = 20 compute-minute
~~~

The original remote proof remains immutable history against the old B snapshot.

It is refused if A tries to use it as backing against the successor snapshot.

Thus stale remote evidence does not silently follow capacity across Treasury
history.

## Remote failure path

B publishes a fresh proof of the successor 20-minute capacity.

A makes a fresh 20-minute customer promise.

The customer accepts.

B reserves the 20.

The remote execution then fails before consumption.

B's execution receipt says:

~~~text
success = false
consumed_measure = null
~~~

and the reservation finalizes:

~~~text
RELEASED
~~~

B signs a failure notice:

~~~text
capacity_released = true
downstream_performance_proven = false
~~~

That failure crosses back to A.

A cannot reinterpret it as successful remote completion.

Therefore A cannot create its customer-facing service-performance attestation.

Even if the customer already performed their own side, the downstream exchange
cannot settle.

The original promise remains unchanged history.

Thus:

> **DOWNSTREAM FAILURE MUST PROPAGATE WITHOUT HISTORY REWRITE**

## Capacity after failure

Because B's failed attempt consumed nothing:

~~~text
visible = 20
reserved = 0
unencumbered = 20
~~~

Capacity becomes available again while the failed attempt remains recorded.

## Crossing sovereignty

048 also verifies role-local transport signatures:

- B must cross B's proof;
- A must cross A's subcontract request;
- B must cross B's reservation grant;
- B must cross B's completion or failure;
- A must cross the final customer-facing federated witness.

A wrong-role crossing signature is refused.

## Laws

~~~text
PROMISOR != CAPACITY HOLDER
REMOTE CAPACITY PROOF != LOCAL AUTHORITY
SUBCONTRACT != OWNERSHIP TRANSFER
UPSTREAM RESERVATION != DOWNSTREAM PERFORMANCE
DOWNSTREAM FAILURE MUST PROPAGATE WITHOUT HISTORY REWRITE
~~~

## Result

The service fabric can now cross sovereign boundaries without pretending those
boundaries disappeared.

The successful path is:

~~~text
Customer
   |
   v
Guild A promise
   |
   v
A subcontract request
   |
   | sovereign crossing
   v
Guild B reservation
   |
   v
B execution
   |
   | signed completion crosses back
   v
Guild A performance evidence
   |
   v
Customer-facing settlement
~~~

Every layer retains its own authority.

## Next aperture

048 proves one customer promise backed by one remote sovereign capacity source.

The next composition is:

~~~text
049 — Multi-Source Federated Service
~~~

One service may require capacity from multiple sovereign providers:

~~~text
Guild B = 30 compute-minute
Guild C = 30 compute-minute

             \ /
              v

Guild A promises one 60-minute service
~~~

That would force exact rules for:

~~~text
ONE PROMISE MAY DEPEND ON MULTIPLE SOVEREIGN SOURCES
PARTIAL RESERVATION != FULL BACKING
PARTIAL COMPLETION != CUSTOMER PERFORMANCE
SOURCE FAILURE MAY RELEASE ONLY ITS OWN AUTHORITY
AGGREGATION != OWNERSHIP
ALL REQUIRED SUBCONTRACTS MUST COMPLETE BEFORE DOWNSTREAM PERFORMANCE
~~~

That would turn the sovereign service mesh into an actual compositional
resource network.
