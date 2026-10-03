# Experiment 011 — Portable Lease Authority / reLATTE Crossing

## Question

Can one authoritative GHoT queue owner issue, renew, recover, and complete leases for remote bodies using portable reLATTE-shaped crossings without moving claim authority to those bodies?

## Trial A — deterministic crossing simulation

```bash
python3 ghot/portable_lease_sim.py
```

The simulation proves:

1. the owner dispatch is visible only to its target worker;
2. a different worker cannot claim it;
3. CLAIM returns ADMITTED / capability-issued;
4. replaying the identical CLAIM returns the same receipt;
5. RENEW extends the owner lease;
6. owner redispatch is blocked while that lease is live;
7. after expiry, the owner may retire A's lease and dispatch to B;
8. stale A completion is refused;
9. a tampered crossing fails HMAC source verification;
10. B can claim and COMPLETE;
11. owner commits the HOLD to released;
12. replaying COMPLETE returns the same receipt rather than releasing twice.

Expected:

```json
{
  "simulation_passed": true
}
```

## Trial B — start an owner authority

On the queue owner:

```bash
export GHOT_LEASE_SHARED_SECRET='development-only-value'
python3 ghot/lease_authority.py serve --port 7790
```

Inspect the advert:

```bash
python3 ghot/lease_authority.py show
```

## Trial C — prepare an owner dispatch

After an owner-side Wake/Energy plan has selected a remote worker:

```bash
python3 ghot/lease_authority.py prepare \
  <hold-id> \
  <worker-id> \
  <child-energy-plan-id> \
  --ttl 120
```

The remote worker cannot manufacture this dispatch.

## Trial D — remote poll + work

On the selected worker:

```bash
export GHOT_LEASE_SHARED_SECRET='development-only-value'
python3 ghot/lease_remote.py http://OWNER:7790 --worker-id <worker-id> poll
```

Then:

```bash
python3 ghot/lease_remote.py http://OWNER:7790 --worker-id <worker-id> work --lease-seconds 60
```

Expected trail:

```text
owner DISPATCH
 -> worker POLL crossing
 -> VERIFIED receipt
 -> worker CLAIM crossing
 -> ADMITTED receipt
 -> remote TASK + local RECEIPT
 -> zero or more RENEW crossings
 -> COMPLETE crossing
 -> owner HOLD release
 -> EXECUTED receipt
```

## Trial E — replay

Resend an identical signed crossing with the same crossing_id.

Expected: the exact cached receipt returns. No second claim/release transition occurs.

## Trial F — worker death / owner redispatch

Let worker A claim and then stop renewing.

After lease expiry, the owner prepares a fresh dispatch to B.

Expected:

- A's stale claim is retired;
- old dispatch becomes lease-expired;
- A completion is refused;
- B can claim the new dispatch.

## Pass

011 passes when:

- queue mutation remains owner-local;
- remote execution uses portable crossing/receipt records;
- dispatch gates which worker may claim;
- replay is idempotent;
- stale workers cannot complete;
- owner recovery can retarget work;
- crossing tamper is refused;
- CI runs the deterministic crossing simulation.

## Mutation opened

012 should replace the shared-secret bridge with the stronger identity/signature profile and make Wake Composer automatically create remote DISPATCH records when an energy plan selects a remote body.

That would remove the manual `prepare` seam and push the portable crossing all the way into normal scheduling.
