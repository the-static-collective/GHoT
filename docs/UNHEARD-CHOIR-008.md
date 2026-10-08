# UNHEARD CHOIR 008 — THE MISSING NODE

**Status:** executable GHoT synthetic adversarial provenance experiment, stacked on 007 → 006 → 005 → 004 → 003 → 002 → 001. No hardware sensing, human attestation, independently verified collection time, external dispatch, native reLATTE admission, or actual physical authority.

## What changed

007 verifies **every statement present in an owner-curated graph**, but cannot find an omitted dependency that every signer chose not to report.

008 introduces a separately provisioned, locally pinned P-256 **audit root** and two additional independently keyed audit roles. The externally pinned root is supplied to the verifier as a separate trust input—**not loaded from the owner-controlled 007 manifest**.

Each auditor signs a cryptographic commitment to an independently asserted *simulated path*. Each then signs a challenge- and owner-manifest-bound reveal of the entire path. The checker recomputes all ancestor cryptography from 001–007, verifies the independently pinned audit policy, both audit commitments, both reveals, and computes signed-graph discrepancies.

```text
007 owner-controlled signed graph                  008 separate signed audit reports
fixture-primary                                   fixture-primary
  → fixture-east                                    → fixture-east
  → fixture-root-a (declared terminal)             → fixture-hidden
                                                   ↑
fixture-secondary                                 fixture-secondary
  → fixture-west                                    → fixture-west
  → fixture-root-b (declared terminal)             → fixture-hidden

007: REVIEW_DECLARED_DISJOINT_SIGNED_GRAPH_NOT_ADMITTED
008: HOLD_EXTERNAL_AUDIT_CONTRADICTS_OWNER_GRAPH
```

**What has been observed?** A contradiction between *two separately pinned families of signed synthetic assertions*. This is not evidence that the physically existing world contains `fixture-hidden`. It is strong enough within the bounded policy to **refuse promotion** of an apparently complete owner-curated source graph.

## Executable source / trust boundaries

1. **Original 003–007 inputs preserved**. Every source/observer signature, P-256 challenge, instrument data, custody assertion and owner-signed graph node remains subject to inherited fresh checks.
2. **New external root pin:** the verifier receives `trusted_root` separately from the external `audit_policy`. The audit policy signature must verify against exactly that locally supplied root. The trust root is distinct from all original owner, sensor, custodian, observer and graph-controller identities. Auditors must also have distinct keys.
3. **Two separately signed simulated trace commitments:** each is bound to an external policy digest, channel, policy epoch and a trace digest. A signed self-reported collection time predates the owner challenge in the *claimed* chronology.
4. **Two separately signed reveals:** each must exactly match its prior signed commitment and bind the same fresh owner challenge and signed 007 graph manifest, preventing a previously revealed path from automatically authorizing another graph.
5. **Typed paths:** one bounded ordered acyclic list of 1–32 `fixture-*` nodes per channel, beginning with the channel's declared 006 dependency root.
6. **Graph comparison:** exact upstream edges are compared to **fully verified** 007 node attestations; any extra edge, node not appearing in the signed 007 roster, or shared node between the two claimed audit traces produces `HOLD_EXTERNAL_AUDIT_CONTRADICTS_OWNER_GRAPH`.
7. **Missing auditors:** if external audit is entirely absent, return `HOLD_NO_INDEPENDENTLY_PINNED_AUDIT`; if only one auditor is present, return `HOLD_MISSING_INDEPENDENT_AUDIT_CHANNEL`. Partial policy/trust-root materials are invalid.
8. **Inheritance:** an existing parent 007 HOLD is never cleared by an apparently satisfactory external audit. A full match with no inherited HOLD is **review-only**: `REVIEW_AUDIT_TRACES_MATCH_DECLARED_GRAPH_NOT_ADMITTED`.
9. **Cold replay:** the assessment re-executes deterministic 001–007 checks, signed external commitments and manifests in a new Python process, using only public verification keys.

## The important limit

The audit root is not self-authorizing *relative to the checker* but is **still only caller-supplied test configuration**. If the party controlling the environment replaces the externally pinned root and both auditor keys, that party can produce consistent false reports. Even genuine P-256 signatures provide no guarantee that source acquisition occurred, that auditors are physically independent, or that the complete real-world dependency field has been surveyed.

Claimed collection timestamps are locally signed numbers, not trusted timestamp evidence. Despite the name `precommit`, the prototype **does not prove that a commitment existed before another party issued a challenge or committed its owner graph**; externally witnessed append-only chronology would be required.

007 may report a signed graph which omits `fixture-hidden`; 008 may report signed traces which include it. The engine **does not conclude which side is lying**. It merely preserves the disagreement as a reason to HOLD. An actually omitted upstream cause unreported by *both* the 007 graph and the independent audit cannot be inferred.

```text
COVERED BY SIGNED GRAPH != COMPLETE IN THE WORLD
SIGNED OMITTED PATH != VERIFIABLE FALSEHOOD
EXTERNAL SIGNING KEY != INDEPENDENT SENSOR
EXTERNAL ROOT PIN != VERIFIED HUMAN TRUST
SIGNED PRECOMMIT CLOCK != ATTESTED TEMPORAL ORDER
TWO MATCHING AUDIT TRACES != PHYSICAL TRUTH
CONTRADICTION != PROOF OF WHICH CLAIM IS FALSE
NO REPORTED GAP != NO UNKNOWN GAP
HOLD != DELETION
REVIEW != ADMISSION
LOCAL SHA RECEIPT != NATIVE reLATTE RECEIPT
```

## Run / review

```bash
python3 ghot/unheard_choir_missing_node.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_missing_node.py' -v
```

Requires Python 3 stdlib, OpenSSL and all preceding GHoT standalone Choir modules present on the stacked branch.

The demo constructs all temporary P-256 keys in a temporary directory and deletes them after execution. The CLI `assess` takes the 13 signed inputs required by 007, four additional inputs `--audit-policy`, `--audit-commits`, `--audit-reports`, `--trusted-root`, and `--now`. `verify` additionally takes `--receipt` and cold-recomputes the full assessment from the public evidence. Even correct signatures do not create any native effect.

The hostile tests cover falsified graph completeness, absent coverage, forged external trust roots, swapped or duplicated auditors, modified raw trace bytes, forged signatures and epochs, invalid chronological claims, stale challenge/cut binding and cross-process replay.

## 009 suggested pressure

**THE TIMESTAMP THAT LIED** — the owner and auditor may fabricate any timeline of signed commits without a shared, independently witnessed append-only log. Introduce a bounded multi-party signed transparency log with independent sequencers, fork detection, equivocation proofs and immutable challenge-parent relationships. Even that would verify **when a claim was published**, not whether it was physically true.
