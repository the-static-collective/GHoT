# Declarative Merge Plugins

Experiment 021 makes 020 merge grammars locally installable without allowing a
package to execute Python, shell commands, imports, network calls, or arbitrary
filesystem writes.

Core law:

> EXTENSIBILITY DOES NOT REQUIRE EXECUTABLE PLUGIN CODE.

## Package format

A merge plugin is one JSON document:

```text
ghot.merge-plugin.package/v0
```

It declares:

```text
package id/version
merge-contract descriptor
source schema/version/selector/payload type
target state kind/version/path
target schema declaration
bounded DSL operation
deterministic conformance fixtures
```

Packages are content-addressed before installation.

## No package-supplied code

V0 supports exactly one declarative operation:

```text
catalog-object-snapshot/v0
```

The package may map a fixed set of source expressions into one local catalog
entry.

Allowed expressions are:

```text
source.particular
source.node_id
parcel.id
parcel.address
payload.address
payload.<one-direct-key>
```

There is no:

- eval;
- Python source;
- import;
- shell;
- subprocess;
- arbitrary file read;
- network request;
- nested attribute/path traversal.

The runtime implementation remains GHoT-owned code. The package only supplies
data to that bounded implementation.

```text
PLUGIN MANIFEST != EXECUTABLE CODE
```

## Target isolation

Every package id must use only:

```text
letters digits . _ -
```

and every plugin target must stay inside:

```text
GHOT_HOME/knowledge/plugins/<package-id>/
```

A plugin cannot target:

- `organ/state.v1.json`;
- BODY identity keys;
- authority/trust records;
- lease state;
- another plugin's namespace;
- files outside `GHOT_HOME`.

```text
PLUGIN TARGET != ARBITRARY LOCAL PATH
```

## Validation

Validate a package without installing it:

```bash
python3 ghot/merge_plugin.py validate \
  examples/merge-plugins/foreign-work-memory.package.json
```

Validation checks:

- package kind/version;
- package id grammar;
- contract descriptor structure;
- source payload type;
- target namespace isolation;
- authority/freshness effects are `none`;
- explicit selection is required;
- operation kind is allowlisted;
- field expressions are bounded;
- key fields are actually produced;
- target schema matches target state kind/version;
- fixture count and shape.

Then every fixture is executed through the same bounded operation that would be
used after installation.

Installation is refused if any fixture output differs from its expected result.

## Install

```bash
python3 ghot/merge_plugin.py install \
  examples/merge-plugins/foreign-work-memory.package.json
```

The exact manifest is written beneath:

```text
GHOT_HOME/merge-plugins/packages/<package-id>/manifest.v0.json
```

A BODY-signed install receipt is written beneath:

```text
GHOT_HOME/merge-plugins/receipts/
```

The receipt binds:

```text
package id/version
package content address
contract id
installed path
installation time
BODY particular
conformance passed
fixture count
```

## Discovery integrity

Installed plugin contracts enter the 019/020 registry only when:

1. the manifest still validates;
2. its content address re-derives;
3. the install receipt exists;
4. the BODY signature verifies;
5. receipt package address equals the current manifest address.

If the installed manifest changes afterward:

```text
plugin status = invalid
contract disappears from pantry
```

The old install receipt does not bless modified package contents.

## Pantry origin

020 contract descriptors now include:

```text
origin.kind
origin.package_id
origin.package_version
origin.package_address
origin.operation_kind
```

Built-ins report:

```text
origin.kind = builtin
```

Installed packages report:

```text
origin.kind = plugin
```

Because the origin fields are part of the contract descriptor, the 020 contract
address and durable selection bind package provenance too.

## Example plugin

The repository includes:

```text
examples/merge-plugins/foreign-work-memory.package.json
```

It teaches the pantry a new grammar that core GHoT does not hard-code:

```text
source:
  ghot.organ.state/v1
  selector /work
  payload object

target:
  knowledge/plugins/ghot.plugin.foreign-work-memory/foreign-work.v0.json
  ghot.foreign-work-catalog/v0
```

The package maps:

```text
source particular
source node id
payload.status
parcel id
payload address
```

into observational foreign-work memory.

Before installation, `/work` has no compatible merge contract.

After installation, the pantry discovers the new grammar.

Actual mutation still follows the existing chain:

```text
ADMIT
 -> pantry INSPECT
 -> SELECT
 -> PROPOSE
 -> 019 APPLY / REJECT
 -> merge receipt
```

## Remove

```bash
python3 ghot/merge_plugin.py remove <package-id>
```

Removal moves the installed package out of the active package directory while
preserving historical install receipts.

A selection that refers to a removed plugin cannot later produce a merge plan.

```text
OLD SELECTION + REMOVED CONTRACT -> REFUSE
```

## Collision rules

Installation refuses:

- a plugin contract id that collides with a built-in;
- duplicate installed contract ids from different packages;
- reusing one package id with different package content without removing it
  first.

## What an install receipt means

The BODY-signed install receipt means:

> this body validated this exact package content and its declared fixtures, then
> installed that package locally.

It does not mean:

- the plugin is globally trustworthy;
- the package author is trusted;
- the merge semantics are universally correct;
- a parcel should be selected;
- a merge should be applied.

```text
CONFORMANCE PASS != SEMANTIC INFALLIBILITY
INSTALL RECEIPT != MERGE AUTHORITY
```

## Operator surface

```bash
python3 ghot/merge_plugin.py validate <package.json>
python3 ghot/merge_plugin.py install <package.json>
python3 ghot/merge_plugin.py list
python3 ghot/merge_plugin.py remove <package-id>

python3 ghot/merge_contract_pantry.py list
python3 ghot/merge_contract_pantry.py inspect <parcel-id>
```

## Laws

- EXTENSIBILITY != ARBITRARY CODE EXECUTION
- PLUGIN MANIFEST != EXECUTABLE CODE
- PLUGIN TARGET != ARBITRARY LOCAL PATH
- INSTALLED PLUGIN != TRUST
- INSTALLED PLUGIN != AUTHORITY
- CONFORMANCE PASS != SEMANTIC INFALLIBILITY
- INSTALL RECEIPT != MERGE RECEIPT
- INSTALL RECEIPT != MERGE AUTHORITY
- PLUGIN DISCOVERY != SELECTION
- REMOVED CONTRACT != DURABLE EXECUTION RIGHT
