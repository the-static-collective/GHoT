# Curious Doors

Experiment 025 turns durable 024 composition wants into a local read-only human surface.

The surface answers one question:

> What is this body currently wondering about, based only on durable local evidence?

It does not create wants, refresh the network, request packages, offer packages, validate packages, or install packages.

```text
SURFACE != REQUEST
```

## Four door states

Each durable WANT projects into exactly one visible state.

### open-gap

```text
I don't know how to compose this yet.
```

The local 020 pantry still has no compatible grammar, there are no observed candidates in the WANT or its refresh history, and no request link exists.

### candidate-observed

```text
A structurally matching grammar has appeared in observed history.
```

The local gap is still open and at least one exact-shape candidate has been observed, but no candidate has been requested.

This is not a recommendation.

### requested

```text
A grammar has been requested; this gap is still locally unresolved.
```

At least one 024 want→request link exists, but the local 020 pantry still lacks a compatible grammar.

A later 023 OFFER or 022 HOLD does not change this state. Only local grammar availability does.

### resolved-local

```text
This old gap is now locally satisfied.
```

The historical WANT still exists, but current local pantry inspection now finds one or more compatible grammars.

### blocked

If the underlying WANT or current local evidence cannot be safely projected, the surface displays a blocked door with the local projection error rather than guessing.

## Candidate observation delta

025 does not call the network.

It reads only already-persisted 024 observations.

For the latest stored observation, it computes:

```text
candidate ids in latest observation
  MINUS
candidate ids already seen in the original WANT or earlier observations
```

The result appears as:

```text
new_candidate_ids_in_latest_observation
new_candidate_count_in_latest_observation
```

This means 'new in that stored observation relative to earlier stored evidence.'

It does not mean urgent, unread, trusted, or recommended.

```text
NEW CANDIDATE != NOTIFICATION AUTHORITY
```

## Ordering

Doors are sorted only by:

```text
created_at
then door_id
```

The surface explicitly reports:

```text
ordering_is_priority = false
```

No score, weight, urgency, relevance rank, or recommendation is computed.

```text
DISPLAY ORDER != RANK
ATTENTION != PRIORITY
```

## JSON projection

Print the current read-only snapshot:

```bash
python3 ghot/curious_doors.py snapshot
```

The top-level `ghot.curiosity.surface/v0` includes state counts and the complete door projection.

Snapshot generation reads durable local state only. It performs no exchange discovery or refresh.

## Static HTML render

Render a standalone read-only view:

```bash
python3 ghot/curious_doors.py render \
  --out /tmp/curious-doors.html
```

The generated page contains no form, button, script, request action, or mutation endpoint.

## Local HTTP surface

Serve it manually:

```bash
python3 ghot/curious_doors.py serve
```

Default:

```text
http://127.0.0.1:7794/
```

Read-only GET endpoints:

```text
/
/curious-doors
/health
```

POST, PUT, and DELETE receive HTTP 405.

## Normal organ integration

A normal:

```bash
python3 ghot/organ.py
```

supervises Curious Doors on loopback port 7794.

Disable it explicitly:

```bash
python3 ghot/organ.py --no-curious-doors
```

The organ service state declares:

```text
read_only = true
auto_want = false
auto_refresh = false
auto_request = false
auto_offer = false
auto_install = false
```

Supervision keeps the view reachable. It does not create curiosity state.

## What the surface does not do

Curious Doors never:

- scans the LAN;
- contacts exchange peers;
- creates a WANT;
- performs REFRESH;
- picks a candidate;
- sends REQUEST;
- performs OFFER;
- validates a plugin;
- installs a plugin;
- ranks doors;
- raises notifications;
- rewrites historical WANT state.

## Laws

- SURFACE != REQUEST
- SURFACE != WANT
- SURFACE != REFRESH
- ATTENTION != PRIORITY
- DISPLAY ORDER != RANK
- NEW CANDIDATE != NOTIFICATION AUTHORITY
- CANDIDATE DISPLAY != RECOMMENDATION
- REQUESTED DISPLAY != OFFER AUTHORITY
- RESOLVED DISPLAY != REMOTE STATE
- SUPERVISED SURFACE != CURIOSITY AUTHORITY
