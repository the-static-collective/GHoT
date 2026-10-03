# Typed Launch Descriptors

Experiment 027 gives Static-OS a machine-portable way to carry a possible next destination across UI shells without carrying executable authority.

The sequence is:

```text
CURIOUS DOOR
    ↓
typed launch descriptor
    ↓
user selects descriptor
    ↓
shell routes to owning destination
    ↓
destination PREFLIGHT
    ↓
ready / stale / blocked
    ↓
optional inert invocation proposal
```

At no point in 027 does routing or preflight execute an operation.

```text
LAUNCH != EXECUTE
CONTEXT != CONSENT
ROUTE != PERMISSION
DESCRIPTOR != COMMAND
DESTINATION REVALIDATES AUTHORITY
```

## Separate from 026 navigation

027 does not remove 026's human-readable navigation channel.

Each Curious Door v2 contains both:

```text
navigation   # 026 evidence links + inert command text
launches     # 027 machine-portable typed descriptors
```

This preserves the older human interface while giving Static-OS a cleaner machine routing object.

## Descriptor shape

A descriptor binds:

```text
launch id
human label
source door id / WANT id / door state
destination app id
destination owner contract
destination operation
bounded context
declared effect if eventually executed
revalidation requirements
```

It explicitly carries:

```text
executes = false
permission_transfer = false
consent_granted = false
```

and requires:

```text
explicit_user_selection = true
destination_revalidation = true
execution_revalidation = true
```

Descriptors deliberately contain no:

```text
argv
shell command
display command
executable URL
consent token
authorization token
```

## Destination apps

027 defines three initial route families.

### composition-wants

Operations:

```text
show-want
refresh-candidates
request-candidate
```

### merge-plugin-parcel

Operations:

```text
show-parcel
validate-parcel
install-parcel
```

### merge-contract-pantry

Operation:

```text
inspect-parcel
```

The descriptor names the app and operation. It does not know how to invoke the app.

## Fetch a descriptor

Curious Doors exposes a read-only descriptor endpoint:

```text
GET /launch?launch_id=<launch-id>
```

For example, the descriptor may be copied to a file and inspected or preflighted elsewhere.

Fetching the descriptor does not route or execute it.

POST, PUT, and DELETE remain refused.

## Destination-side preflight

After a user selects a descriptor, a shell may route it to the owning destination for preflight.

CLI reference implementation:

```bash
python3 ghot/launch_preflight.py verify /path/to/launch.json
python3 ghot/launch_preflight.py preflight /path/to/launch.json
```

Preflight returns:

```text
ready
stale
blocked
```

### ready

Current evidence still supports presenting the described operation.

`ready` is not authorization.

### stale

The descriptor was valid when projected, but its operation no longer matches current state.

Examples:

- candidate was unshared;
- plugin parcel advanced from HOLD to VALIDATED;
- gap became locally satisfied;
- referenced local evidence disappeared.

### blocked

The descriptor or required evidence cannot be safely verified.

Examples:

- descriptor content was tampered;
- remote source cannot currently be revalidated;
- local validation evidence is corrupt.

## Invocation proposals only appear after destination preflight

A launch descriptor never contains argv.

If preflight returns `ready`, the destination may produce:

```text
ghot.launch.invocation-proposal/v0
```

containing a fresh argv proposal.

Even that proposal declares:

```text
executes = false
authorization_granted = false
consent_granted = false
requires_separate_operator_action = true
execution_revalidation_required = true
```

This is the key authority split:

```text
SURFACE knows where
SHELL carries context
DESTINATION checks now
OPERATOR still decides
EXECUTION must revalidate again
```

## Request-candidate preflight

`request-candidate` performs the strongest preflight in 027.

After user selection, the Composition Wants destination checks:

1. the WANT still verifies;
2. the local composition gap is still open;
3. the candidate still belongs to verified WANT history;
4. descriptor context still equals candidate evidence;
5. the source exchange endpoint returns a fresh signed advert;
6. source BODY particular is unchanged;
7. exact package address is still shared;
8. contract id is unchanged;
9. source shape still exactly matches the gap.

This may perform a network GET.

It never sends a grammar request.

```text
REMOTE REVALIDATION READ != REQUEST
```

## Plugin parcel preflight

A HOLD validation launch is ready only while the parcel is still exactly HOLD.

After actual validation, that old descriptor becomes stale and a new INSTALL descriptor appears.

INSTALL preflight additionally rechecks that the validation report still hashes to the queue's stored validation address, still binds the same package address, and still declares the package installable.

After actual install, the old INSTALL descriptor becomes stale.

## Resolved gaps

Once a compatible local grammar exists, request/validate/install launch descriptors disappear.

The resolved door emits only a read-only merge-pantry inspection launch.

## Preflight is read-only

All local preflight operations are required to leave local state byte-identical.

Request-candidate preflight may perform a remote signed-advert GET, but does not write local request state or send a request.

Every preflight result declares:

```text
executes = false
authorization_granted = false
consent_granted = false
permission_transfer = false
execution_revalidation_required = true
```

## Laws

- LAUNCH != EXECUTE
- CONTEXT != CONSENT
- ROUTE != PERMISSION
- DESCRIPTOR != COMMAND
- PREFLIGHT READY != AUTHORIZATION
- INVOCATION PROPOSAL != EXECUTION
- SHELL SELECTION != DESTINATION CONSENT
- REMOTE REVALIDATION READ != REQUEST
- DESTINATION REVALIDATES AUTHORITY
- EXECUTION REVALIDATES AGAIN
