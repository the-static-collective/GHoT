# UNHEARD CHOIR 013 — THE LETTER THAT OUTLIVED ITS ADDRESS

**GHoT synthetic cryptographic experiment**, stacked on 012 → 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001.

## Problem

012 can send a correctly signed offline letter to `east`. But its recipient may die and be reconstituted with a different signing identity and epoch while an old signed letter is in transit. A message that accurately names yesterday's recipient is **not a capability for today's recipient**.

This slice preserves the historical proof, refuses automatic grant inheritance, and allows a separately pinned new owner to sign an extremely narrow archival-only decision.

## The executable witness

```text
Old EAST incarnation:
  logical address: east
  signing identity: EAST-V1 / old 010 gossip receiver key
  historical 012 parcel: validly signed WEST -> old east, not-after=1050
  own historical 010 observation: contradictory co-witnessed 009 log

New EAST incarnation:
  logical address: east
  signing identity: EAST-V2 / separately pinned new P-256 key
  incarnation epoch: 2
  simulated receiver now: 1100
  historical parcel has expired but remains verifiable.

A. New EAST gets old signed parcel and independent old EAST 010 public view.
   Reverify all 001–012 evidence at the original signed challenge instant.
   Verify an actual historical fork on these exact independently signed views.

B. New EAST validates locally provisioned V2 signing-key pin and a
   V2-signed incarnation snapshot, bound to:
      - old receiver public key and 012 pinned roots
      - exact prior 012 parcel digest
      - logical address 'east'
      - new signer and incarnation epoch=2

   Without a CURRENT V2 grant:
     HOLD_STALE_INCARNATION_NO_ARCHIVE_GRANT

C. V2 owner signs an exact parcel-specific, exact incarnation-specific,
   bounded simulated expiry permit:
     ARCHIVE_HISTORICAL_EVIDENCE_ONLY

   If the permit is verified and fresh:
     HOLD_ARCHIVED_AS_HISTORY_BY_NEW_OWNER_NOT_ADMITTED

D. V2 signs a new GHoT-experimental local custody receipt and writes it
   into its own SQLite journal, linked to a genesis receipt digest.

E. Fresh Python interpreter verifies the signed receipt from public inputs
   only: 012 parcel, separately held historical local view and pins,
   new independently pinned V2 public key, signed incarnation policy,
   and optional newly signed archival-only permit.
```

**Neither signed outcome is admission.** The new owner's grant permits only preservation of history in this synthetic local ledger. It grants no forwarding, network transmission, device execution, GHoT source dispatch, receiver mutation, native reLATTE authority or native reLATTE signed RECEIVE/HOLD.

## Why this is different from 012

- Prior 012 signatures remain authentic and cold-verifiable **as statements made about the previous identity**. They are deliberately verified at the signed historical challenge instant for historical integrity, never confused with live freshness.
- A **new local P-256 signer** is provisioned independently from the parcel. `current-owner-pin` comes from local trust configuration; a self-signed identity advertised by WEST cannot replace that pin.
- An exact signed incarnation binds *old and new identity, epoch, historical trust snapshot and parcel digest*. Reusing the old public key or epoch 1 as a claimed new identity is refused.
- A **separate new-owner-signed archival grant** is required to change the owner-local disposition from unsigned/ungranted HOLD to archival HOLD. Its action is exactly `ARCHIVE_HISTORICAL_EVIDENCE_ONLY`; parcel, epoch, signed incarnation and bounded expiry are all cryptographically bound. The prior receiver and WEST cannot issue it.
- New owner's experimental signed receipt is bound to the independent historical fork verification result, current pin, current policy and simulated receiver clock. Missing, forged, stale or altered materials fail closed.
- Local SQLite uses transactional writes and signature replay of existing records. The fixture supports **exactly one parcel identity per recipient database**. Replays of the same state are idempotent; attempts to change a previously signed HOLD into an archived HOLD are refused.
- The verification-only CLI needs no private signer and no access to the old runtime. It can cold-verify after the old sender and old receiver signer files disappear.

## Adversarial conditions

Tests cover: old 012 route re-labeling; forged WEST parcel signature; changed 010 site evidence; reusing the old EAST private key as new owner; swapping the independently pinned V2 key; owner policy self-signature under an unpinned key; forged/mismatched incarnation epoch; reused grant against another parcel; grant action escalation to forwarding; grant expiry; contradictory simulated clocks; old root substitution; duplicate import; stored receipt corruption; forged local owner signature; cold public replay; and attempted receipt reclassification after local history has been signed.

Even an authentic old parcel past its original TTL may be *examined as historical evidence* in this experiment. That historical verification is **not** a claim that it was received while the TTL was live. The current owner issues a new grant for its own archival handling, not an extension of the old grant.

## Honest authority and security boundaries

```text
SAME LOGICAL ADDRESS != SAME SIGNING IDENTITY
OLD VALID PARCEL != CURRENT GRANT
HISTORICAL SIGNATURE != LIVE ROUTE AUTHORITY
OLD EPOCH != NEW EPOCH
NEW SELF-SIGNATURE != INDEPENDENTLY CERTIFIED IDENTITY
PREPROVISIONED PIN != PROOF OF REAL HUMAN OWNERSHIP
CURRENT ARCHIVAL GRANT != FORWARDING GRANT
ARCHIVAL HOLD != NATIVE reLATTE RECEIVE/HOLD
OLD CLOCK EXPIRY != EVIDENCE DELETION
LOCAL SIGNED RECEIPT != IMMUTABLE EXTERNAL CUSTODY
OWNER RECONSTITUTION != OWNER TRANSFER
LOCAL CLOCK != TRUSTED WALL CLOCK
```

All source identities, observations, challenged times, epochs and death/reconstitution are **synthetic fixtures**. No network packets, actual machine destruction, independent hardware owners, cryptographically trusted real-world timestamping, or live reLATTE organ integration have been demonstrated. The new owner policy is authenticated to a locally supplied pinned key; who provisioned that key is outside the experiment's trust proof.

SQLite journal integrity is local, and can be rolled back by a privileged database owner unless a trusted signed tip is held elsewhere.

## Reproduction

Requires Python 3 stdlib and OpenSSL from the GHoT repository root:

```bash
python3 ghot/unheard_choir_reincarnation.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_reincarnation.py' -v
```

Subprocess receiver import:

```bash
python3 ghot/unheard_choir_reincarnation.py import \
  --parcel old-parcel.json \
  --historic-local-package old-east-010-public.json \
  --historic-pins old-east-pins.json \
  --incarnation signed-new-east-incarnation.json \
  --current-owner-pin preprovisioned-new-east-public-key.json \
  --archive-grant new-owner-signed-archival-grant.json \
  --new-owner-key existing-new-east-private.pem \
  --receiver-db current-east-history.sqlite \
  --now 1100
```

Omit `--archive-grant` for the default no-grant HOLD. Import never silently creates a new signer key. The `verify` command uses the same public documents plus `--receipt`, with **no private key or database required**.

## Next pressure: 014 — THE TWO EQUAL SUCCESSORS

A node is allegedly reconstituted twice at the same logical address, with **two separately pinned valid new-owner keys**, each claiming to be the rightful successor. Source and destination histories may both be cryptographically authentic. Which successor can accept which incoming letter, and under what independently established authority? The executable experiment should preserve mutually incompatible succession claims as owner-relative histories without manufacturing a globally correct owner from a signature alone.
