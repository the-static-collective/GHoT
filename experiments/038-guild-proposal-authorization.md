# Experiment 038 — Guild Proposal / Treasury Authorization

## Question

Can a Guild possess real treasury capacity without that capacity silently
becoming permission to spend or execute?

## Flow

~~~text
signed treasury snapshot
        |
        v
resource proposal
        |
        v
Guild-local authorization
        |
        v
one bounded execution attempt
        |
        +--> EXECUTED
        |      |
        |      v
        |   resource reduced
        |
        +--> FAILED
               |
               v
        resource unchanged

both paths
        |
        v
signed execution receipt
        |
        v
new treasury snapshot
~~~

## Capacity is not authority

The initial snapshot contains:

~~~text
compute capacity = 120 compute-minute
storage capacity = 480 gb-hour
~~~

A worker may propose use of 30 compute-minutes.

The proposal is attributable and content-addressed, but carries:

~~~text
authority = proposal-only
~~~

An attempt to execute directly from that visible capacity without a Guild
authorization is refused.

Thus:

> **CAPACITY != SPENDING AUTHORITY**

## Proposal is not authorization

The proposal binds:

~~~text
snapshot_id
resource_entry_id
requested unit + quantity
purpose_ref
proposer
~~~

The Guild steward then separately signs a bounded authorization over that exact
proposal, resource, snapshot, executor, quantity, purpose, and expiry.

An outsider cannot produce a valid Guild authorization.

Changing the proposal after authorization invalidates the authorization.

Thus:

~~~text
PROPOSAL != AUTHORIZATION
AUTHORIZATION BINDS EXACT PROPOSAL
~~~

## Authorization is not execution

Authorization does not mutate the Treasury.

It creates one bounded permission:

~~~text
one_execution_attempt = true
~~~

The authorization is spent by the attempt, not by success.

That distinction prevents a failed operation from silently reusing old consent.

## Successful execution

The first authorized operation consumes:

~~~text
30 compute-minute
~~~

and emits a signed execution receipt with:

~~~text
status = EXECUTED
success = true
authorization_spent = true
consumed_measure = 30 compute-minute
~~~

The next treasury snapshot replaces the old 120-minute capability entry with a
new 90-minute capability entry and adds the execution receipt as evidence.

The prior snapshot remains immutable.

## Failed execution

A second proposal requests 20 compute-minutes from the new 90-minute snapshot.

It receives a fresh authorization and the execution attempt fails before
resource consumption.

The signed receipt says:

~~~text
status = FAILED
success = false
authorization_spent = true
consumed_measure = null
~~~

The authorization cannot be replayed.

The next treasury snapshot records the failure receipt but leaves compute
capacity at 90 minutes.

Thus:

> **EXECUTION != SUCCESS**

and:

> **FAILED EXECUTION != RESOURCE CONSUMPTION**

## Expiry

A separate authorization is allowed to expire.

Even though the Treasury still contains sufficient compute capacity, the old
authorization cannot be revived from capacity alone.

A fresh proposal/authorization path is required.

## Replay refusal

Both successful and failed execution authorizations are one-shot.

~~~text
ONE AUTHORIZATION -> AT MOST ONE EXECUTION ATTEMPT
~~~

The protocol therefore distinguishes:

~~~text
consent to one attempt
!=
permission until success
~~~

## Treasury lineage

The experiment produces:

~~~text
snapshot 0
  120 compute-minute
      |
      | successful authorized use of 30
      v
snapshot 1
  90 compute-minute
  + success receipt
      |
      | failed authorized attempt of 20
      v
snapshot 2
  90 compute-minute
  + success receipt
  + failure receipt
~~~

Every snapshot points backward to its predecessor. No old snapshot is edited.

## Laws

~~~text
CAPACITY != SPENDING AUTHORITY
PROPOSAL != AUTHORIZATION
AUTHORIZATION != EXECUTION
EXECUTION != SUCCESS
FAILED EXECUTION != RESOURCE CONSUMPTION
ONE AUTHORIZATION -> AT MOST ONE EXECUTION ATTEMPT
~~~

## Next aperture

038 creates a real sovereign spending boundary, but it exposes the next hard
problem: **competing authorizations against the same snapshot**.

Two individually valid proposals could each be within visible capacity while
their combined use would exceed it.

The next experiment should therefore test reservation / concurrency:

~~~text
treasury snapshot
   |
   +--> authorization A reserves 80
   |
   +--> authorization B requests 80
            |
            v
         REFUSED
~~~

or, after A expires/fails/releases its reservation:

~~~text
reserved capacity returns
-> new authorization may be issued
~~~

That would freeze:

~~~text
VISIBLE CAPACITY != UNENCUMBERED CAPACITY
AUTHORIZATION != RESERVATION
RESERVATION != CONSUMPTION
RELEASE != EXECUTION
~~~

and close the first real double-spend-style aperture in the Guild economy.
