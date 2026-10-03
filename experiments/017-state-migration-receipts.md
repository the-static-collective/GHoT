# Experiment 017 — State Migration Receipts

## Question

Can GHoT move real durable state from one schema generation to the next while preserving the source, proving before/after content, surviving an interrupted receipt write, and refusing unknown or changed inputs?

## Trial A — normal v0 → v1

```bash
python3 ghot/state_migration_sim.py
```

The simulation begins with a real-shaped `ghot.organ.state/v0`.

Expected:

1. inspection reports migration required;
2. exactly one registered plan exists;
3. plan mode is `apply`;
4. exact v0 source bytes are backed up;
5. source v0 remains preserved;
6. target v1 is atomically written;
7. target adds the presence linkage;
8. before/after semantic addresses match the receipt;
9. BODY P-256 migration receipt verifies;
10. startup manifest witnesses that migration receipt;
11. startup health is healthy afterward.

## Trial B — idempotence

Apply migration again.

Expected:

```text
applied: []
migration_required: false
```

No second migration receipt is created for the same already-receipted state.

## Trial C — interrupted receipt window

Construct:

```text
valid v0 source
valid transformed v1 target
no migration receipt
```

Expected:

```text
migration_required: true
plan.mode: reconcile-receipt
```

Apply. The target bytes are not rewritten; the target is recomputed from preserved source, the semantic address must match, the missing BODY-signed receipt is created, and the migration gate clears.

## Trial D — source race

Create a plan, then mutate the source state before applying it.

Expected:

```text
apply refused
target not created
```

A stale migration plan cannot authorize a different source.

## Trial E — unknown version

Present `ghot.organ.state / 99`.

Expected: no plan, migration-required remains true, and startup health remains blocked.

## Trial F — normal daemon upgrade

With an existing valid `.ghot/organ/state.v0.json`, run:

```bash
python3 ghot/organ.py
```

Expected startup sequence:

```text
v0 detected
 -> migration receipt
 -> v1 canonical state
 -> boot manifest witnesses migration receipt
 -> startup receipt
 -> daemon cycle writes current presence linkage
```

## Pass

017 passes when the dedicated migration simulation and the entire 001–016 suite remain green.

## Mutation opened

018 can extend this into portable state parcels:

```text
select bounded state slice
 -> content address
 -> migration/version metadata
 -> signed export receipt
 -> cross to another body
 -> verify
 -> HOLD / ADMIT / merge locally
```

That would let durable memory move between organs under the same explicit crossing laws as work, without collapsing local ownership into a magical shared database.
