# Activation Broker

Experiment 029 turns the 027→028 launch path into a small Static-OS consent ceremony without moving consent authority into the UI.

Core flow:

```text
current typed launch
    ↓
read-only launch index
    ↓
read-only destination preflight preview
    ↓
human sees exact proposed invocation/effect
    ↓
human types ACT
    ↓
broker verifies exact previewed proposal still matches
    ↓
028 issues one bounded ticket
    ↓
028 spends it and revalidates again
    ↓
one owning-subsystem attempt
    ↓
broker displays verified signed outcome
```

## BROKER is not consent

The broker may coordinate the ceremony, but it cannot manufacture consent.

Selecting a launch from the broker index only opens a preview.

```text
UI CLICK != ACT TICKET
```

The index contains no ACT form and performs no mutation.

## Read-only launch index

A supervised broker is available by default at:

```text
http://127.0.0.1:7795/
```

The root page lists only the currently projected typed launches from Curious Doors.

Each item links to:

```text
/preview?launch_id=<launch-id>
```

Selection is navigation only.

## Preview

Preview runs the full 027 destination preflight and shows:

- label;
- destination app/operation;
- bounded context;
- possible effect;
- preflight status/checks;
- exact invocation proposal, when READY;
- exact proposal content address.

Preview may perform a network READ for candidate revalidation, but it writes no local state.

```text
PREVIEW != AUTHORITY
```

Only a READY preview exposes the ACT form.

## Exact proposal binding

The ACT form carries the exact proposal address shown to the operator.

When ACT arrives, the broker preflights again before asking 028 to issue a ticket.

If the current proposal differs:

```text
ACT -> REFUSE
ticket_issued = false
```

Therefore:

```text
PREVIEWED PROPOSAL != CHANGED PROPOSAL
```

028 also independently receives the expected proposal address and refuses ticket issuance if its own fresh preflight differs.

## Explicit ACT

The browser ceremony requires the user to type exactly:

```text
ACT
```

and submit:

```text
POST /act
```

The button click alone is insufficient.

Wrong phrases are refused before ticket issuance.

## Browser same-origin guard

For browser requests carrying an Origin header, POST /act requires:

```text
Origin == http://<broker Host header>
```

An unrelated webpage cannot submit the ACT ceremony into localhost through an ordinary cross-origin form.

CLI/local API clients without an Origin header remain supported.

This is a browser request-origin boundary, not human identity proof.

## Delegation to 028

The broker does not implement a second ticket system.

After exact ACT binding, it delegates to:

```text
ghot.activation-tickets@0
```

for:

- ticket issuance;
- atomic one-time claim;
- execution-time revalidation;
- one operation attempt;
- signed execution receipt.

## Result truth

The broker never calls an HTTP 200 or returned object a success by itself.

It verifies the 028 execution receipt and exposes:

```text
receipt_verified
signed_status
signed_success
verified_success
```

`verified_success=true` only when:

```text
receipt signature verifies
AND status == EXECUTED
AND signed success == true
```

Only then is:

```text
success_claim_basis = verified-signed-execution-receipt
```

Otherwise the UI displays refusal, failure, or unverified state literally.

```text
RESULT DISPLAY != SUCCESS CLAIM
```

## Current-launch binding

The broker resolves launch ids from the current local Curious Doors projection.

Once an operation changes state and that launch disappears, replaying the old launch id through the broker fails.

The broker does not accept an arbitrary launch descriptor body from HTTP clients.

## CLI

Preview:

```bash
python3 ghot/activation_broker.py preview <launch-id>
```

ACT one exact previewed proposal:

```bash
python3 ghot/activation_broker.py act \
  <launch-id> \
  <proposal-address> \
  --confirm ACT
```

Serve:

```bash
python3 ghot/activation_broker.py serve
```

## Organ supervision

A normal:

```bash
python3 ghot/organ.py
```

supervises the broker on loopback port 7795.

Disable explicitly:

```bash
python3 ghot/organ.py --no-activation-broker
```

Service state declares:

```text
launch_index_read_only = true
preview_read_only = true
act_required = true
daemon_supplies_act = false
ui_click_grants_consent = false
broker_grants_consent = false
same_origin_browser_act_required = true
success_requires_verified_signed_receipt = true
```

Supervision keeps the ceremony reachable. It does not participate in consent.

## Laws

- BROKER != CONSENT
- UI CLICK != ACT TICKET
- LAUNCH SELECTION != CONSENT
- PREVIEW != AUTHORITY
- PREVIEWED PROPOSAL != CHANGED PROPOSAL
- BROKER AVAILABILITY != OPERATION AUTHORIZATION
- SAME ORIGIN != HUMAN IDENTITY
- HTTP 200 != SUCCESS
- RESULT DISPLAY != SUCCESS CLAIM
- VERIFIED RECEIPT != BROKER INFERENCE
