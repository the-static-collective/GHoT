# Experiment 021 — Declarative Merge Plugins

## Question

Can GHoT learn a new merge grammar through a locally installed package without
executing package-supplied code, while preserving the 018–020 authority chain?

## Deterministic proof

```bash
python3 ghot/merge_plugin_sim.py
```

The simulation uses the repository example package:

```text
examples/merge-plugins/foreign-work-memory.package.json
```

## Trial A — no grammar before install

ADMIT a `ghot.organ.state/v1` parcel with selector `/work`.

Before installation:

```text
compatible_contract_ids = []
```

Core GHoT does not secretly know how to merge that parcel.

## Trial B — validation and installation

Validate the package and run its declared fixture.

Expected:

```text
fixture passed
package content address derived
BODY-signed install receipt verifies
```

Install the same exact package twice.

Expected:

```text
same verified install receipt
```

## Trial C — dynamic pantry discovery

After installation:

```text
ghot.organ.work->foreign-work-catalog/v0
```

appears in the pantry with:

```text
origin.kind = plugin
origin.package_id
origin.package_address
origin.operation_kind = catalog-object-snapshot/v0
```

The already-admitted `/work` parcel becomes compatible.

Then the normal chain must work:

```text
SELECT
 -> PROPOSE
 -> 019 APPLY
 -> signed merge receipt
```

The target must be confined to the package-owned namespace.

## Trial D — removal invalidates selection

SELECT the plugin for another parcel, then remove the plugin before PROPOSE.

Expected:

```text
PROPOSE REFUSED
```

A durable selection cannot resurrect an uninstalled grammar.

## Trial E — installed manifest tamper

Reinstall the valid package, then change its installed manifest without
regenerating the BODY install receipt.

Expected:

```text
plugin status = invalid
plugin absent from active pantry registry
```

Restore the exact original manifest.

Expected:

```text
verified install receipt matches again
plugin returns to pantry
```

## Trial F — rejected package classes

Installation must refuse packages containing:

1. unknown operation kind such as `python.eval/v0`;
2. a failing conformance fixture;
3. target path traversal;
4. an authority effect other than `none`;
5. a contract id colliding with a built-in;
6. an expression attempting nested traversal.

All refusals occur before the package enters the active registry.

## Pass

021 passes when the plugin simulation and the complete 001–020 smoke chain are
green.

## Mutation opened

022 can make package provenance portable without making remote install
automatic:

```text
PLUGIN PACKAGE
  -> content address
  -> optional author signature
  -> portable package parcel
  -> remote HOLD
  -> local inspect
  -> local VALIDATE
  -> explicit INSTALL
  -> BODY install receipt
```

That would allow merge grammars themselves to cross between bodies while
preserving the same rule already used for state:

```text
ARRIVAL != INSTALLATION
```
