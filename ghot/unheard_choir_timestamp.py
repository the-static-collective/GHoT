#!/usr/bin/env python3
"""UNHEARD CHOIR 009 — The Timestamp That Lied.

A separate simulated transparency-log authority, sequencer and two co-witnesses
attest to the ordering of published artifact submissions. Forks and assertions
of prior publication *in this log* are detectable. The signed log does not
establish sample-collection time, real wall-clock timestamps, fact truth,
independent humans, or any native GHoT/reLATTE power.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from unheard_choir import InvalidWorld, canonical, digest
from unheard_choir_missing_node import assess as assess_008, build_fixture
from relatte_identity import (
    IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk,
    particular_for_public_key, verify_p256,
)

P = "ghot.unheard-choir-009-log-policy/v0"
S = "ghot.unheard-choir-009-submission/v0"
E = "ghot.unheard-choir-009-entry/v0"
C = "ghot.unheard-choir-009-checkpoint/v0"
R = "ghot.unheard-choir-009-review/v0"
PD = b"GHOT-CHOIR-009-POLICY-v0|"
SD = b"GHOT-CHOIR-009-SUBMISSION-v0|"
QD = b"GHOT-CHOIR-009-SEQUENCER-v0|"
WD = b"GHOT-CHOIR-009-WITNESS-v0|"
GENESIS = digest({"domain": "ghot.unheard-choir-009-genesis/v0"})
EVENTS = (
    "owner-challenge", "owner-manifest", "audit-commit-primary",
    "audit-commit-secondary", "audit-reveal-primary", "audit-reveal-secondary",
)
HEX = re.compile(r"^[0-9a-f]{64}$")


def exact(obj: Any, keys: Any, label: str):
    if type(obj) is not dict or set(obj) != set(keys):
        raise InvalidWorld(f"{label}: unknown or missing fields")


def key(raw: Any) -> dict:
    try:
        return normalize_public_jwk(raw)
    except (IdentityProfileError, ValueError, TypeError) as exc:
        raise InvalidWorld("malformed pinned P-256 key") from exc


def identities(keys: list) -> set:
    return {particular_for_public_key(key(x)) for x in keys}


def check_sig(body: dict, signature: Any, public: dict, domain: bytes, label: str):
    if type(signature) is not str or not verify_p256(key(public), domain + jcs_bytes(body), signature):
        raise InvalidWorld(label + ": invalid P-256 signature")


def sign(keypair: IdentityKey, body: dict, domain: bytes) -> str:
    return keypair.sign(domain + jcs_bytes(body))


def signed_artifacts(args: list) -> dict:
    # Inherited 008 already verifies all 001–008 object signatures and roles.
    parent, roster, challenge, _, _, _, _, _, _, _, _, manifest, _, audit_policy, commits, reports, _ = args
    maps = [
        {item["channel"]: item for item in commits},
        {item["channel"]: item for item in reports},
    ]
    return {
        "owner-challenge": (challenge, roster["owner_public_key"]),
        "owner-manifest": (manifest, roster["owner_public_key"]),
        "audit-commit-primary": (maps[0]["primary"], audit_policy["auditors"]["primary"]),
        "audit-commit-secondary": (maps[0]["secondary"], audit_policy["auditors"]["secondary"]),
        "audit-reveal-primary": (maps[1]["primary"], audit_policy["auditors"]["primary"]),
        "audit-reveal-secondary": (maps[1]["secondary"], audit_policy["auditors"]["secondary"]),
    }


def make_policy(args: list, root: IdentityKey, seq: IdentityKey,
                witness_a: IdentityKey, witness_b: IdentityKey,
                *, epoch: int = 1) -> dict:
    if type(epoch) is not int or not 0 <= epoch <= 999999:
        raise InvalidWorld("invalid log epoch")
    parent, roster, challenge, _, anchor, _, _, pins, _, _, _, manifest, _, ap, _, _, audit_root = args
    keys = [roster["owner_public_key"], audit_root]
    keys += [roster["actors"][x] for x in ("source", "observer-east", "observer-west")]
    keys += [ap["auditors"][x] for x in ("primary", "secondary")]
    for channel in ("primary", "secondary"):
        p = pins["channels"][channel]
        keys.extend((p["instrument_public_key"], p["custodian_public_key"]))
    keys += [e["controller_public_key"] for e in manifest["entries"]]
    extras = [root.public_jwk(), seq.public_jwk(), witness_a.public_jwk(), witness_b.public_jwk()]
    if len(identities(keys + extras)) != len(keys) + len(extras):
        raise InvalidWorld("log trust root and witnesses must be distinct from all inherited roles")
    body = {
        "schema": P, "scope": "OWNER_INDEPENDENT_SIMULATED_LOG_ONLY",
        "008_assessment_cut": digest({"parent": parent["proposal_digest"],
                                     "challenge": digest(challenge),
                                     "manifest": digest(manifest),
                                     "audit_policy": digest(ap)}),
        "epoch": epoch,
        "sequencer_public_key": seq.public_jwk(),
        "witnesses": {"a": witness_a.public_jwk(), "b": witness_b.public_jwk()},
    }
    return {**body, "signature": sign(root, body, PD)}


def verify_policy(args: list, policy: Any, trusted_root: Any):
    exact(policy, ("schema", "scope", "008_assessment_cut", "epoch",
                   "sequencer_public_key", "witnesses", "signature"), "log policy")
    exact(policy["witnesses"], ("a", "b"), "log witness pins")
    if (policy["schema"] != P or policy["scope"] != "OWNER_INDEPENDENT_SIMULATED_LOG_ONLY"
        or type(policy["epoch"]) is not int
        or not 0 <= policy["epoch"] <= 999999):
        raise InvalidWorld("unsupported log policy")
    parent, _, challenge, _, _, _, _, _, _, _, _, manifest, _, ap, _, _, _ = args
    cut = digest({"parent": parent["proposal_digest"],
                  "challenge": digest(challenge),
                  "manifest": digest(manifest), "audit_policy": digest(ap)})
    if policy["008_assessment_cut"] != cut:
        raise InvalidWorld("log belongs to stale 008 evidence cut")
    owner_roles = [args[1]["owner_public_key"], args[16]]
    owner_roles += list(args[1]["actors"].values())
    owner_roles += list(args[13]["auditors"].values())
    owner_roles += [p["controller_public_key"] for p in args[11]["entries"]]
    for c in ("primary", "secondary"):
        owner_roles += [args[7]["channels"][c]["instrument_public_key"],
                        args[7]["channels"][c]["custodian_public_key"]]
    pins = [trusted_root, policy["sequencer_public_key"]] + list(policy["witnesses"].values())
    if len(identities(owner_roles + pins)) != len(owner_roles) + len(pins):
        raise InvalidWorld("log trust roots or checkpoints reuse inherited identities")
    body = {k: v for k, v in policy.items() if k != "signature"}
    check_sig(body, policy["signature"], trusted_root, PD, "separate log root")


def make_submission(artifacts: dict, event_id: str, signer: IdentityKey,
                    *, claimed_prior_to: str | None = None) -> dict:
    if event_id not in EVENTS or claimed_prior_to not in (None,) + EVENTS:
        raise InvalidWorld("unsupported event name or publication assertion")
    artifact, public_key = artifacts[event_id]
    if key(signer.public_jwk()) != key(public_key):
        raise InvalidWorld("source actor cannot impersonate a signed artifact's owner")
    body = {
        "schema": S, "event_id": event_id, "artifact_digest": digest(artifact),
        "claimed_prior_to_in_this_log": claimed_prior_to,
        "scope": "SIMULATED_PUBLICATION_CLAIM_ONLY",
    }
    return {**body, "signature": sign(signer, body, SD)}


def verify_submission(artifacts: dict, submission: Any):
    exact(submission, ("schema", "event_id", "artifact_digest",
                       "claimed_prior_to_in_this_log", "scope", "signature"), "submission")
    event_id = submission["event_id"]
    if type(event_id) is not str or event_id not in EVENTS:
        raise InvalidWorld("unknown publication event")
    if (submission["schema"] != S or submission["scope"] != "SIMULATED_PUBLICATION_CLAIM_ONLY"
        or submission["artifact_digest"] != digest(artifacts[event_id][0])
        or submission["claimed_prior_to_in_this_log"] not in (None,) + EVENTS):
        raise InvalidWorld("wrong signer/event/claim cut")
    body = {k: v for k, v in submission.items() if k != "signature"}
    check_sig(body, submission["signature"], artifacts[event_id][1], SD, "source actor")


def entry_head(index: int, previous: str, submission: dict) -> str:
    return digest({"domain": E, "index": index, "previous": previous, "submission": submission})


def append_entries(submissions: list) -> list:
    if type(submissions) is not list or len(submissions) > len(EVENTS):
        raise InvalidWorld("log exceeds bounded six-event fixture")
    prior, entries = GENESIS, []
    for i, sub in enumerate(submissions):
        head = entry_head(i, prior, sub)
        entries.append({"schema": E, "index": i, "prev_head": prior,
                        "submission": sub, "head": head})
        prior = head
    return entries


def verify_entries(entries: Any, artifacts: dict) -> tuple[list[str], dict]:
    if type(entries) is not list or len(entries) > len(EVENTS):
        raise InvalidWorld("invalid append-only log size")
    heads, indices, seen = [GENESIS], {}, set()
    for i, entry in enumerate(entries):
        exact(entry, ("schema", "index", "prev_head", "submission", "head"), "log entry")
        if entry["schema"] != E or type(entry["index"]) is not int or entry["index"] != i:
            raise InvalidWorld("out-of-order log slot or non-contiguous index")
        sub = entry["submission"]
        verify_submission(artifacts, sub)
        name = sub["event_id"]
        if name in seen:
            raise InvalidWorld("duplicate publication event")
        seen.add(name)
        prior = heads[-1]
        if entry["prev_head"] != prior or entry["head"] != entry_head(i, prior, sub):
            raise InvalidWorld("altered append-only history")
        heads.append(entry["head"])
        indices[name] = i
    return heads, indices


def make_checkpoint(policy: dict, size: int, head: str, seq: IdentityKey,
                    a: IdentityKey, b: IdentityKey) -> dict:
    if (type(size) is not int or not 1 <= size <= len(EVENTS)
        or type(head) is not str or not HEX.fullmatch(head)):
        raise InvalidWorld("invalid checkpoint size or head")
    if (key(seq.public_jwk()) != key(policy["sequencer_public_key"])
        or key(a.public_jwk()) != key(policy["witnesses"]["a"])
        or key(b.public_jwk()) != key(policy["witnesses"]["b"])):
        raise InvalidWorld("unauthorized checkpoint co-signature")
    body = {"schema": C, "scope": "MULTIPARTY_SIMULATED_APPEND_CHECKPOINT",
            "policy_digest": digest(policy), "epoch": policy["epoch"],
            "size": size, "head": head}
    return {**body, "sequencer_signature": sign(seq, body, QD),
            "witness_signatures": {"a": sign(a, body, WD),
                                   "b": sign(b, body, WD)}}


def verify_checkpoint(policy: dict, checkpoint: Any):
    exact(checkpoint, ("schema", "scope", "policy_digest", "epoch",
                       "size", "head", "sequencer_signature", "witness_signatures"), "checkpoint")
    exact(checkpoint["witness_signatures"], ("a", "b"), "checkpoint witness signatures")
    if (checkpoint["schema"] != C
        or checkpoint["scope"] != "MULTIPARTY_SIMULATED_APPEND_CHECKPOINT"
        or checkpoint["policy_digest"] != digest(policy)
        or checkpoint["epoch"] != policy["epoch"]
        or type(checkpoint["size"]) is not int
        or not 1 <= checkpoint["size"] <= len(EVENTS)
        or type(checkpoint["head"]) is not str or not HEX.fullmatch(checkpoint["head"])):
        raise InvalidWorld("wrong checkpoint scope, size, epoch or policy")
    body = {k: checkpoint[k] for k in ("schema", "scope", "policy_digest",
                                       "epoch", "size", "head")}
    check_sig(body, checkpoint["sequencer_signature"],
              policy["sequencer_public_key"], QD, "sequencer")
    for role in ("a", "b"):
        check_sig(body, checkpoint["witness_signatures"][role],
                  policy["witnesses"][role], WD, "independent co-witness")


def assess(parent, roster, challenge, statements, primary_anchor,
           primary_precommit, primary_measurement, pinset, primary_custody,
           secondary_custody, secondary_measurement, manifest, attestations,
           audit_policy, audit_commits, audit_reports, trusted_root,
           log_policy, log_root, log_entries, checkpoints, *, now):
    inherited = [parent, roster, challenge, statements, primary_anchor,
                 primary_precommit, primary_measurement, pinset, primary_custody,
                 secondary_custody, secondary_measurement, manifest, attestations,
                 audit_policy, audit_commits, audit_reports, trusted_root]
    earlier = assess_008(*inherited, now=now)
    conflicts, forks, missing = [], [], []
    policy_hash, sizes = None, []
    if all(x is None for x in (log_policy, log_root, log_entries, checkpoints)):
        decision = "HOLD_NO_WITNESSED_TRANSPARENCY_LOG"
    else:
        if any(x is None for x in (log_policy, log_root, log_entries, checkpoints)):
            raise InvalidWorld("partial transparency-log evidence")
        verify_policy(inherited, log_policy, log_root)
        policy_hash = digest(log_policy)
        heads, positions = verify_entries(log_entries, signed_artifacts(inherited))
        missing = sorted(set(EVENTS) - set(positions))
        if type(checkpoints) is not list or not 1 <= len(checkpoints) <= 12:
            raise InvalidWorld("one to twelve signed checkpoints required")
        by_size = {}
        witnessed_tip = False
        for checkpoint in checkpoints:
            verify_checkpoint(log_policy, checkpoint)
            size, head = checkpoint["size"], checkpoint["head"]
            sizes.append(size)
            by_size.setdefault(size, set()).add(head)
            if size == len(log_entries) and head == heads[size]:
                witnessed_tip = True
        forks = sorted(size for size, values in by_size.items() if len(values) > 1)
        # One co-signed head can be entirely alien to the offered log.
        inconsistent = sorted({cp["size"] for cp in checkpoints
                               if cp["size"] > len(log_entries)
                               or cp["head"] != heads[cp["size"]]})
        for entry in log_entries:
            sub = entry["submission"]
            earlier_than = sub["claimed_prior_to_in_this_log"]
            if earlier_than is not None and earlier_than in positions:
                if not positions[sub["event_id"]] < positions[earlier_than]:
                    conflicts.append({
                        "event_id": sub["event_id"],
                        "claims_prior_to": earlier_than,
                        "actual_order": [positions[sub["event_id"]], positions[earlier_than]],
                    })
        if forks:
            decision = "HOLD_MULTIPARTY_WITNESSED_LOG_FORK"
        elif inconsistent:
            decision = "HOLD_SIGNED_CHECKPOINT_INCONSISTENT_WITH_LOG"
        elif missing or not witnessed_tip:
            decision = "HOLD_INCOMPLETE_WITNESSED_LOG_COVERAGE"
        elif conflicts:
            decision = "HOLD_SIGNED_PUBLICATION_ORDER_CLAIM_CONTRADICTED"
        elif earlier["decision"] != "REVIEW_AUDIT_TRACES_MATCH_DECLARED_GRAPH_NOT_ADMITTED":
            decision = "HOLD_INHERITED_008_EVIDENCE_CONTRADICTION"
        else:
            decision = "REVIEW_WITNESSED_LOG_ORDER_NOT_ADMITTED"
    report = {
        "schema": R, "008_assessment_digest": earlier["receipt_digest"],
        "008_decision": earlier["decision"], "log_policy_digest": policy_hash,
        "log_size": len(log_entries) if type(log_entries) is list else 0,
        "checkpoint_sizes": sizes, "forked_checkpoint_sizes": forks,
        "missing_publication_events": missing,
        "contradicted_publication_claims": conflicts,
        "decision": decision,
        "log_order_is_wall_clock_time": False,
        "sample_captured_at_claim_verified": False,
        "external_witness_keys_are_independent_humans": False,
        "physical_truth_proven": False,
        "native_relatte_admission": False, "external_execution": False,
        "authority": "NONE", "effects": [],
        "note": "Co-signed log publication order is not proof of data capture time, sensor truth or signer independence.",
    }
    report["receipt_digest"] = digest(report)
    return report


def verify_replay(*args, now):
    if len(args) != 22:
        return False
    *source, receipt = args
    try:
        return type(receipt) is dict and canonical(receipt) == canonical(assess(*source, now=now))
    except (ValueError, TypeError, KeyError, IdentityProfileError):
        return False


def build_fixture_for_tests(*, earlier_audit_matches=False, log_order_lie=True,
                            fork=False):
    if earlier_audit_matches:
        traces = {"primary": ["fixture-primary", "fixture-east", "fixture-root-a"],
                  "secondary": ["fixture-secondary", "fixture-west", "fixture-root-b"]}
        tmp, args, keys = build_fixture(traces=traces)
    else:
        tmp, args, keys = build_fixture()
    root = Path(tmp.name)
    for name in ("log-root", "log-sequencer", "log-witness-a", "log-witness-b"):
        keys[name] = IdentityKey.load_or_create(root / (name + ".pem"))
    policy = make_policy(args, keys["log-root"], keys["log-sequencer"],
                         keys["log-witness-a"], keys["log-witness-b"])
    artifacts = signed_artifacts(args)
    actor = {"owner-challenge": "owner", "owner-manifest": "owner",
             "audit-commit-primary": "external-primary",
             "audit-commit-secondary": "external-secondary",
             "audit-reveal-primary": "external-primary",
             "audit-reveal-secondary": "external-secondary"}
    publications = [
        make_submission(artifacts, event_id, keys[actor[event_id]],
                        claimed_prior_to="owner-challenge"
                        if log_order_lie and event_id.startswith("audit-commit")
                        else None)
        for event_id in EVENTS
    ]
    events = append_entries(publications)
    cp = make_checkpoint(policy, len(events), events[-1]["head"],
                         keys["log-sequencer"], keys["log-witness-a"],
                         keys["log-witness-b"])
    checkpoints = [cp]
    if fork:
        another = append_entries(publications[:-1])
        # Same size, different signed history (simulated collusion of all log keys).
        changed = dict(publications[-1])
        changed["claimed_prior_to_in_this_log"] = "owner-challenge"
        changed_body = {k: v for k, v in changed.items() if k != "signature"}
        changed["signature"] = sign(keys[actor[EVENTS[-1]]], changed_body, SD)
        forked = append_entries(publications[:-1] + [changed])
        checkpoints.append(make_checkpoint(policy, len(forked), forked[-1]["head"],
                           keys["log-sequencer"], keys["log-witness-a"],
                           keys["log-witness-b"]))
    return tmp, args + [policy, keys["log-root"].public_jwk(), events, checkpoints], keys


def demo():
    tmp, args, _ = build_fixture_for_tests()
    try:
        r = assess(*args, now=1001)
        return {
            "008_decision": r["008_decision"], "009_decision": r["decision"],
            "disputed_publication_claims": len(r["contradicted_publication_claims"]),
            "witnessed_log_size": r["log_size"],
            "forked_checkpoint_sizes": r["forked_checkpoint_sizes"],
            "physically_proven_capture_time": r["sample_captured_at_claim_verified"],
            "external_execution": r["external_execution"],
            "cold_replay_verified": verify_replay(*args, r, now=1001),
        }
    finally:
        tmp.cleanup()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "verify"))
    names = ("parent", "roster", "challenge", "statements",
             "primary_anchor", "primary_precommit", "primary_measurement", "pinset",
             "primary_custody", "secondary_custody", "secondary_measurement",
             "manifest", "attestations", "audit_policy", "audit_commits",
             "audit_reports", "trusted_root",
             "log_policy", "log_root", "log_entries", "checkpoints")
    for name in names + ("receipt",):
        parser.add_argument("--" + name.replace("_", "-"), type=Path)
    parser.add_argument("--now", type=int)
    opts = parser.parse_args()
    try:
        if opts.command == "demo":
            result = demo()
        else:
            if any(getattr(opts, x) is None for x in names[:17]) or opts.now is None:
                parser.error("assess/verify require 008 evidence files and --now")
            rest = [getattr(opts, n) for n in names[17:]]
            if sum(x is not None for x in rest) not in (0, 4):
                parser.error("all log fields or none")
            source = [read(getattr(opts, x)) for x in names[:17]]
            source += [read(x) for x in rest] if all(rest) else [None] * 4
            if opts.command == "assess":
                result = assess(*source, now=opts.now)
            else:
                if opts.receipt is None:
                    parser.error("verify requires --receipt")
                result = {"verified": verify_replay(*source, read(opts.receipt), now=opts.now)}
    except (ValueError, TypeError, KeyError, OSError, IdentityProfileError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if opts.command != "verify" or result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
