# UNHEARD CHOIR 016 — THE WITNESS WHO OWNS NOTHING

**Experimental GHoT cryptographic specimen**. Stacked on 015 → 014 → 013 → 012 → 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001. All witnesses, incidents, institutions, clocks, log histories and source reviews are **synthetic**. P-256 signatures authenticate fixture statements, not real-world facts, legal rights or native reLATTE admission.

## Problem

An independent third party may hold the last preserved copy of genuine historical evidence while **owning no current source capability**. The source may not answer, may sign an assertion that its own record is unavailable, may explicitly decline new review, or may revoke a specific previously signed source approval. The holder may also possess an incomplete packet that lacks some of the signed material.

The holder's **custody** and signed inventory must not become source authority. The source's silence cannot be treated as refusal. A local omission cannot prove global absence. Revocation of a grant cannot erase the history that the grant was once signed.

## Four executable situations

At simulated receiver clock 1250, original 015 evidence is preserved:

1. **Complete historical evidence** — the holder signs its local packet inventory. All 015 narrow review/consent checks replay as `HOLD_THREE_PARTY_ARCHIVAL_EVIDENCE_ONLY_NOT_ADMITTED`. 016 returns **`HOLD_CUSTODY_EVIDENCE_ONLY_NOT_ADMITTED`**. Possession grants no power.
2. **Holder packet omits current source review** — the source and successor consent slots are `null`, while the holder signs an exact `ABSENT_FROM_HOLDER_PACKET` statement with no document digest. No source reply is observed. 016 returns **`HOLD_SOURCE_RESPONSE_UNKNOWN_NOT_DENIAL`**, not `DENIED` and not an assertion that the record does not exist elsewhere.
3. **Independently signed source-local unavailability or local record gap** — the original 015 source reviewer (not the holder or old owner) signs `SOURCE_UNAVAILABLE_LOCAL` or `SOURCE_RECORD_NOT_FOUND_LOCAL` with a bounded simulated interval and explicit `proves_nonresponse_elsewhere=false`. 016 returns an attribution-preserving **HOLD**, never an unqualified statement that the world lacks that record.
4. **Specific fresh source-review revocation** — the 015 source reviewer signs a `REVOKE_EXACT_SOURCE_REVIEW` notice that binds the full prior source review digest, prior 015 policy, holder and historic instrument, plus its own simulated effective window. Before the effective clock instant the original source review remains in 016's custody-only HOLD; at/after the simulated instant, a matching revocation blocks current archival review, returning **`HOLD_SOURCE_REVOKED_CURRENT_ARCHIVE_REVIEW`**. The historical source approval and delegation remain verifiable signed artifacts and are not deleted.

An explicit source `SOURCE_DECLINED_NEW_REVIEW` statement differs from a source that simply **never responded**. The former produces a signed local decline HOLD; the latter remains UNKNOWN.

A missing 015 successor-local consent yields **`HOLD_OWNER_CONSENT_NOT_IN_PACKET`**. Any unresolved 014 succession dispute remains **`HOLD_PREDECESSOR_AUTHORITY_UNRESOLVED`**, regardless of the holder's completeness or source replies.

## Role split and keys

- **Historical holder:** the 015 third-party P-256 signer. It signs a bounded local inventory of exactly three slots: holder presentation, fresh source review, and current successor consent. Each slot is either `PRESENT` with the exact document SHA-256 digest or `ABSENT_FROM_HOLDER_PACKET` with no digest. Extra slots, invented digest assertions, unsigned omissions and assertions of world absence are refused.
- **Source reviewer:** the already independently pinned 015 source-review P-256 signer. Only this exact signer can sign local unavailability, local record gap, explicit refusal, or revocation. Revocation must reference the exact prior source-review digest. The holder, former owner, current successor, 014 reviewer and 016 neutral recorder cannot forge source status.
- **New 016 local policy root:** a separate P-256 trust root, pinned by the verifier *outside* the incoming evidence, signs the precise 015 policy/014 policy/legacy delegation/holder/source/recorder binding. The new root and neutral recorder must not reuse any inherited actor's signing key.
- **Neutral recorder:** a separately keyed P-256 signer signs the final full 016 HOLD assessment and commits one bounded case to a local SQLite journal. The recipient's record is replayable from public 001–016 evidence in a fresh Python process without any private key or database access.

No signed 016 receipt is a native reLATTE RECEIVE, native HOLD, production source grant, lawful asset title, forwarding permission or license to execute.

## Non-collapse laws

```text
CUSTODY != SOURCE AUTHORITY
HOLDER'S SIGNED OMISSION != GLOBAL ABSENCE
SILENCE != DENIAL
NO REPLY != NO SOURCE
SOURCE'S LOCAL RECORD GAP != HISTORICAL NONEXISTENCE
EXPLICIT SIGNED DECLINE != UNSIGNED NONRESPONSE
REVOKED APPROVAL != ERASED HISTORICAL SIGNATURE
HISTORIC VALIDITY != CURRENT RE-ADMISSION
SOURCE-LOCAL NOTICE != UNIVERSAL SOURCE TRUTH
SIGNED PACKET DIGEST != PHYSICAL CUSTODY PROOF
SIGNED LOCAL HOLD != NATIVE reLATTE HOLD
SOURCE REVIEW != OWNER CONSENT
OWNER CONSENT != GLOBAL SUCCESSION
RECORD RETENTION != PERMISSION TO FORWARD
```

## Adversarial gates

Hostile tests alter signed slot digests, invent local source presence, deny that a present document exists, rewrite a signed local omission into a global claim, reassign an original holder, forge source statuses, spoof the source P-256 signer with the old owner or holder, change a specific revocation target digest, alter policy/issuer/legacy bindings, smuggle external execution, misstate a simulated notice window, reuse inherited keys as current root, replay a signed receipt with new revocation, and corrupt a SQLite record. A revoked source approval remains historically reconstructible through the inherited 015 verifier; no earlier signature is mutated or expunged.

Only one signed case is supported per SQLite fixture database. This demonstrates idempotent durable local receipts, not a production multi-case ledger. A privileged file operator can roll back SQLite state without independently pinned signed tips.

## How to run

From GHoT repository root, with Python 3 stdlib and OpenSSL:

```bash
python3 ghot/unheard_choir_witness_custody.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_witness_custody.py' -v
```

The `assess`, `record` and `verify` CLI commands take the first ten mandatory public 015 documents (`--parcel`, `--historical-local-package`, `--historical-pins`, `--succession-policy`, `--succession-root`, `--reviewer-selections`, `--candidate-archive-grants`, `--legacy-delegation`, `--third-party-policy`, `--third-party-root`), optional `--third-party-presentation`, `--fresh-source-review`, `--new-owner-consent`, and separate 016 `--custody-policy`, `--custody-root`, `--holder-inventory`, optional `--source-notice`. `assess` additionally requires a simulated `--now` clock. `record` requires a pre-existing, locally held `--neutral-private-key` and `--neutral-db`; the command never creates a new signing identity. `verify` only requires the public `--receipt` and can run without signing keys, runtime, SQLite database or source access.

The absence of a CLI path for an optional source document means that **this presented packet does not contain it**. The holder manifest cryptographically authenticates that local observation; it does **not** certify who else possesses the document, why it was missing, whether an external source responded, or who caused any delay.

## Limits

These are simulated signed claims and simulated time, not trusted legal delegation or physical-world measurement. A source's signed statement of local unavailability could still be false; 016 authenticates the signer rather than making the content infallible. `REVOKE_EXACT_SOURCE_REVIEW` is a simulation-scoped source-local revocation assertion, not a legally enforced or natively bound reLATTE source revocation. Source noncooperation is explicitly **unknown** until an attributable statement appears, and even an attributable record-gap notice is local rather than global evidence. Native crossing, external execution, historical truth, actual machine/human independence, and secure network transmission remain out of scope.

## Next pressure — 017: THE NEGATIVE THAT OUTLIVED THE POSITIVE

Can a signed revocation itself survive loss, forking, contradictory successors and selective gossip when a newer witness possesses a valid pre-revocation approval but never heard of the change? Prove observer-relative `UNKNOWN_REVOCATION_STATE` across snapshots without allowing delayed revocation notifications to retroactively destroy historical truth or arbitrarily revoke a current grant.
