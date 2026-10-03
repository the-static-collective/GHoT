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
