# UNHEARD CHOIR 020 — THE REFEREE WHO DIED

**Executable GHoT synthetic P-256 signing experiment**, stacked on 019 → 018 → 017 → 016 → 015 → 014 → 013 → 012 → 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001.

## Problem

019 permitted a specially pinned referee to choose a single archival-review candidate, with separate owner consent, but only as a signed local HOLD. What happens when that referee identity is retired and the same historical source documents become relevant to a **new** local archival question?

The original referee signed a statement that was valid for its original scope. That is *permanent historical evidence*, but cannot be replayed as authority for a different case. A replacement needs independently pinned epoch-2 identity, a root-signed retirement/transition scope and a **new case-specific signed decision**. Even that does not transfer current source power.

## Executable proof

1. Assemble and cold-verify the entire 001–019 public source history and the original signed 019 neutral receipt, recording `HOLD_SCOPED_ARCHIVAL_REVIEW_SELECTED_NOT_ADMITTED`.
2. The simulated fixture deletes the original referee's `019-referee.pem` **private key file**. The old signature and original 019 receipt still verify from public evidence. The original IdentityKey object may remain in process memory; this tests file absence and denied identity reuse, **not secure cryptographic destruction**, actual human death, or hardware erasure.
3. A **new independently pinned local 020 root** signs a policy linking the exact 019 signed receipt digest and 019 source-fork event set to a different, explicit local question `CHOIR-020-NEW-ARCHIVE-REVIEW-001`. It pins entirely different P-256 signer keys for epoch-2 referee, new case owner, and local neutral recorder. All are distinct from every 001–019 role key.
4. The same independent 020 root signs a retirement notice asserting the old referee is retired **for future 020 cases only**, along with the old/new public keys and epoch transition 1→2. The declaration explicitly does not prove biological death or transmit native source permissions.
5. Without the signed transition → `HOLD_NEW_REFEREE_EPOCH_NOT_ADMITTED`. Transition but no fresh referee statement → `HOLD_NEW_CASE_REFEREE_MISSING`. Fresh case-bound epoch-2 referee signature but no new owner-local consent → `HOLD_NEW_CASE_OWNER_CONSENT_MISSING`.
6. The replacement referee signs the exact new case ID, new policy digest, retirement digest, epoch=2, selected artifact or explicit `DECLINE`, synthetic validity interval and no native effects. A distinct new owner signs `CONSENT` or `REFUSE` bound to that **exact new referee signature and case**. An owner's refusal yields `HOLD_NEW_CASE_OWNER_REFUSED_OR_EXPIRED`.
7. When *both* consent to the exact archival choice, the maximum disposition remains `HOLD_NEW_CASE_ARCHIVAL_REVIEW_ONLY_NOT_ADMITTED`.
8. A separately pinned neutral 020 P-256 signer durably signs the new case's local HOLD into its own one-case SQLite journal. A fresh interpreter can reverify original 019 and current 020 receipts from **public JSON only**, with no private key or local SQLite database.

The old source-fork evidence and the old receipt survive **without modification**, and the replacement signatures are a new history instead of fabricated continuity.

## Non-collapse rules

```text
OLD VALID REFEREE SIGNATURE != CURRENT NEW-CASE AUTHORITY
RETIRED FOR NEW CASES != PROVEN BIOLOGICAL DEATH
OLD PRIVATE FILE GONE != PRIVATE KEY CERTIFIED DESTROYED
SAME SOURCE EVIDENCE != SAME GOVERNING QUESTION
ROOT-SIGNED SUCCESSION POLICY != NATIVE SOURCE GRANT
EPOCH 1 HISTORY != EPOCH 2 POWER
FRESH REFEREE APPROVAL != OWNER CONSENT
OWNER CONSENT FOR CASE A != OWNER CONSENT FOR CASE B
NEW REFEREE KEY != GLOBAL IDENTITY OR OWNERSHIP
SIGNED LOCAL HOLD != NATIVE reLATTE HOLD
HISTORICAL VALIDITY != LIVE ACTION PERMISSION
```

## Hostile matrix

The tests reject old referee or old owner 019 signatures submitted as 020 statements; old keys attempting to sign with the fresh 020 domain; old actor collisions with new pinned root, successor, owner or recorder; wrong new case identity, stale epoch, unsanctioned native permission, false death claims, missing retirement, absent and mismatched owner consent, forged signatures, expired synthetic consent intervals, modified source ancestry, receipt corruption, attempts to rewrite existing signed HOLD and replay with changing case disposition.

In all worlds, `native_relatte_receive=false`, `native_relatte_admission=false`, `external_execution=false`, `forwarding_permitted=false`, `effects=[]`, and `authority=NONE`.

## Reproduction

From GHoT root with Python 3 standard library and OpenSSL:

```bash
python3 ghot/unheard_choir_referee_reincarnation.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_referee_reincarnation.py' -v
```

The `verify` CLI consumes all original 015 public files (`--parcel` through `--new-owner-consent`), 016/017/018/019 public evidence files (`--custody-policy` through `--historic-owner`), then `--historic-receipt`, `--replacement-policy`, `--replacement-root`, `--retirement-notice`, `--fresh-referee`, `--fresh-owner` and `--receipt` (one JSON file each). No signer private key, SQLite database or live node is required. The workflow `.github/workflows/unheard-choir-020.yml` runs a fast preflight demo, adversarial 020 tests, and all inherited 001–019 regressions.

## Scope limitations

All participants, clocks, identities, keys, decisions, history and transport are **synthetic fixtures**. The use of P-256 correctly authenticates messages produced by keys in the fixture, but neither the local root nor signed epoch establishes a real third-party institutional mandate. The simulation does not perform real distributed gossip, real private-key destruction, physical custody, legal succession, actual native reLATTE signed RECEIVE/HOLD or device execution. A privileged disk owner can roll back a SQLite journal unless receipts are independently retained. This is *case-scoped archival decision logic*, not a production key revocation or trust registry.

## 021 pressure — THE REFEREE WHO RETURNED

What if the old referee's private key reappears, signs a technically valid fresh-looking request, or a remote observer never receives the retirement notice? Require independently anchored new-policy epochs and source of current trust, hold on missing retirement, and preserve an attributable proof that old signatures cannot silently return to power.
