# Experiment 025 — Curious Doors

## Question

Can Static-OS expose durable composition curiosity as a continuously available local surface while keeping the entire surface read-only and non-authoritative?

## Deterministic proof

```bash
python3 ghot/curious_doors_sim.py
```

## Trial A — open gap

Create one concrete 024 WANT with zero candidates.

Expected surface state:

```text
open-gap
```

Snapshot generation must leave the complete `composition-wants/` tree byte-identical.

## Trial B — candidate appears

Perform an explicit 024 REFRESH against a source advertising an exact-shape grammar.

Expected surface state:

```text
candidate-observed
```

The door reports one candidate and one candidate newly observed in the latest stored refresh.

The surface itself performs no network refresh.

HTML rendering must leave WANT history byte-identical and contain no form, button, or script.

## Trial C — explicit request elsewhere

Use the existing 024 candidate-specific REQUEST command.

Expected surface state:

```text
requested
```

The surface merely reflects the new durable request link.

## Trial D — source offer

Source explicitly performs normal 023 OFFER.

Requester receives normal 022 HOLD.

Expected surface state remains:

```text
requested
```

because the local composition gap is still unresolved.

## Trial E — local resolution

Requester explicitly performs normal 022 VALIDATE and INSTALL.

Expected surface state:

```text
resolved-local
```

The historical WANT and request history remain visible.

## Trial F — real HTTP view

Start the local Curious Doors HTTP surface.

Expected:

```text
GET /                 -> 200 HTML
GET /curious-doors    -> 200 JSON
POST /curious-doors   -> 405
```

The served HTML contains no form, button, or script.

## Trial G — projection remains read-only

Generate another final snapshot.

Expected complete `composition-wants/` tree remains byte-identical.

## Pass

025 passes when the four visible states occur in order:

```text
open-gap
candidate-observed
requested
resolved-local
```

and the complete 001–024 smoke chain remains green.

## Mutation opened

026 can make the surface navigable without making it authoritative:

```text
CURIOUS DOOR
    ↓
inspect evidence
    ↓
open existing local tool
    ↓
operator acts in the owning subsystem
```

That suggests deep links or copied command intents rather than mutation buttons inside Curious Doors itself.

Preserve:

```text
NAVIGATION != ACTION
LINK != AUTHORITY
SURFACE CONTEXT != SUBSYSTEM PERMISSION
```
