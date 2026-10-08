# RADIO-ATTENTION-003 — Second Ear / Selective Listening

Status: draft, stacked on RADIO-EAR-002 (#72) → LISTENING-HEAP-001 (#71) → INSTRUMENT-RACK-001 (#69). No normative core changes and no transmitter.

## Executable proposition

- Owner lists 2–3 specific center frequencies and **two distinct receiver indices** (0–7). The index distinction is not independently verified physical identity.
- GHoT generates proposal-only, exact-card-bound SURVEY plan. No hardware is invoked.
- A separate explicit owner approval permits exactly that bounded sequential survey; each sample window has a distinct native GHoT signed reLATTE-shaped crossing, signed receipt, exact portable raw I/Q bytes and SHA-256.
- From the VERIFIED raw-data-derived eight uncalibrated TIME-window amplitude values, a fixed heuristic proposes one focus target. It is NOT a true FFT spectral scan or a station detector.
- Another owner approval permits exactly one focused capture through the second device index, with a separately signed GHoT dispatch. No autonomous physical execution.
- A deterministic comparator notes amplitude disagreement; it is NOT an Autodisco AI response. It proposes repeating a disputed frequency or exploring the runner-up, but **cannot execute that next action**.
- A combined SVG over the two independently captured evidence packets is fed to the actual native Autodisco v20 LOOK-TWICE PREPARE producer. This earns two isolated first-listen PACKETS, not model responses or dialogue.

## Boundaries

SURVEY != ALL SPECTRUM; DEVICE INDEX != INDEPENDENT PHYSICAL RADIO; SEQUENTIAL SAMPLE != SIMULTANEOUS OBSERVATION; NON-OBSERVATION != SILENCE; AMPLITUDE != INFORMATION VALUE; AI PACKET != AI RESPONSE; PROPOSAL != SELECTION; RX != TX; SIGNED != PHYSICALLY TRUE.

The survey is sequential and preserves its **unobserved gaps**. The hardware program is receive-only rtl_sdr (inherited from #72). Driver success is a host report; no antenna, RF source, unique physical receiver ID, calibration, clock accuracy, overrun or independent signal identity is certified. The later AI reasoning model remains separately gated; don't pretend the deterministic comparator is a real Autodisco model.

Fixed heuristic: rank frequency by sum of eight noncalibrated time-amplitude values (not Fourier bins). For chosen center frequency, difference between survey and focus sums ≥16 proposes repeat, otherwise proposes the runner-up. This is a demonstration policy, NOT learned optimal active inference, and is not calibrated across receivers.

## Test

    python3 ghot/radio_attention_sim.py

With a real checked-out Autodisco v20:

    AUTODISCO_LOOK_TWICE_SCRIPT=/path/to/v20/scripts/look-twice.mjs python3 ghot/radio_attention_sim.py

CI uses a fake rtl_sdr executable with predeclared differences between frequencies and receivers. It checks signed GHoT dispatch/portable IQ packets, freshness and replay, explicit owner approvals, instrument index/frequency role, adulterated provenance and false source claims. It then invokes **real v20 native prepare** from pinned producer commit 1e06cee07061116eb31afbcdc60b34971ee5b130.

## Optional two-radio operator command sequence

Two RTL-SDR devices must actually be installed, independently identified by the operator, and approved to receive the selected signals. The driver accepts indices only, not hardware identity proofs. Choose a private directory for all evidence JSON; individual output files are created with mode 0600 without overwrite. Handle raw I/Q samples with appropriate privacy and retention.

Create a JSON file /tmp/attention-spec.json:

    {
      "schema": "ghot.radio-attention-field-spec/v0",
      "surveyor_index": 0,
      "listener_index": 1,
      "frequencies_hz": [162400000, 162475000, 162550000],
      "sample_rate_hz": 1024000,
      "survey_complex_samples": 4096,
      "focus_complex_samples": 8192,
      "rx_scope": "public-or-otherwise-authorized"
    }

Examples are allocated weather-radio centers, not a guarantee of locally detectable broadcasts. Configure explicit opt-in:

    export GHOT_ADAPTER_MANIFESTS="$PWD/integrations/radio-ear-002/adapter-manifest.json"

Plan, inspect, then separately approve the survey:

    python3 ghot/radio_attention_operator.py plan-survey --spec-file /tmp/attention-spec.json --out /tmp/survey-plan.json
    python3 ghot/radio_attention_operator.py run-survey --spec-file /tmp/attention-spec.json --plan-file /tmp/survey-plan.json --approve-receive-only --operator local-operator --out /tmp/survey.json

Plan, inspect, then separately approve the second receiver's focus:

    python3 ghot/radio_attention_operator.py plan-focus --survey-file /tmp/survey.json --out /tmp/focus-plan.json
    python3 ghot/radio_attention_operator.py run-focus --survey-file /tmp/survey.json --plan-file /tmp/focus-plan.json --approve-receive-only --operator local-operator --out /tmp/focus.json

Only compare and propose a next listen, no further capture:

    python3 ghot/radio_attention_operator.py compare --survey-file /tmp/survey.json --focus-file /tmp/focus.json --out /tmp/compare.json

Produce native v20 first-listen PACKETS (no model inference):

    python3 ghot/radio_attention_operator.py prepare-autodisco --survey-file /tmp/survey.json --focus-file /tmp/focus.json --autodisco-script /path/to/v20/scripts/look-twice.mjs --out /tmp/first-packets.json

## Physical gates remaining

Actual connected two-receiver field test, continuous scan scheduler, calibration and independent clock/identity evidence, real Autodisco first-encounter model response, meaningful information-gain metric, radio law/privacy review and separately authorized transmitting hardware. None of those is presented as complete by hosted CI.

A future revision may bind a genuinely model-produced (verified) recommendation as advisory to GHoT, but a model claim may never grant receiver execution or TX authority by itself.
