# Experiment 010 — Atomic Claim / Work Lease

## Question

Can multiple Wake Composer workers share one durable HOLD queue without double-starting work, while still recovering when a claimed worker dies?

## Trial A — deterministic concurrency simulation

```bash
python3 ghot/lease_sim.py
```

The simulation proves:

1. worker A claims a HOLD;
2. worker B is blocked while A's lease is live;
3. A renews and B remains blocked beyond the original expiry;
4. renewal stops and B recovers after the extended lease expires;
5. cancellation before claim makes work unclaimable;
6. expiry before claim makes work unclaimable;
7. cancellation after a live claim is explicitly blocked;
8. a stale expired worker cannot commit a late success;
9. the recovered current worker can release successfully.

Expected:

```json
{
  "simulation_passed": true
}
```

## Trial B — two wake workers

Create a runnable HOLD and start two processes against the same GHOT_HOME:

```bash
python3 ghot/wake_composer.py watch --worker-id worker-a --lease-seconds 30
```

and:

```bash
python3 ghot/wake_composer.py watch --worker-id worker-b --lease-seconds 30
```

Expected: only one worker owns the current claim for any HOLD.

## Trial C — crashed worker

Let worker A claim a runnable HOLD, terminate A abruptly, leave B running, and wait beyond the lease window.

Expected: A stops renewing, its claim expires, B records recovery, B receives a new lease, and B may execute.

## Trial D — cancellation race

Cancel before any worker claims:

```bash
python3 ghot/wake_composer.py cancel <hold-id> "operator cancelled"
```

Expected: future claims return inactive/cancelled.

If a worker already owns a live lease, cancellation reports that an active claim blocks the transition.

## Trial E — late stale result

Let worker A's lease expire, allow B to recover, then allow A to return a late result.

Expected: A's old lease id cannot mark the HOLD released.

## Pass

010 passes when:

- at most one live claim exists per HOLD;
- live leases exclude other workers;
- renewal extends exclusivity;
- expired leases are recoverable;
- terminal-before-claim work never executes;
- stale workers cannot commit;
- claim/recovery/completion history is durable;
- CI runs the deterministic lease simulation.

## Mutation opened

011 should make queue ownership portable across bodies rather than dependent on one shared filesystem:

- authoritative queue owner;
- remote workers request signed/receipted leases;
- lease renewal crosses the same authority boundary;
- partition behavior is explicit;
- no split-brain claim authority.

That is the seam where GHoT's local work leases can cross into reLATTE semantics.
