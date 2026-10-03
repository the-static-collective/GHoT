# Experiment 029 — Static-OS Activation Broker

## Question

Can Static-OS make the 027→028 path usable as one visible consent ceremony while preserving the facts that a click is not consent, preview is not authority, changed context invalidates ACT, and success is grounded only in a verified signed execution receipt?

## Deterministic proof

```bash
python3 ghot/activation_broker_sim.py
```

## Trial A — read-only preview

Create a current request-candidate launch and call broker preview.

Expected:

- complete local state tree remains byte-identical;
- destination preflight is READY;
- exact proposal address is shown;
- no activation ticket exists;
- no source request exists;
- preview_executes=false;
- broker_grants_consent=false;
- ui_click_grants_consent=false.

Rendered preview contains the explicit ACT form.

## Trial B — wrong ACT and wrong binding

Attempt ACT with a non-ACT phrase.

Expected refusal and zero tickets.

Attempt ACT with the wrong proposal address.

Expected refusal and zero tickets.

## Trial C — world changes after preview

UNSHARE the candidate after preview and submit the exact old proposal binding.

Expected:

```text
REFUSE
ticket count = 0
source request inbox = empty
```

Re-SHARE and obtain a fresh READY preview.

## Trial D — broker HTTP surface

Start the real loopback broker.

GET `/`.

Expected:

- read-only current launch index;
- no ACT form;
- no ACT button;
- preview links only;
- byte-identical local state.

GET `/health`.

Expected:

```text
preview_read_only = true
click_grants_consent = false
act_required = true
browser_post_same_origin_required = true
```

GET `/preview?...` remains byte-identical.

## Trial E — browser boundaries

POST exact ACT from an unrelated Origin.

Expected HTTP 403 and zero tickets.

POST same-origin with the wrong phrase.

Expected HTTP 409 and zero tickets.

POST same-origin with exact ACT + exact shown proposal address.

Expected exactly one ticket and one 028 attempt.

## Trial F — request result truth

Expected broker result:

```text
receipt_verified = true
signed_status = EXECUTED
signed_success = true
verified_success = true
success_claim_basis = verified-signed-execution-receipt
broker_inferred_success = false
```

Source receives exactly one normal signed request.

Repeat the old launch ACT after state advances.

Expected refusal and no second request.

## Trial G — result rendering

A verified EXECUTED+success receipt may render a verified-success statement.

A verified FAILED receipt must render failure and must not contain the success statement.

An unverified receipt must render unverified and must not contain the success statement.

## Trial H — downstream real operations

Source separately performs 023 OFFER.

Broker then coordinates fresh ACT ceremonies for:

```text
validate-parcel
install-parcel
```

Expected real 022/021 state transitions and verified signed activation results.

## Trial I — resolved read-only operation

Once resolved, broker coordinates one bounded `inspect-parcel` activation.

Expected verified signed result containing the installed compatible contract.

## Pass

029 passes when all ceremony trials and the complete 001–028 smoke chain are green.

## Mutation opened

030 can compose Curious Doors and Activation Broker into one Static-OS shell page without collapsing their authority split:

```text
read-only curiosity column
+ read-only launch selection
+ broker preview pane
+ explicit ACT pane only for READY launch
+ signed receipt timeline
```

Preserve:

```text
SHELL != SUBSYSTEM
PANE != AUTHORITY
SELECTION != CONSENT
TIMELINE != VERDICT
```
