# GHoT — Working entry for the one garden

This file is **for working intelligences**, not marketing. `README.md` may be historical. Never infer current truth from its polish or last heading.

## Receive / re-enter

1. **Receive this request first.** All Static Collective work belongs to one sprawling garden; repo boundaries indicate local ownership, not unrelated projects. Do not route every task into a central project by habit.
2. **Discover the relevant organ.** Include both **public and private** repositories accessible through the authorized connector, not just the public GitBook Living Map. If access to private repos is missing, report `COVERAGE_BOUNDED`, never `nothing exists`.
3. **Check source-owned evidence.** Read local `AGENTS.md`, `CONTINUE.md` or the project's existing stronger status contract (such as `PROJECT_STATUS.json`), exact commits/PRs, and field receipts as needed. Verify state live before working. Do not ask the human to repeat recorded foundations.
4. **Preserve foundations.** Important explicit human corrections and invariants go in the owning project's small `garden/intent.json` or equivalent owner-approved record. A changed program status is auto-derived from GitHub evidence. Never infer human intent from a PR title alone.
5. **Act, then leave a unit.** GHoT work units should identify goal, source, execution, actual result, corrections, unknowns, and next door. Use MEMENTO Return Tickets for historical re-entry, MOTIF receipts for reasoning/alternatives, Chart Swan for possible cross-project synthesis, and GitBook/Live Map only as navigational projections. Preserve original source owner and visibility.
6. **Never promote on retrieval.** `OBSERVED` is not `ACCEPTED`; draft is not merged; merged is not deployed; running is not field-tested. Current user intent and project evidence outrank stale indexes.

## Self-filling file mechanics

- `garden/intent.json` — source-linked, human-approved **foundations and next move**. This is the only manually edited data file in the v0 pulse.
- `garden/pulse.py` — standard-library GitHub reader, authenticated, pagination-aware, and private-inclusive. Fails closed without a token. No changes to remote repos.
- `CONTINUE.md` — generated *replaceable view* from owner intent and latest visible branch/PR facts. Scheduled jobs refresh **only if source state changes**; there is no two-hour timestamp-only commit flood.
- `README.md` — optional; no required edits, promotional copy, or duplication. Keep history intact until its owner elects to archive or replace it.

`python garden/pulse.py inventory --owner the-static-collective --out /private/location/repo-inventory.json` explicitly produces a restricted local file; never commit it to a public repository. A repository-scoped GitHub Actions token may not see private neighbors: use an authorized user/app token only in an appropriate private runtime, not a public workflow log.

`python garden/pulse.py pulse --owner the-static-collective --repo GHoT --intent garden/intent.json --out CONTINUE.md` generates the local snapshot. The workflow in `.github/workflows/garden-pulse.yml` is **not active until this branch is merged**; by default it reads and writes only this repository.

## Stop conditions

- Credentials, personal life, or private source contents would leave their authorized boundary.
- No valid source supports a claimed deployment/test.
- Proposed cross-project association is being treated as admitted authority.
- A freshness failure or missing permission prevents correct re-entry.

Report `KNOWN / CHANGED / HELD / NEXT`, with source links and evidence scope. Do work instead of reconstructing a brochure.