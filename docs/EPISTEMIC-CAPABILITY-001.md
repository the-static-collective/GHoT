# GHoT Epistemic Capability 001

**Status:** bounded executable experiment  
**Parent:** RSC Composer 001  
**Branch:** `epistemic-capability-001`

## Thesis

A capability is not fully described by what an organ can do.

For some work, correctness also depends on **what the organ was allowed to know while doing it**.

GHoT Epistemic Capability 001 makes that constraint explicit as:

```text
context_posture
```

The first postures are:

- `fresh`
- `bounded-window`
- `lineage-enabled`
- `owner-local`

This experiment is derived from the RSC Composer 001 crossing of GHoT, reLATTE, AutoDisco First-Listen Radio, and ROroomOM.

## Governing laws

```text
MEMORY POSTURE != IDENTITY
CONTEXT GRANT != AUTHORITY
CONTEXT DIGEST != CONTEXT CONTENT
DISTRIBUTION != INDEPENDENCE
```

A posture is an execution constraint.

It is not a psychological assertion about the worker.

It does not prove identity, memory, consciousness, independence, trustworthiness, or authority.

## Scheduler change

`ghot/capability_composer.py` now accepts an optional `context_posture`.

Posture is an **eligibility constraint**, not a preference score.

For a request such as:

```text
capability = listen.analyze
context_posture = fresh
```

a body offering only:

```text
listen.analyze
context_posture = lineage-enabled
```

is ineligible even if it has more RAM, better power state, or would otherwise receive the highest deterministic score.

This preserves:

```text
CAPABILITY MATCH
  +
EPISTEMIC POSTURE MATCH
  ↓
ELIGIBILITY

ELIGIBILITY
  ↓
PREFERENCE SCORING
```

A preference can choose among eligible workers.

A preference cannot waive an epistemic boundary.

## Record extension

The existing v0 schemas remain backward-compatible and gain optional epistemic fields.

### OFFER

```json
{
  "kind": "ghot.offer",
  "version": "0",
  "capability": "listen.analyze",
  "context_posture": "fresh",
  "available": true
}
```

### TASK

```json
{
  "kind": "ghot.task",
  "version": "0",
  "capability": "listen.analyze",
  "context_posture": "fresh",
  "context": {
    "current_track": {
      "id": "track-001"
    }
  }
}
```

### RECEIPT

```json
{
  "kind": "ghot.receipt",
  "version": "0",
  "capability": "listen.analyze",
  "context_posture": "fresh",
  "context_audit": {
    "supplied_context_sha256": "...",
    "supplied_context_keys": ["current_track"],
    "forbidden_context_keys_present": []
  }
}
```

The receipt binds the exact supplied context through canonical JSON SHA-256 without requiring that the receipt duplicate the context itself.

```text
DIGEST BINDS CONTEXT
DIGEST != DISCLOSURE
```

## Deterministic fake workers

`ghot/epistemic_capability.py` intentionally does **not** call an LLM.

It exposes deterministic fake workers so the contract can be tested independently of model behavior.

Both workers offer the same nominal capability:

```text
listen.analyze
```

But their posture differs.

### Fresh worker

Requires:

```text
current_track
```

Forbids:

```text
catalog_history
prior_dj_transcripts
motif_index
hidden_retrieval
```

If any forbidden key is present, execution is rejected and the receipt records the contamination.

### Lineage-enabled worker

Requires:

```text
current_track
lineage_sources
```

This models the First-Listen Radio distinction between an ordinary mechanically fresh DJ and the declared Archivist role.

## Demo

Run:

```bash
python3 ghot/epistemic_capability.py
```

The demo emits three specimens:

1. fresh worker + bounded current-track context → `ok`
2. lineage-enabled worker + explicit lineage sources → `ok`
3. fresh worker + leaked catalog history → `rejected`

The third case is the important one.

The worker is not asked to “please ignore” forbidden history.

The task fails its declared contract.

## Tests

Run:

```bash
python3 experiments/test_epistemic_capability.py
```

The test suite checks:

1. a high-resource lineage worker cannot satisfy a fresh scheduler request;
2. a fresh receipt carries the exact context SHA-256;
3. leaked catalog history causes rejection;
4. lineage-enabled mode requires explicit lineage sources;
5. the demo contains successful fresh/archive paths and a rejected contaminated path.

## Why this is not merely an AutoDisco feature

The same contract shape can support:

- blind peer review;
- independent model critique;
- fresh-reader manuscript reaction;
- jury or panel isolation;
- before/after evaluation;
- adversarial review;
- contamination-sensitive research;
- reproducibility experiments;
- bounded-memory agents;
- archival comparison.

AutoDisco gave us the clearest specimen because “first listen” makes contamination intuitively obvious.

RSC revealed the more general primitive.

## Next crossing

Once this contract survives real execution, the next bounded crossing is:

```text
RSC RESEED PACKET
      ↓
ROroomOM INSTRUMENT DECK
      ↓
human inspects:
  capability
  context posture
  supplied context
  forbidden context
  destination
  expected receipt
      ↓
explicit selection
      ↓
GHoT plan
      ↓
execution
      ↓
context-audited receipt
```

That would give Recursive Systems Composition a human-visible cockpit while preserving:

```text
RECOMMENDATION != SELECTION
PREPARE != EXECUTE
CONTEXT GRANT != AUTHORITY
```
