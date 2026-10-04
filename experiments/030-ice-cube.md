# Experiment 030 — Ice Cube 001

## Question

Can GHoT turn slow spare compute into a frozen mathematical artifact, carry the result through the existing reLATTE-shaped crossing path without teaching reLATTE the mathematics, obtain an independent bounded Dogram receipt, then preserve owner-local HOLD → ADMIT → explicit merge into a reusable local pantry?

## Specimen

The first family is:

```text
Mandelbrot quadratic family
  × Lucas-selected period
  × Halley root iteration
  × Fibonacci/Lucas mapping-torus monodromy
```

For Lucas index `n`:

```text
period q = L_n
g(z) = f_c^q(z) - z
```

The worker renders a Halley basin for roots of `g`.

The torus monodromy uses the Fibonacci companion matrix

```text
A = [[1,1],[1,0]]
M = A^(2n)
```

so `det(M)=1` and `trace(M)=L_(2n)`. A finite cyclic mapping-torus quotient uses:

```text
shift = trace(M) mod fiber_count
```

The continuous monodromy and finite quotient are both preserved in the specimen.

## Cross-repo requirement

Use sibling checkouts:

```text
GHoT   branch ice-cube-030
Dogram branch impl/ice-cube-001
```

The reLATTE wire format is the existing GHoT implementation of:

```text
relatte.crossing-envelope/v0
relatte.receipt/v0
```

No reLATTE core change is required.

## Run the bounded proof

From the GHoT checkout:

```bash
python3 ghot/ice_cube_sim.py \
  --dogram-repo ../Dogram
```

The default simulation intentionally renders only 48×48 pixels so it is fast enough for conformance.

For a larger actual mining pass:

```bash
python3 ghot/ice_cube.py \
  --root ~/.ghot \
  --dogram-repo ../Dogram \
  --lucas-index 5 \
  --width 1024 \
  --height 1024 \
  --max-halley-iter 18
```

A weak CPU can simply take longer. The result is reusable once frozen.

## Trial A — work crossing

Expected:

- work spec is content-addressed;
- GHoT creates a signed `relatte.crossing-envelope/v0`;
- the crossing declares `GHOT_ICE_CUBE_WORK`;
- the crossing knows the work address and capability, not the mathematical truth.

## Trial B — expensive production

Expected:

- GHoT evaluates the Lucas-selected Halley basin;
- render is canonical binary P5 PGM;
- exact SL(2,Z) monodromy matrix and finite mapping-torus quotient are recorded;
- several converged Halley trajectories become witnesses;
- deterministic pixel challenges are derived from the canonical work spec.

## Trial C — independent Dogram receipt

Dogram verifies:

- Lucas recurrence and period;
- exact Fibonacci matrix power;
- trace and determinant;
- existing finite mapping-torus analysis;
- Halley replay and residuals;
- render content address;
- deterministic challenged pixels by recomputation.

Dogram does **not** rerender every pixel.

Expected receipt scope:

```text
bounded-math-and-projection-witness/v0
```

## Trial D — execution receipt remains distinct

GHoT signs an execution receipt only after production and Dogram return.

Preserve:

```text
GHOT EXECUTION RECEIPT != DOGRAM VERIFICATION RECEIPT
EXECUTION != VERIFICATION
VERIFICATION != ADMISSION
```

## Trial E — result crossing

The result state includes the actual render bytes as base64, not merely its hash.

Existing State Parcel export creates a reLATTE-shaped signed crossing.

Receiver automatically reaches:

```text
HOLD
```

and nothing stronger.

Expected:

```text
HELD
semantic_effect = none
```

## Trial F — owner-local admission

The receiver explicitly chooses:

```text
ADMIT
```

Expected a signed ADMITTED receipt and no rewrite of canonical live state.

## Trial G — explicit pantry grammar

Install:

```text
ghot.plugin.verified-ice-cube
```

The declarative grammar accepts exactly:

```text
ghot.ice-cube-result/v0
selector $
```

and targets:

```text
ghot.verified-ice-cube-catalog/v0
```

Compatibility does not merge. The simulation performs:

```text
INSPECT
→ SELECT
→ PROPOSE
→ APPLY
```

and verifies the signed merge receipt.

## Pass

030 passes when one run proves:

```text
WORK
→ signed reLATTE crossing
→ GHoT compute
→ GHoT execution receipt
→ Dogram bounded verification receipt
→ frozen artifact
→ signed state-parcel crossing
→ HOLD
→ owner-local ADMIT
→ explicit merge grammar selection
→ APPLY receipt
→ verified Ice Cube pantry
```

and the render recovered from the admitted parcel hashes to the exact address Dogram verified.

## Laws opened

```text
SLOW != USELESS
RENDER != AUTHORITY
EXECUTION != VERIFICATION
VERIFICATION != ADMISSION
ADMISSION != MERGE
CHALLENGE SET != FULL PROOF
ROAD != MATHEMATICS
FROZEN ARTIFACT != FROZEN MEANING
```

## Next mutation

031 should let the normal GHoT capability/power field advertise `ghot.ice-cube/v0`, HOLD deferrable cubes while power is scarce, and wake them automatically when a body reports surplus compute/power.

That is where "mining ice cubes" becomes a persistent background organ rather than a manually invoked experiment.
