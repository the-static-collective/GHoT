"""RADIO HOUSE 003 — two sovereign local key/state roots; native signed reLATTE
crossing and receipt, but NO live network transport or remote operator identity.

A narrow public-text hashing job crosses by deliberate offline JSON courier.
Receiving operator's 002 media/power/capability gates remain authoritative.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ghot.radio_house_002 import (CAPABILITY, MAX_INPUT, CHUNK, _atomic, _event,
                                  connect, enable, observe_media, offer,
                                  tick, verify as verify_worker, digest)
PROTOCOL = "ghot.radio-house-signed-work/v0"
PAYLOAD_SCHEMA = "ghot.radio-house-public-hash-input/v0"
CROSSING_SCHEMA = "relatte.crossing-envelope/v0"
RECEIPT_SCHEMA = "relatte.receipt/v0"
JOB_PREFIX = "rh3-"

# resolved direct imports from GHoT's existing native reLATTE P-256 implementation
from ghot.relatte_identity import (
    IdentityKey, jcs_bytes, particular_for_public_key, sign_crossing,
    sign_receipt, timestamp_ms, verify_crossing, verify_receipt,
)


def require(ok, code):
    if not ok:
        raise ValueError(code)


def fields(obj, expected):
    return type(obj) is dict and set(obj) == set(expected)


def valid_id(value):
    return type(value) is str and 1 <= len(value) <= 58 and value[0].islower() and all(
        c.islower() or c.isdigit() or c == "-" for c in value)


def validate_payload(payload):
    require(fields(payload, {"schema", "job_id", "text", "capability"}), "PAYLOAD_FIELDS_INVALID")
    require(payload["schema"] == PAYLOAD_SCHEMA and payload["capability"] == CAPABILITY
            and valid_id(payload["job_id"]), "PAYLOAD_CAPABILITY_OR_ID_INVALID")
    require(type(payload["text"]) is str and payload["text"].isascii()
            and 0 < len(payload["text"].encode("utf8")) <= MAX_INPUT,
            "PAYLOAD_MUST_BE_BOUNDED_PUBLIC_ASCII")
    return payload


def make_bundle(requester_key, worker_public, job_id, text, *, at, lifetime=120):
    require(type(at) is int and 0 < at < 100_000_000_000, "ISSUED_TIME_INVALID")
    require(type(lifetime) is int and 1 <= lifetime <= 900, "LIFETIME_INVALID")
    worker_particular = particular_for_public_key(worker_public)
    payload = validate_payload({"schema": PAYLOAD_SCHEMA, "capability": CAPABILITY,
                                "job_id": job_id, "text": text})
    body = {
        "schema": CROSSING_SCHEMA, "crossing_id": "",
        "protocol_version": "0", "source_particular": requester_key.particular(),
        "source_world": "world:ghot:radio-house-requester",
        "source_history_head": digest(jcs_bytes(payload)),
        "parents": [], "declared_kind": "RADIO_HOUSE_PUBLIC_HASH_003",
        "payload_refs": [{"address": digest(jcs_bytes(payload)),
                          "role": "public-hash-job", "media_type": "application/json"}],
        "requested_effect": {"action": "REQUEST_PUBLIC_HASH",
                             "job_id": job_id,
                             "worker_particular": worker_particular},
        "capability_ref": CAPABILITY,
        "privacy_policy": {"public_payload_only": True, "encryption": False,
                           "transport": "manual-offline-courier-lab"},
        "audience_policy": {"intended_worker_particular": worker_particular},
        "return_address": None, "created_at": timestamp_ms(at),
        "extensions": {"radio_house_profile": PROTOCOL, "expires_epoch": at+lifetime,
                       "issued_epoch": at, "external_authority_granted": False},
        "signing": {"algorithm": "", "public_key": {}, "signature": "", "domain": ""},
    }
    crossing = sign_crossing(body, requester_key)
    require(verify_crossing(crossing), "LOCAL_CROSSING_SIGNATURE_FAILED")
    return {"schema": "ghot.radio-house-bundle/v0", "crossing": crossing, "payload": payload}


def verify_bundle(bundle, *, pinned_requester_public, expected_worker_public, at):
    require(fields(bundle, {"schema", "crossing", "payload"})
            and bundle["schema"] == "ghot.radio-house-bundle/v0", "BUNDLE_FIELDS_INVALID")
    c, p = bundle["crossing"], validate_payload(bundle["payload"])
    require(verify_crossing(c), "CROSSING_SIGNATURE_INVALID")
    require(c["signing"]["public_key"] == pinned_requester_public, "REQUESTER_PIN_MISMATCH")
    require(c["source_particular"] == particular_for_public_key(pinned_requester_public),
            "REQUESTER_IDENTITY_MISMATCH")
    require(c["schema"] == CROSSING_SCHEMA and c["protocol_version"] == "0"
            and c["source_world"] == "world:ghot:radio-house-requester"
            and c["declared_kind"] == "RADIO_HOUSE_PUBLIC_HASH_003"
            and c["capability_ref"] == CAPABILITY, "CROSSING_PROFILE_INVALID")
    expected_worker = particular_for_public_key(expected_worker_public)
    require(fields(c["requested_effect"], {"action", "job_id", "worker_particular"}) and
            c["requested_effect"] == {
                "action": "REQUEST_PUBLIC_HASH", "job_id": p["job_id"],
                "worker_particular": expected_worker}, "WRONG_WORKER_OR_ACTION")
    require(c["audience_policy"] == {"intended_worker_particular": expected_worker},
            "WRONG_INTENDED_AUDIENCE")
    require(c["privacy_policy"] == {"public_payload_only": True, "encryption": False,
                                   "transport": "manual-offline-courier-lab"},
            "PRIVACY_PROFILE_MISMATCH")
    require(c["payload_refs"] == [{
        "address": digest(jcs_bytes(p)), "role": "public-hash-job",
        "media_type": "application/json"}], "PAYLOAD_HASH_OR_ROLE_MISMATCH")
    require(c["source_history_head"] == digest(jcs_bytes(p)) and
            c["parents"] == [] and c["return_address"] is None,
            "SOURCE_HISTORY_MISMATCH")
    require(fields(c["extensions"], {"radio_house_profile", "expires_epoch",
                                    "issued_epoch", "external_authority_granted"})
            and c["extensions"]["radio_house_profile"] == PROTOCOL
            and c["extensions"]["external_authority_granted"] is False,
            "EXTENSION_PROFILE_INVALID")
    issued = c["extensions"]["issued_epoch"]
    expiry = c["extensions"]["expires_epoch"]
    require(type(at) is int and type(issued) is int and type(expiry) is int and
            0 < issued <= at <= expiry and expiry - issued <= 900 and
            c["created_at"] == timestamp_ms(issued), "CROSSING_EXPIRED_OR_NOT_YET_VALID")
    return c["crossing_id"]


def _ledger(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS radio_house_003 (
        crossing_id TEXT PRIMARY KEY,
        payload_digest TEXT NOT NULL,
        input_job_id TEXT NOT NULL,
        worker_job_id TEXT NOT NULL UNIQUE,
        owner_admission_receipt TEXT NOT NULL,
        finished_receipt TEXT
    )""")


def _receipt(crossing_id, signer, *, kind, effect, job_id, payload_digest,
             result_sha256=None, checkpoint_hash=None, at):
    body = {
        "schema": RECEIPT_SCHEMA, "receipt_id": "", "crossing_id": crossing_id,
        "world_id": "world:ghot:rock-radio-node-lab",
        "receiver_particular": signer.particular(),
        "kind": kind, "semantic_effect": effect,
        "contract_ref": PROTOCOL, "pre_state_ref": payload_digest,
        "post_state_ref": result_sha256,
        "descendant_refs": ([result_sha256] if result_sha256 else []),
        "residual_refs": ([] if result_sha256 else [job_id]),
        "note": "Local 002 bounded public hash; separate operator controls; not air/monetization",
        "created_at": timestamp_ms(at),
        "extensions": {"radio_house_profile": PROTOCOL, "worker_job_id": job_id,
                       "result_sha256": result_sha256,
                       "audit_checkpoint_hash": checkpoint_hash,
                       "owner_decision": "EXPLICIT_SIMULATED_LOCAL_APPROVAL",
                       "radio_or_media_effect": "NONE",
                       "remote_transport": "OFFLINE_MANUAL_COURIER"},
        "signing": {"algorithm": "", "public_key": {}, "signature": "", "domain": ""},
    }
    return sign_receipt(body, signer)


def accept(conn, bundle, *, receiver_key, pinned_requester_public, power,
           operator_approved=False, at):
    """Native valid signed source is NOT admission: local idle, power, explicit
    human choice and namespace collision are checked in one SQLite transaction.
    """
    crossing_id = verify_bundle(bundle,
        pinned_requester_public=pinned_requester_public,
        expected_worker_public=receiver_key.public_jwk(), at=at)
    require(type(operator_approved) is bool, "LOCAL_DECISION_INVALID")
    payload = bundle["payload"]
    worker_id = JOB_PREFIX + crossing_id.split(":")[-1][:40]
    payload_sha = digest(jcs_bytes(payload))
    def op():
        _ledger(conn)
        old = conn.execute("SELECT * FROM radio_house_003 WHERE crossing_id=?",
                           (crossing_id,)).fetchone()
        if old:
            require(old["payload_digest"] == payload_sha and old["worker_job_id"] == worker_id,
                    "REPLAY_CONFLICT")
            return json.loads(old["owner_admission_receipt"])
        require(operator_approved, "LOCAL_OPERATOR_APPROVAL_MISSING")
        gate = offer(conn, power, at=at)
        require(gate["status"] == "OFFER_LOCAL_BOUNDED_ONLY", "LOCAL_MEDIA_OR_POWER_HOLD")
        require(conn.execute("SELECT 1 FROM jobs WHERE job_id=?", (worker_id,)).fetchone()
                is None, "WORKER_JOB_COLLISION")
        conn.execute(
            "INSERT INTO jobs(job_id,capability,input_text,input_digest,operator_approved)"
            " VALUES(?,?,?,?,1)",
            (worker_id, CAPABILITY, payload["text"], digest(payload["text"].encode("utf8"))),
        )
        receipt = _receipt(crossing_id, receiver_key, kind="HELD", effect="local-state-change",
                           job_id=worker_id, payload_digest=payload_sha, at=at)
        conn.execute(
            "INSERT INTO radio_house_003(crossing_id,payload_digest,input_job_id,"
            "worker_job_id,owner_admission_receipt) VALUES(?,?,?,?,?)",
            (crossing_id, payload_sha, payload["job_id"], worker_id,
             json.dumps(receipt, sort_keys=True)),
        )
        _event(conn, "RADIO_HOUSE_003_LOCAL_ADMISSION",
               {"crossing_id": crossing_id, "worker_job_id": worker_id,
                "receipt_id": receipt["receipt_id"]})
        return receipt
    return _atomic(conn, op)


def advance(conn, bundle, *, receiver_key, pinned_requester_public, power, at):
    crossing_id = verify_bundle(bundle, pinned_requester_public=pinned_requester_public,
                                expected_worker_public=receiver_key.public_jwk(), at=at)
    _ledger(conn)
    row = conn.execute("SELECT worker_job_id FROM radio_house_003 WHERE crossing_id=?",
                       (crossing_id,)).fetchone()
    require(row is not None, "NOT_LOCALLY_ADMITTED")
    return tick(conn, row["worker_job_id"], power, at=at)


def settle(conn, bundle, *, receiver_key, pinned_requester_public, at):
    crossing_id = verify_bundle(bundle, pinned_requester_public=pinned_requester_public,
                                expected_worker_public=receiver_key.public_jwk(), at=at)
    def op():
        _ledger(conn)
        row = conn.execute("SELECT * FROM radio_house_003 WHERE crossing_id=?",
                           (crossing_id,)).fetchone()
        require(row is not None, "NOT_LOCALLY_ADMITTED")
        if row["finished_receipt"]:
            return json.loads(row["finished_receipt"])
        worker = conn.execute("SELECT * FROM jobs WHERE job_id=?",
                              (row["worker_job_id"],)).fetchone()
        require(worker is not None, "LOCAL_WORKER_JOB_MISSING")
        require(worker["status"] == "COMPLETE", "WORK_NOT_COMPLETE")
        # 002's independent checkpoint and exact local source cold verification.
        verify_worker(conn)
        final_hash = digest(worker["input_text"].encode("utf8"))
        require(worker["result_digest"] == final_hash, "WORKER_RESULT_MISMATCH")
        checkpoint = conn.execute(
            "SELECT event_hash FROM events WHERE kind='WORK_CHECKPOINT'"
            " ORDER BY seq DESC LIMIT 1").fetchone()
        require(checkpoint is not None, "CHECKPOINT_NOT_FOUND")
        receipt = _receipt(crossing_id, receiver_key, kind="EXECUTED",
                           effect="artifact-created", job_id=row["worker_job_id"],
                           payload_digest=row["payload_digest"],
                           result_sha256=final_hash, checkpoint_hash=checkpoint["event_hash"], at=at)
        conn.execute("UPDATE radio_house_003 SET finished_receipt=? WHERE crossing_id=?",
                     (json.dumps(receipt, sort_keys=True), crossing_id))
        _event(conn, "RADIO_HOUSE_003_RESULT_SEALED",
               {"crossing_id": crossing_id, "receipt_id": receipt["receipt_id"],
                "result_digest": final_hash})
        return receipt
    return _atomic(conn, op)


def verify_return(bundle, admission, final, *, pinned_requester_public,
                  pinned_worker_public, at):
    crossing_id = verify_bundle(bundle, pinned_requester_public=pinned_requester_public,
                                expected_worker_public=pinned_worker_public, at=at)
    worker_particular = particular_for_public_key(pinned_worker_public)
    for receipt, kind in ((admission, "HELD"), (final, "EXECUTED")):
        require(verify_receipt(receipt, expected_public_key=pinned_worker_public,
                               expected_receiver_particular=worker_particular),
                "WORKER_RECEIPT_SIGNATURE_OR_PIN_INVALID")
        require(receipt["crossing_id"] == crossing_id and receipt["kind"] == kind and
                receipt["contract_ref"] == PROTOCOL and
                receipt["extensions"]["radio_house_profile"] == PROTOCOL and
                receipt["extensions"]["radio_or_media_effect"] == "NONE",
                "RECEIPT_CONTEXT_MISMATCH")
    p = bundle["payload"]
    worker_id = JOB_PREFIX + crossing_id.split(":")[-1][:40]
    expected = digest(p["text"].encode("utf8"))
    require(admission["extensions"]["worker_job_id"] == worker_id and
            final["extensions"]["worker_job_id"] == worker_id and
            admission["pre_state_ref"] == digest(jcs_bytes(p)) and
            final["pre_state_ref"] == digest(jcs_bytes(p)),
            "RECEIPT_INPUT_BINDING_MISMATCH")
    require(final["semantic_effect"] == "artifact-created" and
            final["post_state_ref"] == expected and
            final["extensions"]["result_sha256"] == expected and
            final["extensions"]["audit_checkpoint_hash"], "RESULT_NOT_REPRODUCED")
    return {"status": "SIGNED_CROSSING_AND_LOCAL_HASH_RETURN_VERIFIED",
            "crossing_id": crossing_id, "worker_particular": worker_particular,
            "result_sha256": expected, "actual_media_actions": 0,
            "transport": "OFFLINE_MANUAL_COURIER", "external_authority": "NONE"}


def demo(root):
    """Two independent local identities / durable states; courier via JSON file."""
    from ghot.radio_house_002 import favorable_lab_power
    root = Path(root)
    require(not root.exists(), "DEMO_REQUIRES_NEW_ROOT")
    sender, rock = root / "requester", root / "rock-node"
    sender.mkdir(parents=True, mode=0o700)
    rock.mkdir(parents=True, mode=0o700)
    requester_key = IdentityKey.load_or_create(sender / "identity" / "requester-p256.pem")
    receiver_key = IdentityKey.load_or_create(rock / "identity" / "receiver-p256.pem")
    bundle = make_bundle(requester_key, receiver_key.public_jwk(),
                         "public-hash-001", "synthetic public useful work. " * 45,
                         at=1000)
    # Deliberate source-owned file courier; there is no network service.
    courier = sender / "courier.json"
    courier.write_text(json.dumps(bundle, sort_keys=True), encoding="utf8")
    restored = json.loads(courier.read_text(encoding="utf8"))
    conn = connect(rock)
    power = favorable_lab_power()
    enable(conn, True)
    observe_media(conn, "IDLE_CONFIRMED", at=1001)
    admission = accept(conn, restored, receiver_key=receiver_key,
                       pinned_requester_public=requester_key.public_jwk(),
                       power=power, operator_approved=True, at=1001)
    first = advance(conn, restored, receiver_key=receiver_key,
                    pinned_requester_public=requester_key.public_jwk(),
                    power=power, at=1001)
    observe_media(conn, "RECORDING", at=1002)
    during = advance(conn, restored, receiver_key=receiver_key,
                     pinned_requester_public=requester_key.public_jwk(),
                     power=power, at=1002)
    observe_media(conn, "IDLE_CONFIRMED", at=1003)
    last = None
    for _ in range(100):
        last = advance(conn, restored, receiver_key=receiver_key,
                       pinned_requester_public=requester_key.public_jwk(),
                       power=power, at=1003)
        if last["status"] == "COMPLETE":
            break
    require(last is not None and last["status"] == "COMPLETE", "LAB_NOT_FINISHED")
    final = settle(conn, restored, receiver_key=receiver_key,
                   pinned_requester_public=requester_key.public_jwk(), at=1003)
    cold = verify_worker(conn)
    conn.close()
    review = verify_return(restored, admission, final,
                           pinned_requester_public=requester_key.public_jwk(),
                           pinned_worker_public=receiver_key.public_jwk(), at=1004)
    return {"status": review["status"], "source_receipt": admission["receipt_id"],
            "work_receipt": final["receipt_id"],
            "media_interruption": during["status"],
            "compute_during_recording_bytes": during["work_done_bytes"],
            "compute_resumed_at_cursor": first["cursor"],
            "final_compute": last["status"], "cold": cold["status"],
            "courier": "OFFLINE_MANUAL_COURIER",
            "live_network_calls": 0, "media_broadcasts": 0, "donated_work_claim": False}


if __name__ == "__main__":
    import sys
    require(len(sys.argv) == 3 and sys.argv[1] == "demo", "USAGE: demo NEW_ROOT")
    print(json.dumps(demo(sys.argv[2]), indent=2, sort_keys=True))
