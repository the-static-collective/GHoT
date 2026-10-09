# PRINT-WITNESS-006 — Full Measure local confirmation to PENNY work-review candidate

## The actual crossing

This is **not** a live physical print, a real authenticated human witness, a PENNY payout or a signed reLATTE crossing. It is an executable, review-only bridge from GHoT's real local PDF/venue preparation through Full Measure's *native existing* contribution rules into PENNY-014's *native unchanged* ledger checks.

```text
real PDF bytes -> GHoT 004 local PDF preflight -> GHoT 005 held proposal
  -> manual selection of an actual Full Measure project + pledge in a local store
  -> native Full Measure transition authorization, source event order, separate confirmer
  -> native Full Measure Deed count (1 for confirmed local record, 0 for reported only)
  -> PENNY review candidate with no quantity assigned
  -> native PENNY-014 zero-event world inspection
  -> 0 pending, 0 backed, 0 issued, 0 treasury events
```

### Source owners, still separate

- **GHoT 004/005**: source-verified PDF/print venue proposal with zero physical action. The bridge cold-recomputes GHoT 005's own JS JSON-body checksum and confirms that 005 is still on held, zero-issue state. Original GHoT 004 receipt was separately source-cold-verified in 005's native workflow.
- **Full Measure**: pinned [`field-quest-engine-001` PR #54](https://github.com/the-static-collective/full-measure-world-layer/pull/54) at `c9206d5055ad574a23acb2eceb5f8785a4ad64fe`. This bridge directly runs its `authorizePledgeTransition` on accepted, reported, confirmed stages and `buildFullMeasureSheet` on the reconstructed local trace. The simulated local store's states and fields match existing Full Measure server structures, not a parallel second RPG ledger.
- **PENNY**: pinned [`PENNY-014` PR #17](https://github.com/the-static-collective/Jubilee-treasury/pull/17) at `a36777cb87bcfb6b7706b910ba18c4c4b24c73a3`. This bridge calls unchanged `newKeys`, `createWorld` and `inspectWorld` on an **empty signed-policy genesis** with independently generated role keys. All ephemeral keys are process-local; the source does NOT import an actual Treasury state or append a work or coin event.

### Exact proof limits

Full Measure's current local Express JSON event store is **not authenticated cryptographically** and its local server permits actor selection by request header. A coherent exported `pledge.confirmed` event plus a second actor is **not proof that a real independently verified human performed an action**, that the work occurred, or that a page came back from a shop. This bridge expressly outputs `full_measure_human_identity_authenticated=false`, `source_export_signature_verified=false` and `actual_physical_print_independently_verified=false` even if its local Deed projection equals one.

Only a structurally consistent original Full Measure local event chain can enter the candidate: `pledge.proposed` (by contributor) → `pledge.accepted` (by opener/steward) → `pledge.reported_complete` (by contributor) → optionally `pledge.confirmed` (by a distinct opener/steward). Dates must be strictly ordered and match the pledge snapshot. Source project/pledge IDs, circle members, individual event IDs, role gates and contribution recipient must agree. Duplicate, missing, self-confirmed, time-reordered, cross-project and role-smuggled records hold.

If a valid local chain stops at `reported_complete`, the ordinary native Full Measure sheet reports **0** Deeds, and the PENNY review remains `HOLD_UNCONFIRMED_FULL_MEASURE_REPORT`. When the local chain reaches `confirmed`, the native Full Measure sheet may report one locally confirmed Deed, and PENNY receives a **`REVIEW_ELIGIBLE_ONLY_NEEDS_INDEPENDENT_WORK_WITNESS`** proposal with 0 authorized monetary allocation. Neither source state authenticates real people.

## How to run

Obtain exact donor checkouts at the pinned SHAs. Install the original Full Measure dependencies with `npm ci --ignore-scripts --no-audit --no-fund`; install `pypdf==5.9.0` if regenerating the underlying 004 PDF. From the GHoT 006 branch:

```sh
FM="$PWD/external/full-measure"
PN="$PWD/external/penny-014"
FM_DONOR_ROOT="$FM" PENNY_DONOR_ROOT="$PN" \
 GHOT_005_PROOF_PATH="$PWD/dist/print-witness-006/held005.json" \
 (cd "$FM" && node --import tsx --test "$OLDPWD/tests/print-work-review-006.test.mjs")

# Only if your local 005 packet, selected Full Measure event store and reviewer
# selection file have been provided and checked for private information:
node "$FM/node_modules/tsx/dist/cli.mjs" ghot/print_work_review_006.mjs \
 "$FM" "$PN" \
 "$PWD/dist/print-witness-006/held005.json" \
 "$PWD/private/full-measure-local-store.json" \
 "$PWD/private/operator-selection.json" \
 "$PWD/private/NEW-print-review-006.json"
```

`operator-selection.json` is a strict `ghot.print-work-review-selection-006/v0` document with exactly `source_composition_id`, `source_quest_id`, `project_id`, `pledge_id`, `local_review_ref`. This is a **local operator association**, not a cryptographic source-authoritative link. The selected Full Measure local store must have `projects`, `pledges`, `domainEvents`, and `circleMembers` arrays, each bounded. Do not upload real people's identity data or private PDF bytes to GitHub or publicly share a store export. Result exposes event/pledge SHA-256 commitments and an external reference but not names, descriptions, notes, addresses or raw events.

## CI

The workflow `.github/workflows/print-work-review-006.yml` source-verifies a generated one-page PDF through **real GHoT 004**, produces a source-cold-verified **real GHoT 005** held packet, then uses a **deliberately synthetic** Full Measure record with two distinct local actor IDs. It runs Full Measure's original transition and Deed modules, native PENNY-014 zero-ledger policy, native Full Measure/PENNY donor regressions and hostile event-tamper tests. No real venue, person, coins, or live ledger is involved.

## What is still required to cross into any real work value

An actual authenticated Full Measure event service, independently established identity and authorization of the confirmer, a verified external physical print receipt/observation, separately agreed fair work terms, identity and consent of the intended PENNY beneficiary, an independent signed PENNY-014 work-witness authorization, and **separate** signed physical penny deposits with independent depositor/custodian/counter roles. Even that software chain is not a live regulated financial service without consumer law, custody and compliance work. None of those acts occur in 006.

**Non-collapse laws:** `LOCAL CONFIRMATION != AUTHENTICATED HUMAN`, `FULL MEASURE DEED != PENNY WORK CERTIFICATE`, `PENNY WORK CERTIFICATE != COIN DEPOSIT`, `SIGNED JOURNAL != PHYSICAL TRUTH`, `REVIEW ELIGIBLE != WORK APPROVED`, `PRINT RECEIPT != PHYSICAL COLLECTION`, `NATIVE REPLAY != PUBLISHABLE FINANCIAL INSTRUMENT`.
