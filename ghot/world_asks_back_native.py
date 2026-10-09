#!/usr/bin/env python3
"""WORLD-ASKS-BACK-002: native GHoT system.hash after native reLATTE R3 ADMIT.

Requires a local checkout of reLATTE containing scripts/wab-receiver.ts.
Fixture-only sovereign identities; actual local system.hash work, NO hardware.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# The existing GHoT reference_node package is organized for direct script imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import world_asks_back as wab
from relatte_identity import (
    IdentityKey, jcs_bytes, sign_crossing, sign_receipt, timestamp_now,
    verify_receipt,
)

NATIVE_DOMAIN = b"GHOT-WAB002-NATIVE-GRANT|"
NATIVE_SCOPES = {
    "household": "authorize-local-hash-of-my-proposal",
    "fabricator": "authorize-local-hash-compute",
    "stockist": "authorize-local-hash-of-stock-claim",
}
CAPABILITY = "system.hash"


def offer_address(offer: dict[str, Any]) -> str:
    return wab.digest(offer)


def current_hash_offer(body_fn) -> dict[str, Any]:
    record = body_fn()
    if not isinstance(record, dict):
        raise ValueError("CURRENT_BODY_INVALID")
    offers = record.get("offers")
    if not isinstance(offers, list):
        raise ValueError("NATIVE_OFFERS_ABSENT")
    selected = [o for o in offers if isinstance(o, dict) and o.get("capability") == CAPABILITY]
    if len(selected) != 1 or selected[0].get("available") is not True:
        raise ValueError("NATIVE_HASH_OFFER_WITHDRAWN_OR_AMBIGUOUS")
    limits = selected[0].get("limits")
    if not isinstance(limits, dict) or limits.get("remote_shell") is not False:
        raise ValueError("NATIVE_HASH_LIMITS_NOT_SAFE")
    return copy.deepcopy(selected[0])


def fixture(home: Path) -> tuple[dict, dict, dict]:
    home.mkdir(parents=True, exist_ok=True)
    keys = {r: IdentityKey.load_or_create(home / (r + ".pem")) for r in wab.ROLES}
    pinned = {r: keys[r].public_jwk() for r in wab.ROLES}
    states = {
        "household": {"asset": {"part": "hinge-a", "state": "missing"},
                      "fit": "hinge-a", "urgency": 2, "privacy": "local-only",
                      "acceptance": "fixture-geometry-check"},
        "fabricator": {"printer": "idle", "energy_units": 5, "designs": ["hinge-a"]},
        "stockist": {"stock": {"PLA": 30}, "sources": ["PLA-local"],
                     "routes": ["local-pickup"]},
    }
    claims = {r: wab.signed_claim(r, states[r], keys[r]) for r in wab.ROLES}
    proposal = wab.compose(claims, pinned)
    if proposal["status"] != "PROPOSED":
        raise AssertionError("fixture failed to produce candidate")
    return proposal, pinned, keys


def signed_native_crossing(proposal: dict, offer: dict, household_key: IdentityKey) -> dict:
    return sign_crossing({
        "schema": "relatte.crossing-envelope/v0",
        "protocol_version": "0",
        "source_particular": household_key.particular(),
        "source_world": "world:ghot:synthetic-household",
        "declared_kind": "ghot.wab-native-hash/v0",
        "payload_refs": [{"address": wab.digest(proposal), "role": "proposal"}],
        "requested_effect": {"action": "execute-bounded-hash", "scope": "local-compute-only"},
        "created_at": timestamp_now(),
        "extensions": {"world_asks_back_native": {
            "proposal_id": proposal["proposal_id"], "cut": proposal["cut"],
            "capability": CAPABILITY, "physical_execution": False,
            "offer_address": offer_address(offer),
            "nonce": uuid.uuid4().hex,
        }},
    }, household_key)


def native_grants(crossing: dict, proposal: dict, keys: dict) -> dict:
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=4)).isoformat()
    grants = {}
    for role in wab.ROLES:
        body = {
            "schema": "ghot.wab-native-grant/v0",
            "role": role, "proposal_id": proposal["proposal_id"],
            "cut": proposal["cut"], "crossing_id": crossing["crossing_id"],
            "offer_address": crossing["extensions"]["world_asks_back_native"]["offer_address"],
            "capability": CAPABILITY, "scope": NATIVE_SCOPES[role],
            "decision": "AUTHORIZE_LOCAL_HASH", "expires_at": expiry,
            "public_key": keys[role].public_jwk(),
        }
        grants[role] = {**body, "signature": keys[role].sign(NATIVE_DOMAIN + jcs_bytes(body))}
    return grants


def receiver_call(relatte: Path, request: dict) -> dict:
    script = relatte / "scripts" / "wab-receiver.ts"
    if not script.is_file():
        raise FileNotFoundError("NATIVE_RELATTE_WAB_BRIDGE_NOT_INSTALLED")
    completed = subprocess.run(
        ["node", "--experimental-strip-types", str(script)],
        cwd=relatte, input=json.dumps(request), text=True, capture_output=True,
        timeout=30, check=False,
    )
    if completed.returncode:
        raise RuntimeError("RELATTE_NATIVE_RECEIVER_DENIED: " + completed.stderr[-1200:])
    result = json.loads(completed.stdout)
    if result.get("schema") != "relatte.wab-native-result/v0":
        raise RuntimeError("WRONG_NATIVE_RECEIVER_RESPONSE")
    return result


def submit(relatte: Path, root: Path, proposal: dict, crossing: dict,
           grants: dict | None) -> dict:
    return receiver_call(relatte, {
        "schema": "relatte.wab-native-request/v0", "action": "submit",
        "receiver_root": str(root), "proposal": proposal, "crossing": crossing,
        "grants": grants,
        "received_at": timestamp_now(), "disposed_at": timestamp_now(),
    })


def validate_native_admission(result: dict, crossing: dict) -> None:
    if (result.get("status") != "ADMITTED_FOR_LOCAL_HASH"
            or result.get("approved") is not True
            or result.get("physical_execution") is not False
            or result.get("economic_credit") != 0):
        raise ValueError("NATIVE_HASH_NOT_ADMITTED")
    receive = result.get("receive_receipt")
    disposition = result.get("disposition_receipt")
    for record in (receive, disposition):
        if not isinstance(record, dict) or not verify_receipt(record):
            raise ValueError("NATIVE_SIGNED_RECEIPT_INVALID")
        if (record["crossing_id"] != crossing["crossing_id"]
                or record["world_id"] != "world:ghot:wab-native-hash"
                or record["receiver_particular"] != "particular:relatte:wab-native-hash"):
            raise ValueError("NATIVE_RECEIVER_CROSSING_MISMATCH")
    if (receive["kind"] != "RECEIVED" or receive["semantic_effect"] != "none"
            or disposition["kind"] != "R3_ADMIT"
            or disposition["semantic_effect"] != "local-state-change"
            or disposition.get("extensions", {}).get("local_receiver", {}).get("receive_receipt_id") != receive["receipt_id"]):
        raise ValueError("NATIVE_RECEIVER_NOT_ADMITTED")


def execute_authorized_hash(
    proposal: dict, crossing: dict, admitted: dict, frozen_offer: dict, *,
    body_fn, execute_fn, node_key: IdentityKey,
) -> dict:
    validate_native_admission(admitted, crossing)
    if current_hash_offer(body_fn) != frozen_offer:
        raise ValueError("NATIVE_OFFER_CHANGED_BEFORE_EXECUTION")
    if crossing["extensions"]["world_asks_back_native"]["offer_address"] != offer_address(frozen_offer):
        raise ValueError("NATIVE_CROSSING_STALE_OFFER")
    # This is the only real GHoT effect: hashing the exact canonical proposal
    # through reference_node.execute, not printing a physical part.
    raw = jcs_bytes(proposal).decode("utf-8")
    task, receipt = execute_fn(
        CAPABILITY, raw,
        constraints={"native_admit_receipt_id": admitted["disposition_receipt"]["receipt_id"],
                     "crossing_id": crossing["crossing_id"],
                     "network": "not-required", "physical_execution": False},
    )
    expected_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if (not isinstance(receipt, dict) or receipt.get("status") != "ok"
            or receipt.get("capability") != CAPABILITY
            or receipt.get("output") != {"sha256": expected_sha}
            or not isinstance(task, dict) or task.get("capability") != CAPABILITY):
        raise ValueError("NATIVE_GHOT_HASH_RECEIPT_MISMATCH")
    witness = sign_receipt({
        "schema": "relatte.receipt/v0",
        "crossing_id": crossing["crossing_id"],
        "world_id": "world:ghot:local-hash-witness",
        "receiver_particular": node_key.particular(),
        "kind": "EXECUTED", "semantic_effect": "artifact-created",
        "post_state_ref": "sha256:" + expected_sha,
        "created_at": timestamp_now(),
        "note": "native GHoT system.hash produced proposal digest, no physical work",
        "extensions": {"world_asks_back_native": {
            "native_receiver_admit": admitted["disposition_receipt"]["receipt_id"],
            "native_ghot_task_id": task["task_id"],
            "native_ghot_receipt_id": receipt["receipt_id"],
            "physical_execution": False, "economic_credit": 0,
        }},
    }, node_key)
    if not verify_receipt(witness):
        raise ValueError("NATIVE_EXECUTION_WITNESS_INVALID")
    return {"status": "NATIVE_LOCAL_HASH_EXECUTED", "native_execution": receipt,
            "execution_witness": witness, "crossing_id": crossing["crossing_id"],
            "physical_part_produced": False, "economic_credit": 0}


def demo(relatte: Path, *, approving: bool = True) -> dict:
    with tempfile.TemporaryDirectory(prefix="wab002-") as tmp:
        root = Path(tmp)
        # Keep GHoT's real local body/record store scoped to this disposable world.
        if "reference_node" in sys.modules:
            raise RuntimeError("GHOT_RUNTIME_ALREADY_IMPORTED")
        prior = os.environ.get("GHOT_HOME")
        os.environ["GHOT_HOME"] = str(root / "ghot-state")
        try:
            from reference_node import body, execute
            proposal, pinned, keys = fixture(root / "owners")
            offer = current_hash_offer(body)
            receiver_root = root / "native-r3-receiver"
            boot = receiver_call(relatte, {
                "schema": "relatte.wab-native-request/v0", "action": "init",
                "receiver_root": str(receiver_root), "trusted_pins": pinned,
                "proposal": proposal,
            })
            if boot["status"] != "POLICY_PINNED_LOCALLY":
                raise RuntimeError("RECEIVER_NOT_INITIALIZED")
            crossing = signed_native_crossing(proposal, offer, keys["household"])
            grants = native_grants(crossing, proposal, keys) if approving else {}
            admitted = submit(relatte, receiver_root, proposal, crossing, grants)
            if not approving:
                if (admitted["status"] != "HELD_NO_CONSENT"
                        or admitted["disposition_receipt"]["kind"] != "R3_HOLD"):
                    raise AssertionError("MISSING_GRANTS_DID_NOT_HOLD")
                return {"status": "HOLD", "receive_receipt": admitted["receive_receipt"],
                        "disposition_receipt": admitted["disposition_receipt"],
                        "execution": None}
            node_key = IdentityKey.load_or_create(root / "ghot-state" / "identity" / "body-p256.pem")
            executed = execute_authorized_hash(
                proposal, crossing, admitted, offer,
                body_fn=body, execute_fn=execute, node_key=node_key)
            return {"status": "NATIVE_LOCAL_HASH_EXECUTED",
                    "receiver_receive": admitted["receive_receipt"],
                    "receiver_admit": admitted["disposition_receipt"],
                    "result": executed, "proposal_id": proposal["proposal_id"],
                    "instrument_count": 11, "candidate_count": 11}
        finally:
            if prior is None: os.environ.pop("GHOT_HOME", None)
            else: os.environ["GHOT_HOME"] = prior


def main(args: list[str]) -> int:
    if len(args) != 3 or args[1] not in ("demo", "hold"):
        raise ValueError("usage: python3 ghot/world_asks_back_native.py demo|hold <relatte-repo-path>")
    result = demo(Path(args[2]).resolve(), approving=args[1] == "demo")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        raise SystemExit(1)
