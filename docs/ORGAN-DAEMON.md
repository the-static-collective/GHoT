> **027 note:** Curious Doors v2 now projects a separate typed Static-OS launch channel in addition to 026 human navigation. Launch descriptors contain no argv or executable URL and grant no consent or permission. A user-selected descriptor must be routed to its owning destination for fresh preflight, and even a `ready` preflight remains non-executing and unauthorized. Organ service state declares `typed_launches=true`, `launches_execute=false`, `launch_context_grants_consent=false`, `launch_context_transfers_permission=false`, and `destination_revalidation_required=true`. See `docs/TYPED-LAUNCH-DESCRIPTORS.md`.

> **026 note:** Curious Doors v1 remains loopback-only and read-only but now exposes GET-only evidence navigation plus inert subsystem-owned command intents. The surface never executes an intent or transfers permission; action intents have no executable URL. Organ service state declares `navigation_executes=false`, `permission_transfer=false`, and `evidence_get_only=true`. See `docs/CURIOUS-DOOR-NAVIGATION.md`.

> **025 note:** A normal organ now supervises the loopback-only read-only Curious Doors surface on port 7794. It projects durable 024 wants and current local pantry state but never creates a WANT, refreshes the network, requests/offers a package, validates, installs, ranks, or notifies. See `docs/CURIOUS-DOORS.md`.

> **023 note:** A normal organ now supervises a non-authoritative grammar exchange service on HTTP 7793 / UDP 47890. The service advertises only explicitly shared package metadata and can record signed requests, but it never auto-shares, auto-requests, auto-offers, or auto-installs. See `docs/GRAMMAR-EXCHANGE.md`.

> **022 note:** Port 7792 is now a shared HOLD-only parcel porch with separate `/state-parcel` and `/merge-plugin-package` protocols. Sharing the supervised HTTP service does not merge their inbox, validation, admission, or installation authority. See `docs/PORTABLE-MERGE-PLUGINS.md`.

> **018 note:** The default organ now also supervises a dedicated HOLD-only state parcel porch on port 7792. BODY discovery advertises that porch separately from the normal task service. Network receive may HOLD valid parcels but cannot ADMIT them. See `docs/STATE-PARCELS.md`.

> **017 note:** The canonical daemon current-state record is now `ghot.organ.state/v1` at `.ghot/organ/state.v1.json`, linked to the current boot presence. Valid v0 state crosses through the signed migration path in `docs/STATE-MIGRATIONS.md`.

# Organ Daemon

Experiment 014 makes joining the local GHoT organism a one-command operation:

```bash
python3 ghot/organ.py
```

The daemon is a supervisor. It does not replace the authority boundaries built
in earlier experiments.

## What one organ process composes

```text
BODY HTTP service
+ BODY discovery responder
+ fresh BODY probe
+ executor/power offer refresh
+ liveness field maintenance
+ trusted authority porch resolution
+ portable lease worker
+ HOLD-only state parcel porch
= one running GHoT organ
```

Each cycle asks:

```text
What body am I?
What can I do now?
What power can I afford?
Who else is here?
Which bodies have gone stale or departed?
Which authority porches do I already trust?
Where are those authorities now?
Is work addressed to this body?
```

## Current state

The daemon maintains one replaceable current-state record:

```text
.ghot/organ/state.v1.json
```

It includes:

- stable node id;
- current BODY identity / power / offers summary;
- liveness field snapshot;
- currently resolved trusted authorities;
- latest lease-worker result;
- supervised service states;
- local subsystem errors;
- current boot id / manifest address / startup receipt linkage.

This file is a current view, not immutable history.

Meaningful state changes and liveness transitions are also written as durable
organ events under `.ghot/records`.

## Failure locality

One subsystem error does not terminate the organism cycle.

Examples:

```text
peer discovery fails
 -> record local error
 -> keep BODY identity
 -> keep previous liveness knowledge
 -> continue authority resolution / work loop

authority discovery fails
 -> record local error
 -> do not invent authority
 -> next cycle retries

lease worker fails
 -> record local error
 -> HOLD/lease authority remains elsewhere
 -> next cycle retries
```

Network service threads are supervised as well. If BODY HTTP or the BODY
discovery responder dies, the daemon attempts to recreate that service.

```text
DEATH IS LOCAL
```

applies inside the process too.

## Power refresh

No separate power daemon is introduced.

Every cycle calls the existing BODY probe. BODY probing already recomputes:

```text
hardware
identity
executors
power
power-adjusted offers
```

Therefore offer willingness can change while the organ remains the same body.

## Liveness

Each cycle includes:

```text
local BODY observation
+ LAN peer discovery
 -> LivenessField.refresh_observations()
```

Previously known bodies are not erased when a discovery sweep misses them. They
age through the existing:

```text
awake -> stale -> departed
```

state model.

## Authority porch resolution

The daemon does not scan and then trust.

It calls the 013 trusted resolution path:

```text
signed advert
 -> freshness
 -> remembered trust or explicit pin
 -> current road
```

Unknown authorities remain outside the automatic worker loop.

## Lease work

The daemon passes currently trusted authority roads to the existing portable
lease worker.

The worker still performs:

```text
POLL
 -> CLAIM
 -> RENEW
 -> local execution
 -> COMPLETE
```

and the remote authority still decides whether the crossing is admitted and
whether the HOLD is released.

Thus:

```text
DAEMON != LEASE AUTHORITY
SUPERVISION != ADMISSION
```

## Service entrypoints

Normal organ:

```bash
python3 ghot/organ.py
```

One diagnostic cycle without opening BODY network services:

```bash
python3 ghot/organ.py --once --no-serve
```

Useful controls:

```bash
--http-port 7788
--discovery-port 47888
--interval 5
--discovery-timeout 2
--authority-timeout 2
--lease-seconds 60
--state-port 7792
--no-state-porch
```

## Process boundary

014 intentionally does not start a lease authority automatically.

A body may be:

- an ordinary organ;
- an authority owner;
- both, when explicitly configured as both.

Those roles remain composable rather than silently collapsed.

## Laws

- DAEMON != AUTHORITY
- PROCESS != ORGANISM
- CURRENT STATE != HISTORY
- SERVICE FAILURE != BODY DEATH
- PEER DISCOVERY FAILURE != PEER NONEXISTENCE
- AUTHORITY DISCOVERY FAILURE != AUTHORITY REVOCATION
- SUPERVISION != ADMISSION
- DEATH IS LOCAL
