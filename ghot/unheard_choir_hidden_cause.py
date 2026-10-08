#!/usr/bin/env python3
"""UNHEARD CHOIR 007: signed simulated provenance reveals a common upstream.

Locally pinned signatures attest only assertions about a *declared* graph.
Never infer world completeness, physical independence, or native authority.
"""
from __future__ import annotations
import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import Any
from unheard_choir import InvalidWorld, canonical, digest
from unheard_choir_lying_witness import ROLES, check_challenge, make_challenge, roster_for, sign_statement
from unheard_choir_collusion import make_anchor, signed_precommit, signed_measurement
from unheard_choir_counterfeit import assess as assess_006, make_pinset, sign_custody, sign_secondary
from relatte_identity import IdentityKey, IdentityProfileError, jcs_bytes, normalize_public_jwk, particular_for_public_key, verify_p256

M = "ghot.unheard-choir-007-manifest/v0"
N = "ghot.unheard-choir-007-node/v0"
R = "ghot.unheard-choir-007-result/v0"
MD = b"GHOT-CHOIR-007-MANIFEST-v0|"
ND = b"GHOT-CHOIR-007-NODE-v0|"
ID = re.compile(r"^fixture-[a-z0-9]+(?:-[a-z0-9]+)*$")


def exact(obj, keys, label):
    if type(obj) is not dict or set(obj) != set(keys):
        raise InvalidWorld(label + ": unknown or missing fields")


def valid_id(x):
    if type(x) is not str or len(x) > 64 or not ID.fullmatch(x):
        raise InvalidWorld("invalid simulated graph node ID")


def key(x):
    try:
        return normalize_public_jwk(x)
    except (ValueError, TypeError) as exc:
        raise InvalidWorld("invalid P-256 public key") from exc


def distinct(values):
    return len({particular_for_public_key(key(v)) for v in values}) == len(values)


def signed_manifest(parent, roster, challenge, pins, entries, owner):
    check_challenge(parent, roster, challenge, challenge["issued_at"])
    if key(owner.public_jwk()) != key(roster["owner_public_key"]):
        raise InvalidWorld("owner signing key is unpinned")
    if type(entries) is not list or not 1 <= len(entries) <= 32:
        raise InvalidWorld("manifest requires 1..32 entries")
    body = {"schema": M, "scope": "SIGNED_DECLARED_GRAPH_ONLY",
            "parent_digest": parent["proposal_digest"],
            "roster_digest": digest(roster), "challenge_digest": digest(challenge),
            "pinset_digest": digest(pins), "entries": entries}
    return {**body, "signature": owner.sign(MD + jcs_bytes(body))}


def verify_manifest(parent, roster, challenge, pins, manifest):
    exact(manifest, ("schema", "scope", "parent_digest", "roster_digest",
          "challenge_digest", "pinset_digest", "entries", "signature"), "manifest")
    if (manifest["schema"] != M or manifest["scope"] != "SIGNED_DECLARED_GRAPH_ONLY"
        or manifest["parent_digest"] != parent["proposal_digest"]
        or manifest["challenge_digest"] != digest(challenge)
        or manifest["roster_digest"] != digest(roster)
        or manifest["pinset_digest"] != digest(pins)):
        raise InvalidWorld("manifest stale or bound to other world, owner, epoch or instrument")
    entries = manifest["entries"]
    if type(entries) is not list or not 1 <= len(entries) <= 32:
        raise InvalidWorld("invalid manifest size")
    index = {}
    keys = [roster["owner_public_key"]]
    keys.extend(roster["actors"][role] for role in ROLES)
    for role in ("primary", "secondary"):
        p = pins["channels"][role]
        keys.extend((p["instrument_public_key"], p["custodian_public_key"]))
    for entry in entries:
        exact(entry, ("node_id", "epoch", "controller_public_key", "expected_parent_count"), "manifest entry")
        valid_id(entry["node_id"])
        if entry["node_id"] in index:
            raise InvalidWorld("duplicate manifest node")
        if type(entry["epoch"]) is not int or not 0 <= entry["epoch"] <= 999999:
            raise InvalidWorld("invalid graph incarnation")
        if type(entry["expected_parent_count"]) is not int or not 0 <= entry["expected_parent_count"] <= 32:
            raise InvalidWorld("invalid upstream count")
        index[entry["node_id"]] = entry
        keys.append(entry["controller_public_key"])
    if [e["node_id"] for e in entries] != sorted(index):
        raise InvalidWorld("manifest entries not deterministically sorted")
    if not distinct(keys):
        raise InvalidWorld("graph signer shares owner, claimant, sensor or another node identity")
    for channel in ("primary", "secondary"):
        for source in pins["channels"][channel]["dependency_roots"]:
            if source not in index:
                raise InvalidWorld("graph omits 006 channel entrypoint")
    unsigned = {k: v for k, v in manifest.items() if k != "signature"}
    if type(manifest["signature"]) is not str or not verify_p256(
        roster["owner_public_key"], MD + jcs_bytes(unsigned), manifest["signature"]
    ):
        raise InvalidWorld("invalid owner graph signature")
    return index


def attest(manifest, challenge, entry, parents, signer):
    if type(parents) is not list or len(parents) != entry["expected_parent_count"]:
        raise InvalidWorld("upstream attestation contradicts pinned count")
    for x in parents:
        valid_id(x)
    if parents != sorted(set(parents)):
        raise InvalidWorld("upstream edges must be unique and sorted")
    if key(signer.public_jwk()) != key(entry["controller_public_key"]):
        raise InvalidWorld("upstream controller not pinned")
    body = {"schema": N, "scope": "SIMULATED_UPSTREAM_ASSERTION_ONLY",
            "manifest_digest": digest(manifest), "challenge_digest": digest(challenge),
            "node_id": entry["node_id"], "epoch": entry["epoch"],
            "parents": list(parents), "asserted_fixture_complete": True}
    return {**body, "signature": signer.sign(ND + jcs_bytes(body))}


def verify_attestations(manifest, challenge, index, attestations):
    if type(attestations) is not list or len(attestations) > 32:
        raise InvalidWorld("invalid attestation count")
    graph = {}
    for item in attestations:
        exact(item, ("schema", "scope", "manifest_digest", "challenge_digest",
                    "node_id", "epoch", "parents", "asserted_fixture_complete", "signature"), "node attestation")
        node = item["node_id"]
        if type(node) is not str or node not in index or node in graph:
            raise InvalidWorld("duplicate or unknown signed node")
        ref = index[node]
        parents = item["parents"]
        if type(parents) is not list or len(parents) != ref["expected_parent_count"]:
            raise InvalidWorld("missing claimed upstream edges")
        for x in parents:
            valid_id(x)
            if x not in index:
                raise InvalidWorld("upstream outside signed owner roster")
        if parents != sorted(set(parents)):
            raise InvalidWorld("duplicate or unsorted upstream edges")
        if (item["schema"] != N or item["scope"] != "SIMULATED_UPSTREAM_ASSERTION_ONLY"
            or item["manifest_digest"] != digest(manifest)
            or item["challenge_digest"] != digest(challenge)
            or item["node_id"] != ref["node_id"] or item["epoch"] != ref["epoch"]
            or item["asserted_fixture_complete"] is not True):
            raise InvalidWorld("node attestation stale or falsely bound")
        unsigned = {k: v for k, v in item.items() if k != "signature"}
        if type(item["signature"]) is not str or not verify_p256(
            ref["controller_public_key"], ND + jcs_bytes(unsigned), item["signature"]
        ):
            raise InvalidWorld("node controller signature invalid")
        graph[node] = parents
    return graph, sorted(set(index) - set(graph))


def ancestors(graph, starts):
    visited, active = set(), set()
    def walk(node):
        if node in active:
            raise InvalidWorld("cycle in signed upstream claims")
        if node in visited:
            return
        if node not in graph:
            raise InvalidWorld("unattested upstream")
        active.add(node)
        for parent in graph[node]:
            walk(parent)
        active.remove(node)
        visited.add(node)
    for node in starts:
        walk(node)
    return sorted(visited)


def assess(parent, roster, challenge, statements, primary_anchor,
           primary_precommit, primary_measurement, pinset, primary_custody,
           secondary_custody, secondary_measurement, manifest, attestations, *, now):
    inherited = assess_006(parent, roster, challenge, statements, primary_anchor,
                           primary_precommit, primary_measurement, pinset,
                           primary_custody, secondary_custody, secondary_measurement, now=now)
    paths = {"primary": [], "secondary": []}
    shared, missing, count = [], [], 0
    if manifest is None and attestations is None:
        decision, manifest_hash = "HOLD_MISSING_SIGNED_GRAPH", None
    else:
        if manifest is None or attestations is None:
            raise InvalidWorld("partial graph cannot authorize inference")
        index = verify_manifest(parent, roster, challenge, pinset, manifest)
        graph, missing = verify_attestations(manifest, challenge, index, attestations)
        count = len(graph)
        manifest_hash = digest(manifest)
        if missing:
            decision = "HOLD_INCOMPLETE_SIGNED_PROVENANCE"
        else:
            for node in graph:
                ancestors(graph, [node])
            paths = {
                channel: ancestors(graph, pinset["channels"][channel]["dependency_roots"])
                for channel in ("primary", "secondary")
            }
            shared = sorted(set(paths["primary"]) & set(paths["secondary"]))
            if shared:
                decision = "HOLD_ATTESTED_HIDDEN_COMMON_CAUSE"
            elif inherited["decision"] != "REVIEW_DECLARED_DISTINCT_MODALITIES_CONCORDANT_NOT_ADMITTED":
                decision = "HOLD_006_PARENT_UNRESOLVED"
            else:
                decision = "REVIEW_DECLARED_DISJOINT_SIGNED_GRAPH_NOT_ADMITTED"
    result = {
        "schema": R, "parent_digest": parent["proposal_digest"],
        "challenge_digest": digest(challenge),
        "006_assessment_digest": inherited["assessment_digest"],
        "006_decision": inherited["decision"], "manifest_digest": manifest_hash,
        "signed_node_count": count, "missing_signed_nodes": missing,
        "traced_upstream": paths, "common_upstream_nodes": shared,
        "decision": decision,
        "declared_graph_exhausts_real_world": False,
        "physical_independence_proven": False,
        "hidden_unreported_common_cause_excluded": False,
        "signed_claim_is_truth": False, "native_relatte_admission": False,
        "external_execution": False, "authority": "NONE", "effects": [],
    }
    result["receipt_digest"] = digest(result)
    return result


def verify_replay(*args, now):
    if len(args) != 14:
        return False
    *sources, receipt = args
    try:
        return type(receipt) is dict and canonical(receipt) == canonical(assess(*sources, now=now))
    except (ValueError, KeyError, TypeError, IdentityProfileError):
        return False


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def example():
    from unheard_choir_false_aperture import propose
    root = Path(__file__).resolve().parents[1] / "fixtures"
    files = ("unheard-choir-002/observed-world.json", "unheard-choir-003/field.json",
             "unheard-choir-003/untrusted-catalog.json",
             "unheard-choir-003/owner-registry.json", "unheard-choir-003/reviewed-history.json")
    parent = propose(*(read(root / p) for p in files))
    with tempfile.TemporaryDirectory() as temp:
        node_upstream = {
            "fixture-primary": ["fixture-east"],
            "fixture-east": ["fixture-common"],
            "fixture-common": [],
            "fixture-west": ["fixture-common"],
            "fixture-secondary": ["fixture-west"],
        }
        names = list(ROLES) + ["owner", "primary-sensor", "primary-custodian",
                                "secondary-sensor", "secondary-custodian"] + list(node_upstream)
        keys = {name: IdentityKey.load_or_create(Path(temp) / (name + ".pem")) for name in names}
        roster = roster_for(parent, keys["owner"], {role: keys[role] for role in ROLES})
        challenge = make_challenge(parent, roster, keys["owner"], issued_at=1000, nonce="a" * 32)
        statements = [sign_statement(challenge, role, "PRESENT", keys[role]) for role in ROLES]
        anchor = make_anchor(parent, roster, keys["primary-sensor"])
        samples = [1] * 8
        commit = signed_precommit(parent, roster, anchor, keys["primary-sensor"],
                                  samples=samples, captured_at=900)
        primary = signed_measurement(challenge, commit, samples, keys["primary-sensor"])
        pins = make_pinset(parent, roster, challenge, anchor, keys["owner"],
                           keys["primary-custodian"], keys["secondary-custodian"],
                           keys["secondary-sensor"],
                           primary_roots=["fixture-primary"], secondary_roots=["fixture-secondary"])
        secondary = sign_secondary(pins, challenge, [200, 200] + [0] * 6, keys["secondary-sensor"])
        custody_primary = sign_custody(pins, challenge, "primary", digest(primary),
                                       keys["primary-custodian"], declared_acquired_at=1000)
        custody_secondary = sign_custody(pins, challenge, "secondary", digest(secondary),
                                         keys["secondary-custodian"], declared_acquired_at=1000)
        entries = [{"node_id": n, "epoch": 1, "controller_public_key": keys[n].public_jwk(),
                    "expected_parent_count": len(node_upstream[n])} for n in sorted(node_upstream)]
        manifest = signed_manifest(parent, roster, challenge, pins, entries, keys["owner"])
        attestations = [attest(manifest, challenge, entry, node_upstream[entry["node_id"]],
                               keys[entry["node_id"]]) for entry in entries]
        inputs = (parent, roster, challenge, statements, anchor, commit, primary,
                  pins, custody_primary, custody_secondary, secondary, manifest, attestations)
        return inputs


def demo():
    inputs = example()
    report = assess(*inputs, now=1001)
    return {"006_decision": report["006_decision"],
            "007_decision": report["decision"],
            "common_upstream_nodes": report["common_upstream_nodes"],
            "signed_graph_complete_for_fixture": not report["missing_signed_nodes"],
            "physical_truth_proven": report["signed_claim_is_truth"],
            "external_execution": report["external_execution"],
            "cold_replay_verified": verify_replay(*inputs, report, now=1001)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "assess", "verify"))
    fields = ("parent", "roster", "challenge", "statements", "primary_anchor",
              "primary_precommit", "primary_measurement", "pinset", "primary_custody",
              "secondary_custody", "secondary_measurement", "manifest", "attestations")
    for name in fields + ("receipt",):
        parser.add_argument("--" + name.replace("_", "-"), type=Path)
    parser.add_argument("--now", type=int)
    options = parser.parse_args()
    try:
        if options.command == "demo":
            output = demo()
        else:
            if any(getattr(options, f) is None for f in fields[:11]) or options.now is None:
                parser.error("assess and verify need 006 source files and --now")
            if (options.manifest is None) != (options.attestations is None):
                parser.error("both graph inputs or neither")
            arguments = [read(getattr(options, f)) for f in fields[:11]] + [
                read(options.manifest), read(options.attestations)
            ] if options.manifest else [read(getattr(options, f)) for f in fields[:11]] + [None, None]
            if options.command == "assess":
                output = assess(*arguments, now=options.now)
            else:
                if options.receipt is None:
                    parser.error("verify needs --receipt")
                output = {"verified": verify_replay(*arguments, read(options.receipt), now=options.now)}
    except (ValueError, OSError, TypeError, KeyError, IdentityProfileError) as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if options.command != "verify" or output["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
