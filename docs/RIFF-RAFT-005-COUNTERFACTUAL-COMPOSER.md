# RIFF-RAFT-005 — COUNTERFACTUAL QUEST COMPOSER

A GHoT organ can now use **two existing independently verified game-world observations** to propose *new* bounded experiments. It does not mutate actual land, grant new world permissions, start a GHoT executor, or infer stakeholder consent.

## Provenance anchor: a real previous result

The input is **not a story about the prior run**. GHoT requires the raw signed RIFF-RAFT-004 return artifact from [GitHub Actions 37987898459](https://github.com/the-static-collective/reLATTE/actions/runs/37987898459). GHoT's preexisting OpenSSL-backed P-256 verifier validates the final return, both signed admitted Minecraft instances, both signed held Minecraft candidates, stage order, fresh observer blockstates, world snapshots, source provenance and local `HOLD`. RIFF-RAFT-005 also pins the original return:

- Signed return crossing: `relatte-crossing-v0:0b61b9476c0ab3e2b57a5090781d2591e8c1145ac84c2eea2f67efb301d54fa3`.
- Receipt: `relatte-receipt-v0:5ad43d10051e60ce2f5d52fca00808027785b55bc31c70ff75a88f2496a06d11`.
- Byte-precise packet SHA-256: `9956d0887a5f65495cb777a5ba06aa03451946c46285930d8d96eeaa2a7d0a17`.

No new proposal exists if this specific signed source is absent, changed, incomplete, or not independently verifiable.

## What becomes a new question

The bounded composer reads each source's *actual measured* `causal_signature.broken` lamp states, not its prior proposed expectation alone. It also checks that the observed mask is physically consistent with the original missing repeater location in Minecraft.

| Previous observation | Proposed policy | Next repeater removal | Expected new in-game observation |
|---|---|---|---|
| World A, 3 lit of 9 | shift fault downstream by 2 lamp stages | x = 2 | 5 lit of 9 |
| World B, 6 lit of 9 | shift fault upstream by 4 lamp stages | x = -28 | 2 lit of 9 |

The computation uses only the existing set of legal vanilla repeater locations `[-28,-13,2,17,32]` and observed nine lamp coordinates. Unreachable, duplicate, out-of-domain, or source-disagreeing proposals HOLD and do not turn into new game commands. The two specific policies are declared, not autonomously expanded.

```text
signed source world result (R3_HOLD)
    ↓ GHoT verifies P256 signatures and raw bytes
actual observed 3/9 + 6/9
    ↓ bounded counterfactual policy, source hashes preserved
PROPOSE new game tests 5/9 + 2/9
    ↓ explicit opt-in in reLATTE Minecraft-005 only
two actual vanilla servers independently execute
    ↓ server observes deliberate fault / reset / repair
fresh non-OP protocol observers inspect each world
    ↓ two signed R3_HOLD results
reLATTE compares *distinct* source-derived expectations
    ↓ third signed R3_HOLD carrying original 004 ancestor
GHoT independently verifies all three new signed crossings
    ↓ independently RE-verifies all signed 004 source crossings
GHoT HOLD, no task launch, no physical execution
```

## Operation

```sh
python3 ghot/riff_raft_counterfactual.py \
  prior-004-return-bundle.json /tmp/riff-raft-005
python3 ghot/riff_raft_counterfactual_sim.py
python3 ghot/riff_raft_counterfactual_return_sim.py
```

The composer produces two manifests `counterfactual-A.json` and `counterfactual-B.json`, each SHA-256-bound to source's prior crossing, receipt, instance, original Minecraft observed-state digest and previous quest ID. Both declare `operator_must_select=true`, `future_game_execution_observed=false`, `owner_admission=false`, `auto_dispatch=false` and `authority_effect=none`.

The receiving program `ghot/riff_raft_counterfactual_return.py` refuses a 005 signed return if it omits the complete 004 signed ancestor, alters a source-derived quest, disagrees with its own game measurement, substitutes a result that was not actually observed, or expands authority. Good returns produce **HOLD**; the receiver has no outbound I/O or scheduler mutation path.

This is **constrained adaptive question generation**, not unconstrained machine learning. It uses source evidence to select from bounded physically legal *game* interventions. The labels about water and biomass are symbolic; **no real ecological effect, seed establishment, resource use or private-world permission is observed or implied**.

## Fragility / recovery

The current CI consumes the pinned 004 artifact. GitHub Actions artifacts are temporary (original workflow uses a 7-day retention); after expiry the new build will intentionally HOLD until the same verified source evidence is restored or the baseline is deliberately re-run and re-pinned. It must not silently regenerate a replacement source and pretend that its byte identity remained unchanged.

The next important step after proving this is a durable, independently replicated evidence custody store, with source signers backed by proper trust roots, plus a finite human-inspectable queue of alternative counterfactual interventions.

```text
OBSERVED WORLD != INTENDED WORLD
SOURCE HOLD != SOURCE DELETION
EVIDENCE -> QUESTION != EVIDENCE -> EXECUTION
FUTURE EXPECTATION != FUTURE OBSERVATION
COUNTERFACTUAL GAME SUCCESS != TERRAFORMING
```
