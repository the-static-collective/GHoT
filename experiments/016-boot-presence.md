# Experiment 016 — Morning Presence Check

## Question

Can a booted GHoT body report exactly what woke, sign that wake with its body
identity, detect incompatible durable state, and expose current health locally
without turning presence reporting into authority?

## Trial A — deterministic presence simulation

```bash
python3 ghot/presence_sim.py
```

The simulation proves:

1. a boot manifest records the explicit boot surface;
2. the manifest address re-derives;
3. the body P-256 startup receipt verifies;
4. receipt and manifest addresses match;
5. healthy runtime state reports `healthy`;
6. loopback `/health` reports health;
7. loopback `/presence` returns the same startup receipt;
8. a runtime service failure changes health to `degraded`;
9. persisted manifest tampering changes health to `blocked`;
10. an unsupported durable state version records `migration_required`;
11. unsupported durable state blocks health rather than being silently rewritten.

Expected:

```json
{
  "simulation_passed": true
}
```

## Trial B — direct morning check

Start:

```bash
python3 ghot/organ.py
```

Then locally:

```bash
curl http://127.0.0.1:7791/health
curl http://127.0.0.1:7791/presence
```

Expected presence includes:

```text
boot id
body particular
code revision
boot surface
state compatibility
dependency readiness
signed startup receipt
current health
```

## Trial C — systemd provenance

Install/start:

```bash
python3 ghot/install_organ.py systemd-user --enable-now
```

Expected manifest:

```text
boot_surface.surface = systemd-user
boot_surface.instance = ghot-organ.service
```

## Trial D — Termux provenance

After Termux:Boot launches the installed hook, expected manifest:

```text
boot_surface.surface = termux-boot
boot_surface.instance = ghot-organ
```

## Trial E — manifest tamper

After a startup receipt exists, change a persisted manifest field without
regenerating the receipt.

Expected:

```text
/health -> blocked
reason -> boot-manifest-invalid
```

## Trial F — incompatible state

Place a durable state file with an unsupported version in the selected
`GHOT_HOME`, then start.

Expected:

```text
state.migration_required = true
health = blocked
automatic_migrations_applied = []
```

No unknown-state rewrite occurs.

## Pass

016 passes when the deterministic presence simulation and complete 001–015
smoke suite remain green.

## Mutation opened

017 can add explicit state migration receipts and versioned startup gates:

```text
inspect old state
 -> propose migration
 -> bounded migration function
 -> before/after content addresses
 -> signed migration receipt
 -> boot admitted or blocked
```

Then a machine can cross software generations without either silently rewriting
its memory or becoming permanently stranded by an old state file.
