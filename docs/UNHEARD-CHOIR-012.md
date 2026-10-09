# UNHEARD CHOIR 012 — THE DEAD LETTER THAT CAME HOME

**Status:** executable GHoT offline transport experiment stacked on 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001. **Everything in this specimen is simulated.** No native reLATTE RECEIVE, native GHoT dispatch, physical sensor, independent human witness, real transport acknowledgement, trusted wall clock or network service is claimed.

## The question

011 can resume delivery between two local simulated observers using independently signed sender and recipient records. 012 detaches the evidence from the originating process and makes a **portable public JSON parcel** that can be imported by a separate receiver process using locally provisioned trust anchors.

```text
WEST runtime
  genuine 009 co-witnessed log A
  verified 010 WEST observation
  verified 011 signed WEST→EAST evidence envelope
  WEST signs portable offline parcel
       │
       └── writes incoming.json   (NO private keys)
                                │ offline file copy
EAST runtime                    ▼
  locally provisioned 008 audit root, 009 log root,
  010 gossip root, 010 roster digest and EAST public key
  independently held 010 EAST package with log B
  locally provisioned EAST private key (NOT in parcel)
       │
       ├── replays all public 001–011 evidence in imported JSON
       ├── independently checks signed parcel route and challenge scope
       ├── compares the incoming WEST log with owner-held EAST log
       │     → HOLD_GOSSIP_REVEALS_UNSEEN_FORK
       ├── owner-local disposition: RECEIVED_HELD_FORK_EVIDENCE_NOT_ADMITTED
       └── signs an owner-local receipt, commits to EAST's own SQLite database
                 │
                 └── read-only verification of receipt in yet another process,
                     using only public keys and evidence (NO private signer)
```

**Receiver choice remains receiver-local.** The sender cannot change EAST's trust roots, substitute its 010 local view, sign EAST's custody receipt or grant itself admission.

## Contents

- `ghot/unheard_choir_dead_letter.py`: canonical, exact-schema, sender-signed parcel containing all public inherited 008 evidence, 009 log policy and root, 010 roster and root, and fully signed 011 evidence envelope. Portable SHA-256 cargo digest; separate locally pre-provisioned pinned roots and owner identity. Independent local assessment; signed owner-local `RECEIVED_HELD` or signed `REJECT_EXPIRED` disposition. Strict double-signature authentication.
- `tests/test_unheard_choir_dead_letter.py`: adversarial damaged cargo, actor spoofing, independent root substitution, changed recipient, expired challenge and parcel window, forged origin/recipient evidence, duplicate import, overwritten SQLite receipt, owner-local public cold replay in a new Python process, and source-key absence from parcel.
- `.github/workflows/unheard-choir-012.yml`: inherited 001–011 tests, new 012 matrix, isolated CLI demo and explicitly checked outcomes.
- This document: laws, supported boundaries and honest claims.

## Source and destination authority

The recipient's `--pins` file is provisioned **outside the incoming parcel**. It pins the 008 independent audit public root, the 009 witnessed-log policy root, 010 gossip trust root, recipient site P-256 key and exact gossip roster digest. None of these source trust claims may be replaced by the sender's `cargo`.

The recipient's own 010 observation package is a separate `--local-package` file. It is not supplied as authoritative content from the incoming mail. The verifier cryptographically checks its signatures and evidence ancestry, then calls 010 to compare against the signed source's conflicting log. A sender who fabricates an otherwise signed parcel without the right local keys, prior source or destination cannot force the disposition.

The parcel is signed by the **actual pinned WEST 010 key** and binds the complete cargo digest, exact EAST destination, bounded synthetic `simulated_not_after` clock and one-time nonce. It does not contain any P-256 private key. The expiration limit cannot exceed the original 004 challenge expiration.

If the **parcel is authentic but past its simulated validity window**, EAST signs a bounded owner-local `REJECT_EXPIRED_SIMULATED_WINDOW` receipt instead of accepting stale evidence. The signer uses the original source's challenge instant only to verify *historical signature integrity*; freshness for custody is checked separately against the locally provided simulation clock. It is not an independently authenticated wall clock.

A valid, fresh, independently verified contradictory log yields `RECEIVED_HELD_FORK_EVIDENCE_NOT_ADMITTED`. This is **not reLATTE RECEIVE** and cannot authorize device effects. A signature failure or substituted trust root fails closed before producing a signed custody record. Duplicates return the original receipt and do not write a new local row. A replay attempting to reclassify the same evidence under a different local clock is denied.

## Durability and key separation

The receiving process inserts a sequential, P-256-signed receipt in **its own** transactional SQLite journal. Every receipt binds:
- full signed parcel digest,
- recipient's own independent 010 package digest,
- recipient's locally provisioned trust-pin digest,
- receiver's computed disposition,
- local monotonic index, previous receipt digest,
- the synthetic verification clock used for its decision.

A fresh Python process verifies the receipt by redoing the entire inherited signature and fork check using the public parcel, public independent local package, pre-provisioned public keys and signed owner-local receipt, without invoking the original sender or either private signer.

The present bounded receiver ledger demonstrates **one parcel identity per local fixture database**; it allows idempotent replay of that identity, but does not yet claim an arbitrary multi-parcel general-purpose registry. A production multi-parcel implementation would need per-record source evidence and local-package references for full history replay.

## Important limits

- **Offline JSON file transport is not native reLATTE crossing**. The receiver signed receipt is GHoT experiment syntax, *not* a native reLATTE `RECEIVE` or `HOLD` receipt.
- Two execution processes using separate locally provisioned keys do **not** establish physical machine or human independence. A user/colluding operator can still own all keys.
- Transfer of a file or a signature's existence does not prove trusted wall-clock time, actual custody of hardware, first publication time, or physical-world truth.
- SQLite journal durability is local only and is not anti-rollback when a privileged attacker can erase/rewrite files; a backed-up signed tip and external custody would be needed for stronger recovery.
- The signed clock bounds are simulated; an attacker who controls the receiver clock can misstate whether the window has passed. The program does not provide an external timestamp oracle.
- No network, radio, RF, external effects, power delegation, autonomous destination admission or production security claim.

```text
CARGO DIGEST != SIGNED ROUTE
SIGNED ROUTE != AUTHORITY
EXPORTED FILE != IMPORTED FILE
IMPORTED FILE != OWNER ADMISSION
LOCAL SIGNED HOLD != NATIVE reLATTE HOLD
HISTORICAL SIGNATURE != CURRENT AUTHORIZATION
STALE EVIDENCE != LOST HISTORY
OWNER'S LOCAL TRUST ROOT != SENDER-SUPPLIED KEY
VERIFYABLE PUBLIC RECEIPT != VERIFIED HUMAN CUSTODY
DEATH OF SENDER != DEATH OF EVIDENCE
```

## Reproduction

Python 3 stdlib and OpenSSL, from GHoT root:

```bash
python3 ghot/unheard_choir_dead_letter.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_dead_letter.py' -v
```

CLI export from the origin using its *existing* signer key, before removing access to it:

```bash
python3 ghot/unheard_choir_dead_letter.py export \\
  --source-evidence original-008-public-documents.json \\
  --log-policy log-policy.json --log-root log-root.json \\
  --gossip-roster observer-roster.json --gossip-root gossip-root.json \\
  --sender-envelope west-to-east-011.json \\
  --sender-key west-private.pem --not-after 1050 \\
  --nonce bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \\
  --output incoming.json
```

The export command does not overwrite an existing parcel and does not include the sender's private key. The source-evidence file contains an object with the 17 named public 008 evidence components documented in the Python module; the export checks every required field and revalidates signed 011 ancestry before signing the parcel.

CLI import in a separately invoked Python process:

```bash
python3 ghot/unheard_choir_dead_letter.py import \
  --parcel incoming.json \
  --local-package recipient-owned-010.json \
  --pins recipient-local-pins.json \
  --receiver-key recipient-private.pem \
  --receiver-db recipient-custody.sqlite \
  --now 1001
```

The receiving signer key is **required to exist already**; import never silently creates a new identity. The read-only `verify` mode takes `--parcel`, `--local-package`, `--pins` and `--receipt`, and needs no secret keys. For the provided test, the original sender key isn't passed into the recipient process.

## 013 next pressure

**THE LETTER THAT OUTLIVED ITS ADDRESS** — receiver incarnation and destination authority change while mail is in flight. Prove that an old-but-correctly-signed packet cannot be admitted under a new owner/reconstituted node's address; preserve cryptographically attributable historical delivery attempts, explicit sovereign resumption/redirect policy, and owner-authorized forward receipt only where independently granted. Again, do not silently interpret a GHoT synthetic custody receipt as native reLATTE admission.
