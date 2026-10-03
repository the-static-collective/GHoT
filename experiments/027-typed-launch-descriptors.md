# Experiment 027 — Typed Launch Descriptors

## Question

Can Static-OS carry a possible action from Curious Doors to its owning subsystem as portable typed context, while forcing fresh destination-side revalidation and never granting execution, authorization, consent, or permission?

## Deterministic proof

```bash
python3 ghot/launch_descriptor_sim.py
```

## Trial A — two channels

Create one open 024 WANT.

Expected Curious Door v2 contains:

```text
navigation  # existing 026 human channel
launches    # new 027 machine channel
```

Initial launch descriptors include `show-want` and `refresh-candidates`.

Every descriptor verifies and contains no argv, href, command, executable, consent token, or authorization.

## Trial B — read-only destination preflight

Preflight the show and refresh descriptors.

Expected:

```text
status = ready
executes = false
authorization_granted = false
consent_granted = false
permission_transfer = false
```

The complete requester state tree remains byte-identical.

## Trial C — candidate request launch

Explicitly REFRESH through 024 outside the surface.

Expected one `request-candidate` launch appears.

Preflight it.

Expected destination performs a fresh signed advert GET and returns ready while source request inbox remains empty.

## Trial D — stale remote context

UNSHARE the candidate on the source.

Preflight the exact same descriptor.

Expected:

```text
status = stale
```

No request is sent.

Re-SHARE and preflight again.

Expected `ready` again.

## Trial E — tamper

Change candidate id inside the descriptor without recomputing launch id.

Expected:

```text
status = blocked
```

before destination routing.

## Trial F — actual request remains external

Run the real 024 request operation separately.

Expected door becomes `requested` but has no validate/install launch until a plugin parcel actually arrives.

## Trial G — HOLD validation launch

Source explicitly performs 023 OFFER.

Expected requester receives 022 HOLD and Curious Doors emits a typed `validate-parcel` launch.

Preflight returns ready and leaves local state unchanged.

## Trial H — state advance invalidates old launch

Run real 022 VALIDATE separately.

Expected old validate descriptor preflights as stale.

A new `install-parcel` descriptor appears.

Preflight install.

Expected ready with no local mutation.

## Trial I — resolution invalidates install

Run real 022 INSTALL separately.

Expected old install descriptor preflights as stale.

Door becomes `resolved-local` and exposes only typed `inspect-parcel` for merge pantry.

## Trial J — portable descriptor fetch

Fetch resolved launch via:

```text
GET /launch?launch_id=<id>
```

Expected exact descriptor bytes semantically match the surface descriptor, fetch is read-only, and POST returns 405.

## Trial K — no hidden authority

Across all ready/stale/blocked results:

```text
executes = false
authorization_granted = false
consent_granted = false
permission_transfer = false
```

## Pass

027 passes when all new trials and the complete 001–026 smoke chain are green.

## Mutation opened

028 can add an explicit user-issued consent/activation ticket at the destination boundary:

```text
ready preflight
   ↓
user chooses ACT
   ↓
bounded one-operation consent ticket
   ↓
destination revalidates again
   ↓
one execution
   ↓
signed receipt
```

Preserve:

```text
READINESS != CONSENT
CONSENT TICKET != BLANKET AUTHORITY
ONE ACTION != SESSION AUTHORITY
EXECUTION != SUCCESS
```
