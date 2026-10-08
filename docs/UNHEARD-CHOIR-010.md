# UNHEARD CHOIR 010 — THE UNSEEN FORK

**GHoT experiment, stacked on 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001.** All data, signers, clocks, graph nodes, instrument streams and log histories in this specimen are synthetic. No physical measurement, real peer network, public broadcast, trusted wall-clock, actual human identity, native reLATTE receipt or execution.

## The question

009 can detect two co-signed, conflicting checkpoints **when both appear in one verifier's view**. But an equivocating log may distribute one internally consistent, correctly signed history to one recipient, and a different internally consistent, correctly signed history to a second recipient. Each independently sees only one valid past.

010 gives each recipient its own separately signed receipt and durable local SQLite journal and checks what changes after exchanging **public evidence packages**.

## Executable experiment

```text
The same real P-256 log sequencer + both co-witnesses sign:

  WEST: A B C D E F     checkpoint size=6, head=HASH_A
     009 local status: REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED
     010 west receives and records signed observation #0 in west.sqlite

  EAST: A B C D F E     checkpoint size=6, head=HASH_B
     009 local status: REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED
     010 east receives and records signed observation #0 in east.sqlite

  Both views have the exact same 009 policy, epoch and 008 ancestry.
  Each event still refers to correctly signed 008 artifact submissions.

  BEFORE GOSSIP:
    WEST cannot see EAST's checkpoint;
    → HOLD_NO_PEER_GOSSIP_EVIDENCE
    NOT evidence that no other fork exists.

  CROSS-SITE EVIDENCE EXCHANGE:
    Both observers present their complete correctly signed 009 log, checkpoint,
    authenticated site identity, and owner-local signed observation receipts.
    Same policy + same epoch + same entry count + different witnessed heads.
    → HOLD_GOSSIP_REVEALS_UNSEEN_FORK
```

The fork is genuine **as a pair of incompatible cryptographically witnessed simulated append histories**. This still does not identify a malicious actor or establish which version reflects actual events.

## New authority/provenance boundaries

1. The 010 **gossip trust root** and two **observer site signing keys** are provisioned outside the 009 policy and distinct from every 001–009 signer. The local root signs a scope-limited exact-cut gossip roster; the verifier pins its root key separately. This is *trust configuration*, not proof of different human operators.
2. Each isolated observer reruns the entire 009 signed evidence chain, including full 001–008 ancestry, and accepts only `REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED`. A site records precisely **one fully co-witnessed log tip** per append operation; a previous 009 HOLD cannot be overridden through gossip.
3. Each site signs a `LOCAL_ATTESTATION_NO_EFFECT` receipt binding its 010 roster, local monotonic index, previous signed local receipt digest, 009 assessment digest, exact checkpoint digest, checkpoint size/head and all raw log-entry digests. Signing is real P-256 using GHoT `relatte_identity`.
4. Receipts are inserted **transactionally** into separate SQLite files with `BEGIN IMMEDIATE`, unique checkpoint constraints, sequential signatures, and `synchronous=FULL`. Reusing the same checkpoint at a site is refused, and a subsequent write verifies existing signatures and ancestry first. The local receipt chain is durably and independently readable.
5. A **public gossip package** contains the full signed 009 log entries, cosigned checkpoint and complete local observation receipt chain. It contains no private keys or server address. A recipient checks the 009 world and signer keys afresh, checks the local observer's signed chain and makes sure its tip refers to those exact raw bytes.
6. Before cross-site exchange, **`HOLD_NO_PEER_GOSSIP_EVIDENCE`**. When both verified tips are present for the same policy, epoch and size and have different heads, **`HOLD_GOSSIP_REVEALS_UNSEEN_FORK`**. Same tips only imply **`REVIEW_MATCHING_WITNESSED_LOGS_NOT_ADMITTED`**; different sizes imply a separate HOLD since 010 does **not** implement a logarithmic append consistency proof.
7. Results and envelopes are deterministic and cold replayable in another Python process using only public evidence. Gossip comparison **does not write into either peer's SQLite journal**. The local owner is free to inspect or HOLD after learning of peer evidence.
8. No network transmission occurs in the demo. The evidence *exchange* happens through explicit function arguments/file packages. Real-time discoverability, secure transport, NAT or radio protocols, real alternate operator custody and native reLATTE crossings remain unimplemented.

## What the SQLite files can and cannot establish

Both SQLite journals survive reopening, but **SQLite alone is not append-only, tamperproof storage against a privileged writer**. Signature chaining detects edited receipts and missing intermediate links if a verifier has the expected signed tip. A sufficiently privileged attacker could delete or replace entire databases, replay an earlier legitimate tip, omit a peer's package or prevent a gossip exchange. The experiment has no off-device persistence checkpoint, witness quorum or external gossip delivery guarantee.

A signed 009 checkpoint that was shown only to one site may remain invisible forever to the other. 010 establishes fork evidence only after the two parties **actually exchange** their contradictory authenticated histories; it cannot prove that all sites have participated or that no further unseen forks exist.

```text
NO PEER MESSAGE != NO FORK
LOCAL SIGNED RECORD != EXTERNAL IMMUTABILITY
TWO INDEPENDENT KEYS != TWO INDEPENDENT PEOPLE
SIGNED LOG HISTORY != PHYSICAL EVENT HISTORY
GOSSIP PACKAGE != ADMISSION
COMPARE != OVERWRITE
DETECT FORK != CHOOSE CORRECT FORK
WITNESSED CHECKPOINT != TRUSTED CLOCK
P-256 RECEIPT != NATIVE reLATTE RECEIPT
HEARD FROM TWO != HEARD FROM ALL
```

## Run

Python 3 stdlib and OpenSSL, at GHoT repository root:

```bash
python3 ghot/unheard_choir_gossip.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_gossip.py' -v
```

The demo generates ephemeral signer keys, uses the inherited 008/009 specimen, signs **two** fully valid but different six-entry 009 histories, stores separately keyed observation receipts in two SQLite databases, checks the HOLD without gossip, exchanges public evidence in-memory, then confirms the fork and runs a cold full verification of its signed result. No private keys are exported; the databases in the demo exist only inside the temporary fixture directory.

The read-only CLI `compare` takes the original 17 signed 008 source documents plus `--log-policy`, `--log-root`, `--gossip-roster`, `--gossip-root`, `--local-package`, optional `--peer-package`, and `--now`. The `verify` CLI repeats those arguments with `--receipt` to verify the assessment in a completely fresh interpreter.

A dedicated workflow runs inherited 001–009 tests, the 010 adversarial suite, and an isolated demo.

## 011 pressure: The Vanishing Witness

A signed fork proof is useful only if it can be carried beyond two local machines. The next experiment should handle intentional message drops, stale signed checkpoints, selective disclosure, witness recovery after local disk loss, bounded anti-entropy and delivery receipts through authorized reLATTE crossings—without confusing **transport** with trust or elevating gossip into owner-local permission.
