# Atomic Claim / Work Lease

Experiment 010 makes the HOLD queue safe for multiple wake workers sharing the same GHoT queue filesystem.

The problem is simple: two workers can observe the same runnable HOLD. Without a claim, both can execute it.

V0 therefore requires an exclusive expiring lease before work starts.

## Lifecycle

```text
HOLD
  -> atomic claim
  -> LEASE
      -> healthy worker renews
      -> execution
      -> completion

or:

LEASE
  -> worker dies
  -> renewal stops
  -> lease expires
  -> another worker recovers
  -> new lease
```

## Filesystem primitive

V0 uses:

```text
.ghot/holds/<hold-id>.json
.ghot/claims/<hold-id>.json
.ghot/locks/<hold-id>.lock
```

Claim, cancel and expire transitions are serialized by exclusive creation of the per-HOLD transition lock. Claim creation itself also uses exclusive file creation.

This is a local/shared-filesystem primitive, not distributed consensus.

Transition locks protect only short state changes. If a process dies while holding one, V0 treats the lock as stale after a short bounded window and recovers it. Long-running execution ownership is represented by the renewable lease, not the transition lock.

## Lease renewal

A claim records hold id, lease id, worker id, claim time, lease duration, lease expiry, parent energy plan, and any recovered prior lease.

Wake Composer defaults to a 60-second lease and renews approximately every one-third of the lease duration while real execution is active.

If the worker dies, renewal dies with it.

## Recovery

When another worker encounters an expired claim it records claim.expired, removes the stale claim, creates a new lease, then records claim.recovered and claim.acquired.

The new claim names the old lease in recovered_from_lease_id.

## Completion fencing

An old lease id cannot commit success. Before a HOLD becomes released, the queue verifies that the HOLD is still held, the supplied lease id is the current claim, and the claim itself is not expired.

Therefore a late worker whose lease expired cannot overwrite the result after another worker recovered the HOLD.

## Cancellation and expiry boundary

Before claim, cancellation or expiry wins and the work cannot be claimed.

After a live claim exists, V0 does not pretend already-started execution can be retroactively revoked. A cancellation attempt reports that the active claim blocks the transition.

After that claim completes, is abandoned, or expires, a later transition may proceed if the HOLD is still active.

## Claim events

- claim.acquired
- claim.renewed
- claim.expired
- claim.recovered
- claim.completed
- claim.abandoned

## Worker identity

Wake Composer accepts --worker-id and --lease-seconds. If no worker id is supplied, V0 derives <node-id>:pid-<process-id>, allowing two processes on one body to be distinguished.

## Scope

010 prevents duplicate execution only for workers sharing the same queue filesystem. It does not yet make a local lock file global authority across unrelated filesystems or a network partition.

That later crossing should use an explicit authoritative owner plus portable receipts.

## Laws

- SEEING WORK != OWNING WORK
- CLAIM != COMPLETION
- CLAIM MUST EXPIRE
- HEALTHY WORK MUST RENEW
- EXPIRED CLAIM != CURRENT AUTHORITY
- STALE WORKER MUST NOT COMMIT
- CANCEL BEFORE CLAIM != CANCEL AFTER EXECUTION START
- LOCK FILE != GLOBAL CONSENSUS
