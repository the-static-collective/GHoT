> **012 note:** This document records the Experiment 011 shared-secret bridge. Experiment 012 supersedes its HMAC source-verification profile with reLATTE P-256 identity signatures and automatic identity-bound dispatch. See `docs/IDENTITY-AUTOMATIC-DISPATCH.md`.

# Portable Lease Authority / reLATTE Crossing

Experiment 010 made one shared queue safe for multiple local/shared-filesystem workers.

Experiment 011 moves execution off that filesystem while keeping claim authority owner-local.

Core law:

> execution may roam; lease authority does not.

## Authority split

The queue owner alone may:

- decide which HOLD is dispatchable;
- name the target worker;
- issue the owner DISPATCH;
- grant or refuse a lease;
- renew the current lease;
- accept completion;
- commit the HOLD release.

A remote worker may:

- poll for dispatches addressed to itself;
- request the named dispatch;
- execute locally after lease grant;
- renew while work is active;
- return or complete the lease.

The worker cannot select arbitrary held work for itself.

## Owner dispatch

Before a remote claim can succeed, the owner creates a short-lived DISPATCH:

```text
dispatch_id
authority_id
hold_id
target_worker_id
child_energy_plan_id
capability
payload
payload_address
expires_at
status
```

The dispatch is a local disposition made by the authority. It is not created by the remote requester.

An unclaimed dispatch expires by its dispatch TTL. Once it is claimed, execution lifetime is governed by the renewable lease instead.

## Crossing grammar

Worker requests use the existing reLATTE V0 envelope shape:

```text
relatte.crossing-envelope/v0
```

with:

- declared_kind = GHOT_LEASE_<ACTION>
- capability_ref = ghot.work-lease/v0
- requested_effect carrying HOLD / dispatch / lease references
- source_particular naming the worker
- source_world naming the worker body

Actions:

- POLL
- CLAIM
- RENEW
- COMPLETE
- ABANDON

The authority answers with:

```text
relatte.receipt/v0
```

Typical receipt mapping:

- successful CLAIM -> ADMITTED / capability-issued
- successful RENEW -> VERIFIED / local-state-change
- successful COMPLETE -> EXECUTED / local-state-change
- successful ABANDON -> RETURNED / local-state-change
- denied crossing -> REFUSED / none
- remote execution failure -> FAILED / local-state-change

## V0 source-verification profile

011 uses canonical JSON plus HMAC-SHA256 with an out-of-band shared key.

This gives us a runnable authenticated LAN crossing and replay-safe receipt path without adding a Python crypto dependency.

It does NOT claim to satisfy a stronger public-key identity profile.

The envelope and receipt explicitly carry:

```text
source_verification_profile: shared-secret-hmac-v0
public_key_identity_claimed: false
```

The `signing.public_key` object is populated only with profile/key-id metadata because the upstream reLATTE V0 schema requires that object. No asymmetric key claim is made.

## Replay

Every crossing has a content-derived crossing_id that includes a nonce.

The authority caches the first receipt by crossing_id.

If the same crossing is retried because a network response was lost, the authority returns the same receipt instead of repeating the state transition.

Therefore:

```text
NETWORK RETRY != SECOND CLAIM
```

## Remote recovery

If worker A stops renewing:

1. A's lease expires;
2. the owner observes the expired claim when preparing a new dispatch;
3. the stale claim is retired with durable evidence;
4. A's old dispatch becomes lease-expired;
5. the owner may issue a fresh dispatch to worker B;
6. A can no longer complete under its old lease;
7. B may claim and execute.

Recovery remains owner-mediated. Worker B does not seize A's work by unilateral inference.

## HTTP transport

V0 authority server:

```bash
python3 ghot/lease_authority.py serve --port 7790
```

Authority advert:

```text
GET /authority
```

Crossing endpoint:

```text
POST /crossing
```

The HTTP transport is a trusted-LAN prototype. HMAC authenticates crossing contents, but HTTP itself does not encrypt metadata or payloads.

Do not treat this as safe for hostile networks.

## Provisioning

The authority reads `GHOT_LEASE_SHARED_SECRET` when supplied. Otherwise it creates a local `.ghot/lease-authority/shared-secret` file.

A remote worker must receive the same value out of band and expose it as `GHOT_LEASE_SHARED_SECRET`.

The CLI can display the local development value with:

```bash
python3 ghot/lease_authority.py show-secret
```

This is deliberately a development bridge, not the final identity system.

## Remote worker

Poll:

```bash
GHOT_LEASE_SHARED_SECRET=... \
python3 ghot/lease_remote.py http://AUTHORITY:7790 --worker-id worker-a poll
```

Execute the first owner dispatch:

```bash
GHOT_LEASE_SHARED_SECRET=... \
python3 ghot/lease_remote.py http://AUTHORITY:7790 --worker-id worker-a work --lease-seconds 60
```

The remote worker:

1. polls;
2. claims the owner-issued dispatch;
3. executes with the ordinary GHoT reference-node capability path;
4. renews while active;
5. sends the local receipt id back in COMPLETE;
6. waits for the authority's EXECUTED receipt.

Only that final authority receipt establishes owner-side HOLD release.

## Laws

- EXECUTION MAY ROAM; LEASE AUTHORITY DOES NOT
- REMOTE WORKER != QUEUE OWNER
- DISPATCH != CLAIM
- CLAIM != EXECUTION
- REMOTE RECEIPT != OWNER RELEASE
- NETWORK RETRY != SECOND EFFECT
- SHARED-SECRET AUTH != PUBLIC-KEY IDENTITY
- SCHEMA COMPATIBILITY != COMPLETE TRUST PROFILE
- OWNER-LOCAL DISPOSITION SURVIVES TRANSPORT
