# UNHEARD CHOIR 014 — THE TWO EQUAL SUCCESSORS

**Status:** executable cryptographic GHoT experiment, stacked on UNHEARD CHOIR 013 → 012 → 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001. All log histories, receiver deaths, claims and times are synthetic. The P-256 signatures are real fixture signatures, not certifications of human ownership.

## The problem

013 proved that a signed parcel for yesterday's owner does not grant authority to today's reconstituted node. But consider two different nodes, both announcing that they are the new `east`, both signed with distinct valid P-256 keys, both presenting valid 013 incarnation statements, and both possessing independently signed 013 archival-only grants.

The system must **not** interpret authentication as ownership or compare identities by whichever claim arrived first. The old address and parcel remain the same; the successor claims may both be legitimate *claims* without establishing a single legitimate owner.

## The runnable 014 witness

```text
HISTORICAL WEST -> EAST-V1 012 PARCEL (expires at simulated 1050)
          |
          | 013 public verification of real signed legacy evidence
          +----------------------------------------------+
          |                                              |
     NORTH-V2 claimant                             SOUTH-V2 claimant
     new P-256 key N                               new P-256 key S
     signed new epoch=2 incarnation                signed new epoch=2 incarnation
     locally signed archival-only grant           locally signed archival-only grant
          |                                              |
          +-----------------+----------------------------+
                            |
           external-to-claimants, locally pinned
              P-256 policy review root
              signed exact historic policy:
                  NORTH identity/claim
                  SOUTH identity/claim
                  reviewer signing key
                  neutral recorder signing key
                            |
            SCENARIO A: no reviewer selection
              HOLD_TWO_EQUAL_SUCCESSORS_UNRESOLVED

            SCENARIO B: reviewer signs NORTH and SOUTH
              with same valid policy and conflicting choices
              HOLD_CONTRADICTORY_SIGNED_SUCCESSION_SELECTIONS

            SCENARIO C: reviewer signs NORTH only
              + independently checked NORTH owner-signed
                exact parcel/epoch/time-bound archival grant
              HOLD_SELECTED_SUCCESSOR_ARCHIVAL_ONLY_NOT_ADMITTED

            SCENARIO D: reviewer signs NORTH only
              without NORTH's separate 013 archival grant
              HOLD_SELECTED_SUCCESSOR_NO_OWNER_ARCHIVAL_GRANT
```

Every branch explicitly declares that global rightful ownership is **not established**, native reLATTE RECEIVE/HOLD is **not implemented**, no forwarding is granted and no external action is produced.

## Separate authorities, separate roles

**Historical source:** the immutable signed 012 parcel, historical independently held 010 recipient observation, and locally pinned 012 historical trust roots. Each 013 incarnation is checked against the same historical origin and same epoch; signature validity remains attached to the original evidence, not to present ownership.

**Competing claims:** two differently keyed signers, NORTH and SOUTH, each separately sign a full 013 incarnation for logical address `east` at epoch 2. Their claims and public keys are bound into a locally signed, exact 014 policy. Both claims are re-evaluated through the full 013 verifier to confirm that without new grants the old message stays in HOLD. A signature proves attribution to a key, **not rightful succession**.

**Review root:** a **separately provisioned, locally pinned P-256 key** signs the 014 policy and binds exactly two candidate incarnations, one review-signer public key, and one *neutral recorder* public key. The verifier never derives its trust root from the sender or the candidates. All these keys are distinct from every 001–013 source, actor, instrument, custodian, auditor, graph controller, witnessed-log signer and 010 site key.

**Reviewer:** a key separate from both claimants signs exact candidate-specific review statements with bound policy/candidate/parcel digests, a bounded synthetic expiry and explicit `effect_permission=NONE`. One unexpired review selection is a **local archival-review choice, not universal appointment**. Two valid competing reviewer choices force HOLD even if both statements were signed by the same legitimate reviewer. A stale selection remains authenticated history but does not confer present review permission.

**Individual local grant:** archival permission is a *separate 013 grant signed by the selected candidate owner*. The reviewer cannot impersonate the candidate's local will. Unselected grants are still verified so the record cannot preserve invalid signatures as if they were valid.

**Neutral recorder:** a final distinct key signs the dispute assessment and preserves it in a separate neutral SQLite journal. The receipt is bound to the full asserted archive/dispute state, policy digest, selected and unselected 013 historical assessments, local simulated clock, and genesis predecessor. It is never signed by NORTH or SOUTH merely because they claim the address. Once written, a different reviewer selection cannot rewrite an already-signed local controversy.

## Adversarial gates

The hostile tests include: forged or substituted reviewer/root keys, old V1 signer masquerading as policy root, duplicate selection statements, changed chosen candidate/epoch/parcel digests, owner-self-appointed reviewer, conflicting valid selections, expired local review decision, invalid candidate archival grants including **unselected** candidate grants, scope escalation to forwarding, signed receipt forgery, neutral recorder spoofing, a corrupted SQLite journal, attempted retrospective reassessment and public-only subprocess replay without any private signing key.

The bounded fixture is **one controversy per neutral local SQLite journal**. A production multi-case store would require per-case public evidence references and an externally pinned signed-tip recovery mechanism. A privileged file owner can roll back the SQLite database.

The locally pinned review root is an **assumption in the test**, not a source of real-world global ownership jurisdiction. Separate P-256 keys do not demonstrate independent human custodians, institutional recognition, actual succession, or an online legal entitlement. Signed clocks are simulated values without trusted wall-clock timestamping.

## Laws

```text
SAME ADDRESS != SAME OWNER
TWO VALID SIGNATURES != ONE RIGHTFUL SUCCESSOR
REVIEW ROOT != GLOBAL SOVEREIGN
REVIEW SELECTION != ACTUAL OWNERSHIP
REVIEW SELECTION != CANDIDATE'S LOCAL GRANT
LOCAL ARCHIVAL GRANT != FORWARDING OR EXECUTION
TWO VALIDLY SIGNED CONTRADICTIONS != TWO VALID AUTHORITIES
HISTORY PRESERVED != DISPUTE DECIDED
POLICY-BOUND ARCHIVE HOLD != NATIVE reLATTE HOLD
NEUTRAL WITNESS != RIGHTFUL SUCCESSOR
SIGNED LOCAL RECEIPT != EXTERNAL IMMUTABLE CUSTODY
SIMULATED CLOCK != TRUSTED WORLD TIME
```

## Run

Requires Python 3 standard library and OpenSSL. From repository root:

```bash
python3 ghot/unheard_choir_successors.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_successors.py' -v
```

`assess` CLI accepts public `--parcel`, separately owned `--old-local-package`, `--historical-pins`, signed `--policy`, independent `--local-review-root`, `--selections` JSON list, `--archive-grants` JSON object containing both contender slots, and `--now`. `record` additionally requires `--neutral-private-key` already present on the local vessel and `--neutral-db`; it never creates a signer identity. `verify` accepts the same public artifacts plus `--receipt` and cold-recomputes all 001–014 evidence without access to any private signer or source database.

## 015 adversarial frontier — THE RIGHTFUL THIRD PARTY

Suppose two successors have genuine identity signatures **and a third party possesses a prior contractual or owner-local delegation receipt** that was never presented to either. Do signed delegation grants compose across owner succession? Can an off-chain legal/political or physical custodian present an old but valid instrument without treating its historical signature as a current grant? The next experiment should make independent *source* admission and *new owner* consent explicit, preserve multiple inconsistent jurisdictional claims without arbitrarily inventing global sovereignty, and keep local archiving available without forwarding.
