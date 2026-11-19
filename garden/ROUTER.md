# GHoT — garden-wide source event router (operator document)

**Intent:** One garden, many sovereign organs. Every relevant change may be *observed and routed as an unadmitted, attributable candidate* without turning this repository into a universal authority or public inventory.

## What is implemented

- `python garden/router.py sweep`: authenticated GitHub API discovery via `/user/repos`, retaining both private and public repos visible to the supplied credentials, paginated. Each visited repo gets its default-branch commit SHA and a bounded latest-updated PR window. A first scan establishes a baseline; subsequent scans emit events for actual branch, PR-state, PR-update, default-branch or visibility changes. A newly discovered repo gets a `repo_observed` event. Permission errors and truncated windows are explicit coverage limits.
- Append-only `events.jsonl` with stable receipt IDs; state and private `outbox/<inbox>/<id>.json` written to the operator's local private directory. If a process crashes after appending but before committing state, the next run avoids duplicating already-journaled IDs. Outboxes are `HELD`, `admission:none`, and **have no network dispatch or repository mutation**.
- `python garden/router.py context --query NAME --out /private/path/file.json`: bounded local source-address packet for selective re-entry. It is a pointer, not replacement for owner-project status. It does **not** search ChatGPT history by itself.
- `garden/routes.json` maps watched repos and event kinds into local inboxes. Every route must be explicitly allowed, and its events retain original private visibility. No public publication by default.
- `python -m unittest discover -s garden/tests -v` includes regression checks for private inclusion, status changes, no-op scans, repeated journals, missing permissions, route isolation, and owner-only local files.

## Requirements and first local run

Python 3.10+ standard library; an authenticated GitHub token with **read access to the intended public and private repos**. The current GitHub connector and a GitHub Actions `GITHUB_TOKEN` do not automatically grant that access to a different program. Do not paste the token into chat or commit it.

From a trusted local GHoT checkout:

```bash
# Use your own secure local credential provider for GH_TOKEN.
python -m unittest discover -s garden/tests -v
python garden/router.py sweep --owner the-static-collective
python garden/router.py context --query HUMKIN --out /path/OUTSIDE/the/repo/humkin-context.json
```

**Private output path:** defaults to `~/.ghot/garden-router`; NEVER point `--home` or `--out` at the public checkout, CI artifacts or a public cloud bucket. On POSIX, directories are mode 0700 and files 0600. On Windows protect the directory with the current user's account ACL; POSIX permission bits are not a Windows security guarantee.

For a Windows computer with GitHub CLI logged in, `powershell -ExecutionPolicy Bypass -File .\garden\run-local.ps1` requests the token from `gh auth token` only for the current process and runs one sweep. To enable two-hour user-scoped scanning on Windows, run `powershell -ExecutionPolicy Bypass -File .\garden\run-local.ps1 -Action Install`; inspect it using `-Action Status` or remove it using `-Action Remove`. It runs only while that user is signed in and must be reinstalled before its one-year recurrence window ends. These Windows Task Scheduler operations are **not field-tested on the user's machine**.

**Schedule:** rerun `sweep` at the operator's chosen interval (for example every 2 hours) in a private, authorized runner. This PR does not create a working unattended schedule or cross-repo credentials. The existing GHoT GitHub Actions pulse remains **repo-scoped** and must not be presented as an organization-wide router. Future GitHub App/webhook ingress needs signature verification, delivery replay protection, and the same privacy gates.

## Invariants / known limits

1. The scanner's scope is **visible to the supplied token**, never "all GitHub." Private repos count if the token can see them. A repo disappearing from inventory could mean a permission change, so the router records a visibility gap, **never a deletion**.
2. PR history is bounded by `--max-pr-pages` (default 2 pages of 100 per repo, latest updated). An old PR absent from the returned window is UNKNOWN, not closed or merged. For deep archaeology, use the native project tools.
3. Branch SHA / PR state is GitHub evidence, **not** deployment, real device proof, human authorization or admission. Outbox entries cannot execute, merge, publish or authorize anything.
4. Private identifiers and event metadata stay in the operator-private runtime. The public GitBook atlas can provide public pointers; it must not publish private inventory from this router.
5. The owner project remains the canonical truth. MEMENTO's Return Tickets preserve historical cuts; MOTIF receipts preserve tested hypotheses; the router only detects changes and points to them.
6. Event router does not have access to ChatGPT conversation history. That is a **separate one-pass entry responsibility** for capable ChatGPT sessions, specified in `chatgpt/ENTRY.md` and root `AGENTS.md`.
7. Local journals and inboxes are not synced between computers by this v1. Build a secure, explicit recipient transport later; don't assume this program created it.

## First field acceptance test

Use a token that can actually see private MEMENTO/Groove Rooms alongside public projects. Sweep once; inspect `last_coverage` and compare with current authenticated GitHub enumeration (110 was one observed aperture, not a permanent invariant). Sweep unchanged; expect zero new events. Make one harmless PR status change in a test repo; sweep again; expect precisely one attributable status receipt with no cross-repo writes. Search the history of the affected organ in a fresh ChatGPT chat and recheck the repo's current evidence. If fresh-chat retrieval fails, repair the entry trigger—not the data volume.
