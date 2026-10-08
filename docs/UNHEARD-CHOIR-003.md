# UNHEARD CHOIR 003 — THE FALSE APERTURE

**Owner:** GHoT. **Status:** deterministic simulation; draft branch stacked on UNHEARD CHOIR 002. **Not** hardware, real sourcing, authenticated source owners, privacy consent, independently signed witnesses, or native reLATTE dispatch.

## The attack

What if the advertised instrument has invented coverage, inflated gain, stale identity, or access that its supposed owner never granted?

002 can propose an instrument from a declared aperture catalogue. 003 refuses to treat that catalogue's **claims** as reliable evidence, then reuses 002's instrument probe only after an exact, fresh simulation approval.

```text
11 observed simulated signals
  + current instrument field (GHoT 002 shape)
  + UNTRUSTED vendor promises
  + separately supplied local owner registry fixture
  + owner-accepted history commitment to replayable 002 simulated observations
      -> REJECT unsupported, stale, withdrawn, private, unaffordable
      -> REPLAY historical 002 fixture experiments
      -> compare measured NEW SIMULATED SOURCE IDS / prior trial / cost
      -> propose one current permitted instrument, or HOLD
      -> future oracle is not opened during planning
EXPLICIT TEST APPROVAL of exact proposal and aperture
      -> revalidate every current input
      -> native 002 simulator (fixture-only)
      -> recompute before/after source-set delta
      -> unsigned, cold-verifiable receipt; no external effect
```

**Adversarial catalogue fixture** includes a fictional all-seeing instrument with advertised gain 1,000,000, a privately held community instrument that is not permissioned for proposal, an unaffordable radio ear, a material probe whose prior synthetic trial returned empty, and one lower-advertised community instrument whose prior simulated observation produced one new source ID.

The machine chooses the community proposal **because of accepted prior simulated novelty, not advertising**. This is a deliberately bounded policy test, not measured information gain in reality.

## Trust boundaries

1. The `field.json` file represents current instrument declarations with strict source-cut/epoch identifiers. Those declarations are still hypothetical.
2. `untrusted-catalog.json` represents attacker-controlled marketing. Its advertised gain is displayed in an audit witness but is **never used** in selection.
3. `owner-registry.json` is a separately supplied **simulation-only owner-accepted fixture**, not an identity credential. Its exact field and source digests, instrument/epoch matching, and history commitment prevent *catalogue-only* tampering from becoming consent. Attackers who control the registry itself remain in scope for future experiments; local digests do not prove independent origin.
4. `reviewed-history.json` supplies simulated prior trials. The code recomputes each prior trial using 002's actual fixture-only simulation and counts newly disclosed source IDs. A history record with wrong epochs or false physical-status claims refuses. Even a replayable fixture observation cannot establish a real source existed.
5. The future oracle remains separate and is opened only after exact proposal/aperture test approval and fresh 003 checks. This approval is NOT an owner signature or cryptographic credential.
6. A newly reported source ID is only a **novel simulated observation**, not human benefit, improved information, verified emergency, or real resource availability.

### Attack outcomes

| Attack | Expected |
| --- | --- |
| Huge gain promise for nonexistent aperture | `UNDECLARED_APERTURE` |
| Private instrument where local fixture owner refuses proposal | `OWNER_DID_NOT_ALLOW_PROPOSAL` |
| Current instrument above exploration budget | `UNAFFORDABLE_INSTRUMENT` |
| Existing instrument, but zero measured historical novelty | `NO_MEASURED_SIMULATED_NOVELTY` |
| Changed source, epoch, availability, registry or archive after planning | fresh revalidation denies stale plan |
| Duplicate/conflicting claims for one aperture | all those claims quarantined |
| No evidenced permitted candidate | `HOLD_NO_EVIDENCED_PERMITTED_INSTRUMENT` |
| Missing exact mock approval | future oracle not opened |
| Approved bounded future fixture returns no source | zero novel IDs, not world silence |
| Approved fixture contains consent-declined human need | HELD, no disclosed new need |
| Tampered output, even with recomputed SHA digest | cold re-execution differs, verify false |

## Run (stdlib Python, no dependencies)

From GHoT repo root:

```sh
python3 ghot/unheard_choir_false_aperture.py plan \
  --world fixtures/unheard-choir-002/observed-world.json \
  --field fixtures/unheard-choir-003/field.json \
  --claims fixtures/unheard-choir-003/untrusted-catalog.json \
  --registry fixtures/unheard-choir-003/owner-registry.json \
  --history fixtures/unheard-choir-003/reviewed-history.json > /tmp/choir003-plan.json

PROPOSAL_ID=$(python3 -c 'import json; print(json.load(open("/tmp/choir003-plan.json"))["proposal_digest"])')

python3 ghot/unheard_choir_false_aperture.py simulate \
  --world fixtures/unheard-choir-002/observed-world.json \
  --field fixtures/unheard-choir-003/field.json \
  --claims fixtures/unheard-choir-003/untrusted-catalog.json \
  --registry fixtures/unheard-choir-003/owner-registry.json \
  --history fixtures/unheard-choir-003/reviewed-history.json \
  --plan /tmp/choir003-plan.json \
  --oracle fixtures/unheard-choir-002/hidden-oracle.json \
  --approve-proposal "$PROPOSAL_ID" \
  --approve-aperture community-queue > /tmp/choir003-receipt.json
```

To cold-verify, repeat the `simulate` arguments above with the positional command `verify` and `--receipt /tmp/choir003-receipt.json`. In GitHub Actions the complete cold-process CLI path is exercised.

```sh
python3 -m unittest discover -s tests -p 'test_unheard_choir.py' -v
python3 -m unittest discover -s tests -p 'test_unheard_choir_blindspot.py' -v
python3 -m unittest discover -s tests -p 'test_unheard_choir_false_aperture.py' -v
```

## What 003 does **not** claim

- It does not discover undeclared blind spots.
- It does not prevent an attacker from authoring the entire registry, field, and purported archive. To prevent that requires independent authorization, signatures, and owner-local verification, **not** SHA-256 alone.
- It does not measure information-theoretic reduction in uncertainty or practical value. Novel source-ID counts are a deliberately narrow, gameable proxy.
- It does not autonomously listen or build hardware. It proposes an existing fixture instrument, without invoking the GHoT Instrument Rack (still on an independently governed draft PR stack).
- It does not access actual human information or validate consent, and no generated 003 receipt is signed or admitted by reLATTE.

```text
CLAIM != CAPABILITY
SOURCE CUT != WORLD COMPLETENESS
CATALOGUE PRESENCE != CURRENT OWNER PERMISSION
DIGEST AGREEMENT != INDEPENDENT AUTHENTICATION
HISTORICAL OBSERVATION != FUTURE ENTITLEMENT
NOVELTY != INFORMATION VALUE
INFORMATION VALUE != HUMAN BENEFIT
PROPOSAL != EXECUTION
UNOBSERVED != NONEXISTENT
EMPTY PROBE != WORLD SILENCE
```

## 004 candidate — THE LYING WITNESS

Attacker controls both the vendor catalogue and the owner-looking local registry. Introduce *independent native source-owner signing and challenge-response*, current incarnation checks, adversarial replay across world boundaries, and one permitted but misleading historical evidence sample. Require actual native GHoT and reLATTE validation for executable consequence. Prove that a signed false claim stays a false claim.
