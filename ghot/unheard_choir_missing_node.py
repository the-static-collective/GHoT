#!/usr/bin/env python3
"""UNHEARD CHOIR 008 — The Missing Node.

An externally pinned *test-local* audit root, distinct from the owner-controlled
007 graph, authorizes two differently keyed fictional trace reporters. Each
commits a trace digest and signs a graph-bound reveal. A signed 007 disjoint
graph can thereby be contradicted by signed reports of shared upstream nodes.

This does NOT prove the reports true, independent physical sensing, temporal
ordering, ownership, or completeness of the world. No native authority/effect.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, canonical, digest
from unheard_choir_hidden_cause import (
    assess as assess_007, signed_manifest, attest, valid_id,
)
from relatte_identity import IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk, particular_for_public_key, verify_p256
from unheard_choir_lying_witness import ROLES, make_challenge, roster_for, sign_statement
from unheard_choir_collusion import make_anchor, signed_precommit, signed_measurement
from unheard_choir_counterfeit import make_pinset, sign_custody, sign_secondary

P = "ghot.unheard-choir-008-audit-policy/v0"
C = "ghot.unheard-choir-008-precommit/v0"
W = "ghot.unheard-choir-008-trace-witness/v0"
R = "ghot.unheard-choir-008-assessment/v0"
PD = b"GHOT-CHOIR-008-EXTERNAL-ROOT-POLICY-v0|"
CD = b"GHOT-CHOIR-008-TRACE-COMMIT-v0|"
WD = b"GHOT-CHOIR-008-TRACE-REVEAL-v0|"
ROLES_008 = ("primary", "secondary")


def exact(value: Any, keys: tuple | set, where: str) -> None:
    if type(value) is not dict or set(value) != set(keys):
        raise InvalidWorld(f"{where}: missing or extra fields")


def jwk(value: Any) -> dict:
    try:
        return normalize_public_jwk(value)
    except (IdentityProfileError, ValueError, TypeError) as exc:
        raise InvalidWorld("invalid trust root or auditor P-256 key") from exc


def kid(value: Any) -> str:
    return particular_for_public_key(jwk(value))


def signed(body: dict, private: IdentityKey, domain: bytes) -> dict:
    return {**body, "signature": private.sign(domain + jcs_bytes(body))}


def check_signature(body: dict, signature: Any, public: dict, domain: bytes, label: str):
    if type(signature) is not str or not verify_p256(jwk(public), domain + jcs_bytes(body), signature):
        raise InvalidWorld(f"{label}: invalid P-256 signature")


def trace_shape(trace: Any) -> list[str]:
    if type(trace) is not list or not 1 <= len(trace) <= 32:
        raise InvalidWorld("audited path must contain 1..32 nodes")
    for node in trace:
        valid_id(node)
    if len(set(trace)) != len(trace):
        raise InvalidWorld("audit trace must be acyclic and have no duplicated nodes")
    return trace


def make_policy(parent: dict, challenge: dict, pins: dict, root: IdentityKey,
                auditors: dict[str, IdentityKey], *, epoch: int = 1) -> dict:
    if set(auditors) != set(ROLES_008) or type(epoch) is not int or not 0 <= epoch <= 999999:
        raise InvalidWorld("requires two bounded audit roles")
    body = {
        "schema": P, "scope": "EXTERNALLY_PINNED_LOCAL_SIMULATION_ONLY",
        "parent_proposal_digest": parent["proposal_digest"],
        "challenge_digest": digest(challenge),
        "pinset_digest": digest(pins),
        "epoch": epoch,
        "auditors": {r: auditors[r].public_jwk() for r in ROLES_008},
    }
    return signed(body, root, PD)


def verify_policy(parent: dict, roster: dict, challenge: dict, pins: dict,
                  manifest: dict, policy: Any, trusted_root: Any) -> None:
    exact(policy, ("schema", "scope", "parent_proposal_digest", "challenge_digest",
                   "pinset_digest", "epoch", "auditors", "signature"), "audit policy")
    exact(policy["auditors"], ROLES_008, "auditors")
    if (policy["schema"] != P or policy["scope"] != "EXTERNALLY_PINNED_LOCAL_SIMULATION_ONLY"
        or policy["parent_proposal_digest"] != parent["proposal_digest"]
        or policy["challenge_digest"] != digest(challenge)
        or policy["pinset_digest"] != digest(pins)):
        raise InvalidWorld("audit policy not bound to live 003/004/006 world")
    if type(policy["epoch"]) is not int or not 0 <= policy["epoch"] <= 999999:
        raise InvalidWorld("invalid audit policy epoch")
    keys = [trusted_root, roster["owner_public_key"]]
    keys += [roster["actors"][r] for r in ROLES]
    for channel in ROLES_008:
        keys += [pins["channels"][channel]["instrument_public_key"],
                 pins["channels"][channel]["custodian_public_key"],
                 policy["auditors"][channel]]
    keys += [e["controller_public_key"] for e in manifest["entries"]]
    if len({kid(x) for x in keys}) != len(keys):
        raise InvalidWorld("externally pinned root/auditors must differ from all graph signers")
    body = {k: v for k, v in policy.items() if k != "signature"}
    check_signature(body, policy["signature"], trusted_root, PD, "audit root")


def make_commit(policy: dict, challenge: dict, channel: str, trace: list[str],
                auditor: IdentityKey, *, claimed_collected_at: int = 900) -> dict:
    trace_shape(trace)
    if channel not in ROLES_008 or jwk(auditor.public_jwk()) != jwk(policy["auditors"][channel]):
        raise InvalidWorld("unrecognized auditor signer")
    if type(claimed_collected_at) is not int or not 1 <= claimed_collected_at < challenge["issued_at"]:
        raise InvalidWorld("declared sample capture time must precede challenge")
    body = {
        "schema": C, "scope": "SIGNED_CLAIMED_TRACE_COMMIT_NOT_TEMPORAL_PROOF",
        "policy_digest": digest(policy),
        "parent_proposal_digest": policy["parent_proposal_digest"],
        "channel": channel, "audit_epoch": policy["epoch"],
        "trace_digest": digest(trace),
        "claimed_collected_at": claimed_collected_at,
    }
    return signed(body, auditor, CD)


def make_report(policy: dict, challenge: dict, manifest: dict, channel: str,
                trace: list[str], commit: dict, auditor: IdentityKey) -> dict:
    trace_shape(trace)
    if channel not in ROLES_008 or jwk(auditor.public_jwk()) != jwk(policy["auditors"][channel]):
        raise InvalidWorld("unrecognized audit witness")
    if digest(trace) != commit["trace_digest"]:
        raise InvalidWorld("revealed trace does not match signed commitment")
    body = {
        "schema": W, "scope": "SIGNED_SIMULATED_TRACE_ASSERTION_ONLY",
        "policy_digest": digest(policy),
        "challenge_digest": digest(challenge),
        "manifest_digest": digest(manifest),
        "channel": channel, "audit_epoch": policy["epoch"],
        "commit_digest": digest(commit),
        "trace": list(trace),
    }
    return signed(body, auditor, WD)


def check_commit(policy: dict, challenge: dict, channel: str, commitment: Any):
    exact(commitment, ("schema", "scope", "policy_digest", "parent_proposal_digest",
                       "channel", "audit_epoch", "trace_digest", "claimed_collected_at",
                       "signature"), "audit commitment")
    if (commitment["schema"] != C
        or commitment["scope"] != "SIGNED_CLAIMED_TRACE_COMMIT_NOT_TEMPORAL_PROOF"
        or commitment["policy_digest"] != digest(policy)
        or commitment["parent_proposal_digest"] != policy["parent_proposal_digest"]
        or commitment["channel"] != channel or commitment["audit_epoch"] != policy["epoch"]):
        raise InvalidWorld("stale commitment, channel or policy")
    when = commitment["claimed_collected_at"]
    if type(when) is not int or not 1 <= when < challenge["issued_at"]:
        raise InvalidWorld("commit declared time outside range (not independently witnessed)")
    if type(commitment["trace_digest"]) is not str or len(commitment["trace_digest"]) != 64 or any(
        x not in "0123456789abcdef" for x in commitment["trace_digest"]
    ):
        raise InvalidWorld("invalid trace digest")
    body = {k: v for k, v in commitment.items() if k != "signature"}
    check_signature(body, commitment["signature"], policy["auditors"][channel], CD, "auditor commit")


def check_report(policy: dict, challenge: dict, manifest: dict, channel: str,
                 commit: dict, report: Any, expected_start: str) -> list[str]:
    exact(report, ("schema", "scope", "policy_digest", "challenge_digest",
                   "manifest_digest", "channel", "audit_epoch", "commit_digest",
                   "trace", "signature"), "audit trace report")
    trace = trace_shape(report["trace"])
    if (report["schema"] != W or report["scope"] != "SIGNED_SIMULATED_TRACE_ASSERTION_ONLY"
        or report["policy_digest"] != digest(policy)
        or report["challenge_digest"] != digest(challenge)
        or report["manifest_digest"] != digest(manifest)
        or report["channel"] != channel
        or report["audit_epoch"] != policy["epoch"]
        or report["commit_digest"] != digest(commit)
        or digest(trace) != commit["trace_digest"]
        or trace[0] != expected_start):
        raise InvalidWorld("auditor path not bound to committed source, challenge and graph")
    body = {k: v for k, v in report.items() if k != "signature"}
    check_signature(body, report["signature"], policy["auditors"][channel], WD, "auditor witness")
    return trace


def witness_collection(entries: Any, label: str) -> dict[str, dict]:
    if type(entries) is not list or len(entries) > 2:
        raise InvalidWorld(label + ": expected at most two signed objects")
    found = {}
    for item in entries:
        if type(item) is not dict or type(item.get("channel")) is not str:
            raise InvalidWorld("invalid auditor object")
        channel = item["channel"]
        if channel not in ROLES_008 or channel in found:
            raise InvalidWorld("duplicate or unknown audit channel")
        found[channel] = item
    return found


def assess(parent, roster, challenge, statements, primary_anchor,
           primary_precommit, primary_measurement, pinset, primary_custody,
           secondary_custody, secondary_measurement, manifest, attestations,
           audit_policy, audit_commits, audit_reports, trusted_root, *, now):
    earlier = assess_007(
        parent, roster, challenge, statements, primary_anchor, primary_precommit,
        primary_measurement, pinset, primary_custody, secondary_custody,
        secondary_measurement, manifest, attestations, now=now,
    )
    traces, absent, discrepancies, overlap = {}, [], [], []
    if all(x is None for x in (audit_policy, audit_commits, audit_reports, trusted_root)):
        decision = "HOLD_NO_INDEPENDENTLY_PINNED_AUDIT"
        policy_hash = None
    else:
        if any(x is None for x in (audit_policy, audit_commits, audit_reports, trusted_root)):
            raise InvalidWorld("partial audit evidence or local root pin")
        verify_policy(parent, roster, challenge, pinset, manifest, audit_policy, trusted_root)
        commits = witness_collection(audit_commits, "audit commitments")
        reports = witness_collection(audit_reports, "audit reports")
        policy_hash = digest(audit_policy)
        for channel in ROLES_008:
            commit, report = commits.get(channel), reports.get(channel)
            if commit is None or report is None:
                absent.append(channel)
                continue
            check_commit(audit_policy, challenge, channel, commit)
            roots = pinset["channels"][channel]["dependency_roots"]
            if len(roots) != 1:
                raise InvalidWorld("008 toy audit profile requires exactly one channel root")
            traces[channel] = check_report(
                audit_policy, challenge, manifest, channel, commit, report, roots[0]
            )
        if absent:
            decision = "HOLD_MISSING_INDEPENDENT_AUDIT_CHANNEL"
        else:
            overlap = sorted(set(traces["primary"]) & set(traces["secondary"]))
            graph = {node["node_id"]: node["parents"] for node in attestations}
            for channel in ROLES_008:
                for i, node in enumerate(traces[channel]):
                    if node not in graph:
                        discrepancies.append({"channel": channel, "node": node, "difference": "UNLISTED_NODE"})
                    elif i + 1 < len(traces[channel]) and traces[channel][i + 1] not in graph[node]:
                        discrepancies.append({"channel": channel, "node": node, "difference": "UNDECLARED_EDGE"})
                    elif i + 1 == len(traces[channel]) and graph[node]:
                        discrepancies.append({"channel": channel, "node": node, "difference": "UNREPORTED_DECLARED_PARENTS"})
            if overlap or discrepancies:
                decision = "HOLD_EXTERNAL_AUDIT_CONTRADICTS_OWNER_GRAPH"
            elif earlier["decision"] != "REVIEW_DECLARED_DISJOINT_SIGNED_GRAPH_NOT_ADMITTED":
                decision = "HOLD_INHERITED_007_RESTRICTION"
            else:
                decision = "REVIEW_AUDIT_TRACES_MATCH_DECLARED_GRAPH_NOT_ADMITTED"
    result = {
        "schema": R, "007_assessment_digest": earlier["receipt_digest"],
        "007_decision": earlier["decision"], "challenge_digest": digest(challenge),
        "external_audit_policy_digest": policy_hash,
        "audited_traces": traces, "missing_audit_channels": absent,
        "shared_nodes_claimed_by_auditors": overlap,
        "signed_graph_conflicts": discrepancies, "decision": decision,
        "external_root_pinned_in_local_fixture": policy_hash is not None,
        "audit_claims_physically_verified": False,
        "commit_timestamps_independently_proven": False,
        "undeclared_common_causes_excluded": False,
        "external_execution": False, "authority": "NONE", "effects": [],
        "note": "Contradictory authenticated trace *claims* force HOLD, not factual proof.",
    }
    result["receipt_digest"] = digest(result)
    return result


def verify_replay(*args, now):
    if len(args) != 18:
        return False
    *sources, expected = args
    try:
        return type(expected) is dict and canonical(expected) == canonical(assess(*sources, now=now))
    except (ValueError, KeyError, TypeError, IdentityProfileError):
        return False


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_fixture(graph=None, traces=None):
    """Returns synthetic evidence and temporary keys; caller retains tmp handle."""
    from unheard_choir_false_aperture import propose
    root = Path(__file__).resolve().parents[1] / "fixtures"
    refs = ("unheard-choir-002/observed-world.json", "unheard-choir-003/field.json",
            "unheard-choir-003/untrusted-catalog.json", "unheard-choir-003/owner-registry.json",
            "unheard-choir-003/reviewed-history.json")
    parent = propose(*(load(root / n) for n in refs))
    graph = graph or {
        "fixture-primary": ["fixture-east"], "fixture-east": ["fixture-root-a"],
        "fixture-root-a": [], "fixture-secondary": ["fixture-west"],
        "fixture-west": ["fixture-root-b"], "fixture-root-b": [],
    }
    traces = traces or {
        "primary": ["fixture-primary", "fixture-east", "fixture-hidden"],
        "secondary": ["fixture-secondary", "fixture-west", "fixture-hidden"],
    }
    tmp = tempfile.TemporaryDirectory()
    roles = set(ROLES) | {
        "owner", "primary-sensor", "secondary-sensor", "primary-custodian",
        "secondary-custodian", "external-root", "external-primary", "external-secondary",
    } | set(graph)
    keys = {n: IdentityKey.load_or_create(Path(tmp.name) / (n + ".pem")) for n in sorted(roles)}
    roster = roster_for(parent, keys["owner"], {r: keys[r] for r in ROLES})
    challenge = make_challenge(parent, roster, keys["owner"], issued_at=1000, nonce="a" * 32)
    claims = [sign_statement(challenge, r, "PRESENT", keys[r]) for r in ROLES]
    anchor = make_anchor(parent, roster, keys["primary-sensor"])
    samples = [1] * 8
    precommit = signed_precommit(parent, roster, anchor, keys["primary-sensor"],
                                 samples=samples, captured_at=900)
    primary = signed_measurement(challenge, precommit, samples, keys["primary-sensor"])
    pins = make_pinset(parent, roster, challenge, anchor, keys["owner"],
                       keys["primary-custodian"], keys["secondary-custodian"],
                       keys["secondary-sensor"],
                       primary_roots=["fixture-primary"],
                       secondary_roots=["fixture-secondary"])
    secondary = sign_secondary(pins, challenge, [200, 200] + [0] * 6, keys["secondary-sensor"])
    custody_a = sign_custody(pins, challenge, "primary", digest(primary),
                             keys["primary-custodian"], declared_acquired_at=1000)
    custody_b = sign_custody(pins, challenge, "secondary", digest(secondary),
                             keys["secondary-custodian"], declared_acquired_at=1000)
    entries = [{"node_id": n, "epoch": 1, "controller_public_key": keys[n].public_jwk(),
                "expected_parent_count": len(graph[n])} for n in sorted(graph)]
    # External root belongs to separate local trust config, never the owner's 007 manifest.
    policy = make_policy(parent, challenge, pins, keys["external-root"], {
        "primary": keys["external-primary"], "secondary": keys["external-secondary"]})
    commits = [make_commit(policy, challenge, channel, traces[channel],
                           keys["external-" + channel], claimed_collected_at=900)
               for channel in ROLES_008]
    manifest = signed_manifest(parent, roster, challenge, pins, entries, keys["owner"])
    attestations = [attest(manifest, challenge, entry, graph[entry["node_id"]],
                           keys[entry["node_id"]]) for entry in entries]
    reports = [make_report(policy, challenge, manifest, role, traces[role],
                           commits[i], keys["external-" + role])
               for i, role in enumerate(ROLES_008)]
    arguments = [parent, roster, challenge, claims, anchor, precommit, primary,
                 pins, custody_a, custody_b, secondary, manifest, attestations,
                 policy, commits, reports, keys["external-root"].public_jwk()]
    return tmp, arguments, keys


def demo():
    tmp, arguments, _ = build_fixture()
    try:
        report = assess(*arguments, now=1001)
        return {
            "007_decision": report["007_decision"],
            "008_decision": report["decision"],
            "auditor_claimed_hidden_node": report["shared_nodes_claimed_by_auditors"],
            "signed_graph_conflict_count": len(report["signed_graph_conflicts"]),
            "physical_truth_proven": report["audit_claims_physically_verified"],
            "external_execution": report["external_execution"],
            "cold_replay_verified": verify_replay(*arguments, report, now=1001),
        }
    finally:
        tmp.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "verify"))
    names = ("parent", "roster", "challenge", "statements", "primary_anchor",
             "primary_precommit", "primary_measurement", "pinset",
             "primary_custody", "secondary_custody", "secondary_measurement",
             "manifest", "attestations", "audit_policy", "audit_commits",
             "audit_reports", "trusted_root")
    for n in names + ("receipt",):
        parser.add_argument("--" + n.replace("_", "-"), type=Path)
    parser.add_argument("--now", type=int)
    opts = parser.parse_args()
    try:
        if opts.command == "demo":
            output = demo()
        else:
            if any(getattr(opts, n) is None for n in names[:13]) or opts.now is None:
                parser.error("assess/verify need signed 007 inputs and --now")
            remaining = [getattr(opts, n) for n in names[13:]]
            if sum(v is not None for v in remaining) not in (0, 4):
                parser.error("provide all external audit inputs or none")
            args = [load(getattr(opts, n)) for n in names[:13]]
            args += [load(p) for p in remaining] if all(remaining) else [None] * 4
            if opts.command == "assess":
                output = assess(*args, now=opts.now)
            else:
                if opts.receipt is None:
                    parser.error("verify also needs --receipt")
                output = {"verified": verify_replay(*args, load(opts.receipt), now=opts.now)}
    except (ValueError, KeyError, OSError, TypeError, IdentityProfileError) as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if opts.command != "verify" or output["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
