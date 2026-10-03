# Activation Tickets

Experiment 028 adds one-operation destination activation after 027 launch preflight.

Core sequence:

```text
typed launch descriptor
    ↓
destination preflight = READY
    ↓
explicit local ACT
    ↓
short-lived signed activation ticket
    ↓
atomic one-time claim
    ↓
destination preflight AGAIN
    ↓
one owning-subsystem operation attempt
    ↓
signed execution receipt
```

## READINESS is not consent

027 may return a READY preflight and an inert invocation proposal.

That still authorizes nothing.

028 only issues a ticket when the local operator explicitly invokes:

```bash
python3 ghot/activation_ticket.py issue \
  launch.json \
  --confirm ACT
```

The consent phrase is exactly `ACT`.

Anything else is refused.

## What a ticket binds

`ghot.activation.ticket/v0` binds:

```text
exact launch descriptor
descriptor content address
exact READY proposal address
destination app / owner / operation
issued time
short TTL
one_operation = true
explicit-local-ACT consent mode
BODY signer particular
```

The default TTL is 120 seconds and the maximum is 600 seconds.

The ticket contains the exact descriptor so execution-time revalidation does not depend on mutable shell state.

## BODY signature is not human identity

The local BODY signs the activation ticket as durable evidence that this local ticket artifact was issued through the bounded activation path.

It does not prove which human acted.

The ticket explicitly records:

```text
human_identity_proven = false
```

```text
BODY SIGNATURE != HUMAN IDENTITY
```

## One ticket means one operation attempt

Execution is separate:

```bash
python3 ghot/activation_ticket.py execute <ticket-id>
```

Before revalidation or action, 028 atomically creates a one-use claim with exclusive file creation.

If a claim already exists:

```text
execute -> REFUSE
```

This makes replay fail closed.

## Execution revalidates again

After the ticket is claimed, the destination runs the full 027 preflight again.

If current state is no longer READY:

```text
receipt.status = REFUSED_STALE
ticket_spent = true
operation_attempted = false
```

If READY returns a different invocation proposal from the one originally consented to:

```text
receipt.status = REFUSED_PROPOSAL_CHANGED
ticket_spent = true
operation_attempted = false
```

The old consent never silently follows a changed proposal.

## Exactly one owning-subsystem attempt

If execution-time preflight is still READY and the proposal address is unchanged, 028 dispatches exactly one operation to the app named by the descriptor.

Current bounded destinations are:

```text
composition-wants
merge-plugin-parcel
merge-contract-pantry
```

and only operations already declared in 027's route table are eligible.

## Execution is not success

If the owning operation throws after revalidation:

```text
receipt.status = FAILED
ticket_spent = true
operation_attempted = true
success = false
```

The same ticket cannot be retried.

A new attempt requires a new READY preflight and a new explicit ACT.

```text
EXECUTION != SUCCESS
FAILED EXECUTION != PRESERVED CONSENT
```

## Successful execution

On success:

```text
receipt.status = EXECUTED
ticket_spent = true
operation_attempted = true
success = true
```

The operation result is stored separately under `GHOT_HOME/activation-tickets/results/` and the receipt binds its content address.

## Signed execution receipt

`ghot.activation.execution-receipt/v0` binds:

```text
ticket id
launch id
destination
final status
started/completed timestamps
consented proposal address
execution-time preflight status
execution-time proposal address
result address or error
ticket_spent
operation_attempted
success
BODY signer
```

The signed receipt witnesses what happened at the execution boundary.

It does not convert failure into success or consent into general authority.

## Inspect a ticket

```bash
python3 ghot/activation_ticket.py show <ticket-id>
```

This shows:

```text
ticket
fresh?
spent?
claim
execution receipt
receipt verification
stored result
```

## Verify an exported ticket

```bash
python3 ghot/activation_ticket.py verify ticket.json
```

## Ticket lifetime

A ticket is unusable if its TTL expires before execution begins.

Once claimed, it is spent forever regardless of outcome.

```text
EXPIRED TICKET != AUTHORITY
SPENT TICKET != FUTURE CONSENT
```

## No session authority

028 does not create sessions, standing approvals, app-wide permission, remembered consent, or blanket shell authority.

Every effectful operation requires its own fresh path:

```text
descriptor
 -> READY preflight
 -> explicit ACT
 -> one ticket
 -> one attempt
```

## Laws

- READINESS != CONSENT
- CONSENT TICKET != BLANKET AUTHORITY
- ONE ACTION != SESSION AUTHORITY
- EXECUTION != SUCCESS
- BODY SIGNATURE != HUMAN IDENTITY
- TICKET ISSUANCE != EXECUTION
- SPENT TICKET != FUTURE CONSENT
- STALE REFUSAL != PRESERVED CONSENT
- FAILED EXECUTION != PRESERVED CONSENT
- CONSENTED PROPOSAL != CHANGED PROPOSAL
- ONE TICKET != RETRY AUTHORITY
