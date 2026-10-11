# AI RECOMPOSITION 001 — The Thinking Workbench

**Status: draft experiment, stacked on GHoT Instrument Rack 001 (#69).**

This is a real bounded native two-route processing demonstration, **not** a new
trained model, distributed GPU, automatic intelligence, user-installed service,
or production-safe inference sandbox.

## Architectural cut

```
human text → explicit PLAN (no execution)
   → [profile: deterministic Unicode word statistics]
   → [optional: locally installed llama-cli + GGUF interpretation]
   → exact-card Instrument Rack dispatch
   → signed GHoT reLATTE-shaped crossing
   → native donor result + signed execution receipt
   → portable seed packet (NOT ADMITTED)
   → comparison report (quality UNASSESSED)
   → cold signed packet verification
```

The GHoT instrument-card family stays owned by Instrument Rack. This experiment
adds one opted-in external adapter, not a second execution bus. The deterministic
route is independent of any language model. The optional model route calls the
**real native local** `llama-cli` executable; tests substitute an obviously fake
local executable, explicitly without claiming real neural inference in CI.

## Use

From the GHoT repository root on an operator-controlled machine:

```sh
export GHOT_HOME="$PWD/.ghot-ai-private"
export GHOT_ADAPTER_MANIFESTS="$PWD/integrations/ai-recomposition-001/adapter-manifest.json"
printf 'Rosemary grows. Rosemary remembers.\n' > /tmp/ai001-input.txt

python3 ghot/ai_recomposition.py plan --mode profile \
  --text-file /tmp/ai001-input.txt --out /tmp/ai001-plan.json

python3 ghot/ai_recomposition.py run --text-file /tmp/ai001-input.txt \
  --plan-file /tmp/ai001-plan.json --approve-exact-plan \
  --dispatch-source operator-001 --out /tmp/ai001-report.json

python3 ghot/ai_recomposition.py verify --report-file /tmp/ai001-report.json
```

The `plan` action does not invoke either organ. The `run` action requires
the exact current plan, original input, operator-selected mode, positive approval
flag and attributable dispatch source. Replaying an identical completed dispatch
reuses its original signed result rather than invoking the donor again. A
prepared dispatch with ambiguous outcome is not retried automatically.

To exercise **both** routes, first explicitly install `llama-cli` and provide
a locally stored model:

```sh
export GHOT_AI_MODEL_PATH=/private/path/to/your/model.gguf
python3 ghot/ai_recomposition.py plan --mode both \
  --text-file /tmp/ai001-input.txt --out /tmp/ai001-both-plan.json
```

Run the selected `both` plan using the `run` command above with the second
plan file and a new report path. `--mode both` refuses during planning if the
model file or executable is unavailable. Capability-card discovery alone does
**not** attest that an accelerator or valid model is installed. The executor
rechecks model availability before inference. Native llama.cpp versions and
model compatibility still require a real operator-host acceptance test.

## Scope and privacy

- **No cloud provider**, outbound API, autonomous tool invocation, arbitrary
  remote shell or automatic model installation. The only subprocesses are
  the opted-in Python adapter and a fixed local `llama-cli` command.
- Model prompt passes through a mode-0600 temporary **file** rather than a
  process argument. Some llama.cpp versions echo prompt contents in stdout;
  text and generated output are **sensitive** and remain owner-local.
- `GHOT_HOME` retains signed dispatch records and raw task inputs. JSON plan
  and report files can also contain private text. Protect these locations,
  never commit a real report, and use appropriate retention and deletion.
- `--temp 0` is used for repeatability, but does **not** prove deterministic
  inference across runtimes, hardware, or model versions.
- Full local GGUF SHA-256 is computed to bind the model bytes, though native
  binary/execution/hardware are not thereby verified.
- The demo does **not** rank answer quality, identify correct interpretations,
  solve model calibration, or claim general performance gains.
- The signed GHoT receipt witnesses a local adapter attempt. It does not
  establish a human identity, prove the output true, grant recipient admission,
  or equal a receiver-signed reLATTE R3 HOLD.
- Report verification checks native signed GHoT packets and input binding; it
  is not an independent model reproduction or full cross-world receiver.

## Test

```sh
python3 -m unittest discover -s tests -p 'test_ai_recomposition_001.py' -v
```

Tests exercise an actual local GHoT Instrument Rack subprocess dispatch, P-256
signing and packet validation with lexical statistics and a fake
`llama-cli` executable. They enforce explicit approval, exact input/plan
binding, historical replay, model-not-ready refusal and tamper rejection.

## STACK² relationship

- CANNON may **source-pin** this experiment and propose it as a typed Stack Card.
- STACK² composition is not run permission. A fresh operator exact-plan approval
  remains necessary at the native GHoT boundary.
- A signed local GHoT instrument receipt is not silently promoted into the
  CANNON 018 native receiver's signed R3 HOLD. That crossing requires its own
  verified reLATTE receiver workflow.
- Branch and donor history remain intact. This branch should stay draft until
  CI and real GGUF smoke tests are independently witnessed.

**RECOMPOSITION != REPLACEMENT.**
**CARD != RUN.**
**REPORT != QUALITY PROOF.**
**MODEL OUTPUT != ADMITTED BELIEF.**
**SIGNED != TRUE.**
