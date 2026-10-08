# UNHEARD CHOIR 007 — THE HIDDEN COMMON CAUSE

**GHoT experimental stack:** 001 #74 → 002 #75 → 003 #76 → 004 #77 → 005 #78 → 006 #79 → **007**. The entire stack is separate draft PR work. No native instrument dispatch, physical observation, or reLATTE admission is performed.

## Question

Can two separately signed instruments, with two separately signed custodians and different local measurement modalities, still share an upstream source they failed to declare?

**Yes—in a fully specified simulation.** 006 compares immediate declared dependency roots. 007 follows a bounded, individually signed directed graph behind those roots, allowing a remote common ancestor to be found.

```text
006 primary immediate root: fixture-primary
                          → fixture-east ──┐
                                         fixture-common
006 secondary immediate root: fixture-secondary
                          → fixture-west ──┘
```

The immediate 006 roots are disjoint, and the two toy modalities agree on `PRESENT`, so 006 permits **REVIEW_DECLARED_DISTINCT_MODALITIES_CONCORDANT_NOT_ADMITTED**. Five more distinct node-controller keys sign their own upstream statements in 007; 007 traces both paths to `fixture-common`, producing **HOLD_ATTESTED_HIDDEN_COMMON_CAUSE**.

## Real execution boundaries

1. Recompute **all existing 006 evidence and its ancestors**: cryptographic source/observer statements, valid fresh P-256 challenge, primary sample commitment and signed samples, secondary separately mapped simulated measurements, custodian statements, instrument epochs and declared root lists.
2. A **local P-256 owner-key-signed graph manifest** is bound to the exact 003 proposal, 004 roster/challenge and 006 signed pinset. It lists up to 32 bounded `fixture-*` nodes with epoch, controller public key and predeclared number of parents.
3. Each node has its own **distinct P-256 signer**, not reused for owner, source, observers, instruments, custodians or other node controllers. That signer's attestation declares sorted upstream edges tied to the exact signed manifest and challenge.
4. Missing attestation produces **HOLD_INCOMPLETE_SIGNED_PROVENANCE**, *not* an inferred leaf. Duplicate nodes, unsigned/unknown upstream nodes, omitted entrypoints, reusing a principal key, stale epochs, modified statements, forged signatures and cycles are denied.
5. The verifier traverses **every node's signed DAG**, not only the paths it expects to find, then computes the full ancestor sets for the primary and secondary sensor roots.
6. Any shared node between those ancestor sets produces **HOLD_ATTESTED_HIDDEN_COMMON_CAUSE**. Where paths are fully signed and claim no overlap, result remains **REVIEW_DECLARED_DISJOINT_SIGNED_GRAPH_NOT_ADMITTED**, not truth.
7. The receipt contains the inherited 006 assessment digest, source-bound graph digest, explicit missing nodes and full reconstructed upstream traces. Verification reruns the entire input against existing 001–006 modules; SHA-256 is an integrity comparison, **not** a new reLATTE signed receipt.

### Adversarial worlds

| Fixture | 006 | 007 |
| --- | --- | --- |
| Sensor roots apparently disjoint but converge through two hops | Review only | **HOLD common upstream** |
| Complete signed graph claims disjoint terminal roots | Review only | **Review only** |
| A signed node missing from the provided evidence | Review only | **HOLD missing coverage** |
| Validly signed graph contains an upstream cycle | Review only | Refuse graph |
| Sensor measurements already conflict in 006 | HOLD | HOLD remains |
| Entire owner-controlled graph lies and hides an unknown common input | Review only | Can still appear disjoint: **no truth claim** |

## Limits: signed provenance ≠ verified provenance

The node-edge attestations in 007 use **real ECDSA P-256**, backed by GHoT's existing `relatte_identity` implementation and OpenSSL. They authenticate each claimant's exact edge list under a **locally provisioned trust roster**. But the signers may lie or collude, and the roster itself could be maliciously curated. A missing node that **is not listed at all** cannot be discovered. Predeclared parent counts are useful consistency checks, but an owner who deliberately understates these counts can manufacture a perfectly signed *apparently* disjoint graph.

This is a **bounded simulated dependency graph**, not a digital twin of physical sensors and not an independently established chain of custody. Timestamp claims, physical independence, sensor custody and real-world accuracy are **not** verified. The graph cannot establish real upstream completeness or that there are no hidden shared causes.

Even the best case remains a **review candidate**, never automatic instrument authority or admission to reLATTE.

## Execute

Requires Python 3 stdlib and OpenSSL. From GHoT repository root:

```bash
python3 ghot/unheard_choir_hidden_cause.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_hidden_cause.py' -v
```

The demonstration generates separate temporary private keys for the source, observers, owner, primary/secondary instruments, custodians and each graph node. Keys never enter the repository. It builds genuine signed evidence, runs 006 and 007, and verifies an exact cold-replay result.

Read-only `assess` needs the eleven original 006 files plus `--manifest`, `--attestations` and a synthetic `--now` clock. Omitting *both* graph files produces HOLD; partially supplying one is invalid. `verify` takes all the same arguments and `--receipt`, to re-execute verification in a fresh Python process without access to the signing keys.

CI reruns 001–007 hostile suites and a cold demo. Original 001–006 schemas and experiments are unchanged.

## Laws

```text
DISJOINT IMMEDIATE ROOTS != DISJOINT ANCESTRY
SIGNED EDGES != COMPLETE ACTUAL DEPENDENCY GRAPH
MULTIPLE VALID KEYS != INDEPENDENT PHYSICAL MEASUREMENTS
OMITTED ATTESTATION != NO PARENTS
SOURCE SIGNATURE != FACTUAL TRUTH
CONTROLLER ASSERTION != EXTERNAL CUSTODY
DECLARED GRAPH CLOSURE != WORLD COMPLETENESS
GRAPH CONVERGENCE != PROOF OF WHICH SENSOR LIED
HOLD != IMPOSSIBLE
REVIEW != ADMISSION
DIGEST != NATIVE SIGNED RECEIPT
```

## 008 — THE MISSING NODE

007 detects a **declared, signed common dependency** that 006 missed, but cannot force all actual dependencies into an owner-controlled manifest. A next hostile experiment should compare externally sourced challenge reports with the graph's claimed frontier, introduce independently provisioned anchor roots and test adversarial owner-controller collusion. It must preserve the distinction between auditability and physical ground truth.
