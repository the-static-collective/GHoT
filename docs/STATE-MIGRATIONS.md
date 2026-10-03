# State Migration Receipts

Experiment 017 makes durable-state version changes explicit, bounded, and receipted.

Core law:

> STATE CHANGE SHOULD LEAVE A RECEIPT.

## First real migration

017 introduces the first production migration in GHoT:

```text
ghot.organ.state / 0
  .ghot/organ/state.v0.json
        ↓
ghot.organ.state / 1
  .ghot/organ/state.v1.json
```

V1 adds a boot-presence linkage:

```text
presence:
  boot_id
  manifest_address
  startup_receipt_id
```

A migrated historical v0 state starts with those values null. The first new daemon cycle writes the current boot's actual presence linkage.

## Registered migration only

The migration registry names the exact state kind, from-version, to-version, source path, target path, and bounded transform function.

A state file that does not match the registered precondition is not passed into the function.

```text
KNOWN MIGRATION != PERMISSION TO REWRITE UNKNOWN STATE
```

## Plan

Before mutation, GHoT derives a `ghot.state.migration.plan/v0` containing the migration id, state kind, versions, paths, before address, proposed after address, and mode.

Modes:

```text
apply
reconcile-receipt
```

The source content is re-read before application. If its semantic address changed after planning, the stale plan is refused.

## Semantic addresses and backup

Before/after addresses are SHA-256 addresses over GHoT's bounded identity-safe canonical JSON representation. This compares state meaning rather than formatting whitespace.

The exact original source bytes are also copied to the backup path, so 017 keeps both a semantic before witness and an exact source backup.

## Mutation order

```text
read exact source
 -> verify kind/version
 -> verify planned before address
 -> run declared transform in memory
 -> verify target kind/version
 -> verify proposed after address
 -> write exact source backup
 -> atomically write target
 -> re-read target
 -> verify after address
 -> BODY-sign migration receipt
 -> persist receipt
```

The original v0 source file remains preserved as a legacy witness. Once a valid v1 target and matching verified receipt exist, it is no longer canonical.

## Migration receipt

`ghot.state.migration.receipt/v0` binds the migration id, state kind, from/to version, source/target/backup paths, before/after addresses, application time, BODY particular, and P-256 signature.

Signature domain:

```text
ghot.state-migration-receipt-signature/v0
```

The receipt proves that possession of the BODY key witnessed this declared state transition. It does not prove the migration function was semantically infallible.

```text
SIGNED MIGRATION != SEMANTIC INFALLIBILITY
```

## Crash reconciliation

There is an important failure window:

```text
target written
   ↓
power loss
   ↓
receipt not written
```

017 does not treat that as complete.

Because the v0 source remains preserved, the next boot can re-run the declared transform in memory. If and only if the existing v1 target has the same semantic address as that declared result, GHoT exposes `mode: reconcile-receipt` and may create the missing signed receipt without rewriting the target.

If the target differs, no reconciliation plan is produced and startup remains blocked.

## Startup gate

Normal `ghot/organ.py` startup now performs:

```text
BODY probe
 -> state inspection
 -> exact registered migrations
 -> signed migration receipts
 -> boot manifest
 -> signed startup receipt
 -> daemon services
```

The boot manifest includes the migration receipts applied during that wake.

If migration application fails, state remains migration-required and startup health remains blocked.

Disable automatic application for inspection/debugging:

```bash
python3 ghot/organ.py --no-auto-migrate
```

## Operator CLI

```bash
python3 ghot/state_migration.py inspect
python3 ghot/state_migration.py plan
python3 ghot/state_migration.py apply
python3 ghot/state_migration.py receipts
```

## Unknown versions

An unknown version receives no generic upgrade.

Example:

```text
ghot.organ.state / 99
```

results in migration-required state, no available migration, and blocked health. No best-effort rewrite is attempted.

## Laws

- STATE CHANGE SHOULD LEAVE A RECEIPT
- MIGRATION PLAN != MIGRATION
- MIGRATION RECEIPT != EXECUTION RECEIPT
- KNOWN MIGRATION != PERMISSION TO REWRITE UNKNOWN STATE
- BACKUP != CANONICAL STATE
- LEGACY SOURCE != CURRENT STATE
- SIGNED MIGRATION != SEMANTIC INFALLIBILITY
- CRASH AFTER WRITE != COMPLETED MIGRATION
