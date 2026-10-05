# MINERAL FIELD 001

## Purpose

Generalize useful-work mining beyond the first Ice Cube family without
pretending every workload has the same verifier.

A **mineral** is a typed useful-work family.

An **Ice Cube** is a frozen, content-addressed artifact/result shape that a
mineral may eventually produce.

```text
MINERAL != ICE CUBE
DECLARED != EXECUTABLE
EXECUTABLE != VERIFIED
PROVENANCE != DOMAIN TRUTH
SAME FREEZER != SAME VERIFIER
```

## Registry

The first registry contains eleven mineral families.

### Executable now

```text
math.fractal.tile/v0
  capability: mineral.fractal.tile/v0
  native kernel: Mandelbrot escape-time tile
  artifact: P5 PGM
  decomposition: pixel grid

math.optimization.landscape/v0
  capability: mineral.optimization.landscape/v0
  native kernel: exact integer Rosenbrock grid
  artifact: canonical JSON integer grid
  decomposition: exact grid region

science.parameter-sweep/v0
  capability: mineral.parameter-sweep/v0
  native kernel: exact rational logistic-map sweep
  artifact: canonical JSON rational trajectories
  decomposition: parameter point/range

world.procedural.chunk/v0
  capability: mineral.procedural-world.chunk/v0
  native kernel: SHA-256 coordinate heightfield
  artifact: canonical JSON byte heightfield
  decomposition: chunk/cell
```

The existing:

```text
math.topology.mapping-torus/v0
```

remains executable through the composed `ghot.ice-cube/v0` path with Dogram.

## Typed HOLD minerals

These are present in the actual registry but are **not advertised as runnable
capabilities** yet.

```text
math.projection.nd/v0
  HOLD_VERIFIER_REQUIRED
  needs formal-object + proof-of-projection contract

science.numeric.simulation/v0
  HOLD_VERIFIER_REQUIRED
  needs checkpoint + invariant semantics

render.raytrace.tile/v0
  HOLD_EXTERNAL_ADAPTER
  needs scene/renderer/sample manifest

render.blender.tile/v0
  HOLD_EXTERNAL_ADAPTER
  needs bounded Blender adapter + scene/version contract

science.protein.search/v0
  HOLD_DOMAIN_VERIFIER
  needs domain-specific scientific evidence contract

ai.asset.batch/v0
  HOLD_PROVENANCE_CONTRACT
  needs frozen recipe/model/input provenance and honest reproducibility envelope
```

Their presence means the system knows what kind of door is missing.

It does not mean the door has crossed.

## GHoT BODY

The ordinary reference node advertises:

```text
mineral.registry/v0
```

plus each executable native mineral.

The registry is light inspection work.

Native mining capabilities are heavy work and therefore inherit the existing
GHoT power field policy.

HOLD mineral capabilities are deliberately absent from BODY offers.

Attempting to execute one through the normal GHoT task path must fail as:

```text
capability not offered by this body
```

rather than falling through to an unrelated adapter.

## Determinism

MINERAL FIELD 001 requires deterministic replay for its four new native
families.

Same canonical input must reproduce:

```text
same work address
same artifact address
same result identity
```

The result still says:

```text
verification_status = UNVERIFIED
```

because deterministic execution is not independent verification.

## Proof

CI runs:

```bash
python3 ghot/mineral_registry_sim.py
```

and proves:

1. all eleven named mineral families exist in the registry;
2. the four new native capabilities appear in an ordinary GHoT BODY;
3. all four are classified as heavy work;
4. the registry itself stays light;
5. each new miner produces a real content-addressed artifact;
6. replay reproduces identical addresses;
7. a native mineral can execute through the ordinary task/receipt path;
8. typed HOLD minerals are not advertised;
9. attempting Blender work while it is HOLD is refused before adapter fallback.

## Next crossings

The HOLD entries are now explicit implementation seams.

Likely sequence:

```text
proof-of-projection mineral
→ external renderer manifest
→ Blender/ray-trace tiles
→ checkpointed numeric simulation
→ domain-specific scientific search
→ generative asset provenance
```

Each should earn its own verifier rather than inheriting Ice Cube authority.
