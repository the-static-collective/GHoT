# Experiment 037 — Guild Treasury

## Question

Can an old-Lightwalker Guild Treasury become a sovereign inventory of
heterogeneous capabilities, claims, obligations, rights, receipts, credits, and
money references without collapsing them into one universal balance?

## Answer shape

The treasury asks:

> **What can this Guild actually mobilize?**

before it asks:

> **How rich is this Guild?**

The protocol intentionally has no answer to the second question unless some
separate Realm or accounting system declares a conversion policy.

## Inventory specimen

The frozen 037 treasury contains:

~~~text
available compute capacity
available storage capacity
an incoming Labor Writ claim
an outgoing Labor Writ obligation
an artifact/access right
a heterogeneous settlement receipt
13 lumen of Realm-local credit
a 250 USD external money reference
an encumbered storage commitment
~~~

These are carried together in one signed Guild-local snapshot.

They are not cross-summed.

## Native units

The resource view exposes native buckets:

~~~text
compute-minute
gb-hour
lumen
USD
~~~

The protocol may aggregate entries only inside the same declared
category/position/unit bucket.

It explicitly returns:

~~~text
universal_total = null
collapse_status = REFUSED_BY_PROTOCOL
~~~

and a direct attempt to request a universal total raises a protocol refusal.

## Treasury entry law

Every entry records:

~~~text
category
position
subject_ref
source_ref
evidence_refs
optional native_measure
metadata
~~~

The entry is content-addressed.

Registration means only that the Guild has chosen to include the claim or
reference in its own inventory view.

Thus:

~~~text
INVENTORY != OWNERSHIP
REFERENCE != CUSTODY
~~~

## Signed snapshots

A treasury snapshot is Guild-steward signed and contains:

~~~text
guild_id
steward_particular
prior_snapshot_id
sequence
sorted entries
~~~

The old snapshot is immutable.

A later snapshot points to the prior snapshot rather than editing it.

## Dynamic claim transition

037 composes directly with Experiment 036.

At snapshot 0, an incoming Labor Writ exists as:

~~~text
category = claim
position = available
~~~

The Guild redeems the Writ. The issuer performs the bounded work and emits a
signed performance receipt.

Snapshot 1 then:

1. retires the live claim entry;
2. adds the terminal performance receipt as evidence;
3. leaves every unrelated capability, obligation, credit, right, and money
   reference untouched.

Snapshot 0 remains byte-for-byte unchanged.

## Hostile controls

The experiment requires refusal for:

- duplicate entries in one snapshot;
- an outsider attempting to transition the Guild treasury;
- retirement of an unknown entry;
- universal-value collapse.

The first three protect inventory integrity.

The fourth protects semantic integrity.

## Portable treasury view

The signed snapshot may cross to another sovereign receiver.

The crossing explicitly requests no:

~~~text
automatic balance mutation
automatic ownership inference
universal valuation
~~~

The destination performs:

~~~text
HOLD -> explicit local ADMIT
~~~

Admission means the destination accepted the snapshot as information.

It does not mean the destination agrees that the Guild owns every referenced
thing, controls every capability, or should value any two resources equally.

## Laws

~~~text
TREASURY != BALANCE
INVENTORY != OWNERSHIP
REFERENCE != CUSTODY
NATIVE UNIT != UNIVERSAL UNIT
RESOURCE VIEW != PRICE
SNAPSHOT != SETTLEMENT
~~~

## Why this matters

A conventional treasury often begins by reducing heterogeneous reality into a
single accounting denomination.

037 begins one layer earlier.

A Guild can know:

- what work it may call;
- what work it owes;
- what compute it can schedule;
- what storage it has committed;
- what rights it can exercise;
- what settlements it can prove;
- what credits a Realm recognizes;
- what outside money references exist;
- what remains unresolved.

Only later may some local policy choose to derive a financial statement.

That statement is a projection over the inventory, not the inventory itself.

## Next aperture

The old Lightwalker **Guild** is now close to becoming a real sovereign economic
actor.

The next experiment should test a **Guild Proposal / Treasury Authorization**
boundary:

~~~text
treasury snapshot
    ->
proposed use of specific resources
    ->
Guild-local authorization
    ->
bounded execution
    ->
new receipts
    ->
new treasury snapshot
~~~

That would prove:

~~~text
TREASURY CAPACITY != SPENDING AUTHORITY
PROPOSAL != AUTHORIZATION
AUTHORIZATION != EXECUTION
EXECUTION != SUCCESS
~~~

and turn the treasury from a passive inventory into a safe compositional
economic organ.
