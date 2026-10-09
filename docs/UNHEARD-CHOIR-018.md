# UNHEARD CHOIR 018 — THE NEGATIVE THAT FORKED

**Stacked executable GHoT simulation**: 018 → 017 → 016 → 015 → 014 → 013 → 012 → 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001.

All institutions, times, people, record copies, site identities and transmissions are synthetic. P-256 signatures authenticate the fixture keys and exact signed statements, **not real-world time, legitimacy, legal authority or physical custody**. No native reLATTE RECEIVE/HOLD, network transport, RF or external device effects are implemented.

## The newly tested edge

In 017 one observer had the original signed 015 source review and another observer had the same approval plus a genuine, later 016 exact-source revocation. 018 deliberately introduces **multiple distinct and fully signed source statements**:

1. The original source reviewer signs a 016 `REVOKE_EXACT_SOURCE_REVIEW` binding the original 015 source-review digest, claiming issue at simulated 1100, effective 1200.
2. **The same source private key** signs a second 016 exact-source revocation binding the same old 015 review, claiming issue at simulated 1120, effective 1230. Both verify; neither is automatically a more authoritative source policy. Distinct signature bodies/intervals cannot be ranked by ECDSA validity, arrival order or claimed clock.
3. The same source reviewer signs a separate 018 `SOURCE_CLAIM_NOT_VALID_GRANT_OR_REACTIVATION` reinstatement *claim*. It binds the original 016 revocation statement, the 016 pinned source policy, the 017 roster, the same historical approval and a fresh synthetic time bound. It explicitly declares `effect_permission=NONE` and `restores_native_source_authority=false`.

```text
        Authentic historical 015 source approval
                         |
             signed original 016 revocation A
                         |
             +-----------+-----------+
             |                       |
         WEST VIEW                EAST VIEW
     additional signed B        original 017 A
     (second revocation)        plus signed 018
                                reinstatement claim
             |                       |
             +-----------+-----------+
                         |
           Independently verify both site keys
           and every source P-256 signature
                         |
       Evidence set {A, B, reinstatement(A)}
       Canonically sorted by exact artifact digest
                         |
          HOLD_SOURCE_REVOCATION_REINSTATEMENT_UNRESOLVED
                         |
          WEST signs owner-local review receipt
          and durably stores once in its own SQLite
          without mutating either 017 original.
```

A separate comparison of WEST's B and EAST's A alone produces **`HOLD_MULTIPLE_SOURCE_REVOCATIONS_UNORDERED`**. Distinct source-signed revocations are retained as multiple authenticated assertions, not necessarily proof of malicious equivocation. The experiment deliberately refuses to *infer* which source statement cancels or supersedes another absent a separate, independent precedence authority.

With only one signed original revocation, the decision is `HOLD_SINGLE_SIGNED_REVOCATION_NO_NATIVE_GRANT`; with no authenticated negative evidence visible, `HOLD_SOURCE_STATE_UNKNOWN_NO_NEGATIVE_EVIDENCE`.

## What the experiment actually proves

- All 015 approval and 016 revocation ancestry is cold-verified using inherited code and locally pinned public identities. The source's original approval remains verifiable and is identified by the same immutable digest in both sides' assessment.
- The reinstatement is authenticated by the **existing 016 source reviewer key**, not an observer/holder/successor key. It must reference an independently verified 016 `REVOKE_EXACT_SOURCE_REVIEW`, exact prior source digest and 017 signed roster. A forged source signature, key substitution, wrong grant, modified effect field, extra schema field, backdated issuance or bad clock fails closed.
- WEST and EAST's separately P-256-signed **017 original snapshots remain unchanged**. New 018 site views sign the exact original snapshot plus additional authenticated source evidence. The views are stored in separate local SQLite databases, with no overwriting of a prior signed view by a later state.
- Each source event is verified, deduplicated by its actual signed artifact digest, and canonically sorted. Sorting is for deterministic **evidence enumeration**, not a priority order. Swapping which site delivered first must not select a winner.
- The local recipient signs a new domain-separated, genesis-bound **018 HOLD receipt** binding both exact signed views, all authenticated source evidence digests, the owner's simulation clock and the computed disposition. Duplicate gossip returns the exact original receipt; a different remote view or clock cannot retrospectively change signed local history.
- A third Python process can verify the receipt with all public 015–018 JSON evidence, no private keys and no source/recipient database. It recomputes original 017 signatures, each 016/018 source claim and the final recipient-local receipt.

## Explicit non-collapse laws

```text
SOURCE SIGNATURE != SOURCE STATEMENT PRECEDENCE
TWO VALID REVOCATIONS != AUTOMATICALLY ONE WINNING REVOCATION
SIGNED REINSTATEMENT CLAIM != LIVE REINSTATEMENT
CLAIMED CLOCK ORDER != INDEPENDENT AUTHORITY ORDER
ARRIVAL ORDER != SOURCE JURISDICTION
VALID OLD APPROVAL != CURRENT LIVE CAPABILITY
SAME SOURCE KEY != CONSISTENT SOURCE HISTORY
AUTHENTIC CONFLICT != PERMISSION TO ERASE EITHER CLAIM
EVIDENCE DEDUPLICATION != HISTORY DELETION
SOURCE EQUIVOCATION != GLOBAL OWNERSHIP ADJUDICATION
SIGNED LOCAL HOLD != NATIVE reLATTE HOLD
COLD REPLAY != PHYSICAL DELIVERY OR PUBLIC IMMUTABILITY
```

## Reproduction

Requires Python 3 standard library and OpenSSL from repository root:

```bash
python3 ghot/unheard_choir_source_fork.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_source_fork.py' -v
```

`verify` consumes 13 public 015 evidence JSON files named `--parcel`, `--historical-local-package`, `--historical-pins`, `--succession-policy`, `--succession-root`, `--reviewer-selections`, `--candidate-archive-grants`, `--legacy-delegation`, `--third-party-policy`, `--third-party-root`, `--third-party-presentation`, `--fresh-source-review`, `--new-owner-consent`; six 016/017 public files `--custody-policy`, `--custody-root`, `--holder-manifest`, `--roster`, `--roster-root`; and `--local-view`, `--remote-view`, `--fork-receipt`. The verifier needs neither signer keys nor SQLite files.

The workflow `.github/workflows/unheard-choir-018.yml` runs 018 adversarial tests, inherited 001–017 suites, and an explicit invariant-checked CLI demo.

## Limits

The two valid revocations might both be compatible in a real institution. This specimen records distinct signed claims with no authority to infer supersession, rather than claiming to adjudicate malicious behavior or factual contradiction. The valid reinstatement **claim** likewise does not prove an authorized current regrant.

No authoritative source epoch/contractual ordering, external signature checkpoint, trusted timestamp, source-wide transparency log, hardware, independent human witness or production reLATTE receipt has been integrated. Observers run on separate local SQLite paths within one host, not on demonstrably separate machines. A privileged disk owner can delete or roll back a local database; durable here means transactional local persistence under normal operation.

## 019 frontier — THE REFEREE WHO REFUSED TO RULE

Introduce externally attested source-epoch precedence and an explicitly owner-local disposition selector, each with its own signing key. Demonstrate that an **independently authorized** precedence proof can resolve which claim is applicable to a *particular* archival review without rewriting signed conflicting source history or manufacturing universal authority. If the referee declines to decide or epochs conflict, preserve both claims and HOLD.
