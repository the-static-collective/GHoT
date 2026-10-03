# RSC Composer 001

**Status:** executable experimental instrument  
**Branch:** `rsc-composer-001`  
**Derived from:** Recursive Systems Composition

## One sentence

RSC Composer turns a set of already-observed artifacts and proposed crossings into a bounded, content-addressed **reseed packet** without pretending that recommendation is selection or that resemblance transfers authority.

## Why this belongs in GHoT

GHoT already asks:

> what body should do this work?

RSC asks one level above:

> what existing artifact has become useful to what other artifact, what boundaries must survive that crossing, and what reversible experiment should expose the next real seam?

The Composer therefore does not replace GHoT capability composition, reLATTE crossings, ROroomOM's human-facing Room, or application-specific systems such as AutoDisco. It prepares the **candidate recompositions** those systems may later instantiate.

```text
ARTIFACTS
  ↓
DISCOVERED PRIMITIVES
  ↓
MIGRATABLE PARTS
  ↓
CROSSING CANDIDATES
  ↓
BOUNDARY CHECKS
  ↓
RECOMMENDED EXPERIMENTS
  ↓
HUMAN SELECTION
  ↓
EXECUTION ELSEWHERE
  ↓
RECEIPTS / OBSERVATIONS
  ↓
RESEED
```

## Governing laws

```text
RECOMMENDATION != SELECTION
CROSSING != COLLAPSE
EXAPTATION != AUTHORITY
RESEED != CANON
```

The executable refuses to recommend a crossing when any declared boundary check is not `pass`.

It also requires every crossing to carry evidence references and a bounded experiment declaration.

The present ranking is intentionally boring and inspectable:

1. reversible before non-reversible;
2. lower declared cost before higher cost;
3. more evidence references before fewer;
4. stable crossing ID as the final tie-breaker.

Those heuristics are **recommendation order only**.

No RSC score is treated as truth, authority, or execution permission.

## Input

An `rsc.seed` packet contains:

- current artifacts;
- each artifact's current role;
- observed primitives;
- migratable parts;
- boundaries that must survive;
- proposed crossings;
- evidence for each crossing;
- explicit boundary checks;
- one bounded experiment per crossing;
- declared readiness.

Schema:

`schemas/rsc-seed.v0.json`

## Output

The Composer emits an `rsc.reseed-packet` containing:

- current artifact summaries;
- discovered primitives;
- migratable parts;
- boundary inventory;
- crossing candidates;
- held crossings and reasons;
- up to three recommended next experiments;
- explicit `human_selection_required: true`;
- a content-derived reseed ID.

The output is material for another cycle.

It is not canon.

## Run

From the repository root:

```bash
python3 ghot/rsc_composer.py experiments/rsc-live-crossing-001.seed.json
```

Or persist the packet:

```bash
python3 ghot/rsc_composer.py \
  experiments/rsc-live-crossing-001.seed.json \
  --output .ghot/rsc/rsc-live-crossing-001.result.json
```

Tests:

```bash
python3 experiments/test_rsc_composer.py
```

---

# Live Crossing 001 — Freshness Is a Capability

The first specimen crosses four existing surfaces:

- **GHoT** — capability offers, deterministic scheduling, execution, receipts;
- **reLATTE / Super Relatte** — portable crossing grammar, local disposition, lineage, non-collapse;
- **AutoDisco First-Listen Radio** — mechanically fresh listeners and a declared lineage-aware Archivist;
- **ROroomOM** — prepare/inspect/approve/execute, no inherited grants, guest-port lineage.

## What each artifact currently knows

### GHoT

GHoT can discover bodies, describe offers, select an eligible body using inspectable policy, execute bounded capabilities, and issue receipts.

Its scheduler currently treats capability primarily as **what work a body can perform**.

### reLATTE

reLATTE can carry a bounded crossing without making the carrier or sender the receiver's authority.

Super Relatte explicitly preserves:

```text
PROJECTION != AUTHORITY
DOOR != CROSSING
RECOMMENDATION != SELECTION
ANCESTRY != AUTHORITY
```

Its Composition Pulse additionally demonstrates that observations, witnesses, questions, adaptations, descendants, and returns can remain attributable without collapsing into one global authority.

### AutoDisco First-Listen Radio

First-Listen Radio contains a different kind of constraint.

An ordinary DJ must not merely be *told* to act surprised.

Its context is mechanically bounded so the first hearing is real.

The Archivist is a declared exception with authorized lineage access.

Therefore the meaningful difference between the two organs is not only personality or model choice.

It is **permitted knowledge state**.

### ROroomOM

The Room already has a suitable human-facing boundary:

```text
PREPARE
  ↓
INSPECT
  ↓
EXPLICIT APPROVAL
  ↓
EXECUTE
  ↓
RECEIPT
```

Its developmental and guest-port work additionally preserves a crucial law: a descendant or guest does not inherit executable grants merely because a relationship exists.

## Discovered primitive

The crossing exposes a new candidate primitive:

# Epistemic Capability Contract

A capability declaration may specify not only:

> what can this organ do?

but also:

> what may this organ know while doing it?

Candidate postures:

```text
fresh
bounded-window
lineage-enabled
owner-local
```

Examples:

```text
listen.analyze
context_posture = fresh
catalog_lineage = forbidden
window = current-track
```

versus:

```text
archive.compare
context_posture = lineage-enabled
catalog_lineage = allowed
sources = required
```

This is not an identity claim.

It is not a trust score.

It is not proof that isolation occurred.

It is an explicit execution constraint that can later be checked and receipted.

```text
MEMORY POSTURE != IDENTITY
CONTEXT GRANT != AUTHORITY
DISTRIBUTION != INDEPENDENCE
```

## Why this matters outside radio

The First-Listen DJ is only the first obvious specimen.

The same primitive applies to:

- blind review;
- independent model critique;
- juried creative selection;
- before/after usability evaluation;
- reproducibility checks;
- memory-isolated agents;
- adversarial review;
- fresh-reader manuscript response;
- archival comparison;
- contamination-sensitive research workflows.

“Forgetfulness” stops being merely absence.

Under a declared contract it becomes an **operational property of an organ**.

## Composer result

The current seed contains three proposed crossings.

### Recommended 1 — Fresh Listener as a schedulable GHoT capability

**Declared cost:** small  
**Reversible:** yes

Build a bounded specimen in which the same analysis capability is offered under two different context postures:

- fresh;
- lineage-enabled.

Each task should bind a digest of the exact supplied context into its receipt.

The experiment does not need an LLM initially. A deterministic fake worker is sufficient to prove the contract shape.

### Recommended 2 — ROroomOM Epistemic Instrument card

**Declared cost:** medium  
**Reversible:** yes

Add an RSC-facing instrument card that can display:

- the candidate crossing;
- the requested context posture;
- what context will cross;
- what context is forbidden;
- preserved boundary laws;
- the proposed destination;
- the expected receipt.

The human chooses whether to cross.

### Held — Two-body sealed first-listen broadcast

This is the exciting larger experiment, but it is correctly held.

Two different machines do not establish epistemic independence.

Before this crossing becomes ready, the adapter needs an explicit context audit proving what each listener actually received.

That hold is not failure.

It is exactly what RSC Composer is for: preserving the interesting future experiment **without laundering an unresolved boundary into readiness**.

## Next reseed

If Experiment 1 succeeds, feed its receipts back into RSC with a new question:

> Can `context_posture` become a normal GHoT offer/task constraint while reLATTE carries its portable declaration and ROroomOM remains the human selection surface?

If yes, First-Listen Radio stops being an isolated media trick.

It becomes the first application of a general capability system where **knowledge access itself is schedulable, bounded, inspectable, and receipted**.

That would be a genuine new organ produced by the crossing.
