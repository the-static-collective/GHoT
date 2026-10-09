# UNFINISHED BUSINESS 001 — The First Case

Status: **bounded executable proposal**, not admitted Collective-wide canon and not a production dispatcher.

> UNFINISHED != FAILED.
>
> DISCOVERED OPPORTUNITY != AUTHORIZED WORK.
>
> RELEASED != DELETED.

## First real cross-repo observation

This fixture pins three existing GitHub sources at exact observed commits:

- GHoT `ghot/carried_intent_assignment.py`: explicit carried-intent assignment without execution.
- reLATTE `README.md`: a documented crossing and receipt boundary.
- CANNON `README.md`: an owner-selected history principle, currently a bootstrap rather than an admitted implementation.

The **experiment author** declares a candidate relation between GHoT's local assignment work and reLATTE's receipt boundary. That is a hypothesis, not a project-owner request or proof of runtime compatibility. The CANNON inventory-index need is also an experiment hypothesis. Source addresses are pinned but **this tool does not fetch, hash, validate, or execute source files**; canonical Git truth remains in each owning repository.

## Run

```sh
python3 ghot/unfinished_business.py discover fixtures/unfinished-business-001.json --dial 1
python3 ghot/unfinished_business_sim.py
```

For any returned case, an owner may record an explicit decision without executing anything:

```sh
python3 ghot/unfinished_business.py decide fixtures/unfinished-business-001.json \
  --case-id "ghot-ub-case-v0:<exact-id-from-discover>" \
  --decision HOLD --selection-source "owner-human-reviewed" \
  --out /tmp/unfinished-decision.json
```

The decision file must not already exist: witness is exclusive-write. The result/decision identifiers are unsigned SHA-256 **local integrity identifiers**, not signatures or credentials. No network, remote Git, adapter, shell, machine, or physical effect is invoked by this script.

## Status semantics

- `CANDIDATE`: all stated needs have at least one declaration-matched source; still not proven compatible.
- `OBSTACLE`: at least one declared need has no candidate (partially matched candidates are retained).
- `SOURCE_ONLY`: a source lists no outstanding needs. It isn't falsely counted as completed work.
- `HOLD`: owner-declared held item; not a provider.
- `RELEASED`: owner-declared released item; history stays present, but it does not offer work.

The optional human decision is `HOLD`, `RELEASED`, or `ACCEPT_FOR_REVIEW`. Acceptance for review requires a `CANDIDATE`; **none** of these execute a plan or mutate the source inventory. A subsequent source-owner crossing and separate execution permission would be required.

## Radio dial: 1–11

At 1, only exact capability labels connect. Each additional notch permits one more *explicitly authored* relation hop, up to 10 at notch 11. The dial **never** creates semantic relations, infers synonyms, raises trust, or grants execution. Every hop is named in a witness trail, with its proposer and basis preserved in the inventory snapshot.

## First-case outcomes

With the included real-source, experimenter-annotated fixture and dial 1:

1. GHoT's assignment edge receives a reviewable candidate match from reLATTE's documented receipt boundary. **No integration has run.**
2. CANNON's hypothetical cross-repo inventory-index need remains an explicit obstacle.
3. reLATTE's no-needs record is `SOURCE_ONLY`, not a fake success.

Success for this slice is a new *executable, reproducible discovery capability*, not a claim of completed GHoT–reLATTE interoperability. The next case should test owner-confirmed contracts and an actual runnable bounded adapter before claiming a new cross-repo composed capability.

## Negative proofs

`ghot/unfinished_business_sim.py` covers determinism and order changes, held/released exclusion, 1-vs-2 dial sensitivity, invalid commits and path traversal, duplicate identities, malicious capability text, case/result tampering, obstacle-review refusal, unsigned/no-effect decisions, and exclusive-write protection.

## Non-goals

No GitHub scraping or branch census; no silent source authorization; no auto-retirement of projects; no interpretation of creative or personal obligations as tasks; no hidden scoring of humans; no network or remote command execution; no assertion that a hypothetical relation is tested merely because it has a label.

**This is GHoT-owned discovery. CANNON remains owner of selections, reLATTE of crossings, and each work's owner of its disposition.**
