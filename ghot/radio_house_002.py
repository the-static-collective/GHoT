"""RADIO HOUSE 002 — local-first, media-priority volunteer compute.

Standalone experimental organ. This DOES NOT probe OBS, claim ministry identity,
join a distributed network, or provide real-time OS resource isolation.
No remote shell, sockets, child processes, arbitrary plug-ins, or remote tasks.

Run: python3 -m ghot.radio_house_002 demo /tmp/radio-house-002
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

from ghot.power_field import apply_power_policy, probe_power
from ghot.radio_house_001 import make_packet, spool, verify_spool

CHUNK = 256
MAX_INPUT = 65536
MAX_JOBS = 256
MEDIA_TTL_SECONDS = 45
MEDIA_MODES = {"UNKNOWN", "IDLE_CONFIRMED", "RECORDING", "STREAMING", "EDITING"}
HASH_PREFIX = "sha256:"
CAPABILITY = "compute.public-hash/v0"
POWER_SOURCE = {"ac", "mains", "grid", "usb", "solar", "external"}
DB_VERSION = "ghot.radio-house-dual-node/v0"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(blob):
    return HASH_PREFIX + hashlib.sha256(blob).hexdigest()


def _event(conn, kind, payload):
    last = conn.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
    previous = last["event_hash"] if last else "GENESIS"
    item = canonical({"kind": kind, "payload": payload, "previous": previous})
    event_hash = digest(item.encode("utf-8"))
    conn.execute(
        "INSERT INTO events(kind, payload, previous, event_hash) VALUES(?,?,?,?)",
        (kind, canonical(payload), previous, event_hash),
    )
    return event_hash


def _atomic(conn, fn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = fn()
        conn.commit()
        return result
    except BaseException:
        conn.rollback()
        raise


def connect(root):
    root = Path(root)
    require(not root.is_symlink(), "UNSAFE_ROOT_SYMLINK")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(root.is_dir(), "STATE_ROOT_NOT_DIRECTORY")
    dbpath = root / "radio-house-002.sqlite3"
    require(not dbpath.is_symlink(), "UNSAFE_DB_SYMLINK")
    # Local state still needs OS-level access control on a real shared machine.
    conn = sqlite3.connect(dbpath, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS operator (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        enabled INTEGER NOT NULL DEFAULT 0,
        media_mode TEXT NOT NULL DEFAULT 'UNKNOWN',
        observed_at REAL,
        media_epoch INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        capability TEXT NOT NULL,
        input_text TEXT NOT NULL,
        input_digest TEXT NOT NULL,
        cursor INTEGER NOT NULL DEFAULT 0,
        chunk_hashes TEXT NOT NULL DEFAULT '[]',
        result_digest TEXT,
        status TEXT NOT NULL DEFAULT 'WAITING',
        operator_approved INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        previous TEXT NOT NULL,
        event_hash TEXT NOT NULL
    );
    INSERT OR IGNORE INTO operator(singleton) VALUES(1);
    """)
    os.chmod(root, 0o700)
    os.chmod(dbpath, 0o600)
    return conn


def _operator(conn):
    return conn.execute("SELECT * FROM operator WHERE singleton=1").fetchone()


def enable(conn, permitted):
    require(type(permitted) is bool, "OPT_IN_MUST_BE_BOOLEAN")

    def op():
        current = _operator(conn)
        changed = bool(current["enabled"]) != permitted
        # Changing the opt-in requires a fresh media observation before future work.
        conn.execute(
            "UPDATE operator SET enabled=?, media_mode='UNKNOWN', observed_at=NULL,"
            " media_epoch=media_epoch+1 WHERE singleton=1",
            (int(permitted),),
        )
        _event(conn, "OPERATOR_OPT_IN" if permitted else "OPERATOR_WITHDRAWAL",
               {"enabled": permitted, "changed": changed})
        return {"opted_in": permitted, "media_state": "UNKNOWN", "authority": "LOCAL_SIMULATED"}

    return _atomic(conn, op)


def observe_media(conn, mode, *, at=None):
    require(mode in MEDIA_MODES, "MEDIA_MODE_INVALID")
    at = time.time() if at is None else at
    require(type(at) in (float, int) and 0 <= at < 100_000_000_000,
            "OBSERVATION_TIME_INVALID")

    def op():
        conn.execute(
            "UPDATE operator SET media_mode=?,observed_at=?,"
            " media_epoch=media_epoch+1 WHERE singleton=1",
            (mode, float(at)),
        )
        _event(conn, "MEDIA_OBSERVATION",
               {"mode": mode, "observed_at": float(at)})
        return {"media_mode": mode, "observed_at": float(at)}

    return _atomic(conn, op)


def _gate(conn, power, at):
    user = _operator(conn)
    reasons = []
    if not bool(user["enabled"]):
        reasons.append("OWNER_COMPUTE_OPT_IN_ABSENT")
    if user["media_mode"] != "IDLE_CONFIRMED":
        reasons.append("MEDIA_NOT_CONFIRMED_IDLE")
    age = None
    if user["observed_at"] is not None:
        age = at - user["observed_at"]
    if age is None or age < 0 or age > MEDIA_TTL_SECONDS:
        reasons.append("MEDIA_OBSERVATION_STALE_OR_MISSING")
    if type(power) is not dict:
        reasons.append("POWER_PROBE_MISSING")
        power = {}
    offered = apply_power_policy(
        [{"capability": CAPABILITY, "available": True}], power
    )[0]
    if not offered["available"]:
        reasons.append("GHOT_POWER_OFFER_WITHDRAWN")
    if power.get("willingness") not in {"abundant", "normal"}:
        reasons.append("POWER_NOT_FAVORABLE")
    if power.get("source") not in POWER_SOURCE:
        reasons.append("EXTERNAL_POWER_NOT_CONFIRMED")
    temperature = power.get("temperature_c")
    if type(temperature) not in (int, float) or not (-20 <= temperature <= 74):
        reasons.append("THERMAL_HEADROOM_UNCONFIRMED")
    load = power.get("load_per_cpu_1m")
    if type(load) not in (int, float) or not (0 <= load <= 0.7):
        reasons.append("CPU_HEADROOM_UNCONFIRMED")
    return {"schema": "ghot.radio-house-spare-offer/v0",
            "status": "OFFER_LOCAL_BOUNDED_ONLY" if not reasons else "HOLD",
            "reasons": reasons, "media_mode": user["media_mode"],
            "media_age_seconds": age,
            "power_class": offered["power"]["class"],
            "capability": CAPABILITY, "external_dispatch": False,
            "operator_identity_verified": False, "network_actions": 0,
            "recording_interruption_prevention_guaranteed": False}


def offer(conn, power, *, at=None):
    at = time.time() if at is None else at
    return _gate(conn, power, at)


def enqueue(conn, job_id, message, *, operator_approved=False):
    require(type(job_id) is str and 1 <= len(job_id) <= 60
            and job_id[0].islower()
            and all(c.islower() or c.isdigit() or c == "-" for c in job_id),
            "JOB_ID_INVALID")
    require(type(message) is str, "TEXT_ONLY_CAPABILITY")
    blob = message.encode("utf-8")
    require(0 < len(blob) <= MAX_INPUT, "INVALID_INPUT_SIZE")
    require(type(operator_approved) is bool and operator_approved,
            "PER_JOB_APPROVAL_REQUIRED")

    def op():
        num = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        require(num < MAX_JOBS, "JOB_QUOTA_EXCEEDED")
        require(conn.execute("SELECT 1 FROM jobs WHERE job_id=?", (job_id,)).fetchone() is None,
                "JOB_ALREADY_EXISTS")
        conn.execute(
            "INSERT INTO jobs(job_id,capability,input_text,input_digest,"
            "operator_approved) VALUES(?,?,?,?,1)",
            (job_id, CAPABILITY, message, digest(blob)),
        )
        return {"job_id": job_id, "status": "WAITING",
                "input_sha256": digest(blob), "authority": "LOCAL_APPROVAL_CLAIM_ONLY",
                "capability": CAPABILITY}

    return _atomic(conn, op)


def cancel(conn, job_id):
    def op():
        job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        require(job is not None, "UNKNOWN_JOB")
        require(job["status"] != "COMPLETE", "CANNOT_CANCEL_COMPLETED_WORK")
        conn.execute("UPDATE jobs SET status='CANCELLED' WHERE job_id=?", (job_id,))
        _event(conn, "JOB_CANCELLED", {"job_id": job_id, "cursor": job["cursor"]})
        return {"job_id": job_id, "status": "CANCELLED"}
    return _atomic(conn, op)


def tick(conn, job_id, power, *, at=None):
    """Advance at most one 256-byte local hash chunk per atomic call.

    The media state is checked again inside the locked transaction. A changed
    OBS/capture state can only be obeyed at the NEXT chunk boundary. This does
    not preempt native processes, and the operator must provide truthful status.
    """
    at = time.time() if at is None else at

    def op():
        job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        require(job is not None, "UNKNOWN_JOB")
        require(job["capability"] == CAPABILITY and job["operator_approved"] == 1,
                "UNAUTHORIZED_CAPABILITY")
        require(job["status"] in ("WAITING", "COMPLETE", "CANCELLED"),
                "INVALID_JOB_STATUS")
        blob = job["input_text"].encode("utf-8")
        require(len(blob) <= MAX_INPUT and digest(blob) == job["input_digest"],
                "PERSISTED_SOURCE_MISMATCH")
        cursor = job["cursor"]
        saved = json.loads(job["chunk_hashes"])
        require(type(cursor) is int and 0 <= cursor <= len(blob)
                and cursor % CHUNK == 0 or cursor == len(blob),
                "CORRUPT_CURSOR")
        require(type(saved) is list and len(saved) == (cursor + CHUNK - 1) // CHUNK,
                "CORRUPT_FRAME_HISTORY")
        for i, observed in enumerate(saved):
            expected = digest(blob[i * CHUNK:min((i+1)*CHUNK, len(blob))])
            require(observed == expected, "CORRUPT_FRAME_HISTORY")
        if job["status"] in ("COMPLETE", "CANCELLED"):
            return {"job_id": job_id, "status": job["status"], "cursor": cursor,
                    "work_done_bytes": 0}
        gate = _gate(conn, power, at)
        if gate["status"] != "OFFER_LOCAL_BOUNDED_ONLY":
            return {"job_id": job_id, "status": "HOLD",
                    "cursor": cursor, "work_done_bytes": 0, "gate": gate}
        next_cursor = min(cursor + CHUNK, len(blob))
        new_hash = digest(blob[cursor:next_cursor])
        saved.append(new_hash)
        complete = next_cursor == len(blob)
        result = digest(blob) if complete else None
        status = "COMPLETE" if complete else "WAITING"
        conn.execute(
            "UPDATE jobs SET cursor=?, chunk_hashes=?,result_digest=?,status=? "
            "WHERE job_id=?",
            (next_cursor, canonical(saved), result, status, job_id),
        )
        checkpoint = {
            "job_id": job_id, "cursor": next_cursor, "frame_digest": new_hash,
            "media_epoch": _operator(conn)["media_epoch"],
            "complete": complete, "result_digest": result,
        }
        chain = _event(conn, "WORK_CHECKPOINT", checkpoint)
        return {"job_id": job_id, "status": status, "cursor": next_cursor,
                "work_done_bytes": next_cursor - cursor, "checkpoint_hash": chain,
                "output_sha256": result, "media_interference": "NONE_CLAIMED"}

    return _atomic(conn, op)


def verify(conn):
    """Cold inspection of locally held job bytes, frame digests, and hash-linked events.

    Not tamper-evident against somebody who can rewrite the whole local database.
    """
    last = "GENESIS"
    for e in conn.execute("SELECT * FROM events ORDER BY seq").fetchall():
        require(e["previous"] == last, "AUDIT_LINK_BROKEN")
        item = canonical({"kind": e["kind"], "payload": json.loads(e["payload"]),
                          "previous": last})
        last = digest(item.encode("utf-8"))
        require(last == e["event_hash"], "AUDIT_EVENT_TAMPERED")
    count = 0
    for job in conn.execute("SELECT * FROM jobs").fetchall():
        blob = job["input_text"].encode("utf-8")
        require(digest(blob) == job["input_digest"], "JOB_ORIGIN_MUTATED")
        cursor = job["cursor"]
        hashes = json.loads(job["chunk_hashes"])
        require(type(cursor) is int and 0 <= cursor <= len(blob)
                and (cursor % CHUNK == 0 or cursor == len(blob)),
                "CURSOR_INVALID")
        expected = [digest(blob[i:i + CHUNK]) for i in range(0, cursor, CHUNK)]
        require(hashes == expected, "FRAME_DIGEST_MISMATCH")
        if job["status"] == "COMPLETE":
            require(cursor == len(blob) and job["result_digest"] == digest(blob),
                    "FALSE_COMPLETION")
        else:
            require(job["result_digest"] is None, "FALSE_RESULT")
        count += 1
    return {"status": "LOCAL_COLD_REPLAY_VERIFIED",
            "jobs": count, "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "audit_tip": last, "remote_owner_attested": False,
            "actual_media_broadcast": False, "actual_external_jobs": 0}


def status(conn):
    state = _operator(conn)
    jobs = conn.execute("SELECT job_id,status,cursor FROM jobs ORDER BY job_id").fetchall()
    return {"schema": DB_VERSION, "operator_enabled": bool(state["enabled"]),
            "media_mode": state["media_mode"], "media_observed_at": state["observed_at"],
            "jobs": [dict(x) for x in jobs], "real_distributed_jobs": 0}


def favorable_lab_power():
    return {"willingness": "abundant", "source": "solar",
            "temperature_c": 38.0, "load_per_cpu_1m": 0.1,
            "renewable_surplus": True}


def demo(root):
    """Two local organs cooperate in a SYNTHETIC lab; media never loses priority."""
    root = Path(root)
    require(not (root / "radio-house-002.sqlite3").exists(), "DEMO_MUST_START_FRESH")
    conn = connect(root)
    power = favorable_lab_power()
    # Explicitly opt in but do not permit job while recording.
    enable(conn, True)
    now = 1000.0
    observe_media(conn, "IDLE_CONFIRMED", at=now)
    enqueue(conn, "public-hash-example", "public synthetic compute! " * 60,
            operator_approved=True)
    first = tick(conn, "public-hash-example", power, at=now)
    observe_media(conn, "RECORDING", at=1001.0)
    preempted = tick(conn, "public-hash-example", power, at=1001.0)
    payload = b"FAKE LOCAL ROCK IMPACT DEMO AUDIO. " * 30
    packet = make_packet(payload, rights_reference="LAB_ONLY_NO_RIGHTS")
    sender = {"node": "rock-nigeria", "caps": ["media.record-local"], "state": "awake"}
    receiver = {"node": "kinship-minnesota", "caps": ["media.receive-review"], "state": "awake"}
    media = spool(packet, payload, root / "media", source_node=sender,
                  recipient_node=receiver, source_operator_selected=True,
                  recipient_operator_invited=True)
    media_receipt = verify_spool(packet, media["output"])
    observe_media(conn, "IDLE_CONFIRMED", at=1002.0)
    resumed = tick(conn, "public-hash-example", power, at=1002.0)
    for _ in range(100):
        if status(conn)["jobs"][0]["status"] == "COMPLETE":
            break
        tick(conn, "public-hash-example", power, at=1003.0)
    result = status(conn)["jobs"][0]["status"]
    cold = verify(conn)
    conn.close()
    return {"first_compute": first["status"], "recording_hold": preempted["status"],
            "work_done_during_recording_bytes": preempted["work_done_bytes"],
            "media_packet": media_receipt["status"],
            "media_aired": media_receipt["air_proven"],
            "resumed": resumed["work_done_bytes"] > 0,
            "compute_final": result,
            "cold_verify": cold["status"],
            "real_station_or_ministry_actions": 0,
            "remote_compute_jobs": 0}


def main(argv):
    require(len(argv) >= 3, "USAGE: demo|status|enable|disable|media|submit|tick|verify PATH [ARG]")
    command, root = argv[1:3]
    if command == "demo":
        require(len(argv) == 3, "DEMO_ONLY_NEEDS_PATH")
        result = demo(root)
    else:
        conn = connect(root)
        try:
            if command == "enable":
                require(len(argv) == 3, "BAD_ENABLE_ARGS")
                result = enable(conn, True)
            elif command == "disable":
                require(len(argv) == 3, "BAD_DISABLE_ARGS")
                result = enable(conn, False)
            elif command == "media":
                require(len(argv) == 4, "MEDIA_MODE_REQUIRED")
                result = observe_media(conn, argv[3])
            elif command == "submit":
                require(len(argv) == 5, "SUBMIT_JOB_ID_AND_SYNTHETIC_TEXT")
                result = enqueue(conn, argv[3], argv[4], operator_approved=True)
            elif command == "tick":
                require(len(argv) == 4, "JOB_ID_REQUIRED")
                result = tick(conn, argv[3], probe_power())
            elif command == "status":
                require(len(argv) == 3, "STATUS_ONLY_NEEDS_PATH")
                result = status(conn)
            elif command == "verify":
                require(len(argv) == 3, "VERIFY_ONLY_NEEDS_PATH")
                result = verify(conn)
            else:
                raise ValueError("UNKNOWN_COMMAND")
        finally:
            conn.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (ValueError, sqlite3.Error) as exc:
        print("HOLD:", str(exc), file=sys.stderr)
        raise SystemExit(2)
