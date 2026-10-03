# Composition Gaps and Wants

Experiment 024 gives GHoT a bounded way to notice:

> I have one concrete ADMITTED parcel, and I currently have no lawful local merge grammar for its exact source shape.

That observation is a gap, not a request.

```text
ADMITTED PARCEL
      ↓
020 local pantry inspection
      ↓
no compatible local grammar
      ↓
GAP
      ↓
optional observed exact-shape candidates
      ↓
explicit WANT
      ↓
optional REFRESH observations
      ↓
explicit candidate-specific REQUEST
      ↓
normal 023 request / offer flow
```

## Concrete grounding

024 does not invent abstract needs from labels, titles, embeddings, or model interpretation.

A gap is grounded in one exact locally ADMITTED parcel and binds parcel id/address, payload address, admitted materialization address, source state kind/version, selector, and payload type.

Inspect one parcel:

```bash
python3 ghot/composition_want.py inspect <parcel-id>
```

If 020 already has a compatible local grammar, status is `satisfied-local` and there is no gap to want. Otherwise status is `gap`.

## Structural candidate matching

024 extends 023 share metadata with the grammar's declared source shape:

```text
state_kind
state_version
selector
payload_type
```

Candidate matching is exact equality across all four fields. There is no title matching, category inference, semantic embedding, model ranking, or score.

```text
CANDIDATE = OBSERVED EXACT-SHAPE POSSIBILITY
```

A candidate also records source BODY identity, exchange road snapshot, signed advert id/address, package id/version/address, contract id, target kind/version, operation kind, and optional author particular.

The candidate id is based on source identity plus exact package/contract/source shape. The current network road is evidence, not candidate identity.

## Observe candidates

With explicit exchange endpoints:

```bash
python3 ghot/composition_want.py inspect \
  <parcel-id> \
  --exchange-url http://BODY:7793
```

Or LAN discovery:

```bash
python3 ghot/composition_want.py inspect \
  <parcel-id> \
  --scan
```

Multiple candidates are returned in deterministic identifier order only.

```text
ORDER != RANK
CANDIDATE != RECOMMENDATION
```

## Declare a WANT

```bash
python3 ghot/composition_want.py want \
  <parcel-id> \
  --exchange-url http://BODY:7793 \
  --note "I want a lawful grammar for this parcel"
```

This persists `ghot.composition.want/v0` under `GHOT_HOME/composition-wants/wants/`.

A WANT may contain zero candidates. That is intentional.

```text
WANT != KNOWN SOLUTION
```

Creating a WANT does not send a request, choose a candidate, create a crossing, install a package, or mutate the ADMITTED parcel.

## Refresh without mutating the WANT

A zero-candidate WANT can later observe the world again:

```bash
python3 ghot/composition_want.py refresh \
  <want-id> \
  --scan
```

or:

```bash
python3 ghot/composition_want.py refresh \
  <want-id> \
  --exchange-url http://BODY:7793
```

REFRESH persists a separate `ghot.composition.want-observation/v0` binding the want id, gap id, source shape, candidate snapshot, and observation time.

The original WANT bytes do not change. REFRESH does not request anything.

```text
REFRESH != WANT MUTATION
REFRESH != REQUEST
```

## Inspect durable wants

```bash
python3 ghot/composition_want.py wants
python3 ghot/composition_want.py show <want-id>
```

SHOW includes the immutable WANT, current local pantry inspection, refresh observations, and any later want→request links.

## Explicit candidate-specific REQUEST

Only an operator naming both a WANT and one candidate id may continue:

```bash
python3 ghot/composition_want.py request \
  <want-id> \
  <candidate-id>
```

Before creating the ordinary 023 request, 024 revalidates the exact parcel, payload, ADMITTED materialization, source shape, absence of a local compatible grammar, candidate membership, source BODY identity, package address, contract id, and exact source-shape match.

Only then does 024 call the normal 023 signed REQUEST path.

The result leaves a content-addressed `ghot.composition.want-request-link/v0` binding the want, gap, candidate, 023 request id, REQUESTED receipt id, source BODY, package address, and request time.

The link is traceability, not OFFER authority.

## One candidate is still not a choice

024 deliberately does not special-case `candidate_count = 1`.

There is no automatic request, default candidate, or implicit recommendation.

```text
ONE CANDIDATE != AUTOMATIC CHOICE
```

## Gap resolution

If a compatible local grammar later appears, `inspect` reports `satisfied-local`.

An old WANT remains historical evidence, but any attempt to create another request from it is refused.

```text
SATISFIED GAP != REPEAT REQUEST
```

## Drift behavior

If the ADMITTED parcel changes after WANT, REQUEST refuses.

If the candidate is unshared after observation, REQUEST refuses.

If the candidate package address, contract id, source BODY identity, or source shape changes, REQUEST refuses.

The operator can REFRESH and inspect current facts.

## No daemon curiosity loop yet

024 does not automatically inspect every ADMITTED parcel, create wants, refresh them, or request anything. It remains owner-invoked.

## Laws

- GAP != REQUEST
- GAP != WANT
- WANT != AUTHORITY
- WANT != KNOWN SOLUTION
- CANDIDATE != RECOMMENDATION
- ORDER != RANK
- ONE CANDIDATE != AUTOMATIC CHOICE
- REFRESH != WANT MUTATION
- REFRESH != REQUEST
- OBSERVED CANDIDATE != DURABLE ENTITLEMENT
- REQUEST LINK != OFFER AUTHORITY
- SATISFIED GAP != REPEAT REQUEST
