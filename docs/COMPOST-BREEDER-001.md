# COMPOST BREEDER 001 — History-Bearing Film Ecology Loop

COMPOST-BREEDER-001 is the first executable specimen of the loop:

```text
Toaster generation-1 render + history capsule
          ↓
Instrument Rack dispatch
          ↓
Blender DREAMBREEDER six unborn films
          ↓
watchable six-up preview
          ↓
explicit HUMAN KEEP
          ↓
kept unrendered descendant
          ↓
external instrument dispatch
          ↓
portable seed packet
          ↓
explicit seed admission
          ↓
generation-2 Toaster render request
          ↓
generation-2 rendered-history capsule
          ↓
GHoT evidence index
```

## Host role

GHoT is the crossing/orchestration body only.

It does **not**:

- choose the kept film;
- reinterpret Blender proposal semantics;
- claim Blender previews as history;
- reinterpret Toaster render-cause semantics;
- turn a portable packet into admitted material automatically;
- make external seed provenance a historical parent;
- publish or canonize generation 2.

## Exact donor lineage

The specimen pins the current donor contracts:

- Haunted Toaster NEXTGEN-TOASTER-013 history compost — `923b536d068c8daf85e9d960469405e17c4d56f7`;
- Haunted Blender DREAMBREEDER 003 — `5227ffe7b59240bb3daa5527eb4881969091f073`;
- Haunted Blender Cutout Compiler 004 — `2b17439c12d87493455596d0dfa2b11bbbb1bfa0`;
- GHoT Instrument Rack 001 — `3d64e5d486d9324ec6086da69889a81ab2e48cd8`.

Those refs are evidence about the protocol family. They do not make the donor repositories hidden runtime dependencies.

## Phase 1 — breed request

`prepare_breed_request()` observes only a bounded Toaster history reference:

- capsule hash;
- generation;
- exact rendered-media SHA-256;
- parent capsule hashes.

GHoT deliberately does not recompute the Toaster capsule hash. The capsule remains donor-owned provenance evidence.

The request asks an explicitly selected Blender instrument to grow six unborn film previews. Dispatch still occurs through Instrument Rack and therefore receives a signed crossing, execution receipt, portable packet, replay protection, and exact card revalidation.

## Phase 2 — unresolved ecology

`open_session()` requires the donor return to contain:

- one `haunted-blender/dream-ecology/v1`;
- exactly six unique proposal-only proposals;
- unresolved disposition;
- one `haunted-blender/dream-sixup-preview/v1`;
- exactly six proposal-preview entries covering the ecology once;
- matching ecology identity.

The resulting session state is:

```text
AWAITING_HUMAN_KEEP
```

Watching the six-up does not alter that state.

## Phase 3 — explicit KEEP

`prepare_keep_request()` names one proposal explicitly.

The KEEP donor result is admitted only if:

- the returned Blender descendant names that exact proposal;
- it names the exact source ecology;
- the resolved ecology contains a KEEP disposition for that proposal;
- the descendant authority class is `continuation-permission`.

GHoT also records an attributable `keep_source` supplied by the caller.

Selection is therefore never inferred from ranking, preview time, card order, or a donor result.

## Phase 4 — external instrument seed

Any successful Instrument Rack donor result may become a portable seed packet.

`admit_seed_packet()` remains a separate action. Only an existing:

```text
ghot.seed-material/v0
status: ADMITTED_NOT_EXECUTED
semantic_effect: local-material-only
```

may enter the Compost Breeder session.

The founding specimen uses a deterministic Mineral-shaped seed adapter, but the Compost Breeder contract is not mineral-specific.

## Phase 5 — generation 2 request

`prepare_generation2_request()` carries three independent references:

1. parent Toaster rendered-history reference;
2. kept Blender descendant reference;
3. admitted external seed-material reference.

Only the parent Toaster capsule is requested as historical ancestry.

The external seed stays external-work provenance:

```text
EXTERNAL SEED != HISTORICAL PARENT
```

## Phase 6 — generation 2 return

`accept_generation2_result()` requires:

- a returned Toaster rendered-history capsule;
- generation exactly parent generation + 1;
- the original parent capsule hash among child history parents;
- a bounded donor marker naming the exact kept descendant;
- the exact admitted external seed material id;
- a marker history hash equal to the returned child capsule hash.

GHoT then creates:

```text
ghot.compost-breeder-generation2-witness/v0
authority: evidence-index-only
```

The witness ties together:

- parent history;
- child history;
- KEEP packet + descendant;
- external seed material;
- generation-2 return packet.

It does not reinterpret any of them.

## Deterministic subprocess specimen

Run:

```bash
GHOT_HOME="$(mktemp -d)" python3 ghot/compost_breeder_sim.py
```

The simulation creates a real opted-in external adapter with four bounded capabilities:

- `creative.blender.dreambreed.sixup`;
- `creative.blender.dreambreed.keep`;
- `creative.mineral.seed`;
- `creative.toaster.history-render-generation2`.

Each capability increments a durable invocation counter.

The proof demonstrates:

1. rack construction executes nothing;
2. breeding executes exactly once;
3. six unborn proposals + six previews remain unresolved;
4. a mismatched KEEP donor result refuses;
5. the explicit selected KEEP succeeds;
6. external seed execution returns a portable packet;
7. packet admission executes nothing;
8. generation-2 request carries parent history, kept descendant, and external seed separately;
9. child history retains the exact parent capsule;
10. generation-2 return names the exact kept descendant and external seed;
11. exact generation-2 dispatch replay executes no second donor process;
12. a material with escalated status cannot masquerade as admitted seed.

## Founding laws

```text
ORCHESTRATION != SELECTION
PREVIEW != KEEP
WATCHING != KEEP
KEEP REQUEST != KEEP RESULT
PACKET != ADMISSION
ADMISSION != EXECUTION
EXTERNAL SEED != HISTORICAL PARENT
DONOR RESULT != GHOT SEMANTICS
ANCESTRY != AUTHORITY
GENERATION2 REQUEST != GENERATION2 RESULT
GENERATION2 WITNESS != PUBLICATION AUTHORITY
```

## Deliberate nonclaims

- The simulation does not vendor or execute the live Blender/Toaster repositories.
- It proves the crossing contract with donor-shaped subprocesses, not pixel parity with Blender 004.
- It does not automatically HAUNT the five unselected possibilities.
- It does not rank the six previews.
- It does not make external seed material causal history inside the Toaster capsule.
- It does not merge donor code into GHoT.

## Next physical crossing

The next stronger specimen can replace one simulated capability at a time with a real opted-in donor adapter while leaving this orchestration contract unchanged.
