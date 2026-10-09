# UNHEARD CHOIR 017 — THE NEGATIVE THAT OUTLIVED THE POSITIVE

**Executable GHoT simulation stacked on 016 → 015 → 014 → 013 → 012 → 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001.** Real fixture P-256 signatures, synthetic clocks and participants. No network, human identity proof, production source capability, native reLATTE RECEIVE/HOLD, physical custody or external execution.

## Question

Two observers both possess the **same authentic historical 015 source-review approval**. WEST has not seen a later source notice; EAST possesses a valid 016 source-reviewer-signed `REVOKE_EXACT_SOURCE_REVIEW`, binding the exact old approval, with a simulated effective time. Both observers report authentic but incomplete *local* knowledge.

- WEST's original signed state is **`HOLD_REVOCATION_STATE_UNKNOWN`**. Its lack of a notice cannot be treated as proof of unrevoked permission.
- EAST's original signed state is **`HOLD_SIGNED_REVOCATION_WITNESSED_IN_GOSSIP`**. The signed 016 notice is independently reverified under its previously pinned source-reviewer key and exact 015 approval.
- Simulated initial transport drops the notice. WEST remains UNKNOWN; its original signed SQLite observation is unchanged.
- The EAST snapshot reaches WEST through a bounded simulated gossip call. WEST verifies the separate EAST P-256 observer signature **and** the original 016 source-reviewer signature, repeats 015–016 ancestry verification, then signs and commits a **new owner-local gossip assessment**. The result is `HOLD_SIGNED_REVOCATION_WITNESSED_IN_GOSSIP`; the original WEST UNKNOWN is preserved as historical evidence.
- A duplicate transfer returns the same persisted review without another receipt, effect or change to either original.
- A third Python process can cold-verify WEST's owner-local review using public 015–017 evidence alone, with no private signer file or SQLite database.

### Trust boundaries

1. The immutable *historical positive* is the exact signed 015 fresh source review. Both observers bind the same `original_015_source_approval_preserved` SHA-256 digest and the same independent 016 holder inventory, policy and pinned trust root. The source approval is not deleted, mutated or treated as current native authorization.
2. The authenticated *negative* is a separately signed, exact-source-digest-bound **016 local revocation notice** from the inherited P-256 source reviewer. It may be absent from one observer's local packet. Missing ≠ unissued; valid signature ≠ trusted physical timestamp.
3. A separate 017 root, pre-pinned by the verifier outside source evidence, signs exactly two named observer public keys, WEST and EAST. These keys are distinct from every 001–016 actor, reviewer, holder, predecessor source, neutral recorder and prior root. Observer gossip never replaces source authority.
4. Each observer signs its own zero-indexed, genesis-bound observation into its **own SQLite database**. No incoming remote history may overwrite that signed original.
5. After receiving a peer package, the local owner signs a separate single-event **GHoT-experimental review** bound to both fully verified signed snapshots and the actual recipient-local simulated clock. Duplicate imports preserve the receipt unchanged; a different peer evidence package cannot reclassify an earlier signed receipt.
6. Any signed source status other than a revocation is authenticated and retained but **cannot silently become a revocation**. If two different authentic source status statements are seen, the system returns `HOLD_DISTINCT_SIGNED_SOURCE_NOTICES_UNRESOLVED` rather than choosing a preferred signer or arrival order.

### Negative evidence, clocks and exact expiry

The comparison considers a source-signed 016 revocation effective only relative to the **receiver-provided synthetic clock**:
- No signed notice visible to either observer → `HOLD_REVOCATION_STATE_UNKNOWN`.
- Revocation signature valid but simulated effective instant is later than review clock → `HOLD_SIGNED_FUTURE_REVOCATION_NOT_ACTIVE`. Historical approval remains signed but this does *not* authorize device action.
- Signed revocation visible within its simulated notice interval → `HOLD_SIGNED_REVOCATION_WITNESSED_IN_GOSSIP`.
- Signed revocation's simulated notice interval has expired → `HOLD_SIGNED_EXPIRED_NOTICE_NO_NEW_CURRENT_GRANT`. The negative remains verifiable as history. Expiry does **not** reinstate any native permission or prove a restored source grant.
- Two different, validly signed source notices in the cross-site evidence → `HOLD_DISTINCT_SIGNED_SOURCE_NOTICES_UNRESOLVED`. No implicit timestamp winner.

Source-notice fields are exact schema, exact source-review digest, independently authenticated P-256 signature and bounded simulated window via the original 016 verifier. New root and site signatures have distinct domain-separated P-256 signing bytes. Clock data is caller-supplied simulation only, never independently attested calendar time.

## Source and artifact layout

- `ghot/unheard_choir_delayed_revocation.py` — signed 017 roster, two locally signed snapshots, independently signed original SQLite observations, simulated cross-site gossip verification, signed owner-local review, cold replay and `demo` / `verify` CLIs.
- `tests/test_unheard_choir_delayed_revocation.py` — malformed, forged, contradictory, delayed and expired source notices, observer signature spoofing, omitted notice unknown, 015 positive preservation, duplicate/resumption, local SQLite tampering, and public-only subprocess cold verification.
- `.github/workflows/unheard-choir-017.yml` — new hostile 017 test matrix first, then inherited 001–016, then signed demo invariants.
- `docs/UNHEARD-CHOIR-017.md` — this contract and limitations.

## Laws

```text
APPROVAL NOT YET REVOKED TO ME != APPROVAL NEVER REVOKED
MISSING NEGATIVE EVIDENCE != NEGATIVE DOES NOT EXIST
SOURCE-SIGNED REVOCATION != ERASED HISTORICAL APPROVAL
VALID OLD APPROVAL != CURRENT NATIVE GRANT
GOSSIP DELIVERY != RETROACTIVE HISTORY EDIT
OBSERVER SIGNATURE != SOURCE AUTHORITY
SIGNED CLOCK != TRUSTED REAL-WORLD TIME
EXPIRED REVOCATION NOTICE != REINSTATED PERMISSION
DISTINCT SOURCE NOTICES != ORDER-BASED TRUTH
COLD SIGNATURE VERIFICATION != PHYSICAL WITNESS INDEPENDENCE
SIGNED LOCAL HOLD != NATIVE reLATTE HOLD
```

## Reproduction

Requires Python 3 standard library and OpenSSL from GHoT root:

```bash
python3 ghot/unheard_choir_delayed_revocation.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_delayed_revocation.py' -v
```

`verify` consumes the thirteen **public** 015 evidence documents as `--parcel`, `--historical-local-package`, `--historical-pins`, `--succession-policy`, `--succession-root`, `--reviewer-selections`, `--candidate-archive-grants`, `--legacy-delegation`, `--third-party-policy`, `--third-party-root`, `--third-party-presentation`, `--fresh-source-review` and `--new-owner-consent`, followed by `--custody-policy`, `--custody-root`, `--holder-manifest`, `--roster`, `--roster-root`, `--local-snapshot`, `--remote-snapshot`, `--gossip-review`. All are public JSON files. Verification replays both 016 source-local assessments and the new signed receipt without access to any keys or source/receiver SQLite journals.

### Honest limitations

This is an **offline deterministic method-call gossip simulation**, not real online transport, an externally anchored event log, or a distributed consensus system. Each side is an isolated SQLite path within one fixture host, not cryptographic proof of separate physical sites or legal owners. Privileged rollback can erase local SQLite unless a signed tip is preserved by another trusted party. The original 015 source review and 016 revocation are local synthetic P-256 statements; a revocation signature authenticates who asserted revocation, not whether it became legally or natively effective elsewhere. There is **no automatic production reLATTE crossing, grant, asset disposal or external execution**.

## 018 pressure — THE NEGATIVE THAT FORKED

Suppose the source reviewer itself signs **two incompatible revocations**, or signs a revocation and a separately signed reinstatement with overlapping claimed times. Can multiple observer-relative histories preserve signed source equivocation without granting priority to clocks, network arrival or signer key custody? Add explicit owner-local precedence policy/epoch proof and external signed consistency checks only where genuinely available, and let the unresolved source conflict remain durable HOLD.
