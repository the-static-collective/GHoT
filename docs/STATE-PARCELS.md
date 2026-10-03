# Portable State Parcels

Experiment 018 lets bounded durable state move between GHoT bodies without
turning either body into a shared database.

Core rule:

> Crossing state does not transfer authority over the receiver's interior.

## Export

A body may export a bounded JSON slice from inside its own `GHOT_HOME`.

Example:

```bash
python3 ghot/state_parcel.py export \
  organ/state.v1.json \
  --selector /body/offers \
  --target-particular <receiver-particular> \
  --out offers.parcel.json
```

The source path must remain inside `GHOT_HOME`.

Selectors use a bounded RFC6901-style JSON Pointer. `$` selects the whole
document.

The selected payload is normalized into the same identity-safe JSON family used
by the signed protocol surface and is capped at 512 KiB.

## Parcel contents

`ghot.state.parcel/v0` binds:

```text
source node id
source BODY particular
source state relative path
source state kind/version
full source-state semantic address

target BODY particular, optional

selector
payload semantic address
payload size
payload value

current known schema version
relevant migration receipt ids
```

The parcel itself is content-addressed.

## Signed export receipt

Each parcel contains a BODY-signed export receipt:

```text
ghot.state.parcel.export-receipt/v0
```

It binds:

```text
parcel id
parcel address
payload address
source-state address
source BODY particular
target particular
export time
```

with the exporter's P-256 key.

This proves key possession witnessed the exported fragment.

It does not prove the fragment is true, desirable, or authorized for admission.

```text
SIGNED EXPORT != TRUST
```

## reLATTE crossing

The bundle also carries a signed `relatte.crossing-envelope/v0`.

The crossing declares:

```text
GHOT_STATE_PARCEL
capability_ref = ghot.state-parcel/v0
requested_effect.action = OFFER_STATE
requested_disposition = HOLD
payload_ref = parcel address
```

The crossing source particular must equal the parcel source particular.

The crossing and the export receipt are independent signatures over related
evidence.

## Parcel porch

The dedicated receiving porch defaults to:

```text
0.0.0.0:7792
POST /state-parcel
GET  /state-parcels
```

It can run independently:

```bash
python3 ghot/state_parcel.py serve --port 7792
```

and the normal organ daemon supervises it by default:

```bash
python3 ghot/organ.py
```

Disable it explicitly:

```bash
python3 ghot/organ.py --no-state-porch
```

BODY discovery advertises the parcel porch separately from the normal task
service.

```text
TASK PORT != STATE PORCH
SERVICE ADVERTISEMENT != TRUST
```

## Crossing

Direct URL:

```bash
python3 ghot/state_parcel.py send offers.parcel.json http://PEER:7792
```

By currently discovered BODY:

```bash
python3 ghot/state_parcel.py send-node \
  offers.parcel.json \
  <receiver-node-id>
```

`send-node` refuses to use the node id by itself.

It requires:

```text
parcel.target.particular
        ==
currently discovered BODY.identity.particular
```

before crossing.

Thus:

```text
NODE ID != CRYPTOGRAPHIC BODY
```

## Receive means HOLD

A cryptographically valid network parcel can do exactly one automatic thing:

```text
VALID CROSSING
      ↓
HOLD
```

The receiving BODY returns a signed reLATTE receipt:

```text
kind = HELD
semantic_effect = none
```

There is no network ADMIT endpoint.

Unknown-but-valid source bodies may still enter HOLD because signature
verification is not trust admission. The owner can inspect before deciding.

A parcel targeted at another BODY particular receives a signed `REFUSED`
receipt and does not enter the inbox.

## Inbox

Inspect:

```bash
python3 ghot/state_parcel.py inbox
python3 ghot/state_parcel.py show <parcel-id>
```

Inbox records live beneath:

```text
GHOT_HOME/state-parcels/inbox/
```

The original verified bundle is retained beneath:

```text
GHOT_HOME/state-parcels/raw/
```

Duplicate crossings of the same parcel do not create duplicate inbox entries.

## Owner-local dispositions

The owner may choose:

```text
HOLD
ADMIT
REJECT
SCAR
```

Example:

```bash
python3 ghot/state_parcel.py decide \
  <parcel-id> \
  ADMIT \
  --note "useful foreign offer snapshot"
```

Each decision returns a BODY-signed reLATTE receipt.

Terminal dispositions are mutually exclusive.

### HOLD

Keep the parcel pending.

No live state changes.

### ADMIT

Accept the parcel into the receiver's local admitted parcel corpus:

```text
GHOT_HOME/state-parcels/admitted/
```

ADMIT does **not** rewrite `organ/state.v1.json`, `field.v0.json`, or another
canonical live-state file.

It means:

> this body accepts the fragment as locally available foreign state.

It does not mean:

> overwrite my interior with it.

### REJECT

Record owner-local refusal.

No parcel payload is materialized into the admitted corpus.

### SCAR

Deliberately retain the foreign payload as an inactive local witness:

```text
GHOT_HOME/state-parcels/scars/
```

A scar explicitly records:

```text
active = false
```

This lets conflicting, rejected, historically useful, or otherwise unresolved
state remain traceable without becoming active state.

## Receipts

Inspect:

```bash
python3 ghot/state_parcel.py receipts
```

Receiver receipts use `relatte.receipt/v0` and are signed by the receiving
BODY.

Receipt kinds:

```text
HELD
ADMITTED
REJECTED
SCARRED
REFUSED
```

Receipts include parcel id/address, payload address, source particular, target
particular, disposition, and the explicit statement:

```text
canonical_state_mutated = false
```

## Migration metadata

A parcel carries its source schema version plus relevant migration receipt ids
known to the exporting body.

That metadata is provenance.

It does not grant the receiving body permission to migrate or merge its own
state.

```text
MIGRATION METADATA != MIGRATION AUTHORITY
```

## What 018 does not do

018 does not yet define a generic merge operator into canonical live state.

That is intentional.

Safe admission comes first:

```text
CROSS
 -> VERIFY
 -> HOLD
 -> OWNER DISPOSITION
 -> LOCAL CORPUS
```

A future merge protocol can operate on admitted parcels under an explicit
schema-specific merge contract.

## Laws

- CROSSING != ADMISSION
- HOLD != MERGE
- ADMIT != OVERWRITE
- SIGNED EXPORT != TRUST
- NODE ID != CRYPTOGRAPHIC BODY
- SERVICE ADVERTISEMENT != TRUST
- FOREIGN STATE != LOCAL AUTHORITY
- MIGRATION METADATA != MIGRATION AUTHORITY
- SCAR != ACTIVE STATE
- RECEIPT != TRUTH
