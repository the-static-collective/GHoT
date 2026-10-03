# Curious Door Navigation

Experiment 026 makes Curious Doors navigable without turning them into a control surface.

The new law is:

```text
NAVIGATION != ACTION
```

A door may point to evidence or describe a next command. The surface still cannot execute that command, transfer permission to the owning subsystem, or mutate state.

## Two destination types

Every v1 Curious Door carries a `navigation` array containing only two bounded shapes.

### Evidence link

```text
kind = evidence-link
method = GET
effect = none
executes = false
permission_transfer = false
```

Evidence links stay inside the loopback Curious Doors service.

Example:

```text
/door?want_id=<want-id>
```

They expose already-persisted local evidence only.

### Command intent

```text
kind = command-intent
owner_contract = <owning subsystem>
argv = [ ... ]
display_command = <human-readable shell rendering>
effect_if_run = <declared effect>
executes = false
permission_transfer = false
```

A command intent deliberately has no `href`.

It is data describing where the operator may choose to go next.

The surface never passes it to a shell or subprocess.

```text
COMMAND INTENT != EXECUTION
DISPLAY COMMAND != SHELL INVOCATION
```

## State-aware destinations

### open-gap

Curious Doors shows:

- read-only evidence link;
- read-only `composition_want.py show` intent;
- explicit `composition_want.py refresh ... --scan` intent.

REFRESH belongs to `ghot.composition-wants@0`. Curious Doors only displays it.

### candidate-observed

In addition to evidence and refresh, each exact structural candidate receives its own candidate-specific:

```bash
python3 ghot/composition_want.py request <want-id> <candidate-id>
```

intent.

No candidate receives a preferred flag, score, automatic action, or executable link.

### requested, before package arrival

The door shows request evidence but no validate/install intent because there is no local plugin parcel yet.

### requested, package in HOLD

When an already-persisted matching 022 parcel exists locally, the door may display:

```bash
python3 ghot/merge_plugin_parcel.py show <parcel-id>
python3 ghot/merge_plugin_parcel.py validate <parcel-id>
```

Both remain inert intents. VALIDATE still belongs to the plugin-parcel subsystem.

### requested, package VALIDATED

The validation intent disappears and the surface may display:

```bash
python3 ghot/merge_plugin_parcel.py install <parcel-id>
```

Again, the surface does not execute it.

### resolved-local

Mutation-oriented intents disappear.

The door points only to read-only local compatibility inspection:

```bash
python3 ghot/merge_contract_pantry.py inspect <parcel-id>
```

## Evidence detail

The local server now exposes:

```text
GET /door?want_id=<want-id>      HTML evidence view
GET /evidence?want_id=<want-id>  JSON evidence view
```

The evidence projection includes:

- immutable WANT;
- current local pantry inspection;
- 024 refresh observations;
- want→request links;
- already-persisted matching plugin-parcel inbox summaries.

It does not create a plugin inbox helper or BODY identity just to inspect these files. It reads existing inbox JSON directly.

This matters on a pristine root:

```text
OPEN CURIOUS DOORS -> ZERO NEW FILES
```

## HTML behavior

The root page can contain ordinary anchor links to GET-only evidence pages.

It still contains:

```text
no forms
no buttons
no scripts
```

Command intents are rendered as inert `<pre>` text, not clickable action URLs.

POST, PUT, and DELETE remain HTTP 405.

## Permission boundary

`owner_contract` is explanatory provenance.

It means:

> this is the subsystem that owns the described operation.

It does not mean:

> this surface has inherited that subsystem's authority.

Every navigation record explicitly carries:

```text
permission_transfer = false
```

and the surface declares:

```text
navigation_executes = false
navigation_transfers_permission = false
```

## Organ supervision

The normal organ still supervises Curious Doors on loopback port 7794.

Its service state now also declares:

```text
navigation_executes = false
permission_transfer = false
evidence_get_only = true
```

## Laws

- NAVIGATION != ACTION
- LINK != AUTHORITY
- SURFACE CONTEXT != SUBSYSTEM PERMISSION
- COMMAND INTENT != EXECUTION
- DISPLAY COMMAND != SHELL INVOCATION
- OWNER METADATA != PERMISSION
- EVIDENCE LINK != MUTATION
- ACTION INTENT != EXECUTABLE URL
- ARRIVAL OF A LOCAL PARCEL != SURFACE AUTHORITY
- RESOLUTION != STALE ACTION PERMISSION
