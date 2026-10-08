# UNHEARD CHOIR 006 — THE COUNTERFEIT INSTRUMENT

**Status:** bounded, deterministic GHoT executable experiment stacked on 005 → 004 → 003 → 002 → 001. **Simulation only.** This does **not** authenticate physical sensors, actual custody, human owners, collection times, external truth, or authorize any effect.

## Hypothesis

005 defeats colluding signed observers when differently sourced synthetic frames contradict them. But what if the attacker's private key **is the primary sensor's actual pinned key**, or the firmware itself lies?

Then even a correctly signed sensor measurement can be fabricated. 006 asks whether a **second, differently mapped simulated measurement path with separately signed custody claims** is enough to prevent false promotion—and what happens if the two paths share an undeclared common dependency.

```text
source + 2 observers : PRESENT, PRESENT, PRESENT    (3 valid signed statements)
                      │
primary sensor        : [1,1,1,1,1,1,1,1]          (real key, compromised)
primary mapping       : PRESENT                     (005 any-nonzero)
                      │
primary custodian     : independently signs exact primary measurement
                      │
owner signed pinset    : two instrument keys, separate custodian keys,
                         exact challenge, declared dependency roots and
                         two *different* toy modality profiles
                      │
secondary sensor      : [0,0,0,0,0,0,0,0]          (distinct signer)
secondary mapping     : EMPTY                      (thermal two >=128)
secondary custodian   : independently signs exact secondary measurement
                      │
                          ▼
HOLD_COUNTERFEIT_OR_CALIBRATION_CONFLICT_UNRESOLVED
```

**The conflict proves neither which instrument is compromised nor that an event occurred.** It proves only that two separately signed synthetic measurement channels did not agree under fixed, declared local mappings.

## Implemented boundaries

- **Four inherited witnesses** from 004 (one owner-challenge signature, three source/observer statements) and the primary 005 instrument's signed precommit + sample report. Every inherited signature, nonce, time window, source cut and instrument incarnation is reverified by the existing 004/005 code.
- A separate owner-key-signed **current simulation-only pinset**, bound to the exact active challenge, 003 proposal and 005 anchor, declares the keys and roles of both instruments and both custodians.
- Eight distinct P-256 key identities are required across owner, three witnesses, two instruments and two custodians. A sensor cannot be its own custodian; one custodian cannot sign for both sensor roles.
- The primary instrument is allowed to be compromised: it still produces **cryptographically valid** signatures over counterfeit samples. This simulates an attacker with the real primary sensor's signing capability.
- The secondary toy modality uses `SIMULATED_THERMAL_TWO_FRAMES_ABOVE_127_V0` (at least two of eight synthetic 8-bit frames ≥128 means `PRESENT`). It is a **different local interpretation function**, not proof of a distinct calibrated physical sensor.
- Each custodian makes a **signed assertion** binding the exact measurement digest, challenged world, channel, signer, modality, instrument epoch, locally pinned dependency roots and a self-reported acquisition time.
- The two instrument channels explicitly declare upstream dependency roots. If the lists overlap, the decision is **`HOLD_DECLARED_SHARED_DEPENDENCY`**, even if both synthetic outputs agree.
- No evidence or partially supplied custody receipts → HOLD/fail-closed. Changed sensor bytes, wrong calibration, stale/forged signatures, altered custody/owner pins, replayed challenge, changed source cut or impersonated roles → denial.
- If both toy modalities agree and the 005 gate is still a review candidate, 006 returns **`REVIEW_DECLARED_DISTINCT_MODALITIES_CONCORDANT_NOT_ADMITTED`**, never truth, ownership or native execution.

## Critical distinction: signed custody versus verified custody

The newly created 006 P-256 custody records are **real cryptographic signatures on simulated assertions**. They are **not** reLATTE canonical signed receipt objects and do not establish an actual chain of physical custody. They may be false if the custodians lie or a key is compromised. Two separate signers can secretly share hardware, collection code, timekeeping, firmware, data source or operator control. The dependency lists are entirely **declared**, and undisclosed common causes remain unproven.

The primary's 005 precommit timestamp and custodians' 006 acquisition times are self-reported. This test proves integrity *relative to those signatures*, not independent temporal ordering. Even an attacker who supplies a fully different trust root can arrange apparently consistent evidence. The code never treats such assertions as owner authority.

## Run

Requires Python 3 stdlib and OpenSSL. From GHoT root:

```bash
python3 ghot/unheard_choir_counterfeit.py demo
python3 -m unittest discover -s tests -p 'test_unheard_choir_counterfeit.py' -v
```

The demo creates eight separate P-256 key files **inside a temporary directory**, uses the legitimate primary signer key to fabricate the primary observation, and separately signs a contradictory secondary toy measurement and two custody assertions. On exit, the temporary directory and private keys are removed.

The standalone read-only CLI `assess` accepts `--parent`, `--roster`, `--challenge`, `--statements`, `--primary-anchor`, `--primary-precommit`, `--primary-measurement`, `--pinset`, `--primary-custody`, `--secondary-custody`, `--secondary-measurement`, and `--now`. If all four 006 files are omitted the result is a HOLD for missing secondary evidence; a partial set is refused.

`verify` takes the same args plus `--receipt`, reconstructing the result in a separate process. It needs only public evidence and pinned public keys, never the private keys. CI runs all ancestor tests and a cold-process replay test.

## Laws

```text
SIGNED SAMPLE != VERIFIED REAL OBSERVATION
TRUSTED KEY != TRUSTED HARDWARE
DIFFERENT KEYS != INDEPENDENT SENSORS
CUSTODY SIGNATURE != PHYSICAL CUSTODY PROOF
DIVERGENT MODALITIES != IDENTIFIED LIAR
TWO CONCORDANT SIMULATIONS != WORLD TRUTH
DECLARED INDEPENDENCE != VERIFIED INDEPENDENCE
SHARED DEPENDENCY != INDEPENDENT EVIDENCE
TEMPORAL CLAIM != EXTERNALLY ATTESTED TIME
REVIEW CANDIDATE != ADMISSION
P-256 ASSERTION != reLATTE SIGNED RECEIPT
```

## What 007 would need

**THE HIDDEN COMMON CAUSE:** derive actual cross-source provenance graphs from multiple independently attestable devices or verifiable fixtures, record challenges externally, test whether disjoint dependency paths really exist rather than merely being asserted, and reproduce the experiment under adversarial compromised key/custodian trust roots. Native GHoT dispatch and reLATTE RECEIVE/HOLD remain separate integration and authorization tasks until proven.
