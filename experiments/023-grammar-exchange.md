# Experiment 023 — Grammar Exchange Table

## Question

Can two GHoT bodies discover an explicitly shareable merge grammar, request one
exact package address, require a separate local source OFFER, and still leave
the requester with only the normal 022 HOLD until it explicitly validates and
installs the package?

## Deterministic proof

```bash
python3 ghot/grammar_exchange_sim.py
```

## Trial A — installed is not shareable

Install the example 021 plugin on the source.

Expected initial exchange table:

```text
installed: 1
active_shares: 0
```

The signed exchange advert contains no packages.

## Trial B — explicit share

Run local SHARE.

Expected:

- exactly one advertised package;
- package id/address match the installed package;
- retained verified author particular appears when available;
- package bytes do not appear in advert.

Tampering with advert metadata invalidates its signature.

## Trial C — signed discovery

Run the real UDP discovery responder and scanner over loopback.

Expected:

- one fresh signed advert;
- shared package address visible;
- requester has no package HOLD and no plugin install afterward.

## Trial D — signed request only

Requester sends one signed request for the exact package address.

Expected source receipt:

```text
REQUESTED
semantic_effect = none
package_crossed = false
```

Requester still has:

```text
plugin parcel inbox = empty
plugin store = empty
```

Replaying the exact signed request only produces a duplicate REQUESTED receipt.

## Trial E — explicit source OFFER

Source operator locally runs OFFER.

Before crossing, source verifies the requester's current parcel porch particular
against the signed requester particular.

Expected:

- one 022 parcel crosses;
- retained author signature survives when available;
- requester receives HOLD;
- requester plugin store remains empty.

## Trial F — requester-local installation

Requester locally runs:

```text
VALIDATE
INSTALL
```

Expected:

- 021 install receipt verifies;
- plugin appears in requester pantry only after INSTALL.

## Trial G — unshare after request

Create another valid request, then UNSHARE before OFFER.

Expected:

```text
existing request OFFER -> REFUSE
new request -> REFUSE
advert packages -> []
```

## Trial H — decline

Share again, receive another request, then DECLINE it.

Expected later OFFER refusal.

## Trial I — return-road identity mismatch

Requester signs a valid request but names a parcel port currently served by a
different BODY.

Expected source OFFER refusal after porch identity probe.

Nothing enters the wrong BODY's plugin parcel inbox.

## Trial J — tamper and stale request

Modify signed request package address.

Expected signature verification failure.

Evaluate request beyond TTL.

Expected freshness failure.

## Pass

023 passes when the new simulation and the complete 001–022 smoke chain are
green.

## Mutation opened

024 can add **composition wants** without automatic requesting:

```text
local capability/merge need
      +
known installed grammars
      +
discovered shareable grammars
      ↓
GAP
      ↓
candidate package addresses
      ↓
human-visible WANT
      ↓
explicit REQUEST
```

That would let the organism notice:

> I currently lack a lawful grammar for this kind of composition, and another
> body says it can share one.

while preserving:

```text
GAP != REQUEST
CANDIDATE != RECOMMENDATION
WANT != AUTHORITY
```
