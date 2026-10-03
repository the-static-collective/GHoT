# Portable Merge Plugin Packages

Experiment 022 lets declarative merge grammars travel between GHoT bodies without granting remote installation authority.

Core law:

> ARRIVAL != INSTALLATION

The complete path:

```text
PACKAGE
  -> optional AUTHOR SIGNATURE
  -> transport BODY wraps parcel
  -> signed reLATTE crossing
  -> receiver HOLD
  -> local VALIDATE
  -> explicit local INSTALL
  -> 021 BODY install receipt
  -> grammar appears in 020 pantry
```

## Four distinct witnesses

022 keeps four proofs separate: optional author signature, transport crossing signature, local validation record, and the 021 local install receipt. None substitutes for the next decision.

Create a standalone author signature:

```bash
python3 ghot/merge_plugin_parcel.py sign-author package.json --out package.author.json
```

The author signature binds package id/version/content address to an author P-256 particular. A different BODY can later transport the same authored package.

```text
AUTHOR != TRANSPORT SENDER
AUTHOR SIGNATURE != INSTALL RECEIPT
TRANSPORT SIGNATURE != INSTALL RECEIPT
VALIDATION != INSTALLATION
```

## Export

Unsigned:

```bash
python3 ghot/merge_plugin_parcel.py export package.json \
  --target-particular <receiver-particular> \
  --out package.parcel.json
```

Locally author-sign while exporting:

```bash
python3 ghot/merge_plugin_parcel.py export package.json \
  --author-sign \
  --target-particular <receiver-particular> \
  --out package.parcel.json
```

Preserve another author's signature while this BODY transports it:

```bash
python3 ghot/merge_plugin_parcel.py export package.json \
  --author-signature-file package.author.json \
  --target-particular <receiver-particular> \
  --out relayed.parcel.json
```

The supplied author signature must verify against the exact package address.

## Shared porch, separate protocol

The normal parcel porch remains port 7792 with two POST endpoints:

```text
/state-parcel
/merge-plugin-package
```

They share transport infrastructure only. Their parcel types, inboxes, validation rules, local lifecycles, and authority contracts remain separate.

```text
SHARED PORCH != SHARED SEMANTICS
```

## Network receive means HOLD

Direct crossing:

```bash
python3 ghot/merge_plugin_parcel.py send package.parcel.json http://RECEIVER:7792
```

Or by current BODY discovery:

```bash
python3 ghot/merge_plugin_parcel.py send-node package.parcel.json <receiver-node-id>
```

The only automatic network disposition is HOLD. There is no remote validate or install action. A wrong target particular receives a signed REFUSED receipt and never enters the inbox.

## Local inbox and validation

```bash
python3 ghot/merge_plugin_parcel.py inbox
python3 ghot/merge_plugin_parcel.py show <parcel-id>
python3 ghot/merge_plugin_parcel.py validate <parcel-id>
```

Artifacts live beneath `GHOT_HOME/merge-plugin-parcels/` in separate raw, inbox, validation, and receipt stores.

VALIDATE runs the existing 021 structural validator and deterministic fixtures. A successful result moves HOLD -> VALIDATED and produces a BODY-signed VALIDATED receipt, but the plugin remains absent from the active pantry.

```text
HOLD != VALIDATION
VALIDATED != INSTALLED
```

## Explicit install

```bash
python3 ghot/merge_plugin_parcel.py install <parcel-id> --note "accept this grammar"
```

Before install, 022 rechecks the raw bundle, the unchanged validation report, the exact package address, and installable status. It then invokes the 021 installer, which validates the package and fixtures again.

A successful install returns both the existing 021 BODY-signed install receipt and a 022 BODY-signed INSTALLED parcel receipt that references the install receipt id. Only then does the grammar appear in the 020 pantry.

## Reject

```bash
python3 ghot/merge_plugin_parcel.py reject <parcel-id> --note "not for this body"
```

REJECT is terminal for that parcel lifecycle.

## Optional authorship

Unsigned packages may still be HOLDed, locally validated, and explicitly installed. The inbox records `author_signature_status = verified | unsigned`.

An invalid supplied author signature is different: it invalidates the parcel.

```text
UNSIGNED != INVALID SIGNATURE
AUTHOR SIGNATURE != TRUST
```

## Existing 021 safety still applies

Portable delivery does not expand the plugin language: no package Python, eval, shell, imports, network, arbitrary file reads, arbitrary target paths, authority effects, or fixture bypass.

```text
PORTABLE PACKAGE != PORTABLE CODE EXECUTION
REMOTE BODY != LOCAL INSTALL AUTHORITY
```

## Laws

- ARRIVAL != INSTALLATION
- HOLD != VALIDATION
- VALIDATION != INSTALLATION
- AUTHOR != TRANSPORT SENDER
- AUTHOR SIGNATURE != TRUST
- TRANSPORT SIGNATURE != AUTHOR SIGNATURE
- UNSIGNED != INVALID SIGNATURE
- SHARED PORCH != SHARED SEMANTICS
- PORTABLE PACKAGE != PORTABLE CODE EXECUTION
- REMOTE BODY != LOCAL INSTALL AUTHORITY
