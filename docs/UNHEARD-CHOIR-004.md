# UNHEARD CHOIR 004 — THE LYING WITNESS

**Scope:** source-authenticity versus source-truth adversarial specimen. Draft experiment on 003, which remains on 002 → 001. No real sensors, human identity verification, native task dispatch or reLATTE admission.

## Hypothesis and deliberate adversary

A dishonest source signs **PRESENT** with a *real valid ECDSA P-256 signature*. Two separately keyed, explicitly simulation-only observers report **EMPTY** for the exact same freshly issued challenge.

Expected outcome:

```text
owner-pinned challenge signing key
  → issue 128-bit nonce, owner epoch, aperture, instrument,
    current 003 proposal digest, roster digest, short expiry
  → cryptographic owner signature (native GHoT P-256 implementation)
      ↓
source key ────────── signs PRESENT
independent key A ─── signs EMPTY
independent key B ─── signs EMPTY
      ↓
exact source + observer public-key pinning and signature validation
fresh challenge / current incarnation / role / source-bound sample checks
      ↓
HOLD_AUTHENTIC_BUT_CONTRADICTED_SOURCE
      ↓
optional owner-local SQLite one-use review record (no native effect)
```

All signatures are **real P-256 ECDSA via GHoT's existing `relatte_identity.IdentityKey` / `verify_p256` functions** and OpenSSL. The 004 challenge and statements use **new, explicitly different domain-separated signing bytes**, not reLATTE's normative crossing or receipt signing envelopes. The ECDSA signing code is reused, not the authority of a reLATTE crossing.

## What the cryptography does and does not prove

- A signature binds specific bytes to a private key corresponding to a pinned public JWK. It establishes key-level attribution under a **locally supplied** trust policy. It does not establish that the key belongs to a real human, group, hardware sensor, or source owner.
- The owner-signed challenge binds the current 003 proposal, local roster, instrument, owner epoch, a 128-bit unique nonce, issuance time and maximum 120-second validity. Reusing a signed response against a *different* challenge fails.
- The three attestation keys must be distinct from one another and from the challenge key. This is **logical/key independence**, not proof of three independently observed physical events.
- Statements declare `SIMULATED_SELF_REPORTED`. The observer outputs are explicitly synthetic and can both be wrong or colluding. Agreement only produces `REVIEW_CANDIDATE_NOT_ADMITTED`; it is never certified as physical truth.
- A properly signed source's disagreement with the two observer keys forces HOLD rather than accepting a signed false claim.
- The local review occurrence may be recorded at most once per challenge digest in SQLite. A second attempted write is refused, even with altered attestations. Historical read-only assessment remains possible while the challenge is valid.

### Failure modes exercised

| Case | Outcome |
| --- | --- |
| Correctly signed lie contradicting two other signed statements | `HOLD_AUTHENTIC_BUT_CONTRADICTED_SOURCE` |
| Observer A/B disagree | `HOLD_OBSERVER_DISAGREEMENT` |
| Only one observer / absent statements | `HOLD_MISSING_INDEPENDENT_WITNESSES` |
| All three report same outcome | `REVIEW_CANDIDATE_NOT_ADMITTED` |
| Imposter signs with valid unpinned key | Reject before consensus |
| One key claims two roles | Reject distinct-pinned-key boundary |
| Mutated statement after signing | Reject cryptographic signature |
| Fresh nonce replaces old challenge | Reject previous statements |
| Future or expired challenge | Reject freshness |
| Changed owner epoch, parent world/proposal, or trust roster | Reject |
| Physical status asserted where only simulated is allowed | Reject |
| Repeated one-use review occurrence | SQLite uniqueness denial |
| Unapproved native action | No such operation in specimen |

## Usage

From GHoT root, with `python3` and `openssl` on PATH:

```sh
python3 ghot/unheard_choir_lying_witness.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_lying_witness.py' -v
```

The `demo` action creates four **temporary**, separate P-256 private keys (one local challenge signer, one dishonest claimant and two distinct observers) under a temporary directory. Keys are removed when demo exits. No private key is placed in the repository. The demonstration creates an actual owner-signed challenge, three signed simulation-only statements, evaluates contradictions, and tries to record the same event twice. The second local review occurrence must be denied.

For cold-process verification in a separate execution, tests write the public signed challenge, pinned roster, 003 proposal and attestations as JSON, then call:

```sh
python3 ghot/unheard_choir_lying_witness.py assess \
  --parent /tmp/004-parent.json \
  --roster /tmp/004-roster.json \
  --challenge /tmp/004-challenge.json \
  --statements /tmp/004-statements.json \
  --now <DECLARED_TEST_CLOCK>
```

Use `record` with the same arguments and `--db /path/to/local.sqlite` to record one authenticated assessment occurrence. The test clock is supplied in this bounded specimen to allow deterministic stale/future tests. A real operating surface must use a trusted host clock and stronger replay policy, not a caller-controlled timestamp.

## Boundary to 003 and reLATTE

This prototype starts with the **actual 003 proposal** computed from 003 fixture inputs, checking its integrity and binding it to local pinned keys. However it does **not** independently verify real identity, owner constitutional authority or outside-world witness truth. The trust roster is fixture-generated; whoever controls its creation can substitute an entire coordinated lie.

It is intentionally **not** a new normative reLATTE crossing or signed receipt, and no GHoT instrument is actually dispatched. Any eventual cross-repo wiring must use GHoT's existing native fresh card/dispatch and reLATTE's verified receiver and local admission, with independently provisioned and authenticated owner keys. A local SQLite review log does not grant those permissions.

## Non-collapse laws

```text
SIGNED != TRUE
PINNED KEY != HUMAN IDENTITY
OWNER CHALLENGE != OWNER AUTHORITY
TWO KEYS != TWO INDEPENDENT PHYSICAL OBSERVATIONS
AGREEMENT != CORRECTNESS
CHALLENGE VERIFIED != PERMISSION TO ACT
LOCAL RECORD != reLATTE SIGNED RECEIPT
AUTHENTIC SOURCE != ADMISSIBLE CONSEQUENCE
HISTORICAL SIGNATURE != CURRENT CAPABILITY
REVIEW CANDIDATE != ADMISSION
```

## Explicit next pressure

**005 — THE COLLUDING OBSERVERS**: all three keys sign the same lie, or a compromised signer stamps a valid challenge. Can a receiver obtain *external, instrument-distinct evidence* (source-calibrated, context-bounded, privacy-reviewed) and distinguish independent measurement from correlated claims? 004 cannot: it intentionally returns review-only, not truth.
