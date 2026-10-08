# UNHEARD CHOIR 005 — THE COLLUDING OBSERVERS

**Owner:** GHoT. **Status:** bounded executable synthetic-evidence experiment, stacked on 004 → 003 → 002 → 001. All source data and observation outcomes are explicitly fictional. No physical sensor, live radio reception, owner identity verification, native GHoT dispatch, or reLATTE admission.

## The failure of consensus

004 authenticates signed claims and notices disagreements. But three agreeing signatures, even on three distinct keys, may merely reflect coordinated deception.

005 proves a narrower, testable distinction: *claimant consensus* versus *a separately pinned and recomputed sample-based observation from a bounded simulation fixture*.

```text
003 current bounded instrument proposal
  ↓
004 fresh owner-signed nonce + instrument epoch + roster binding
  ↓
Three distinct P-256 claimant keys
  SOURCE          → PRESENT [valid signature]
  OBSERVER EAST   → PRESENT [valid signature]
  OBSERVER WEST   → PRESENT [valid signature]
  ↓
004: REVIEW_CANDIDATE_NOT_ADMITTED
  ↓
Fifth distinct, locally pinned P-256 fixture-instrument key
  ├─ earlier timestamp-declared PRECOMMIT for exact 8 frames, source cut and epoch
  └─ challenge-bound signature over those 8 raw simulated frames
       → deterministic ANY_NONZERO profile
       → [0,0,0,0,0,0,0,0] maps to EMPTY
  ↓
005: HOLD_COLLUDING_CLAIMS_CONFLICT_WITH_SIMULATED_MEASUREMENT
```

**Six real cryptographic signatures:** one 004 challenge, three 004 statements, one 005 precommit and one 005 sample-attestation. ECDSA P-256 signing/verification reuses existing GHoT `relatte_identity` code. New 005 domain-separated messages are not native reLATTE crossing/receipt objects.

## Genuine independence and its limits

1. **Key separation:** all five local keys (challenge issuer, 3 claimants, fixture instrument) must be distinct. This is cryptographically enforced against the locally supplied pinset, not a proof that five different people or sensors exist.
2. **Distinct data pathway:** the claimed `PRESENT` is never the input to `compute_outcome`. The separate raw 8-frame fixture is interpreted by a deterministic `SIMULATED_OCCUPANCY_ANY_NONZERO_V0` profile; the verifier independently recomputes the outcome.
3. **Commitment:** the sample digest and a claimed `captured_at` are signed in the separate precommit, bound to the 003 proposal, 004 roster and instrument incarnation. The challenge-bound signed measurement must reveal the same exact raw bytes.
4. **Not a trusted clock:** `captured_at` comes from the signer, and `issued_at` from the test issuer. Signature checks reject reported chronology violations but **cannot prove the sample bytes really existed before the challenge**; a malicious signer could backdate. Real prechallenge temporal proof requires an independent witness/ledger or authenticated external timestamp.
5. **Not independent physical truth:** distinct signed fixture evidence does not establish an actual physical measurement, calibration or independent instrument custody. Its source can be substituted if an attacker is allowed to replace the external trust anchor.
6. **No external effect:** even unanimous agreement between claimants and fixture samples produces `REVIEW_MATCHES_SIMULATED_MEASUREMENT_NOT_ADMITTED`. Missing fixture evidence produces HOLD. Source-witness disagreement inherited from 004 remains HOLD.

## Attacker matrix

| Attack | Expected |
| --- | --- |
| Three colluding real signatures all say PRESENT, verified fixture raw frames all zero | HOLD conflict |
| Three claimants agree but no distinct sample measurement | HOLD absent evidence |
| Three claimants agree and synthetic frames also indicate PRESENT | Review only, not truth |
| Source/observers disagree despite synthetic measurement | Preserve 004 HOLD |
| Forged or switched claimant key | Reject using 004 verification |
| Instrument signer also source/observer/owner signer | Reject key independence |
| Wrong external pinned key, stale epoch, altered world/roster | Reject |
| Changed raw samples, precommit, calibration or signature | Reject |
| Stale/expired or different challenge | Reject |
| Altered derived outcome with unchanged samples | Reject |
| Recomputed forged receipt digest | Recompute independent receipt and fail verification |
| Attacker controls *entire external instrument anchor* and signs fabricated aligned samples | Returns review-only, **does not assert real truth** |

## Run

From repository root with `python3` and `openssl`:

```sh
python3 ghot/unheard_choir_collusion.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_collusion.py' -v
```

The demo generates **temporary P-256 keys only in an ephemeral directory**. It does not commit keys, external instrument secrets or human data to GitHub. The tests also build public evidence bundles and verify them in a fresh Python process *without the private key files*.

Read-only CLI `assess` requires `--parent`, `--roster`, `--challenge`, `--statements`, `--now`; provide all of `--anchor`, `--precommit`, `--measurement` for synthetic fixture comparison. `verify` repeats the same arguments and adds `--receipt` to recompute the exact asserted result.

No operator-selected physical instrument is opened by this code. It does not use the still separately governed Instrument Rack branch or bypass native signer/receiver authority. The future interface should require an actual pinned source-owner key and fresh GHoT dispatch, then the real reLATTE receiver's RECEIVE/HOLD/ADMIT gates; those operations are **not** exercised here.

## Non-collapse

```text
THREE SIGNATURES != THREE INDEPENDENT OBSERVATIONS
CRYPTOGRAPHIC CONSENSUS != TRUTH
KEY SEPARATION != SENSOR SEPARATION
RAW FRAME RECOMPUTATION != CALIBRATED PHYSICAL FACT
SELF-REPORTED PRECOMMIT TIME != INDEPENDENT TEMPORAL PROOF
LOCAL PINSET != REAL-WORLD OWNER IDENTITY
SIGNED SAMPLE != PERMISSION TO ACT
SIMULATED MEASUREMENT != REAL-WORLD EVIDENCE
REVIEW != ADMISSION
DISAGREEMENT != DECEPTION PROVEN
```

## 006 frontier

**THE COUNTERFEIT INSTRUMENT**: the attacker now controls the data-acquisition hardware or copies the trusted sensor key. Design *independent custody receipts and physically distinct measurement modalities*, then challenge whether multiple independent observations converge without hidden shared dependencies. Native GHoT / reLATTE integration requires separately authorized acts and full fresh source-owner proof.
