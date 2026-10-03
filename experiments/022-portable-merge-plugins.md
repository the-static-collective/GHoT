# Experiment 022 — Portable Merge Plugin Packages

## Question

Can a declarative merge grammar travel between bodies, preserve optional authorship independently from transport, enter only HOLD over the network, and require local validation plus explicit local installation before it becomes active?

## Deterministic proof

```bash
python3 ghot/merge_plugin_parcel_sim.py
```

## Trial A — author != transporter

One BODY signs the package as author. A different relay BODY wraps and transports it.

Expected: author signature verifies, crossing signature verifies, author particular differs from transport source particular, and tampering with package or author signature invalidates the bundle.

## Trial B — real network crossing

Send through the real localhost parcel porch.

Expected receiver result:

```text
HELD
semantic_effect = none
network_install = false
```

The package enters one inbox record. Plugin store remains empty. Pantry still lacks the plugin grammar. Duplicate crossing still does not install it.

## Trial C — no remote install surface

Attempt a remote plugin-install POST.

Expected: 404.

## Trial D — local validation

Run local VALIDATE.

Expected: 021 package validation and fixtures pass, validation record is written, BODY-signed VALIDATED receipt verifies, plugin store remains empty, pantry still lacks the grammar.

## Trial E — explicit local installation

Run INSTALL after VALIDATED.

Expected: 021 installer revalidates the package, BODY-signed 021 install receipt verifies, BODY-signed 022 INSTALLED receipt verifies and references the install receipt, and the grammar appears in pantry only now.

## Trial F — validation drift

Change the stored validation report after VALIDATE.

Expected: INSTALL refused.

## Trial G — local rejection

HOLD and then REJECT another parcel.

Expected: signed REJECTED receipt and later INSTALL refused.

## Trial H — wrong target

Send a valid parcel addressed to another BODY particular.

Expected: signed REFUSED receipt and no inbox entry.

## Trial I — unsigned package

Cross a package without an author signature to a separate receiver.

Expected: parcel verifies, inbox records unsigned, local VALIDATE succeeds, explicit local INSTALL succeeds, and the 021 install receipt verifies.

## Pass

022 passes when the new simulation and the complete 001–021 smoke chain are green.

## Mutation opened

023 can add a grammar exchange table without automatic trust:

```text
local package inventory
 + held foreign package inventory
 + verified author particulars
 + installed package addresses
        ↓
human-readable exchange view
        ↓
REQUEST / OFFER a package address
        ↓
parcel crossing
```

Preserving:

```text
DISCOVERY != REQUEST
REQUEST != CROSSING
CROSSING != INSTALLATION
```
