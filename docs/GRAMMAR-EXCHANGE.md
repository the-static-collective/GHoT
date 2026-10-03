# Grammar Exchange Table

Experiment 023 lets GHoT bodies discover which locally installed merge grammars
another body is explicitly willing to share, request one exact package address,
and receive it only after the source makes a separate local OFFER decision.

Core sequence:

```text
INSTALLED PACKAGE
    ↓
explicit SHARE
    ↓
signed short-lived ADVERT
    ↓
remote DISCOVERY
    ↓
signed REQUEST
    ↓
source request inbox
    ↓
local OFFER / DECLINE
    ↓
022 package parcel
    ↓
remote HOLD
    ↓
remote VALIDATE / INSTALL
```

## Installed is not shareable

Installing a package does not advertise it.

List local exchange state:

```bash
python3 ghot/grammar_exchange.py inventory
```

Explicitly expose one installed package:

```bash
python3 ghot/grammar_exchange.py share <package-id>
```

Stop exposing it:

```bash
python3 ghot/grammar_exchange.py unshare <package-id>
```

Inspect declared versus currently active shares:

```bash
python3 ghot/grammar_exchange.py shares
```

A declared share is active only while the same package id/address remains
receipt-valid in the 021 plugin store.

```text
INSTALLED != SHAREABLE
DECLARED SHARE != CURRENTLY AVAILABLE PACKAGE
```

## Signed exchange advert

The normal organ supervises a grammar exchange service on:

```text
HTTP 7793
UDP discovery 47890
```

A short-lived BODY-signed advert contains metadata only:

```text
node id
BODY particular + public key
exchange port
parcel port

for each explicitly shared package:
  package id
  package version
  package address
  contract id
  title/category
  optional author particular
```

No package bytes ride discovery.

Scan:

```bash
python3 ghot/grammar_exchange.py scan
```

The advert means only:

> this BODY currently says it is willing to share these exact package addresses.

It does not establish trust, request, crossing, or installation.

```text
SIGNED ADVERT != TRUST
DISCOVERY != REQUEST
```

## Signed request

A requester chooses one exact advertised package address:

```bash
python3 ghot/grammar_exchange.py request \
  http://SOURCE:7793 \
  <package-id> \
  <sha256:package-address>
```

The requester first fetches and verifies the source's current signed advert.

The request then binds:

```text
source BODY particular
unique nonce
package id/address
requester node id
requester BODY particular + public key
requester return parcel port
created_at
TTL
request signature
```

Requests are content-addressed and BODY-signed.

The source verifies that:

- request signature is valid;
- request is fresh;
- request targets this source BODY particular;
- exact package id/address is still explicitly shared.

If accepted, the source returns a BODY-signed reLATTE `REQUESTED` receipt with:

```text
semantic_effect = none
package_crossed = false
network_offer = false
```

Thus:

```text
REQUEST != OFFER
```

## Source request inbox

The source may inspect:

```bash
python3 ghot/grammar_exchange.py requests
```

A request remains:

```text
REQUESTED
```

until a local operator explicitly chooses:

```bash
python3 ghot/grammar_exchange.py offer <request-id>
```

or:

```bash
python3 ghot/grammar_exchange.py decline <request-id>
```

DECLINE is terminal for that request.

## Return road identity check

The request carries only a return **parcel port**.

The source stores the network address from which the signed request actually
arrived.

Before OFFER, the source constructs:

```text
http://<observed-requester-ip>:<signed-return-parcel-port>
```

and queries:

```text
GET /merge-plugin-packages
```

The porch must report a current:

```text
receiver_particular
```

equal to the BODY particular inside the signed request.

Only then may the source cross the 022 package parcel.

```text
RETURN ROAD != REQUESTER IDENTITY
```

This prevents a signed request from turning an arbitrary URL into a source-side
fetch/send instruction.

## Explicit OFFER

OFFER revalidates:

- request signature;
- request TTL;
- package is still explicitly shared;
- exact package address is still installed;
- requester return porch matches requester BODY identity.

The source then reconstructs the exact installed package.

If the source retains a verified 022 author signature for that installed
package, it is preserved in the outgoing parcel. Otherwise the package travels
unsigned.

The source creates a normal 022 package parcel targeted to the requester
particular and crosses it to the verified parcel porch.

Expected requester response:

```text
HELD
```

The local offer record binds:

```text
request id
package id/address
022 parcel id/address
crossing id
requester particular
verified return URL
receiver HELD receipt id
optional author particular
offered_at
installed_remotely = false
```

So:

```text
OFFER != INSTALLATION
```

## Requester still owns installation

After OFFER, the requester has only a normal 022 HOLD.

The existing sequence remains unchanged:

```bash
python3 ghot/merge_plugin_parcel.py inbox
python3 ghot/merge_plugin_parcel.py validate <parcel-id>
python3 ghot/merge_plugin_parcel.py install <parcel-id>
```

023 does not create another install path.

## Organ supervision

A normal:

```bash
python3 ghot/organ.py
```

now supervises the exchange HTTP and UDP discovery service.

Disable it explicitly:

```bash
python3 ghot/organ.py --no-grammar-exchange
```

Supervision only keeps the table reachable.

It never performs:

```text
auto-share
auto-request
auto-offer
auto-install
```

```text
SUPERVISION != EXCHANGE AUTHORITY
```

## Exchange table

`inventory` projects four local views:

```text
installed
held_foreign
declared_shares
active_shares
```

This lets a body see both what it has and what has arrived without collapsing
those states.

## Failure and drift behavior

If a package is unshared after REQUEST but before OFFER:

```text
OFFER -> REFUSE
```

If a new request asks for an unshared address:

```text
REQUEST -> REFUSE
```

If a request is declined:

```text
later OFFER -> REFUSE
```

If the request expires:

```text
OFFER -> REFUSE
```

If the return porch's current BODY particular differs from the signed
requester:

```text
OFFER -> REFUSE
```

If package metadata or a request signature is tampered:

```text
verification -> REFUSE
```

## Laws

- INSTALLED != SHAREABLE
- DISCOVERY != REQUEST
- SIGNED ADVERT != TRUST
- REQUEST != OFFER
- SIGNED REQUEST != ENTITLEMENT
- RETURN ROAD != REQUESTER IDENTITY
- OFFER != INSTALLATION
- SUPERVISION != EXCHANGE AUTHORITY
- PACKAGE METADATA != PACKAGE BYTES
- AUTHOR PARTICULAR != AUTHOR TRUST
