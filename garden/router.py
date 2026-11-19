#!/usr/bin/env python3
"""GHoT Garden Router: bounded private-inclusive observation -> local held receipts.

Local first; standard library; no remote writes, webhook receiver, public index, or
new cross-project authority. It consumes GitHub facts and records source pointers.
Run only with a credential authorized for the intended public AND private scope.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from fnmatch import fnmatchcase
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote

try:
    from .pulse import GitHub, inventory
except ImportError:  # `python garden/router.py ...`
    from pulse import GitHub, inventory

SCHEMA = "ghot.garden-router/v1"
DEFAULT_HOME = Path.home() / ".ghot" / "garden-router"
KINDS = {"repo_observed", "branch_advanced", "pr_changed", "pr_updated", "visibility_changed", "default_branch_changed"}


def stable_json(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def protected_dir(path):
    path = Path(path).expanduser()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(path, 0o700)
    return path


def atomic_json(path, payload):
    path = Path(path)
    protected_dir(path.parent)
    tmp = path.with_name(path.name + ".pending-" + str(os.getpid()))
    try:
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as out:
            json.dump(payload, out, ensure_ascii=False, sort_keys=True, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    if os.name == "posix":
        os.chmod(path, 0o600)


@contextmanager
def exclusive_state_lock(home):
    lock = Path(home) / ".scan.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("Garden scan is already locked; inspect the prior process before removing .scan.lock") from exc
    try:
        with os.fdopen(fd, "w") as out:
            out.write(str(os.getpid()) + "\n")
        yield
    finally:
        lock.unlink(missing_ok=True)


def empty_state():
    return {"schema": SCHEMA, "round_robin_cursor": 0, "sequence": 0, "repos": {}, "last_coverage": {}}


def load_state(home):
    path = Path(home) / "state.json"
    if not path.exists():
        return empty_state()
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema") != SCHEMA:
        raise ValueError("Unsupported garden state schema; explicit migration required")
    return state


def pr_state(pr):
    # No title, bodies, review comments or source code copied into the router.
    return {
        "number": int(pr["number"]),
        "status": "MERGED" if pr.get("merged_at") else ("CLOSED" if pr.get("state") == "closed" else ("DRAFT" if pr.get("draft") else "OPEN")),
        "updated_at": pr.get("updated_at"),
        "merged_at": pr.get("merged_at"),
        "head_sha": (pr.get("head") or {}).get("sha"),
        "url": pr.get("html_url"),
    }


def get_prs(api, slug, max_pages):
    result = {}
    truncated = False
    for page in range(1, max_pages + 1):
        chunk = api.get("/repos/" + slug + "/pulls", state="all", sort="updated", direction="desc", per_page=100, page=page)
        if not isinstance(chunk, list):
            raise RuntimeError("Malformed pull request response")
        for raw in chunk:
            item = pr_state(raw)
            result[str(item["number"])] = item
        if len(chunk) < 100:
            break
    else:
        # We may have exactly N*100 entries. Do not imply exhaustive coverage.
        truncated = True
    return result, truncated


def emit(events, state, repo, visibility, kind, before, after, observed_at, source):
    assert kind in KINDS
    state["sequence"] += 1
    payload = {"schema": "ghot.garden-event/v1", "sequence": state["sequence"], "repository": repo,
               "visibility": visibility, "kind": kind, "before": before, "after": after,
               "observed_at": observed_at, "source": source, "authority": "none", "admission": "none"}
    payload["id"] = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    events.append(payload)


def scan(api, original, owner, max_repos=0, max_pr_pages=2, now=None):
    """Return (new_state, changed_events, coverage) without mutating storage.

    Missing from token visibility is never interpreted as deleted. Deep PR history
    is not exhaustively scanned; a PR outside the window is UNKNOWN, not closed.
    """
    if max_repos < 0 or max_pr_pages < 1:
        raise ValueError("Invalid scan bounds")
    # Clone so an API failure never alters caller state.
    state = json.loads(json.dumps(original))
    observed_at = now or datetime.now(timezone.utc).isoformat()
    inv = inventory(api, owner)
    visible = inv["repositories"]
    names = sorted(visible, key=lambda x: x["full_name"].casefold())
    total = len(names)
    start = state["round_robin_cursor"] % max(total, 1)
    count = total if max_repos == 0 else min(max_repos, total)
    chosen = [names[(start + n) % total] for n in range(count)] if total else []
    events, failures, truncated = [], [], []
    for repo in chosen:
        fullname = repo["full_name"]
        slug = "/".join(quote(part, safe="") for part in fullname.split("/"))
        vis = repo.get("visibility") or "unknown"
        default_branch = repo.get("default_branch")
        if not default_branch:
            failures.append({"repository": fullname, "reason": "NO_DEFAULT_BRANCH"})
            continue
        try:
            head = api.get("/repos/" + slug + "/commits/" + quote(default_branch, safe=""))
            sha = head["sha"]
            if not re.fullmatch(r"[a-fA-F0-9]{40}", sha):
                raise ValueError("Invalid commit SHA")
            prs, is_truncated = get_prs(api, slug, max_pr_pages)
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            failures.append({"repository": fullname, "reason": type(exc).__name__})
            continue
        if is_truncated:
            truncated.append(fullname)
        old = state["repos"].get(fullname)
        current = {"visibility": vis, "default_branch": default_branch,
                   "head_sha": sha, "url": repo.get("html_url"),
                   "prs": {**(old.get("prs", {}) if old else {}), **prs}}
        url = repo.get("html_url") or ("https://github.com/" + fullname)
        if old is None:
            emit(events, state, fullname, vis, "repo_observed", None,
                 {"default_branch": default_branch, "head_sha": sha}, observed_at, url)
        else:
            for field, kind, source in [
                ("visibility", "visibility_changed", url),
                ("default_branch", "default_branch_changed", url),
                ("head_sha", "branch_advanced", url + "/commit/" + sha),
            ]:
                if old.get(field) != current[field]:
                    emit(events, state, fullname, vis, kind, old.get(field), current[field], observed_at, source)
            for number, item in prs.items():
                prior = old.get("prs", {}).get(number)
                if prior is None:
                    # First sighting inside an existing repo is a useful new event.
                    emit(events, state, fullname, vis, "pr_changed", None, item, observed_at, item.get("url"))
                elif prior != item:
                    kind = "pr_changed" if prior.get("status") != item.get("status") or prior.get("head_sha") != item.get("head_sha") else "pr_updated"
                    emit(events, state, fullname, vis, kind, prior, item, observed_at, item.get("url"))
        state["repos"][fullname] = current
    state["round_robin_cursor"] = (start + count) % max(total, 1)
    previously_visible = set(state["repos"])
    missing = sorted(previously_visible - {x["full_name"] for x in visible})
    coverage = {"observed_at": observed_at, "owner": owner, "visible_to_token": total,
                "scanned": len(chosen)-len(failures), "scan_failures": failures,
                "pr_windows_truncated": truncated,
                "previously_seen_not_visible_to_token_now": missing,
                "scope": "AUTHENTICATED_VISIBLE_ONLY; PRIVATE_INCLUDED_IF_AUTHORIZED; NOT_EXHAUSTIVE"}
    state["last_coverage"] = coverage
    return state, events, coverage


def routes_for(event, config):
    """Select local held inboxes, not remote receivers. Never dispatch side effects."""
    matches = []
    for rule in config.get("routes", []):
        if event["kind"] not in rule.get("kinds", []):
            continue
        if not any(fnmatchcase(event["repository"].casefold(), p.casefold()) for p in rule.get("repos", [])):
            continue
        if event["visibility"] not in rule.get("visibility", []):
            continue
        target = rule.get("inbox", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", target):
            raise ValueError("Route inbox must be a safe local name")
        matches.append(target)
    return sorted(set(matches))


def save_events(home, events, state, routes):
    home = protected_dir(home)
    ledger = home / "events.jsonl"
    seen = set()
    if ledger.exists():
        with ledger.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    seen.add(json.loads(line)["id"])
    pending = [e for e in events if e["id"] not in seen]
    if pending:
        fd = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            for event in pending:
                f.write(stable_json(event) + "\n")
            f.flush()
            os.fsync(f.fileno())
    # Re-deliver already-journaled receipts after crashes: outbox names are idempotent.
    for event in events:
        for inbox in routes_for(event, routes):
            path = protected_dir(home / "outbox" / inbox) / (event["id"] + ".json")
            if not path.exists():
                atomic_json(path, {"schema": "ghot.garden-handoff/v1", "destination": inbox,
                                   "status": "HELD", "admission": "none", "event": event})
    atomic_json(home / "state.json", state)
    return len(pending)


def context(home, query, limit=25):
    """Bounded re-entry pointers. Historical conversation lookup belongs to ChatGPT."""
    state = load_state(home)
    matches = [(k, v) for k, v in state["repos"].items() if query.casefold() in k.casefold()]
    if not query or len(query) < 2:
        raise ValueError("Supply a specific project or organ query (at least two characters)")
    events = []
    path = Path(home) / "events.jsonl"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    if query.casefold() in event.get("repository", "").casefold():
                        events.append(event)
    return {"schema": "ghot.garden-context/v1", "query": query,
            "coverage": state["last_coverage"], "project_roots": [
                {"name": name, "visibility": r["visibility"], "url": r["url"], "head_sha": r["head_sha"]}
                for name, r in matches[:limit]],
            "recent_events": events[-limit:], "authority": "none", "admission": "none",
            "next": "Open owner AGENTS/CONTINUE/status, search relevant chat history once, verify PRs and tests before acting"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["sweep", "context"])
    parser.add_argument("--owner", default="the-static-collective")
    parser.add_argument("--home", default=str(DEFAULT_HOME))
    parser.add_argument("--routes", default="garden/routes.json")
    parser.add_argument("--max-repos", type=int, default=0, help="0 = all visible repos; >0 = fair round-robin budget")
    parser.add_argument("--max-pr-pages", type=int, default=2)
    parser.add_argument("--query", help="Named project/organ for read-only context lookup")
    parser.add_argument("--out", help="Private local JSON output path for context command")
    args = parser.parse_args(argv)
    home = protected_dir(args.home)
    if args.command == "context":
        packet = context(home, args.query or "")
        if not args.out:
            parser.error("context requires --out: never write private names to public CI logs")
        atomic_json(args.out, packet)
        print("Wrote bounded, local-only source pointers; coverage remains token-bounded.")
        return 0
    api = GitHub(os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"))
    routes = json.loads(Path(args.routes).read_text(encoding="utf-8"))
    with exclusive_state_lock(home):
        prior = load_state(home)
        state, events, coverage = scan(api, prior, args.owner, args.max_repos, args.max_pr_pages)
        stored = save_events(home, events, state, routes)
    # Never log private repo identities or source metadata to public build logs.
    print(f"Source-bounded sweep: visible={coverage['visible_to_token']}, inspected={coverage['scanned']}, "
          f"held_events={stored}, errors={len(coverage['scan_failures'])}, truncated_pr_windows={len(coverage['pr_windows_truncated'])}. "
          "No remote writes or admissions.")
    return 0 if not coverage["scan_failures"] else 2


if __name__ == "__main__":
    sys.exit(main())
