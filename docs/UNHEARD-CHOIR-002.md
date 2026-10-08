# UNHEARD CHOIR 002 — The Instrument That Notices Its Own Blind Spot

**Status:** deterministic fixture-only experiment stacked on [UNHEARD CHOIR 001](https://github.com/the-static-collective/GHoT/pull/74). No physical instrumentation or native crossing.

## Question

Can a bounded question engine notice that a **declared aperture has not been measured**, propose an existing instrument for one new observation, and preserve the distinction between:

```text
NO INPUT IN THIS APERTURE
!=
THE APERTURE WAS MEASURED AND WAS EMPTY
!=
NOTHING EXISTS IN THE WORLD
```

002 tests only *declared* coverage gaps. An undeclared gap is not magically detectable, and the hidden fixture is not a fact available to the planner.

## Actual executable sequence

```text
UNHEARD CHOIR 001 / 11 simulated observations
  + separate declared-coverage catalogue (NO twelfth signal)
    -> verify world digest, source cut, costs, instrument incarnation
    -> proposal-only rank: declared gain proxy / exploration cost
    -> selected "community-queue" instrument (1 of 2 exploration units)
    -> HOLD: no fixture data read, no instrument execution, no owner consent presumed

EXPLICIT EXACT PROPOSAL + APERTURE SIMULATION APPROVAL
    -> fresh same-cut and same-instrument revalidation
    -> bounded fixture-only read of hidden source
    -> either SIMULATED_EMPTY_WINDOW or simulated signal or CONSENT HOLD
    -> re-run actual 001 attention engine on the new simulated observation
    -> cold-verifiable unsigned digest receipt
```

One demonstration fixture holds 11 seen sources. The twelfth source, `quiet-neighbor`, is stored in a **separate oracle file**, not in the planner world or field catalogue. The catalogue contains only three named, previously unobserved apertures with fixed **invented proxy gains**, declared costs, and simulation capability metadata:

| Aperture | Gain proxy | Cost | Availability |
| --- | ---: | ---: | --- |
| radio-far-edge | 11 | 3 | eligible to consider, but unaffordable with budget 2 |
| community-queue | 7 | 1 | eligible, **proposed** |
| material-backlog | 5 | 2 | eligible, not selected |

The planner has **no knowledge** of whether any particular aperture contains a source. It cannot read `hidden-oracle.json` during proposal planning; the oracle is an explicitly supplied **test fixture**, not cryptographically secret data. Anyone reading the full public repo can see the fixture. Only the bounded program's *information path* is blind to it.

The separate 2-unit **exploration** budget does not pretend to recycle the four attention units already used by UNHEARD CHOIR 001. The proposed gain is a hand-authored score, not measured utility.

## Run

Requires Python 3 stdlib only. From the GHoT root:

```bash
python3 ghot/unheard_choir_blindspot.py plan \
  --world fixtures/unheard-choir-002/observed-world.json \
  --field fixtures/unheard-choir-002/field.json \
  > /tmp/choir002-proposal.json
```

Inspect the proposal. It **does not** read the hidden fixture, perform a probe, spend budget, or grant a capability.

Explicitly select the proposed aperture for the *simulation only*:

```bash
PROPOSAL_ID=$(python3 -c 'import json; print(json.load(open("/tmp/choir002-proposal.json"))["proposal_digest"])')
python3 ghot/unheard_choir_blindspot.py simulate \
  --world fixtures/unheard-choir-002/observed-world.json \
  --field fixtures/unheard-choir-002/field.json \
  --plan /tmp/choir002-proposal.json \
  --oracle fixtures/unheard-choir-002/hidden-oracle.json \
  --approve-proposal "$PROPOSAL_ID" \
  --approve-aperture community-queue \
  > /tmp/choir002-receipt.json
```

Verify from a fresh process:

```bash
python3 ghot/unheard_choir_blindspot.py verify \
  --world fixtures/unheard-choir-002/observed-world.json \
  --field fixtures/unheard-choir-002/field.json \
  --plan /tmp/choir002-proposal.json \
  --oracle fixtures/unheard-choir-002/hidden-oracle.json \
  --receipt /tmp/choir002-receipt.json \
  --approve-proposal "$PROPOSAL_ID" \
  --approve-aperture community-queue
```

Run hostile test suites:

```bash
python3 -m unittest discover -s tests -p 'test_unheard_choir.py' -v
python3 -m unittest discover -s tests -p 'test_unheard_choir_blindspot.py' -v
```

The exact proposal digest and selected aperture are **explicit test authorization input**, *not cryptographic operator identity*, source-owner permission, privacy consent or a substitute for native GHoT dispatch. The CLI rejects absent/mismatched approvals **before reading the oracle path**.

## What two worlds prove

*Unobserved:* the planner can identify `community-queue` as a coverage gap and propose `inbox-fixture-readonly` without seeing what is there. The ordinary 001 attention engine only sees the original 11 signals.

*Simulated observed:* a separately approved read of the hidden fixture returns `quiet-neighbor` (declared low salience, `human_need`, with a fixture consent flag). The same 001 engine receives a **new simulated world cut** and notices the source under its protected attention policy.

A different fixture can return `SIMULATED_EMPTY_WINDOW`. That means no simulated fixture signal was returned by this bounded read. It is **not** evidence of no real-world signal. If a human-need fixture has `consent_to_review=false`, the engine emits `HELD_UNREVIEWED_DECLARED_CONSENT` without disclosing the source into a new attention world.

## Preserved constraints

- Exact source cut and field digests, instrument identity, owner epoch, availability, budget, source group, and fixture identity are checked again *after* planning.
- Stale proposals, withdrawn instruments, forged/differing selection, unauthorized/unaffordable probes, unknown source types, duplicate source identity, fabricated physical observation status, injected commands and forged receipts are denied.
- No input-specific oracle result may influence the **proposal**.
- A proposal is not operator selection. The mock approval is not native authority; no signed reLATTE receipt is claimed.
- The signed/native GHoT Instrument Rack #69 and Listening Heap #71 / Radio Ear #72 / Radio Attention #73 are separate unmerged work. This experiment does not assume they landed.
- Nothing contacts a human, inspects a real inbox, monitors spectrum, executes GHoT work, reveals actual private information, or commits an owner-local consequence.

```text
COVERAGE DECLARATION != WORLD COMPLETENESS
BLIND SPOT != HIDDEN CONTENT KNOWLEDGE
PROXY GAIN != OBSERVED INFORMATION GAIN
PROPOSAL != APPROVAL
SIMULATION APPROVAL != SOURCE OWNER AUTHORITY
EMPTY INSTRUMENT RETURN != GLOBAL SILENCE
ATTENTION ALLOCATION != INSTRUMENT DISPATCH
INSTRUMENT CAPABILITY != PERMISSION
SOURCE MENTION != VERIFIED HUMAN NEED
DIGEST != SIGNATURE
```

## Promotion / next hostile experiment

**UNHEARD CHOIR 003 — THE FALSE APERTURE:** flood the machine with invented high-gain blind spots, malicious instrument catalogues, and withdrawn or privately owned probe offers. Can the engine decline a loud but untrusted instrument, ask for the provenance of its *coverage map*, and measure real information improvement instead of trusting an author-declared expected-gain score?

Only after independent source provenance and actual authorization should 002's proposal become a candidate for the existing native GHoT dispatch / Static-OS Instrument Host / reLATTE RECEIVE-HOLD pathway. That integration must be separately proven and reviewed.
