# UNHEARD CHOIR 015 — THE RIGHTFUL THIRD PARTY

**GHoT cryptographic simulation, stacked on 014 → 013 → 012 → 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001.** Real P-256 signatures over synthetic events and independent caller-pinned fixture trust roots. No native reLATTE crossing/RECEIVE/HOLD, physical custody, real human/organizational identity certification, trusted wall-clock time or external execution.

## The question

Suppose NORTH and SOUTH both claim to be EAST's rightful successor. A third party arrives holding a **genuine historical instrument** signed by the original EAST-V1 owner. That instrument is perfectly authenticated and grants the holder a historically bounded interest in preserving the old signed evidence.

Can the third party treat the old owner signature as today's delegation of power? **No.** An old signature establishes an authentic old **claim**, not current authorization. The holder, an independently pinned source reviewer, and the *selected new owner* must each contribute a separate, narrowly scoped signed assertion; and a prior 014 dispute or contested reviewer selection still blocks even the archival-only review path.

The experiment exposes these boundaries without inventing a globally rightful owner.

## Executable chain

```text
EAST-V1 former owner signs historical delegation (claimed time=1000, expires=1050)
                    |
           holder = independent THIRD PARTY key
           original signed 012 parcel digest
           named historical EAST logical address
           permitted historical intent = ARCHIVE_HISTORICAL_FORK_EVIDENCE_ONLY
                    |
          NEW simulated receiver clock = 1100
          OLD grant has expired, but signature and historical evidence survive
                    |
      014 N/S succession review and independent old EAST-local log:
        014 CONTESTED or reviewer signed NORTH AND SOUTH?
           -> HOLD_014_SUCCESSION_NOT_RESOLVED_FOR_ARCHIVAL_REVIEW
        014 ONE scoped candidate review selection and its own 013 archival grant?
           -> 014 archival-only HOLD (NOT universal ownership)
                    |
            THIRD PARTY signs presentation of exact old delegation
           -> HOLD_LEGACY_DELEGATION_NO_FRESH_SOURCE_REVIEW
                    |
          FRESH SOURCE reviewer signs:
             exact holder-presented claim + 015 policy + selected 014 candidate
             exact incarnation + ARCHIVE_ONLY + effect_permission NONE
           -> HOLD_FRESH_SOURCE_BUT_SELECTED_OWNER_CONSENT_MISSING
                    |
          SELECTED candidate's separately pinned P-256 owner signs:
             same historic holder claim + exact fresh source review
             same candidate and epoch + archival-only + effect_permission NONE
           -> HOLD_THREE_PARTY_ARCHIVAL_EVIDENCE_ONLY_NOT_ADMITTED
                    |
          independent neutral P-256 recorder signs local HOLD receipt;
          commits into one-case SQLite journal;
          fresh process revalidates entire 001–015 proof with public evidence only.
```

**All destinations are HOLD.** Even with source and successor consent, the result is *evidence review for historical archiving*, not native reLATTE admission, a production source grant, power over a physical vessel, authorization to forward, adjudication of rightful succession, or device execution.

## Five distinct and non-interchangeable roles

**1. Historical issuer** — the original EAST-V1 P-256 receiver key pinned by the separately held 012 receiver identity. It signs an exactly bounded, 012-parcel-bound historic delegation. The signature verifies today even though its synthetic not-after value is in the past. The historical instrument contains an exact holder public key, scope and window; changing any field invalidates it. It **does not create live privileges**.

**2. Third-party holder** — an entirely different P-256 key. It signs a new request/presentation of *that specific historical instrument* under 015's signed review policy. Being the genuine holder means the third party may submit authenticated evidence, not that it can choose a successor or admit itself.

**3. Independent source reviewer** — a third new P-256 key, separately pinned under 015's trust-root-signed policy. It signs a **fresh** simulated, time-bounded, effectless source review bound to the exact third-party presentation and 014 candidate incarnation. The source review only admits the archival question into local consideration and is not a real native source authority.

**4. Selected successor's local owner** — NORTH or SOUTH's actual 014 P-256 candidate key. 015 independently re-runs all predecessor 013/014 signatures, checks that 014 remains in its bounded archive-review HOLD (not dispute), and demands a new candidate-owner signed consent binding *the exact* third-party claim and *the exact* source review. Neither holder nor source reviewer can sign for the successor. The new owner still cannot claim globally adjudicated physical title.

**5. Neutral recorder** — a fifth separately pinned 015 P-256 key, distinct from every inherited signer, successor, holder, and source reviewer. It signs the determined HOLD disposition and stores one case's receipt in a transactionally committed, locally owned SQLite journal. The actor named in the historical delegation **cannot** modify the receiving owner's signed history.

There is also a **sixth authority, the local 015 policy root**, distinct from all five roles and all inherited source keys. It signs the exact 014 policy digest, original parcel and pinned historical trust, old delegation, holder public key, new source reviewer public key and neutral recorder public key. A claimant cannot supply a replacement root as part of the evidence and thereby appoint itself.

## Signature and adversarial gates

The matrix rejects forged historical signatures, out-of-window delegation, attempting to reuse the former owner's key as holder, altered or changed parcel digest, foreign/new self-appointed trust roots, source-owner key collisions, mismatched third-party claim, expired fresh requests, false source key, source review scoped to a different candidate, changed incarnation digests, source grant attempting forwarding, owner consent from the holder or source reviewer, owner consent referencing another source review, expired new owner consent, stale or conflicting 014 selections, neutral recorder spoofing, unsigned receipt manipulation and SQLite corruption.

There are distinct HOLDs for each missing present-tense gate. A formally signed claim whose validity window expired remains historical, **not current**. A source authorization for SOUTH cannot use NORTH's selected succession review or owner consent. Retroactively adding a grant may not rewrite an already signed and archived local HOLD.

### Limits

- All claimed times, participants, local clocks, node deaths, signatures and provenance are simulated. The P-256 signatures authenticate statements made by fixture keys, **not actual legal rights**.
- 015 does **not** know which 014 candidate is rightful. A locally pinned review choice narrows only which candidate's archival request to evaluate.
- The `source_reviewer` is a scoped simulation-local independent signer. It is **not proof of external source authority** or live donor organ admission.
- Neither old nor fresh signatures establish absolute time; simulated expiry is checked against a caller-supplied clock, not certified UTC.
- GHoT `015-neutral-custody/v0` signed receipts are **not native reLATTE RECEIVEs**.
- SQLite is locally durable across normal restart but cannot prevent privileged disk rollback without independently retained signed state.
- One historical instrument and one signed neutral case per local fixture database; no generalized real third-party legal delegation service, network delivery, actual asset or physical-control path is provided.

## Laws

```text
SIGNED OLD DELEGATION != CURRENT SOURCE AUTHORIZATION
THIRD-PARTY HOLDER != OWNER
PRESENTED CLAIM != VERIFIED SOURCE APPROVAL
SOURCE APPROVAL != CURRENT OWNER CONSENT
CURRENT OWNER CONSENT != GLOBAL RIGHTFUL SUCCESSION
TWO APPROVALS != NATIVE ADMISSION
014 REVIEW SELECTION != OWNERSHIP DECISION
LEGACY VALIDITY != POST-EXPIRY POWER
HISTORICAL EVIDENCE != LIVE AUTHORITY
ARCHIVE_ONLY != FORWARD_OR_EXECUTE
LOCAL GHoT RECEIPT != NATIVE reLATTE RECEIPT
SYNTHETIC TIME != INDEPENDENT TRUSTED CLOCK
```

## Run and replay

From repository root, Python 3 standard library and OpenSSL:

```bash
python3 ghot/unheard_choir_third_party.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_third_party.py' -v
```

The CLI also supports `assess`, `record` and `verify`, accepting the thirteen named JSON public-evidence fields: `--parcel`, `--historical-local-package`, `--historical-pins`, `--succession-policy`, `--succession-root`, `--reviewer-selections`, `--candidate-archive-grants`, `--legacy-delegation`, `--third-party-policy`, `--third-party-root`, `--third-party-presentation`, `--fresh-source-review`, and `--new-owner-consent`. Only the first ten are mandatory for an incomplete-HOLD world; the three present-tense gates can be omitted, or supplied as complete signed JSON.

`assess` also requires `--now`. `record` requires `--neutral-private-key` referencing a previously provisioned local P-256 signer, `--neutral-db`, and `--now`; it does not create a new identity on import. `verify` takes an additional `--receipt` and revalidates all predecessor evidence **without private keys, source/runtime access or the signing database**.

## 016 pressure — THE WITNESS WHO OWNS NOTHING

A source reviewer and new owner both correctly sign archival review; a third-party holder owns no source capabilities, but can still be the only custodian of lost evidence. Test selective source noncooperation, incomplete custody, revocation and partial archival material using **negative evidence and signed omissions**, without allowing non-response to become denial or allowing a hostile gatekeeper to erase the holder's historically valid evidence. No administrative title should be inferred from mere possession.
