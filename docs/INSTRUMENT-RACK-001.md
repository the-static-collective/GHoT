# INSTRUMENT RACK 001 — Capability Cards + Portable Seed Packets

GHoT can now expose explicitly opted-in donor instruments as proposal-only cards,
execute one exact card only after an explicit dispatch, and return the successful
result as a content-addressed portable seed packet.

```text
external adapter manifest
        ↓
INSTRUMENT RACK
        ↓
proposal-only capability card
        ↓
explicit human dispatch
        ↓
signed reLATTE crossing
        ↓
bounded donor-owned adapter execution
        ↓
signed consequence receipt
        ↓
PORTABLE SEED PACKET
        ↓
explicit local admission
        ↓
ADMITTED_NOT_EXECUTED seed material
```

## Why

This is the first literal Collective Instrument Rack.

A donor repository owns its instrument semantics and opts in with
`ghot.external-adapter-manifest/v0`. GHoT may discover and execute only that
declared bounded capability. Discovery does not select it, composing a card does
not run it, and successful execution does not automatically admit the result.

The first real donor model is Haunted Toaster's existing
`creative.toaster.witness-sigil` adapter. That adapter returns SVG + recipe +
Toaster receipt bytes inline, so a remote caller does not need shared filesystem
access to retain the artifact family.

## Rack

```bash
export GHOT_ADAPTER_MANIFESTS=/path/to/the-haunted-toaster/integrations/ghot/adapter-manifest.json
printf '{"action":"rack"}' | python3 ghot/instrument_rack.py | python3 -m json.tool
```

Each card is `ghot.instrument-card/v0` and binds:

- adapter id;
- exact capability;
- manifest SHA-256;
- protocol;
- declared limits;
- current availability.

The card status is always:

```text
PROPOSAL_ONLY
semantic_effect: none
```

Building the rack never starts the donor process.

## Explicit dispatch

Dispatch requires the exact card, an explicit payload, and an attributable
`dispatch_source`.

Before execution GHoT rebuilds the rack and requires the selected card to match
the fresh manifest/capability snapshot exactly. A modified manifest, card, limit,
or availability observation refuses as stale/tampered rather than silently
selecting a replacement.

The dispatch creates and persists a signed `relatte.crossing-envelope/v0`
before invoking the existing bounded GHoT execution path. A prepared crossing
with an unknown outcome refuses automatic retry.

Exact replay of a completed dispatch returns the original result and does not
invoke the donor again.

## Portable seed packet

A successful instrument attempt yields:

```text
ghot.portable-seed-packet/v0
```

The packet binds:

- source card id;
- dispatch id and signed crossing;
- adapter + capability;
- manifest digest;
- input digest;
- donor-result digest;
- GHoT execution receipt;
- signed GHoT consequence receipt;
- any donor-returned inline `*_text + *_sha256` artifact pairs.

Those inline artifacts are verified byte-for-byte before packet creation and
again before admission.

The donor result is carried as evidence. GHoT does not reinterpret its meaning.

## Admission

```text
PACKET
  !=
MATERIAL
```

`admit_seed_packet()` verifies the packet identity, donor-result digest,
dispatch crossing, signed consequence receipt, and inline artifact hashes.

Only then does it persist:

```text
ghot.seed-material/v0
status: ADMITTED_NOT_EXECUTED
semantic_effect: local-material-only
```

Admission executes nothing and does not imply KEEP, truth, publication, or
continuation authority.

## Founding laws

```text
RACK != EXECUTION
DISCOVERY != SELECTION
CARD != ASSIGNMENT
CAPABILITY != AUTHORITY
DISPATCH != SUCCESS
DONOR RESULT != GHOT SEMANTICS
PACKET != ADMISSION
ADMISSION != EXECUTION
MATERIAL != KEEP
PORTABLE != AUTHORITY-FREE
AMBIGUOUS OUTCOME != SAFE RETRY
```

## Deterministic proof

```bash
GHOT_HOME="$(mktemp -d)" python3 ghot/instrument_rack_sim.py
```

The simulation uses a real external adapter process with an invocation counter
and proves:

1. rack/card creation causes zero executions;
2. a tampered card refuses before execution;
3. explicit dispatch invokes the adapter exactly once;
4. exact replay does not invoke it again;
5. the returned packet is content-addressed;
6. packet tampering refuses admission;
7. explicit admission creates reusable material without another execution.

This slice is local-body only by design. The card/packet boundaries are intended
to remain unchanged when later descendants add body assignment and remote
execution.
