"""RADIO HOUSE 001: offline, synthetic, review-only media spool for two sovereign bodies.
No network, OBS, music distribution, real grants, organizational identity, or broadcasts.
Run: python3 -m ghot.radio_house_001 demo /tmp/radio-house-001
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

SCHEMA = "ghot.radio-house-001/v0"
RECEIPT = "ghot.radio-house-receipt/v0"
FRAME_BYTES = 32
FIELDS = {"schema", "packet_id", "owner_node", "recipient_node", "form",
          "payload_sha256", "byte_length", "rights_reference", "scope", "withdrawn"}
NODE_FIELDS = {"node", "caps", "state"}
SCOPE = "PRIVATE_STATION_REVIEW"
HASH = "sha256:"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def digest(data: bytes) -> str:
    return HASH + hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def make_packet(payload: bytes, *, packet_id="synthetic-psalm-001",
                owner_node="rock-nigeria", recipient_node="kinship-minnesota",
                rights_reference="LAB-NO-REAL-RIGHTS", form="podcast-draft"):
    require(isinstance(payload, bytes), "PAYLOAD_MUST_BE_BYTES")
    require(len(payload) > 0 and len(payload) <= 1_000_000, "INVALID_PAYLOAD_SIZE")
    p = {"schema": SCHEMA, "packet_id": packet_id, "owner_node": owner_node,
         "recipient_node": recipient_node, "form": form,
         "payload_sha256": digest(payload), "byte_length": len(payload),
         "rights_reference": rights_reference, "scope": SCOPE, "withdrawn": False}
    validate_packet(p)
    return p


def validate_packet(packet):
    require(type(packet) is dict and set(packet) == FIELDS, "PACKET_FIELDS_INVALID")
    require(packet["schema"] == SCHEMA and packet["scope"] == SCOPE, "SCOPE_INVALID")
    for field in ("packet_id", "owner_node", "recipient_node"):
        s = packet[field]
        require(type(s) is str and 1 <= len(s) <= 64 and
                all(c.islower() or c.isdigit() or c == "-" for c in s) and
                s[0].islower(), "IDENTIFIER_INVALID")
    require(packet["owner_node"] != packet["recipient_node"], "SEPARATE_BODIES_REQUIRED")
    require(packet["form"] in ("podcast-draft", "local-service-recording", "audio-postcard"),
            "FORM_INVALID")
    require(type(packet["payload_sha256"]) is str and packet["payload_sha256"].startswith(HASH)
            and len(packet["payload_sha256"]) == 71 and
            all(c in "0123456789abcdef" for c in packet["payload_sha256"][7:]),
            "DIGEST_INVALID")
    require(type(packet["byte_length"]) is int and 1 <= packet["byte_length"] <= 1_000_000,
            "BYTE_LENGTH_INVALID")
    require(type(packet["rights_reference"]) is str and
            1 <= len(packet["rights_reference"]) <= 120,
            "RIGHTS_REFERENCE_REQUIRED")
    require(type(packet["withdrawn"]) is bool, "WITHDRAWAL_INVALID")
    return packet


def validate_node(node):
    require(type(node) is dict and set(node) == NODE_FIELDS, "NODE_FIELDS_INVALID")
    require(type(node["node"]) is str and node["node"] and type(node["caps"]) is list and
            len(node["caps"]) <= 16 and all(type(x) is str for x in node["caps"]),
            "NODE_INVALID")
    require(node["state"] in ("awake", "offline", "conserve"), "NODE_STATE_INVALID")
    return node


def evaluate(packet, source_node, recipient_node, *,
             source_operator_selected=False, recipient_operator_invited=False,
             local_budget_bytes=None):
    """Claims represent test operator inputs, not independently authenticated people."""
    validate_packet(packet)
    validate_node(source_node)
    validate_node(recipient_node)
    require(type(source_operator_selected) is bool and type(recipient_operator_invited) is bool,
            "OPERATOR_SELECTION_INVALID")
    require(local_budget_bytes is None or
            (type(local_budget_bytes) is int and 0 <= local_budget_bytes <= 10_000_000),
            "BUDGET_INVALID")
    reasons = []
    if packet["withdrawn"]:
        reasons.append("SOURCE_WITHDRAWN")
    if packet["owner_node"] != source_node["node"] or packet["recipient_node"] != recipient_node["node"]:
        reasons.append("NODE_IDENTITY_MISMATCH")
    if "media.record-local" not in source_node["caps"]:
        reasons.append("SOURCE_CAPABILITY_ABSENT")
    if "media.receive-review" not in recipient_node["caps"]:
        reasons.append("RECEIVER_CAPABILITY_ABSENT")
    if not source_operator_selected:
        reasons.append("SOURCE_OWNER_SELECTION_ABSENT")
    if not recipient_operator_invited:
        reasons.append("RECIPIENT_INVITATION_ABSENT")
    if source_node["state"] != "awake" or recipient_node["state"] != "awake":
        reasons.append("NODE_NOT_AWAKE")
    # Input budget is per-transfer, not a grant to publish.
    if local_budget_bytes is not None and local_budget_bytes < FRAME_BYTES:
        reasons.append("LOCAL_DATA_BUDGET_TOO_LOW")
    return {
        "schema": "ghot.radio-house-gate/v0",
        "status": "READY_FOR_OFFLINE_REVIEW_SPOOL" if not reasons else "HOLD",
        "reasons": reasons,
        "source_operator_selection_authenticated": False,
        "recipient_station_invitation_authenticated": False,
        "station_air_authorized": False,
        "podcast_published": False,
        "stream_started": False,
        "source_media_custody": "OWNER_LOCAL",
    }


def _packet_directory(out_dir, packet):
    root = Path(out_dir)
    require(not root.is_symlink(), "OUTPUT_SYMLINK_DENIED")
    return root / (packet["packet_id"] + "-" + packet["payload_sha256"][7:23])


def spool(packet, payload, out_dir, *, source_node, recipient_node,
          source_operator_selected=False, recipient_operator_invited=False,
          max_new_chunks=None, local_budget_bytes=None):
    """Synthetic local-disk delivery. No sockets. On interruption call again with same inputs."""
    gate = evaluate(packet, source_node, recipient_node,
                    source_operator_selected=source_operator_selected,
                    recipient_operator_invited=recipient_operator_invited,
                    local_budget_bytes=local_budget_bytes)
    require(isinstance(payload, bytes) and len(payload) == packet["byte_length"]
            and digest(payload) == packet["payload_sha256"], "SOURCE_BYTES_MISMATCH")
    if gate["status"] == "HOLD":
        return {"status": "HOLD", "gate": gate, "chunks_written": 0, "chunks_total": 0}
    require(max_new_chunks is None or
            (type(max_new_chunks) is int and 0 <= max_new_chunks <= 10_000), "LIMIT_INVALID")
    location = _packet_directory(out_dir, packet)
    chunks_dir = location / "chunks"
    require(not location.is_symlink() and not chunks_dir.is_symlink(), "SYMLINK_DENIED")
    location.mkdir(parents=True, exist_ok=True, mode=0o700)
    chunks_dir.mkdir(exist_ok=True, mode=0o700)
    packet_bytes = (canonical(packet) + "\n").encode("utf8")
    manifest = location / "packet.json"
    if manifest.exists():
        require(not manifest.is_symlink() and manifest.read_bytes() == packet_bytes,
                "EXISTING_PACKET_TAMPERED")
    else:
        # Never rewrite an already-present packet manifest.
        with manifest.open("xb") as f:
            f.write(packet_bytes)
    chunks = [payload[i:i + FRAME_BYTES] for i in range(0, len(payload), FRAME_BYTES)]
    copied = 0
    max_by_budget = None if local_budget_bytes is None else local_budget_bytes // FRAME_BYTES
    allowed = max_new_chunks
    if max_by_budget is not None:
        allowed = max_by_budget if allowed is None else min(allowed, max_by_budget)
    for i, part in enumerate(chunks):
        path = chunks_dir / f"{i:06d}.bin"
        if path.exists():
            require(not path.is_symlink() and path.read_bytes() == part,
                    "CHUNK_REPLAY_TAMPERED")
            continue
        if allowed is not None and copied >= allowed:
            break
        with path.open("xb") as f:
            f.write(part)
        copied += 1
    verified = verify_spool(packet, location, allow_partial=True)
    completed = verified["status"] == "REVIEW_BYTES_COMPLETE"
    receipt = {"schema": RECEIPT, "packet_digest": digest(packet_bytes),
               "source_digest": packet["payload_sha256"], "chunks_written": copied,
               "chunks_present": verified["chunks_present"],
               "chunks_total": len(chunks),
               "status": "HELD_FOR_RECIPIENT_LOCAL_REVIEW" if completed else "INCOMPLETE_RETRYABLE",
               "receiver_admission": "NOT_PERFORMED",
               "broadcast_occurrence": "NONE",
               "source_operator_authority": "SIMULATED_ONLY",
               "recipient_operator_authority": "SIMULATED_ONLY",
               "transport": "LOCAL_DISK_NO_NETWORK"}
    # Result is useful independently of a mutable receipt log.
    return {"status": receipt["status"], "receipt": receipt, "output": str(location)}


def verify_spool(packet, location, *, allow_partial=False):
    """Re-open exact bytes, refuse tampering, and distinguish incomplete vs whole."""
    validate_packet(packet)
    root = Path(location)
    require(root.is_dir() and not root.is_symlink(), "MISSING_OR_UNSAFE_PACKET_DIRECTORY")
    require((root / "packet.json").read_bytes() == (canonical(packet) + "\n").encode("utf8"),
            "PACKET_MANIFEST_MISMATCH")
    parts = []
    expected = (packet["byte_length"] + FRAME_BYTES - 1) // FRAME_BYTES
    chunk_dir = root / "chunks"
    require(chunk_dir.is_dir() and not chunk_dir.is_symlink(), "CHUNK_DIRECTORY_INVALID")
    entries = list(chunk_dir.iterdir())
    require(all(p.is_file() and not p.is_symlink() and p.name.endswith(".bin") and
                len(p.stem) == 6 and p.stem.isdigit() and int(p.stem) < expected
                for p in entries), "UNKNOWN_OR_UNSAFE_CHUNK")
    for i in range(expected):
        path = chunk_dir / f"{i:06d}.bin"
        if not path.exists():
            require(allow_partial, "INCOMPLETE_PACKET")
            continue
        data = path.read_bytes()
        correct = FRAME_BYTES if i < expected - 1 else packet["byte_length"] - FRAME_BYTES * (expected-1)
        require(len(data) == correct, "CHUNK_LENGTH_MISMATCH")
        parts.append((i, data))
    if len(parts) != expected:
        return {"status": "PARTIAL", "chunks_present": len(parts), "chunks_expected": expected}
    joined = b"".join(chunk for _, chunk in parts)
    require(digest(joined) == packet["payload_sha256"], "FINAL_HASH_MISMATCH")
    return {"status": "REVIEW_BYTES_COMPLETE", "chunks_present": expected,
            "chunks_expected": expected, "payload_sha256": digest(joined),
            "air_proven": False, "recipient_review_accepted": False}


def demo(directory):
    payload = b"SYNTHETIC TEST SIGNAL - NOT A SERMON OR BROADCAST. " * 7
    packet = make_packet(payload)
    owner = {"node": "rock-nigeria", "caps": ["media.record-local", "media.edit-local"],
             "state": "awake"}
    recipient = {"node": "kinship-minnesota", "caps": ["media.receive-review"],
                 "state": "awake"}
    gate = evaluate(packet, owner, recipient)
    require(gate["status"] == "HOLD", "FAIL_CLOSED_REGRESSION")
    stage1 = spool(packet, payload, directory, source_node=owner, recipient_node=recipient,
                   source_operator_selected=True, recipient_operator_invited=True,
                   max_new_chunks=2)
    stage2 = spool(packet, payload, directory, source_node=owner, recipient_node=recipient,
                   source_operator_selected=True, recipient_operator_invited=True)
    outcome = verify_spool(packet, stage2["output"])
    return {"first_gate": gate["status"], "first_transfer": stage1["status"],
            "resumed_transfer": stage2["status"], "verification": outcome["status"],
            "air": "NOT_PERFORMED", "actual_station_adoption": False}


if __name__ == "__main__":
    require(len(sys.argv) == 3 and sys.argv[1] == "demo", "USE: demo OUTPUT_PATH")
    print(json.dumps(demo(sys.argv[2]), indent=2, sort_keys=True))
