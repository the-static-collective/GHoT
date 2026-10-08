# THE UNHEARD CHOIR 001 — Attention Before Action

**Owner:** GHoT / experimental attention instrument. **Status:** deterministic, no-network specimen; not a live listener, AI agent, need-verification service, or radio receiver.

## Question

When a low-salience human need appears beside eleven competing simulated observations, does a finite-budget machine notice the need, or spend its entire attention budget on loud signals?

This experiment is deliberately falsifiable: the loudest-first policy and protected-attention policy inspect the **same exact source cut**. Their selection, non-selection and candidate-question records can be compared and replayed.

## Run

From the GHoT repository root, using only Python 3 standard library:

```sh
python3 ghot/unheard_choir.py compare --fixture fixtures/unheard-choir-001/world.json
python3 ghot/unheard_choir.py run --policy protected --fixture fixtures/unheard-choir-001/world.json > /tmp/choir-receipt.json
python3 ghot/unheard_choir.py verify --fixture fixtures/unheard-choir-001/world.json --receipt /tmp/choir-receipt.json
python3 -m unittest discover -s tests -p 'test_unheard_choir.py' -v
```

A cold process independently recomputes the receipt from exactly the provided source world. The receipt has a canonical SHA-256 integrity digest, **not** a digital signature, verified identity, native reLATTE receipt or admissible crossing.

## The controlled encounter

- Eleven ordinary simulated sources: three radio cues, three system anomalies, two available materials, three research questions.
- A **twelfth** source, `quiet-neighbor`, declared `human_need` at salience **0**, attention cost **1**, with explicitly declared `consent_to_review: true`.
- Total attention budget: **4 units**.
- `repeater-east` costs two units; higher-salience sources consume the rest before the quiet signal under the baseline policy.
- `loudest`: greedily attends to high-salience sources, with stable ID tie-breaks.
- `protected`: reserves *one slot* for the highest-ranked declared, opted-in human need that fits, then uses the same loudest-first heuristic with the remaining budget.

The protected rule is a **human-chosen policy assumption**, not an unbiased or learned conclusion that the human need is true, useful, urgent or ethically superior. Its expected outcome is intentionally built into the fixture. If a fixture has no eligible need, the protected policy reduces to loudest-first. The comparison demonstrates a **selection tradeoff**, not superior real-world performance.

## What is evidenced

The deterministic receipt exposes:

```text
exact fixture
  → validate source identities and simulated-only claims
  → finite-capacity attention selection
  → per-source ATTENDED / OBSERVED_NOT_ATTENDED / HELD_UNREVIEWED
  → inspectable reason for each selection and omission
  → proposed questions and proposed probes
  → integrity digest and cold replay
```

For every presented source, the record includes provenance handle, declared status, salience, cost, attention disposition and reason. Every selected signal produces a fixed, source-bound question; all proposals have `executed: false` and `requires_fresh_owner_admission: true`.

**A question is not an instruction.** No subprocess or remote execution, receiver admission, fundraising, broadcast, radio transmission, household contact, data forwarding, GHoT dispatch or material movement occurs. Reading a consent flag is **not** evidence that consent was independently obtained.

## Epistemic limits

1. `SIMULATED_OBSERVED` means a declared fixture input, not actual sensory reception. We do not know the unobserved world; omissions are known only within the presented fixture.
2. Salience is preassigned. There is no learned salience, AI semantic comprehension, independent human classification, real need assessment, or utility measurement.
3. The human-need category and consent flag can be forged by whoever authors a fixture. Never accept this shape as proof of an individual's wishes.
4. This fixture contains no identities, locations, contact information or private need narratives. Any future real-need adapter must handle privacy, minimization, consent verification, retention and revocation separately.
5. The first question under the protected policy comes from the protected slot. It is a deterministic policy consequence, not emergent moral reasoning.
6. This module issues local **unsigned** comparison receipts. It must not be described as a reLATTE signed crossing, validated GHoT task, or native Autodisco output.

## Non-collapse laws

```text
HEARD != UNDERSTOOD
OBSERVED != ATTENDED
UNOBSERVED != NONEXISTENT
SALIENCE != CONSEQUENCE
DECLARED NEED != VERIFIED NEED
CONSENT FLAG != CONSENT EVIDENCE
ATTENTION != PERMISSION
QUESTION != COMMAND
PROPOSAL != EXECUTION
DIGEST != SIGNATURE
SELECTED != HELPED
SIMULATION != PHYSICAL ENCOUNTER
```

## Relation to other owning repos

- **GHoT** owns this attention-selection experiment. Existing Instrument Rack and Listening Heap work remains independently governed in [PR #69](https://github.com/the-static-collective/GHoT/pull/69), [#71](https://github.com/the-static-collective/GHoT/pull/71), [#72](https://github.com/the-static-collective/GHoT/pull/72), and [#73](https://github.com/the-static-collective/GHoT/pull/73). None is silently imported or bypassed.
- **Static-OS** owns future instrument hosting, control dials and owner interfaces, including its separately stacked [INSTRUMENT HOST 001](https://github.com/the-static-collective/static-os/pull/54). A score must not become a GHoT task merely because a dial moves.
- **Autodisco** owns actual first-encounter/artifact interpretation; the questions here are local deterministic templates, **not** AutoDisco-produced interpretations.
- **reLATTE** owns portable crossing syntax, verified signatures, sovereign RECEIVE/HOLD and owner-local consequence. This specimen neither implements nor replaces those gates.
- **Full Measure** owns human participation, help routing and authority. A declared need can at most propose a *future bounded owner-reviewed handoff*. Nothing is automatically matched, published or fulfilled.

## Promotion gates

1. Replace the simulated fixture with an explicitly opted-in typed source adapter that proves only what it actually observed; preserve coverage gaps and real source authority.
2. Test multiple adversarial policy worlds (fake human needs, many competing quiet needs, no consent, withdrawn need, hidden relevant signals, unequal attention costs, corrupt signal feeds, missing sources) before treating protected allocation as a reasonable default.
3. Introduce independent outcome measures: whether a source-grounded question yields novel discriminating information per unit of attention, and whether its opportunity cost is acceptable. Do not bake the hoped-for outcome into evaluation.
4. Integrate **proposal only** into the GHoT Rack/Static-OS host through explicit supported interfaces. Record current capability/card incarnations; deny stale or withdrawn selection.
5. Submit any desired actual GHoT dispatch through its own fresh approval and native signed dispatch; submit any reLATTE crossing through its real verification/RECEIVE/HOLD gates. No custom shortcut.
6. Obtain separately reviewed real-world privacy, spectrum, hardware and local authority gates before physical sensors or human-needs operations.

### Sharp next experiment

**UNHEARD CHOIR 002:** hide a meaningful source from the input field and compare *attention allocation* with *active instrument selection*. Can the system detect its blind spot, request a bounded new observation, and refrain from treating absence of a measurement as silence?
