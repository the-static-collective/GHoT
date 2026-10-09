# UNHEARD CHOIR 019 — THE REFEREE WHO REFUSED TO RULE

**Executable, synthetic GHoT experiment** stacked on 018 → 017 → 016 → 015 → 014 → 013 → 012 → 011 → 010 → 009 → 008 → 007 → 006 → 005 → 004 → 003 → 002 → 001.

## The question

018 preserved a source-authenticated fork: two distinct source-signed revocations and a source-signed reinstatement **claim**. Their cryptographic validity did not prove which signed statement governed. Neither arrived-first logic nor self-reported timestamp can turn source history into an authoritative winner.

019 introduces three **different** present-tense, scoped actors:
- An **independently pinned source-epoch witness** signs bounded assignments for individual verified 018 signed source documents. Its signed assignments are evidence of a *local epoch policy*, not certified physical time or real institutional power.
- A **separate referee** may `DECLINE` or `SELECT` a single signed statement for exactly one local archival-review purpose. A forged referee key is refused. An authentic referee who selects a lower/not-attested event cannot become the winning authority.
- A **separate owner-local selector** may `REFUSE` or `SELECT` exactly the referee's highest independently attested event. Even fully aligned signatures permit only archival review in a GHoT-local HOLD, not a native reLATTE RECEIVE or live grant.

A fourth fresh signer is a **neutral recorder**, and the local trust-policy root is a fifth separate P-256 key. All five are independently pinned or bound by a root-pinned signing policy and are distinct from inherited source actors, 015 third-party holders, 016 source reviewers, 017 observers, and 018 source witnesses. Every producer and checker verifies the complete original 001–018 signed source evidence and retains its digests intact.

## Running witness

```text
Authentic 015 historical source approval
   |
   +-- 016 signed revocation A
   +-- 016 signed revocation B
   +-- 018 signed reinstatement claim for A
             |
        018 observer-local source fork, fully reverified
             |
        external-to-claimants 019 pinned policy root
             |    exact 018 local/remote signed views
             |    all three source-event digests
             |    allowed purpose = ONE_CASE_HISTORICAL_ARCHIVE_REVIEW_ONLY
             |
        independent epoch witness (distinct key)
             +-- A -> signed epoch 1
             +-- B -> signed epoch 2
             +-- reinstatement claim -> signed epoch 3
             |
        referee (distinct key)
             |--- no response ---> HOLD_REFEREE_HAS_NOT_RULED
             |--- signed DECLINE -> HOLD_REFEREE_EXPLICITLY_DECLINED
             |--- lower epoch ---> HOLD_REFEREE_CHOICE_CONTRADICTS_CERTIFIED_PRECEDENCE
             |
             +--- highest uniquely certified epoch
                        |
                 owner-local selector (separate key)
                    |-- absent ----> HOLD_OWNER_LOCAL_SELECTION_ABSENT
                    |-- refusal ---> HOLD_OWNER_LOCAL_REFUSED_OR_DIFFERENT
                    |-- same event -> HOLD_SCOPED_ARCHIVAL_REVIEW_SELECTED_NOT_ADMITTED
                                        |
                              new neutral P-256 signed HOLD receipt
                              transactionally written to one-case SQLite
                              keyless cold-verifiable in a fresh process
```

The result stays HOLD in **every** world. Selection is a statement about **which source evidence to archive/review under this particular local policy**. It does not authorize forwarding, devices, source grants, global asset custody, rightful ownership or production execution.

## Missing or contradictory independently attested epochs

The local epoch witness signs `source_event_digest`, `source_epoch`, `policy_digest`, explicit `grants_execution=false`, and `is_external_certificate_of_source_time=false`. Each assignment is checked with real P-256 verification under an **externally supplied pinned public root's policy**, rather than accepting a claimed key from the source material.

An incomplete assignment set produces **`HOLD_MISSING_INDEPENDENT_EPOCH_PROOF`**. Two individually valid assignments referring to the **same** source artifact at distinct epochs—or two documents with the same independently signed epoch—produce **`HOLD_CONFLICTING_EPOCH_ASSIGNMENTS`**. Neither a referee's choice nor an owner's preference is allowed to erase that independently authenticated contradiction.

Even if all assignments are unique and complete, epoch ordering is **local policy authority only**. A referee may refuse. An owner may refuse. The source's existing claims are not edited by such choices.

## Local receipt and replay

The 019 assessment signs and records:
- Exact digest of the original 018 signed fork and source event set
- Digest of the source-epoch attestations (including contradictory attestations)
- Exact referee and owner-local signed statement digests, or explicit `null`
- Effective GHoT-local HOLD outcome and caller-supplied simulated clock
- `native_relatte_receive=false`, `native_relatte_admission=false`, `forwarding_permitted=false`, `external_execution=false`, `effects=[]`, `authority=NONE`

A separately keyed neutral 019 recorder signs that assessment. The fixture uses a transactionally committed **one-case SQLite journal**. Duplicate imports with unchanged exact evidence reproduce the saved receipt. Attempting to replace an older signed refusal with a new acceptance, change the clock, forge the recorder signature, or rewrite the original source-event digests fails closed.

The public `verify` command recomputes the full 001–019 original provenance and recipient-local disposition from JSON artifacts alone. It requires **no** private signer, source process, network, or SQLite file.

## Laws

```text
HISTORICAL SOURCE SIGNATURE != PRESENT SOURCE AUTHORITY
SOURCE CLAIMED CLOCK != EXTERNAL PRECEDENCE CERTIFICATE
SIGNED EPOCH CERTIFICATE != NATIVE SOURCE GRANT
CERTIFIED ORDER != UNIVERSAL AUTHORITY
REFEREE CHOICE != OWNER CHOICE
REFEREE REFUSAL != AUTO-SELECTION
OWNER REFUSAL != HISTORICAL EVIDENCE DELETION
TWO VALID EPOCHS FOR ONE EVENT != ONE CERTIFIED TRUTH
TWO EVENTS WITH ONE CERTIFIED EPOCH != A TIMESTAMP TIEBREAKER
SCOPED ARCHIVE SELECTION != NATIVE reLATTE RECEIVE
SOURCE FORK HOLD != SOURCE HISTORY ERASURE
SIGNED LOCAL RECEIPT != IMMUTABLE EXTERNAL CUSTODY
```

## Test cases

The 019 adversarial matrix includes:
- Missing epoch attestations, duplicate epoch assignments, two contradictory but authentic attested epochs, out-of-range integers and bool-as-int confusion
- Forged epoch signer, forged referee, forgery of owner and receipt, historical holder impersonating a current referee
- Referee declining, unknown selected artifact, lower epoch selected despite valid signature, purported global referee powers, revoked/superseded clock assertions with insufficient proof
- Independent owner refusing, selecting a different event, signing an admission claim, or acting without the signed referee
- Fully reproduced 018 source fork and 015 original approval digests, with no native action in any path
- Durable one-case neutral SQLite receipt, duplicate exact replay, forged stored record, retrospective change of ruling, and cold public-only separate-interpreter verification

## Reproduction

From GHoT root, Python 3 standard library and OpenSSL:

```bash
python3 ghot/unheard_choir_referee.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_referee.py' -v
```

The public `verify` command takes the 13 original 015 JSON arguments, 016 public `--custody-policy`, `--custody-root` and `--holder-manifest`, 017 `--roster` and `--roster-root`, 018 `--local-view` and `--remote-view`, and 019 `--precedence-policy`, `--precedence-root`, `--epoch-certificates`, optional `--referee-statement`, optional `--owner-selection`, and the signed `--receipt`. All fields are exact and independently verified. The new `assess` and `record` commands accept the same public evidence, with `--now`; `record` additionally needs an already present local `--neutral-private-key` and `--neutral-db`.

## Honest limits

**The source-epoch witness is only a preprovisioned local simulation trust root**, not a validated external organization or a physically anchored source timeline. Signing epochs as unique integers does not itself prove the signer knew the true order, and even a correct source-ordering certificate does **not** imply legal/production authority. The referee role is defined by the local root's policy; it is not a court, globally authoritative identity registry, or native reLATTE source organ. Clocks are synthetic and caller-supplied. The five new identities and the historical source signers are generated in a common local fixture. There is **no real network**; SQLite can be rolled back by a privileged disk owner without independent signed tip custody.

The 018 reinstatement remains a **signed claim**, never a native grant. Even a valid 019 local selection of that claim does not reinstate an expired source approval or authorize external execution. This branch does not merge any earlier stacked experiment or deploy a runtime.

## 020 pressure — THE REFEREE WHO DIED

After an owner-local signed 019 archival selection, revoke/retire the referee's signing identity and restart the witness runtime. Can the signed old decision remain verifiable while no current request is authorized merely by stale signatures? Test new pinned independent referee epochs, owner-local consent for each specific new case, and rejection of historical-referee replay. The old disposition is history; the new decision is a fresh local crossing.
