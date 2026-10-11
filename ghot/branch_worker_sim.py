#!/usr/bin/env python3
"""Owner-local branch worker 030: hostile, independent source-pinned ACT tests."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from activation_ticket import ActivationStore, verify_activation_ticket, verify_execution_receipt
from branch_work import (
    CANDIDATE_SCHEMA, POLICY_SCHEMA, inspect_source,
    make_descriptor, validate_context,
)
from branch_worker import act, preview

REPO = "the-static-collective/planZ"
COMMIT = "e8111fdb64c5587b33aece0fed639ed3d03375ac"
PATH = "002/bin/sense-global.mjs"
BRANCH = "experiment/fatherhand-grant-chain-residue-001"


def write(file: Path, obj: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf8")


def main() -> None:
    donor = Path(os.environ["BRANCH_DONOR_REPO"]).resolve(strict=True)
    actual = subprocess.check_output(
        ["git", "-C", str(donor), "show", COMMIT + ":" + PATH],
        timeout=12,
    )
    digest = hashlib.sha256(actual).hexdigest()
    context = {
        "repository": REPO, "commit": COMMIT, "path": PATH,
        "sha256": digest, "branchHint": BRANCH,
    }
    with tempfile.TemporaryDirectory(prefix="ghot-local-030-") as tmp:
        root = Path(tmp) / "ghot-home"
        file = root / "candidate.json"
        policy_file = root / "branch-worker" / "sources.json"
        candidate = {"schema": CANDIDATE_SCHEMA, "context": context}
        policy = {"schema": POLICY_SCHEMA, "entries": [{
            "context": context, "checkout_root": str(donor),
            "reviewed_for_local_read": True,
        }]}
        write(file, candidate)

        # No local owner review -> fail closed before ticket creation.
        assert preview(file, root=root)["status"] == "HOLD"
        write(policy_file, policy)
        held = copy.deepcopy(policy)
        held["entries"][0]["reviewed_for_local_read"] = False
        write(policy_file, held)
        assert preview(file, root=root)["status"] == "HOLD"
        write(policy_file, policy)

        p = preview(file, root=root)
        assert p["status"] == "READY", p
        assert p["execution_performed"] is False
        assert p["act_authorized"] is False
        assert p["preflight"]["network_read_performed"] is False
        assert p["preflight"]["executes"] is False
        expected = p["proposal_address"]
        assert expected.startswith("sha256:")

        # No shell, no URL, no unpinned source, no permission laundering.
        for replace in (
            {"commit": "main"},
            {"path": "../outside"},
            {"path": "/etc/passwd"},
            {"path": "ghot/reference_node.py;rm"},
            {"repository": "../evil"},
            {"sha256": "ffff"},
        ):
            changed = dict(context, **replace)
            try:
                validate_context(changed)
                if replace.get("sha256") == "ffff":
                    raise AssertionError("accepted unverified sha256")
                raise AssertionError("accepted invalid source identity")
            except ValueError:
                pass
        smuggled = copy.deepcopy(p["descriptor"])
        smuggled["destination"]["operation"] = "run-shell"
        from launch_descriptor import verify_launch_descriptor
        assert not verify_launch_descriptor(smuggled)

        # Explicit local ACT required; the exact proposal is mandatory.
        for phrase, address in (("YES", expected), ("ACT", "sha256:" + "0"*64)):
            try:
                act(file, expected=address, confirm=phrase, root=root)
                raise AssertionError("accepted wrong ACT or proposal")
            except ValueError:
                pass
        assert not (root / "activation-tickets" / "tickets").exists()

        # Synthetic CLI ACT in CI proves ceremony mechanics, not a human identity.
        result = act(file, expected=expected, confirm="ACT", root=root, ttl_seconds=120)
        assert result["verified_success"] is True, result
        assert result["activation_ticket_verified"] is True
        receipt = result["execution_receipt"]
        assert verify_execution_receipt(receipt)
        assert receipt["ticket_spent"] is True
        assert receipt["operation_attempted"] is True
        assert receipt["status"] == "EXECUTED"
        assert receipt["success"] is True
        assert result["operator_identity_proven"] is False
        assert result["remote_execution"] is False
        assert result["donor_program_executed"] is False
        job = result["job"]
        assert job["blob_sha256"] == digest
        assert job["size_bytes"] == len(actual)
        assert job["read_only_git"] is True
        assert job["remote_effects"] == 0
        assert job["branch_program_executed"] is False
        store = ActivationStore(root)
        ticket = store.load_ticket(result["ticket_id"])
        assert verify_activation_ticket(ticket)
        assert ticket["human_identity_proven"] is False
        assert ticket["destination"]["app_id"] == "branch-work"
        assert ticket["proposal_address"] == expected
        try:
            store.execute(result["ticket_id"])
            raise AssertionError("spent ticket replayed")
        except ValueError as exc:
            assert "spent" in str(exc)
        forged = copy.deepcopy(receipt)
        forged["success"] = False
        assert not verify_execution_receipt(forged)

        # The *same* context is no longer READY after policy removal.
        policy["entries"][0]["reviewed_for_local_read"] = False
        write(policy_file, policy)
        assert preview(file, root=root)["status"] == "HOLD"
        policy["entries"][0]["reviewed_for_local_read"] = True
        write(policy_file, policy)

        # Source-policy change after ticket issuance gets a *signed refusal*,
        # cannot dispatch, and consumes the one-use ticket.
        descriptor = make_descriptor(context)
        issued = store.issue(
            descriptor, consent_phrase="ACT", expected_proposal_address=expected
        )
        ticket_id = issued["ticket"]["ticket_id"]
        policy["entries"][0]["reviewed_for_local_read"] = False
        write(policy_file, policy)
        refused = store.execute(ticket_id)
        assert refused["receipt"]["status"] == "REFUSED_STALE"
        assert refused["receipt"]["operation_attempted"] is False
        assert refused["receipt"]["ticket_spent"] is True
        assert verify_execution_receipt(refused["receipt"])
        try:
            store.execute(ticket_id)
            raise AssertionError("refused ticket reused")
        except ValueError as exc:
            assert "spent" in str(exc)
        policy["entries"][0]["reviewed_for_local_read"] = True
        write(policy_file, policy)

        # Exact original-byte hash is mandatory even for locally allowed paths.
        wrong = dict(context, sha256="0"*64)
        write(file, {"schema": CANDIDATE_SCHEMA, "context": wrong})
        assert preview(file, root=root)["status"] == "HOLD"

        # Revoked or invalid Git origins cannot be reinterpreted as owner proof.
        bad = copy.deepcopy(policy)
        bad["entries"][0]["checkout_root"] = str(root)
        write(policy_file, bad)
        write(file, candidate)
        assert preview(file, root=root)["status"] == "HOLD"

        print(json.dumps({
            "schema": "ghot.branch-worker-simulation/v0",
            "test_candidate_commit": COMMIT,
            "source_sha256": digest,
            "verified_one_operation": True,
            "signed_activation_ticket": True,
            "signed_execution_receipt": True,
            "replay_refused": True,
            "post_consent_revalidation": "REFUSED_STALE",
            "source_and_policy_tamper": "HOLD",
            "donor_program_executed": False,
            "remote_effects": 0,
            "human_identity_proven": False,
        }, indent=2))


if __name__ == "__main__":
    main()
