# UNHEARD CHOIR 009 — THE TIMESTAMP THAT LIED

**Owner:** GHoT. **Status:** bounded executable synthetic event-transparency experiment, stacked on UNHEARD CHOIR 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001. No external sensors, trusted wall clock, real independent operators, native reLATTE admission, or external execution.

## Proposition

An instrument can report that it captured samples at 900 while a challenge says it was issued at 1000. Both numbers may be authentic **signed statements**. Neither establishes when data were physically collected, or even when the signed claim became externally visible.

008's synthetic auditors also sign trace-commitments and graph disclosures. 009 adds a *separately provisioned simulated append-only publication log*:

- Separate, locally pinned P-256 log trust root.
- One P-256 log sequencer and **two separate P-256 co-witnesses**, whose keys are distinct from all previous experiment signers.
- Exact typed publication events representing real 008 signed evidence artifacts.
- A SHA-256 hash-chained, 0-based append-only sequence. Each event references a verified 008 artifact digest and is additionally P-256 signed by that source actor.
- A co-signed checkpoint binding log epoch, policy cut, entry count and chain head. Sequencer and both witnesses sign the **same** checkpoint payload, with domain-separated signatures.
- Full cold reconstruction of 001–008 signed evidence, 009 source submissions, entry order, checkpoint signatures, cross-checkpoint forks and canonical deterministic assessment.

### Adversarial simulation

```text
Actual verified local append order:
index 0  owner-challenge
index 1  owner-manifest
index 2  audit-commit-primary
index 3  audit-commit-secondary
index 4  audit-reveal-primary
index 5  audit-reveal-secondary

Signed 009 claims by the auditors:
  audit-commit-primary   says "published before owner-challenge in this log"
  audit-commit-secondary says "published before owner-challenge in this log"

Both claims contradict the co-witnessed append order.
→ HOLD_SIGNED_PUBLICATION_ORDER_CLAIM_CONTRADICTED
```

This **does not falsify** the 008 signers' independent claims that samples were **collected** at time 900. It falsifies only the additional **within-this-log publication-order assertion** in 009. A sample could have existed before the challenge while its evidence was not logged until later.

### Fork demonstration

A malicious log sequencer and both nominal witnesses co-sign one checkpoint at size 6, then co-sign another **different** size-6 checkpoint for the same policy and epoch. Both P-256 attestations verify. If both are presented, the verifier detects contradictory heads at the same size:

`HOLD_MULTIPARTY_WITNESSED_LOG_FORK`

The detection requires visibility of **both** signed checkpoints. If the operator hides one fork from a verifier, 009 has no external gossip/dissemination system to guarantee detection. Because witnesses may collude, multiple keys alone do not prove independent real people.

### Refusal paths

- Invalid log trust root, key reuse with owner/source/instrument/custodian/auditor/graph roles, duplicate or missing witness signatures: refuse.
- Tampered entry, gap, reordered index, duplicate publication event, altered source artifact or role signer: refuse.
- Foreign or stale log policy: refuse.
- Fully signed checkpoint that fails to extend the supplied log: `HOLD_SIGNED_CHECKPOINT_INCONSISTENT_WITH_LOG`.
- Two valid conflicting co-signed checkpoint heads for the same length/epoch: `HOLD_MULTIPARTY_WITNESSED_LOG_FORK`.
- Incomplete event set or missing witnessed tip: `HOLD_INCOMPLETE_WITNESSED_LOG_COVERAGE`.
- Additional signed claim contradicting the verified local append order: `HOLD_SIGNED_PUBLICATION_ORDER_CLAIM_CONTRADICTED`.
- All current evidence consistent with a witnessed order and inherited 008 review state: **`REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED`**, never trust or execution.
- Any previous 008 HOLD persists regardless of how beautiful the log appears.

## Important time and authority distinctions

```text
SIGNED WALL-CLOCK NUMBER != TRUSTED CLOCK
COLLECTED AT != PUBLISHED AT
PUBLISHED TO THIS LOG != FIRST PUBLISHED ANYWHERE
CHECKPOINT ORDER != PHYSICAL EVENT ORDER
MULTIPLE CO-SIGNATURES != INDEPENDENT HUMAN WITNESSES
SIGNED APPEND-ONLY HEAD != IMMUTABLE WORLD HISTORY
ONE RECEIVED FORK != PROOF NO OTHER FORK EXISTS
FORK DETECTED != KNOWING WHICH FORK IS CORRECT
LOG AGREEMENT != EVIDENCE FACTUAL TRUTH
VALID LOG != GRANT TO EXECUTE
LOCAL RECEIPT DIGEST != NATIVE reLATTE RECEIPT
```

There is no wall-clock timestamp authority or externally witnessed creation time in this experiment. The signed checkpoint attests what the simulation's sequencer and cosigners agree to assert **in this event chain**. All keys are ephemeral local fixture keys; no source-owner identity or independent custody is established.

A log checkpoint is an **append assertion** anchored in a locally pinned signing policy. It is not a Merkle tree consistency proof, a public Certificate Transparency log, an independent network broadcast, an external time-stamping service, a consensus blockchain or a reLATTE crossing.

The replay receipt reconstructs a **hypothesis about evidence ordering**, not human benefit, physical measurement or world truth.

## Execute

Python 3 stdlib and OpenSSL, from repository root:

```bash
python3 ghot/unheard_choir_timestamp.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_timestamp.py' -v
```

The demo uses the 008 full signed fixture chain, adds four new independent temporary P-256 keys, signs six typed local-publication events, reconstructs a valid six-entry chain and co-witnessed checkpoint, and checks that the two auditor claims contradict the verified chain order. Keys exist only in the temporary working fixture directory and are deleted when the demo returns.

Read-only `assess` takes all 17 prior 008 public evidence arguments and `--log-policy`, `--log-root`, `--log-entries`, `--checkpoints`, `--now`. `verify` additionally takes `--receipt`. The verifier rechecks all source and log signatures without any private key files. A missing complete log is HOLD; partially supplied log materials are invalid. Dedicated CI reruns 001–009 hostile tests and cold-process replay.

## 010 pressure

**THE UNSEEN FORK**. An operator can produce two fully signed log forks and show only one to each party. Add separately operated gossip witness stores, signed checkpoint exchanges, durable anti-rollback audit indexes and compare independent parties' observed histories. Distinguish witness **observation** of a signed checkpoint from proof that a data sample ever existed at a claimed time.
