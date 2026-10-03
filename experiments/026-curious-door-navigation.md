# Experiment 026 — Curious Door Navigation

## Question

Can Curious Doors point the operator toward evidence and the correct owning subsystem without executing anything, transferring permission, or becoming a mutation surface?

## Deterministic proof

```bash
python3 ghot/curious_navigation_sim.py
```

## Trial A — pristine root

Construct a Curious Doors surface on an empty root and snapshot it.

Expected:

```text
files before = {}
files after  = {}
```

Merely opening the projection must not create a BODY identity, inbox, or other state.

## Trial B — open gap navigation

Create a zero-candidate 024 WANT.

Expected navigation:

- one GET-only evidence link;
- inert read-only WANT inspection command;
- inert REFRESH command intent.

Every destination must report `executes=false` and `permission_transfer=false`.

Command intents must have no `href`.

## Trial C — candidate observed

Explicitly REFRESH outside Curious Doors.

Expected:

- state becomes `candidate-observed`;
- one candidate-specific REQUEST intent appears;
- source has still received no request.

The request intent is an argv array and is not executable by the surface.

## Trial D — evidence HTTP

Start the loopback surface.

Expected:

```text
GET /                         -> HTML with evidence anchor
GET /door?want_id=...         -> HTML detail
GET /evidence?want_id=...     -> JSON evidence
POST /door?...                -> 405
POST /evidence?...            -> 405
```

GET operations leave the complete local state tree byte-identical.

HTML contains no form, button, or script.

## Trial E — explicit REQUEST elsewhere

Run the normal 024 request operation outside the surface.

Expected state:

```text
requested
```

Before any 023 OFFER, there is no validate or install intent because no plugin parcel exists locally.

## Trial F — explicit OFFER elsewhere

Source separately performs normal 023 OFFER.

Requester receives a normal 022 HOLD.

Expected navigation now includes inert plugin-parcel `show` and `validate` intents.

## Trial G — explicit VALIDATE elsewhere

Run normal 022 VALIDATE outside the surface.

Expected:

- validate intent disappears;
- inert install intent appears;
- surface state remains `requested` because no local grammar is installed yet.

## Trial H — explicit INSTALL elsewhere

Run normal 022 INSTALL outside the surface.

Expected:

- state becomes `resolved-local`;
- request/validate/install intents are absent;
- read-only pantry `inspect` intent remains.

## Trial I — final read-only proof

Snapshot and evidence projection once more.

Expected complete local state tree remains byte-identical.

## Pass

026 passes when navigation changes with the owning subsystem state while every surface navigation record remains non-executing and permission-preserving, and the complete 001–025 chain stays green.

## Mutation opened

027 can make these inert intents portable across Static-OS UI shells as typed launch descriptors:

```text
CURIOUS DOOR
  -> typed launch descriptor
  -> user chooses owning app/tool
  -> destination revalidates context
  -> destination decides whether action is allowed
```

Preserve:

```text
LAUNCH != EXECUTE
CONTEXT != CONSENT
DESTINATION REVALIDATES AUTHORITY
```
