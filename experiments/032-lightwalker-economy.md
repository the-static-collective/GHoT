# Experiment 032 — Lightwalker Economy 001

## Question

Can a verified useful-work artifact acquire a durable non-monetary contribution address, cross sovereign boundaries, and receive different Realm-local economic interpretations **without turning verification into money or rewriting the underlying history**?

## Construction

Experiment 032 sits directly on Ice Cube 031.

```text
GHoT useful computation
        |
        v
Ice Cube specimen
        |
        v
Dogram bounded verification
        |
        v
immutable Workmark
        |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
Lantern Realm             Forge Realm           Witness Realm
7 lumen                   96 compute-credit      no valuation
        |                      |                      |
        +---------- same Workmark id ----------------+
```

The Workmark records attributable birth facts and verification references. It deliberately contains no price, token balance, human-worth score, or universal exchange rate.

A Realm publishes an **economic lens** separately. Applying that lens creates an **economic projection**. The projection is content-addressed and points back to both the immutable Workmark and the declared lens that produced it.

## Laws frozen by the experiment

```text
ACT != WORKMARK
WORKMARK != MONEY
WORKMARK != SCORE
DOGRAM VERIFICATION != ECONOMIC VALUATION
VALUATION POLICY != HISTORY
SAME HISTORY != SAME VALUATION
PROJECTION != WORKMARK
PROJECTION MAY NOT REWRITE WORKMARK
REALM-LOCAL VALUE != UNIVERSAL VALUE
DELIVERY != PAYMENT
```

## Why this is Lightwalker-shaped

The original Lightwalker economy wanted useful participation, artifacts, guild/Realm treasuries, and portable proof of contribution. The missing architectural distinction was that a contribution receipt and its economic interpretation are different objects.

Experiment 032 makes that distinction executable.

The first Workmark is born from a verified Ice Cube. Three Realms then read the same Workmark:

- Lantern Realm projects `7 lumen`.
- Forge Realm projects `96 compute-credit`.
- Witness Realm explicitly chooses `no-economic-interpretation`.

All three outputs are valid because none claims to be the Workmark itself.

## reLATTE boundary

The Lantern projection is wrapped in a signed reLATTE crossing with:

```text
declared_kind = LIGHTWALKER_ECONOMIC_PROJECTION
requested_effect.operation = consider-economic-projection
mint_authority_requested = false
```

The receiver first **HOLDs** the parcel with semantic effect `none`, then explicitly **ADMITs** it.

Admission means only:

> this Realm has accepted this projection record into local information.

It does **not** mean payment, settlement, minting, ownership transfer, or universal recognition.

## Dogram boundary

Dogram remains upstream of economics. In this slice it verifies the bounded Ice Cube specimen. The Workmark may reference that verification, but the Realm-local quantity is not a Dogram output.

A future composition can replace the compact Workmark birth in this GHoT experiment with Dogram's richer `CONTRIBUTION-FIELD-001` Workmark and measurement receipts. The economic lens should not need to change.

## Execution

With a Dogram checkout on `impl/ice-cube-001`:

```bash
python3 ghot/lightwalker_economy_sim.py --dogram-repo _dogram_ice
```

The simulation proves:

1. useful work is actually produced;
2. Dogram verification is required before Workmark birth;
3. the Workmark remains byte-for-byte unchanged across valuation;
4. multiple Realms produce different projections over the same Workmark;
5. a Realm may choose no economic interpretation;
6. the economic projection crosses as a signed, non-minting request;
7. the receiver retains HOLD/ADMIT authority.

## Next aperture

The next honest experiment is not "launch a token."

It is:

> Can one Workmark accumulate later attributable consequence receipts and allow a Realm lens to re-project from the newer measurement **without rewriting the birth, retroactively changing prior projections, or making either projection canonical?**

That is the bridge to Dogram Contribution Field + reLATTE + Lightwalker Realm economics.

## Seal

> **WORK MINES THE MARKER. TIME ASSAYS THE ORE. COMMUNITY NAMES AN EXCHANGE RATE.**

The exchange rate is a projection.

The history remains the history.
