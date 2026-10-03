# Experiment 028 — One-Operation Activation Tickets

## Question

Can one explicitly selected 027 launch become exactly one short-lived executable attempt without creating blanket/session authority, while forcing destination revalidation immediately before the operation and signing every final outcome?

## Deterministic proof

```bash
python3 ghot/activation_ticket_sim.py
```

## Trial A — explicit ACT

Create a READY `request-candidate` launch.

Attempt ticket issuance with a different confirmation phrase.

Expected: refusal.

Issue with exact `ACT`.

Expected:

- ticket signature verifies;
- ticket is fresh;
- one_operation=true;
- human_identity_proven=false;
- original preflight was READY.

Tamper with ticket TTL without re-signing.

Expected verification failure.

Evaluate freshness beyond TTL using a synthetic future time.

Expected false.

## Trial B — stale after consent

After ticket issuance, source UNSHAREs the candidate.

Execute ticket.

Expected:

```text
REFUSED_STALE
ticket_spent = true
operation_attempted = false
source request inbox = empty
```

Replay exact ticket.

Expected refusal because atomic claim already exists.

## Trial C — fresh request execution

Source SHAREs the exact package again.

Create a fresh request descriptor and issue a new ACT ticket.

Execute.

Expected:

- execution-time preflight READY;
- proposal address unchanged;
- exactly one real 024/023 signed request is created;
- execution receipt is EXECUTED and verifies;
- request still crosses no package;
- replay refuses.

## Trial D — source still owns OFFER

Source explicitly performs 023 OFFER outside activation.

Expected requester receives one normal 022 HOLD.

## Trial E — validate ticket

Get current `validate-parcel` launch, issue ACT, execute.

Expected real 022 local validation and signed EXECUTED activation receipt.

Plugin parcel becomes VALIDATED.

## Trial F — execution failure consumes consent

Get current `install-parcel` launch and issue ACT.

Use a deterministic destination that throws only after execution-time revalidation succeeds.

Expected:

```text
FAILED
ticket_spent = true
operation_attempted = true
success = false
```

Plugin parcel remains VALIDATED.

Replay refuses.

## Trial G — fresh install consent

Issue a new ACT ticket for the still-current install launch.

Execute.

Expected:

- activation receipt EXECUTED;
- underlying 021 install receipt verifies;
- plugin parcel becomes INSTALLED;
- replay refuses.

## Trial H — resolved state

Expected Curious Door becomes resolved-local and no longer emits request/validate/install launches.

It retains only read-only local compatibility inspection.

## Trial I — read-only activation remains bounded

Issue and execute one ticket for resolved `inspect-parcel`.

Expected signed EXECUTED receipt and one read-only result.

Ticket is still one-use.

## Pass

028 passes when all new trials and the complete 001–027 smoke chain are green.

## Mutation opened

029 can add a tiny Static-OS activation broker that owns only the transition:

```text
selected typed launch
  -> destination preflight
  -> present ACT boundary
  -> issue ticket
  -> hand ticket to owning destination
  -> show signed result
```

The broker must not mint consent itself.

Preserve:

```text
BROKER != CONSENT
UI CLICK != ACT TICKET
RESULT DISPLAY != SUCCESS CLAIM
```
