# Experiment 039 — Reservation / Concurrency

## Question

Can a Guild safely authorize scarce shared capacity when multiple proposals race
against the same visible treasury snapshot?

## Core distinction

A Treasury may visibly contain:

~~~text
120 compute-minute
~~~

but once 80 are reserved, the immediately authorizable capacity is:

~~~text
visible      = 120
reserved     = 80
unencumbered = 40
~~~

Thus:

> **VISIBLE CAPACITY != UNENCUMBERED CAPACITY**

## Atomic reservation

Reservation creation is serialized under a steward-local file lock.

Two proposals each request 80 compute-minutes from the same 120-minute snapshot.

They race concurrently.

Exactly one may produce:

~~~text
authorization
+
ACTIVE reservation
~~~

The other must fail because only 40 remain unencumbered.

The Treasury snapshot itself is not edited merely because capacity was
reserved.

## Authorization is not reservation

Experiment 038 created the bounded authorization object.

039 adds a distinct reservation object binding:

~~~text
snapshot_id
proposal_id
authorization_id
resource_entry_id
reserved native measure
steward
expiry
~~~

These are separate facts:

~~~text
AUTHORIZATION != RESERVATION
~~~

Authorization says a specific operation is permitted.

Reservation says scarce Guild capacity has been encumbered so competing
authorizations cannot claim the same capacity.

## Release

A reservation may be released before execution.

Release produces a new signed finalization record:

~~~text
status = RELEASED
reason = GUILD_CANCELLED_BEFORE_EXECUTION
released_measure = 80 compute-minute
consumed_measure = null
~~~

The original ACTIVE reservation remains immutable.

Once released, the old reservation may not be used for reserved execution.

Thus:

~~~text
RELEASE != EXECUTION
RELEASED RESERVATION INVALIDATES RESERVED EXECUTION
~~~

## Successful execution

After release, the proposal that lost the original race can receive a fresh
authorization and reservation.

Its execution succeeds.

The finalization then says:

~~~text
status = CONSUMED
consumed_measure = 80 compute-minute
released_measure = null
~~~

Only after the signed successful execution receipt is applied does the next
Treasury snapshot reduce capacity:

~~~text
120 -> 40 compute-minute
~~~

Thus:

> **RESERVATION != CONSUMPTION**

## Expiry

A 30-minute reservation on the 40-minute successor snapshot is allowed to
expire.

Expiry generates:

~~~text
status = RELEASED
reason = AUTHORIZATION_EXPIRED
~~~

No execution occurred and no Treasury capacity was consumed.

## Failure

A fresh 30-minute reservation is then executed and fails before resource
consumption.

Experiment 038 already requires:

~~~text
authorization_spent = true
consumed_measure = null
~~~

039 additionally finalizes the reservation as:

~~~text
status = RELEASED
reason = EXECUTION_FAILED
~~~

The failure receipt enters Treasury history, but available compute remains 40.

A subsequent proposal against the new snapshot can reserve that capacity again.

## Stale-history discipline

After an execution receipt changes Treasury history, recovery proposals are
made against the new Treasury snapshot rather than silently continuing from the
older evidence head.

This keeps resource authorization tied to an explicit historical cut.

## Laws

~~~text
VISIBLE CAPACITY != UNENCUMBERED CAPACITY
AUTHORIZATION != RESERVATION
RESERVATION != CONSUMPTION
RELEASE != EXECUTION
RELEASED RESERVATION INVALIDATES RESERVED EXECUTION
ACTIVE RESERVATIONS MAY NOT EXCEED VISIBLE CAPACITY
~~~

## Result

The Guild economic stack can now distinguish:

~~~text
capacity
-> proposal
-> authorization
-> reservation
-> execution attempt
-> success/failure
-> consumption/release
-> new Treasury history
~~~

without treating any neighboring state as equivalent.

## Next aperture

The next problem is distributed reservation authority.

039 is safe inside one steward-local reservation ledger. The next serious test
is whether two Guild nodes can coordinate reservations without a hidden central
lock.

That suggests:

~~~text
040 — Distributed Reservation / Lease

node A sees snapshot S
node B sees snapshot S

A reserves capacity
B has not heard yet

Can reLATTE + Tranch-style local history prevent or safely reconcile
conflicting reservations?
~~~

The target laws become:

~~~text
LOCAL KNOWLEDGE != GLOBAL KNOWLEDGE
RESERVATION CLAIM != CONSENSUS
CONFLICT != SILENT OVERCOMMIT
RECONCILIATION != HISTORY REWRITE
~~~
