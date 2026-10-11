#!/usr/bin/env python3
"""GHoT 030: owner-local, exact-Git-source hashing through activation 028.

No branch code is imported or executed. Git access is read-only and local.
An owner's source allowlist is not an ACT ticket.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from relatte_identity import jcs_bytes, identity_safe
from state_migration import semantic_address
from launch_descriptor import (
    APP_BRANCH_WORK, BRANCH_WORK_SOURCE, derive_launch_id, verify_launch_descriptor,
)

CANDIDATE_SCHEMA = "ghot.branch-worker-candidate/v0"
POLICY_SCHEMA = "ghot.branch-worker-sources/v0"
MAX_SOURCE_BYTES = 1_048_576
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[a-f0-9]{40}$")
CONTENT = re.compile(r"^[a-f0-9]{64}$")
PATH = re.compile(r"^[A-Za-z0-9_./-]{1,220}$")
CONTEXT_KEYS = {"repository", "commit", "path", "sha256", "branchHint"}


def validate_context(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != CONTEXT_KEYS:
        raise ValueError("INVALID_BRANCH_CONTEXT")
    if not all(isinstance(v, str) for v in value.values()):
        raise ValueError("INVALID_BRANCH_STRING")
    repo, commit, path, sha, hint = (
        value["repository"], value["commit"], value["path"],
        value["sha256"], value["branchHint"]
    )
    if not REPOSITORY.fullmatch(repo) or not SHA.fullmatch(commit):
        raise ValueError("INVALID_BRANCH_IDENTITY")
    if not PATH.fullmatch(path) or path.startswith("/") or any(
        p in ("", ".", "..") for p in path.split("/")
    ):
        raise ValueError("INVALID_SOURCE_PATH")
    if not CONTENT.fullmatch(sha):
        raise ValueError("INVALID_SOURCE_SHA256")
    if not hint or hint == "main" or not re.fullmatch(r"[A-Za-z0-9_./-]{1,180}", hint):
        raise ValueError("INVALID_BRANCH_HINT")
    return dict(value)


def make_descriptor(context: dict[str, str]) -> dict[str, Any]:
    context = validate_context(context)
    source_id = semantic_address(context)
    descriptor = identity_safe({
        "kind": "ghot.launch.descriptor", "version": "0",
        "launch_id": "",
        "label": "Inspect one exact locally held source file",
        "source": {
            "surface_contract": BRANCH_WORK_SOURCE,
            "source_id": source_id,
        },
        "destination": {
            "app_id": APP_BRANCH_WORK,
            "owner_contract": "ghot.branch-worker@0",
            "operation": "hash-exact-source",
        },
        "context": context,
        "effect_if_executed": "owner-local-source-hash",
        "requirements": {
            "explicit_user_selection": True,
            "destination_revalidation": True,
            "execution_revalidation": True,
            "consent_required_for_effectful_action": True,
        },
        "executes": False,
        "permission_transfer": False,
        "consent_granted": False,
    })
    descriptor["launch_id"] = derive_launch_id(descriptor)
    if not verify_launch_descriptor(descriptor):
        raise ValueError("BRANCH_DESCRIPTOR_INVALID")
    return descriptor


def candidate_from_file(file: Path) -> dict[str, str]:
    value = json.loads(file.read_text(encoding="utf8"))
    if not isinstance(value, dict) or set(value) != {"schema", "context"}:
        raise ValueError("INVALID_CANDIDATE_ENVELOPE")
    if value["schema"] != CANDIDATE_SCHEMA:
        raise ValueError("INVALID_CANDIDATE_SCHEMA")
    return validate_context(value["context"])


def _git(repo_root: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=12, check=False,
    )
    if result.returncode:
        raise ValueError("ORIGINAL_GIT_OBJECT_UNAVAILABLE")
    return result.stdout if binary else result.stdout.decode("utf8").strip()


def _origin_matches(actual: str, repository: str) -> bool:
    return actual in (
        f"https://github.com/{repository}",
        f"https://github.com/{repository}.git",
        f"git@github.com:{repository}.git",
        f"git@github.com:{repository}",
        f"ssh://git@github.com/{repository}.git",
    )


def inspect_source(context: dict[str, str], *, root: Path) -> dict[str, Any]:
    """Fresh read-only verification. Never accepts a checkout path from a descriptor."""
    context = validate_context(context)
    policy_file = root / "branch-worker" / "sources.json"
    policy = json.loads(policy_file.read_text(encoding="utf8"))
    if not isinstance(policy, dict) or set(policy) != {"schema", "entries"}:
        raise ValueError("INVALID_LOCAL_SOURCE_POLICY")
    if policy["schema"] != POLICY_SCHEMA or not isinstance(policy["entries"], list):
        raise ValueError("INVALID_SOURCE_POLICY_SCHEMA")
    if not 0 < len(policy["entries"]) <= 32:
        raise ValueError("INVALID_LOCAL_SOURCE_POLICY_SIZE")
    matches = []
    for entry in policy["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"context", "checkout_root", "reviewed_for_local_read"}:
            raise ValueError("INVALID_POLICY_ENTRY")
        validate_context(entry["context"])
        if not isinstance(entry["checkout_root"], str) or not entry["checkout_root"]:
            raise ValueError("INVALID_CHECKOUT_ROOT")
        if type(entry["reviewed_for_local_read"]) is not bool:
            raise ValueError("INVALID_READ_REVIEW")
        if entry["context"] == context:
            matches.append(entry)
    if len(matches) != 1 or matches[0]["reviewed_for_local_read"] is not True:
        raise ValueError("EXACT_SOURCE_NOT_OWNER_ALLOWLISTED")
    entry = matches[0]
    checkout = Path(entry["checkout_root"]).resolve(strict=True)
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise ValueError("NOT_A_CHECKED_OUT_GIT_REPO")
    origin = _git(checkout, "config", "--get", "remote.origin.url")
    if not _origin_matches(str(origin), context["repository"]):
        raise ValueError("GIT_ORIGIN_SCOPE_MISMATCH")
    commit, path = context["commit"], context["path"]
    if _git(checkout, "cat-file", "-t", commit) != "commit":
        raise ValueError("PIN_NOT_COMMIT")
    object_expr = commit + ":" + path
    if _git(checkout, "cat-file", "-t", object_expr) != "blob":
        raise ValueError("ENTRY_NOT_GIT_BLOB")
    size = int(_git(checkout, "cat-file", "-s", object_expr))
    if size > MAX_SOURCE_BYTES:
        raise ValueError("SOURCE_TOO_LARGE")
    data = _git(checkout, "show", object_expr, binary=True)
    if not isinstance(data, bytes) or len(data) != size:
        raise ValueError("SOURCE_SIZE_MISMATCH")
    actual = hashlib.sha256(data).hexdigest()
    if actual != context["sha256"]:
        raise ValueError("EXACT_SOURCE_BYTES_CHANGED")
    # The full local policy is bound to both the preview and execution proposal.
    policy_digest = hashlib.sha256(jcs_bytes(policy)).hexdigest()
    return identity_safe({
        "kind": "ghot.branch-worker.source-observation",
        "version": "0",
        "repository": context["repository"],
        "branch_hint": context["branchHint"],
        "commit": commit, "path": path, "blob_sha256": actual,
        "size_bytes": size, "local_policy_sha256": policy_digest,
        "source_read": True, "donor_code_executed": False,
        "permission_transferred": False,
    })


def execute_hash(context: dict[str, str], *, root: Path) -> dict[str, Any]:
    """Invoked ONLY by 028's atomically claimed execution dispatcher."""
    verified = inspect_source(context, root=root)
    return {
        **verified,
        "operation": "hash-exact-source",
        "done_locally": True,
        "read_only_git": True,
        "branch_program_executed": False,
        "remote_effects": 0,
    }
