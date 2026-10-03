# Experiment 024 — Composition Gaps and Wants

## Question

Can GHoT notice a concrete missing merge grammar, preserve that gap as an explicit local WANT, discover exact-shape candidates without ranking them, and require a named candidate before issuing a normal 023 request?

## Deterministic proof

```bash
python3 ghot/composition_want_sim.py
```

## Setup

The source body installs and explicitly shares two 021 packages: the example `/work` grammar and a second package with a different `/presence` source selector.

The requester ADMITs a `ghot.organ.state/v1` parcel selected at `/work` and has no local plugin grammar initially.

## Trial A — gap before solution

Inspect locally with no exchange observations.

Expected:

```text
status = gap
candidate_count = 0
```

Declare a WANT anyway. A zero-candidate WANT is valid and creates no network request.

## Trial B — refresh exact structural candidates

Observe the source exchange advert, which contains two packages.

Expected exact candidates: 1.

Only the package whose source declaration exactly equals `ghot.organ.state / version 1 / selector /work / payload object` appears.

The candidate contains no rank, score, or recommendation field.

REFRESH stores that candidate in a separate observation. The original zero-candidate WANT remains unchanged. No request exists yet.

## Trial C — candidate revalidation

UNSHARE the observed `/work` package after REFRESH and attempt explicit REQUEST using the old candidate id.

Expected: REFUSE, with no 023 request reaching the source.

Re-SHARE the exact package to continue.

## Trial D — explicit candidate-specific request

Invoke `REQUEST <want-id> <candidate-id>`.

Expected: local gap and fresh source advert are revalidated; exact package id/address/contract/source shape is revalidated; a normal 023 REQUESTED receipt returns; `package_crossed = false`; and a want→request link persists.

The requester still has no plugin parcel and no plugin install.

## Trial E — OFFER remains separate

The source explicitly performs the normal 023 OFFER.

Expected requester state:

```text
plugin parcel = HOLD
plugin store = empty
```

024 did not perform OFFER.

## Trial F — requester-local resolution

Requester explicitly runs the normal 022 VALIDATE and INSTALL.

Expected: 021 install receipt verifies, local pantry now contains the `/work` plugin grammar, and the same parcel's gap reports `satisfied-local`.

## Trial G — resolved gap blocks repeat request

Try to use the historical WANT/candidate again.

Expected: REFUSE.

The WANT remains inspectable with its immutable initial state, one refresh observation, one want→request link, and current local compatibility showing the gap is resolved.

## Pass

024 passes when the new simulation and the complete 001–023 smoke chain are green.

## Mutation opened

025 can turn wants into a non-automatic curiosity surface for Static-OS:

```text
open gaps
 + unresolved wants
 + new candidate observations
 + resolved wants
       ↓
CURIOUS DOORS
       ↓
human sees:
  "I don't know how to compose this yet."
  "A grammar has appeared nearby."
  "This old gap is now locally satisfied."
```

while preserving:

```text
SURFACE != REQUEST
ATTENTION != PRIORITY
NEW CANDIDATE != NOTIFICATION AUTHORITY
```
