"""RADIO HOUSE 004 — localhost-clickable worker console and signed SSH-tunnel
transport. A signed transport message is *only an inbox proposal*, never a
compute grant. Real TCP sockets; physically distinct hosts require manual setup.

Ports:
  127.0.0.1:8787  owner-only console (never forward to requesters)
  127.0.0.1:8788  narrow signed intake / signed-result endpoint (SSH forward only)
No public listeners, arbitrary code, OBS controls, auto execution or broadcasts.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ghot.power_field import probe_power
from ghot.radio_house_002 import (connect, enable, observe_media, offer, status as local_status,
                                  cancel, verify as cold_verify)
from ghot.radio_house_003 import (IdentityKey, make_bundle, verify_bundle, accept,
                                  advance, settle, verify_return, require)
from ghot.relatte_identity import normalize_public_jwk, particular_for_public_key

SCHEMA = "ghot.radio-house-console/v0"
MAX_BODY = 128 * 1024
MAX_INBOX = 12
PAGE_FILE = Path(__file__).resolve().parent.parent / "web" / "radio-house-004.html"


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_private(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not path.exists() and not path.is_symlink(), "OUTPUT_ALREADY_EXISTS")
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def _root(root):
    raw = Path(root)
    require(not raw.is_symlink(), "STATE_ROOT_SYMLINK")
    p = raw.resolve()
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(p, 0o700)
    return p


def _key_path(root, role):
    require(role in ("worker", "requester"), "UNKNOWN_ROLE")
    return Path(root) / "identity" / (role + "-p256.pem")


def initialize(root, role, *, requester_pin=None):
    root = _root(root)
    require(not _key_path(root, role).exists(), "IDENTITY_EXISTS")
    if role == "worker":
        require(requester_pin is not None, "EXTERNAL_REQUESTER_PIN_REQUIRED")
        pinned = normalize_public_jwk(_read_json(requester_pin))
        _write_private(root / "requester-pin.json", pinned)
    key = IdentityKey.load_or_create(_key_path(root, role))
    return {"role": role, "particular": key.particular(),
            "public_key": key.public_jwk(), "pin_source": "OPERATOR_SUPPLIED_NOT_TRUSTED_BY_SYSTEM"}


def load_identity(root, role):
    p = _key_path(root, role)
    require(p.is_file() and not p.is_symlink(), "IDENTITY_NOT_INITIALIZED")
    return IdentityKey(p)


def requester_pin(root):
    return normalize_public_jwk(_read_json(Path(root) / "requester-pin.json"))


def _inbox(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS radio_house_004_inbox (
        crossing_id TEXT PRIMARY KEY,
        original_bundle TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('PENDING','ADMITTED','COMPLETE','CANCELLED')),
        created_at INTEGER NOT NULL
    )""")


def _stored(conn, crossing_id):
    _inbox(conn)
    require(type(crossing_id) is str and crossing_id.startswith("relatte-crossing-v0:")
            and len(crossing_id) == len("relatte-crossing-v0:") + 64, "INVALID_CROSSING_ID")
    return conn.execute("SELECT * FROM radio_house_004_inbox WHERE crossing_id=?",
                        (crossing_id,)).fetchone()


def ingest(root, bundle, *, at=None):
    at = int(time.time()) if at is None else at
    receiver = load_identity(root, "worker")
    source_pin = requester_pin(root)
    crossing_id = verify_bundle(bundle, pinned_requester_public=source_pin,
                                expected_worker_public=receiver.public_jwk(), at=at)
    blob = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
    require(len(blob.encode("utf8")) <= MAX_BODY, "BUNDLE_TOO_LARGE")
    conn = connect(root)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _inbox(conn)
            existing = _stored(conn, crossing_id)
            if existing:
                require(existing["original_bundle"] == blob, "INBOX_REPLAY_CONFLICT")
                disposition = existing["state"]
            else:
                count = conn.execute("SELECT COUNT(*) FROM radio_house_004_inbox WHERE state='PENDING'").fetchone()[0]
                require(count < MAX_INBOX, "INBOX_QUOTA_REACHED")
                conn.execute("INSERT INTO radio_house_004_inbox VALUES(?,?,?,?)",
                             (crossing_id, blob, "PENDING", at))
                disposition = "PENDING"
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    finally:
        conn.close()
    return {"crossing_id": crossing_id, "disposition": disposition,
            "execution": "NONE", "operator_approved": False if disposition == "PENDING" else "UNSPECIFIED",
            "station_or_ministry_authority": "NONE"}


def _obs_guard(proc=Path("/proc")):
    """Conservative Linux process check. OBS being open never implies stream idle.
    This is advisory only: an unobserved capture process is still possible.
    """
    if sys.platform != "linux" or not proc.is_dir():
        return {"status": "UNKNOWN_CAPTURE_STATE", "processes": []}
    found = []
    try:
        for pid in proc.iterdir():
            if not pid.name.isdigit():
                continue
            try:
                name = (pid / "comm").read_text(encoding="utf8").strip().lower()
            except (OSError, UnicodeError):
                continue
            if name in {"obs", "obs-studio", "ffmpeg", "arecord", "gst-launch-1.0"}:
                found.append(name)
    except OSError:
        return {"status": "UNKNOWN_CAPTURE_STATE", "processes": []}
    if found:
        return {"status": "CAPTURE_PROCESS_PRESENT_HOLD", "processes": sorted(set(found))}
    return {"status": "NO_KNOWN_CAPTURE_PROCESS", "processes": [],
            "absence_proves_no_recording": False}


def actual_gate(conn, power_provider=probe_power, obs_provider=_obs_guard, *, at=None):
    at = time.time() if at is None else at
    sensor = obs_provider()
    power = power_provider()
    result = offer(conn, power, at=at)
    if sensor["status"] != "NO_KNOWN_CAPTURE_PROCESS":
        result = {**result, "status": "HOLD", "reasons": result["reasons"]+[
            "CAPTURE_PROCESS_OR_UNKNOWN_STATE"]}
    result["obs_sensor"] = sensor
    result["power_snapshot"] = {k: power.get(k) for k in
                                ("source", "willingness", "temperature_c", "load_per_cpu_1m")}
    return result, power


class Worker:
    """A server-bound owner-local worker, no implicit opt-in."""
    def __init__(self, root, *, power_provider=probe_power, obs_provider=_obs_guard):
        self.root = _root(root)
        self.power_provider = power_provider
        self.obs_provider = obs_provider
        self.receiver = load_identity(root, "worker")
        self.source_pin = requester_pin(root)
        self.admin_token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        conn = connect(self.root)
        try:
            _inbox(conn)
        finally:
            conn.close()

    def summary(self):
        conn = connect(self.root)
        try:
            _inbox(conn)
            gate, _ = actual_gate(conn, self.power_provider, self.obs_provider)
            incoming = conn.execute(
                "SELECT crossing_id,state,created_at,original_bundle FROM radio_house_004_inbox "
                "ORDER BY created_at DESC LIMIT ?", (MAX_INBOX+256,)
            ).fetchall()
            rows = []
            for item in incoming:
                blob = json.loads(item["original_bundle"])
                crossing_id = item["crossing_id"]
                from ghot.radio_house_003 import JOB_PREFIX, _ledger
                _ledger(conn)
                ledger = conn.execute("SELECT worker_job_id FROM radio_house_003 WHERE crossing_id=?",
                                      (crossing_id,)).fetchone()
                job = None
                if ledger:
                    job = conn.execute("SELECT cursor,status FROM jobs WHERE job_id=?",
                                       (ledger["worker_job_id"],)).fetchone()
                rows.append({"crossing_id": crossing_id,
                             "job_id": blob["payload"]["job_id"],
                             "preview": blob["payload"]["text"][:90],
                             "size_bytes": len(blob["payload"]["text"].encode("utf8")),
                             "state": item["state"], "cursor": job["cursor"] if job else 0,
                             "compute_status": job["status"] if job else "NOT_ADMITTED"})
            s = local_status(conn)
            return {"schema": SCHEMA, "opted_in": s["operator_enabled"],
                    "media_mode": s["media_mode"], "gate": gate, "inbox": rows,
                    "real_station_adoption": False, "remote_shell_enabled": False,
                    "actual_broadcasts": 0}
        finally:
            conn.close()

    def action(self, op, args):
        require(type(args) is dict, "INVALID_ACTION_PAYLOAD")
        conn = connect(self.root)
        try:
            now = int(time.time())
            if op == "enable":
                require(not args, "EXTRA_ACTION_FIELDS")
                return enable(conn, True)
            if op == "disable":
                require(not args, "EXTRA_ACTION_FIELDS")
                return enable(conn, False)
            if op == "media":
                require(set(args) == {"mode"}, "EXTRA_ACTION_FIELDS")
                return observe_media(conn, args["mode"])
            if op == "verify":
                require(not args, "EXTRA_ACTION_FIELDS")
                return cold_verify(conn)
            require(set(args) == {"crossing_id"} or
                    (op == "step" and set(args) == {"crossing_id", "steps"}),
                    "EXTRA_ACTION_FIELDS")
            row = _stored(conn, args["crossing_id"])
            require(row is not None, "NOT_IN_INBOX")
            bundle = json.loads(row["original_bundle"])
            if op == "approve":
                require(row["state"] == "PENDING", "NOT_PENDING")
                gate, power = actual_gate(conn,self.power_provider,self.obs_provider)
                require(gate["status"] == "OFFER_LOCAL_BOUNDED_ONLY", "MEDIA_OR_POWER_HOLD")
                ack = accept(conn,bundle,receiver_key=self.receiver,
                             pinned_requester_public=self.source_pin,
                             power=power,operator_approved=True,at=now)
                conn.execute("UPDATE radio_house_004_inbox SET state='ADMITTED' WHERE crossing_id=?",
                             (args["crossing_id"],))
                return {"state": "ADMITTED", "receipt_id": ack["receipt_id"],
                        "operator_choice": "OWNER_LOCAL"}
            if op == "step":
                require(row["state"] == "ADMITTED", "JOB_NOT_ADMITTED")
                n = args.get("steps",1)
                require(type(n) is int and 1 <= n <= 10, "STEP_BUDGET_INVALID")
                gate,power = actual_gate(conn,self.power_provider,self.obs_provider)
                require(gate["status"]=="OFFER_LOCAL_BOUNDED_ONLY", "MEDIA_OR_POWER_HOLD")
                last=None
                for _ in range(n):
                    # Fresh status before EVERY frame, never one stale preflight.
                    gate,power = actual_gate(conn,self.power_provider,self.obs_provider)
                    require(gate["status"]=="OFFER_LOCAL_BOUNDED_ONLY", "MEDIA_OR_POWER_HOLD")
                    last=advance(conn,bundle,receiver_key=self.receiver,
                                 pinned_requester_public=self.source_pin,
                                 power=power,at=int(time.time()))
                    if last["status"] == "COMPLETE":
                        receipt=settle(conn,bundle,receiver_key=self.receiver,
                                       pinned_requester_public=self.source_pin,
                                       at=int(time.time()))
                        conn.execute("UPDATE radio_house_004_inbox SET state='COMPLETE' WHERE crossing_id=?",
                                     (args["crossing_id"],))
                        return {"state": "COMPLETE", "receipt_id": receipt["receipt_id"],
                                "result": receipt["post_state_ref"]}
                    if last["status"]=="HOLD":
                        break
                return {"state": "ADMITTED", "cursor": last["cursor"],
                        "work_done_bytes":last.get("work_done_bytes",0)}
            if op == "cancel":
                require(row["state"] in ("PENDING","ADMITTED"), "NOT_CANCELLABLE")
                if row["state"] == "ADMITTED":
                    from ghot.radio_house_003 import JOB_PREFIX
                    worker_id=JOB_PREFIX+args["crossing_id"].split(":")[-1][:40]
                    cancel(conn,worker_id)
                conn.execute("UPDATE radio_house_004_inbox SET state='CANCELLED' WHERE crossing_id=?",
                             (args["crossing_id"],))
                return {"state":"CANCELLED","remote_execution_authorized":False}
            raise ValueError("UNKNOWN_ACTION")
        finally:
            conn.close()

    def result(self, bundle):
        crossing=verify_bundle(bundle,pinned_requester_public=self.source_pin,
                               expected_worker_public=self.receiver.public_jwk(),
                               at=int(time.time()))
        conn=connect(self.root)
        try:
            row=_stored(conn,crossing)
            require(row is not None, "UNKNOWN_JOB")
            require(row["original_bundle"] == json.dumps(bundle,sort_keys=True,separators=(",",":")),
                    "RESULT_REQUEST_BUNDLE_MISMATCH")
            if row["state"] != "COMPLETE":
                return {"state": row["state"], "result_ready":False}
            from ghot.radio_house_003 import _ledger
            _ledger(conn)
            receipts=conn.execute(
                "SELECT owner_admission_receipt,finished_receipt FROM radio_house_003 "
                "WHERE crossing_id=?", (crossing,)).fetchone()
            require(receipts is not None and receipts["finished_receipt"] is not None,
                    "RESULT_NOT_SETTLED")
            cold_verify(conn)
            return {"state":"COMPLETE","result_ready":True,
                    "admission":json.loads(receipts["owner_admission_receipt"]),
                    "final":json.loads(receipts["finished_receipt"])}
        finally:
            conn.close()


def _safe_json(raw):
    def no_dupes(pairs):
        out={}
        for k,v in pairs:
            require(k not in out, "DUPLICATE_JSON_KEY")
            out[k]=v
        return out
    require(len(raw)<=MAX_BODY, "REQUEST_TOO_LARGE")
    try:
        return json.loads(raw.decode("utf8"),object_pairs_hook=no_dupes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_JSON") from exc


class RadioHTTP(BaseHTTPRequestHandler):
    server_version = "RadioHouse004/0"
    sys_version = ""
    def log_message(self, *args):
        pass

    def _host_ok(self):
        host=self.headers.get("Host","")
        return host in {f"127.0.0.1:{self.server.server_port}",
                        f"localhost:{self.server.server_port}"}

    def _write(self, status, item, *, html=False):
        payload=item.encode("utf8") if html else json.dumps(item,sort_keys=True).encode("utf8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _error(self,exc):
        reason=str(exc)[:120]
        status=409 if reason in {"MEDIA_OR_POWER_HOLD","INBOX_QUOTA_REACHED",
                                "NOT_PENDING","JOB_NOT_ADMITTED","CROSSING_EXPIRED_OR_NOT_YET_VALID"} else 400
        self._write(status,{"status":"HOLD","reason":reason})

    def do_GET(self):
        if not self._host_ok():
            return self._write(403,{"status":"HOLD","reason":"HOST_REJECTED"})
        if self.server.surface=="intake":
            if self.path == "/health":
                return self._write(200,{"status":"READY_FOR_SIGNED_BUNDLES_ONLY",
                                       "operator_authority":"NONE"})
            return self._write(404,{"status":"HOLD"})
        if self.path=="/":
            page=PAGE_FILE.read_text(encoding="utf8")
            return self._write(200,page.replace("__ADMIN_TOKEN__",self.server.worker.admin_token),html=True)
        if self.path=="/api/status":
            return self._write(200,self.server.worker.summary())
        return self._write(404,{"status":"HOLD"})

    def do_POST(self):
        if not self._host_ok():
            return self._write(403,{"status":"HOLD","reason":"HOST_REJECTED"})
        length=self.headers.get("Content-Length","")
        if not length.isdigit() or int(length)>MAX_BODY or int(length)<1:
            return self._write(413,{"status":"HOLD","reason":"REQUEST_SIZE_INVALID"})
        if self.headers.get("Content-Type","").split(";")[0].strip()!="application/json":
            return self._write(415,{"status":"HOLD","reason":"JSON_ONLY"})
        try:
            obj=_safe_json(self.rfile.read(int(length)))
            if self.server.surface=="intake":
                if self.path=="/intake":
                    result=ingest(self.server.worker.root,obj)
                elif self.path=="/result":
                    require(type(obj) is dict and set(obj)=={"bundle"},"RESULT_FIELDS_INVALID")
                    result=self.server.worker.result(obj["bundle"])
                else:
                    return self._write(404,{"status":"HOLD"})
            else:
                origin=self.headers.get("Origin","")
                expected={f"http://127.0.0.1:{self.server.server_port}",
                          f"http://localhost:{self.server.server_port}"}
                require(origin in expected, "ADMIN_ORIGIN_REQUIRED")
                require(self.headers.get("X-Radio-House-Token")==self.server.worker.admin_token,
                        "LOCAL_ADMIN_TOKEN_REQUIRED")
                require(self.path.startswith("/api/"),"UNKNOWN_ACTION")
                require(type(obj) is dict,"ADMIN_JSON_OBJECT_REQUIRED")
                result=self.server.worker.action(self.path[len("/api/"):],obj)
            return self._write(200,result)
        except (ValueError,KeyError,TypeError,sqlite3.Error) as exc:
            return self._error(exc)


def _server(worker, port, surface):
    require(type(port) is int and (port == 0 or 1025<=port<=65535),"INVALID_PORT")
    srv=ThreadingHTTPServer(("127.0.0.1",port), RadioHTTP)
    srv.worker=worker
    srv.surface=surface
    srv.daemon_threads=True
    return srv


def serve(root, *, admin_port=8787, intake_port=8788,
          power_provider=probe_power, obs_provider=_obs_guard):
    require(admin_port != intake_port, "PORT_COLLISION")
    worker=Worker(root,power_provider=power_provider,obs_provider=obs_provider)
    admin=_server(worker,admin_port,"admin")
    try:
        incoming=_server(worker,intake_port,"intake")
    except BaseException:
        admin.server_close()
        raise
    print(json.dumps({"status":"LOCAL_CONSOLE_READY",
                      "admin_url":f"http://127.0.0.1:{admin_port}/",
                      "intake_port":intake_port,
                      "binding":"LOOPBACK_ONLY",
                      "warning":"Do not forward admin port or open public firewalls."}),flush=True)
    t=threading.Thread(target=incoming.serve_forever,daemon=True)
    t.start()
    try:
        admin.serve_forever(poll_interval=0.1)
    finally:
        admin.server_close()
        incoming.shutdown()
        incoming.server_close()
        t.join(timeout=2)


def _post(url,obj,*,origin=None):
    headers={"Content-Type":"application/json"}
    if origin:
        headers["Origin"]=origin
    request=urllib.request.Request(url,data=json.dumps(obj).encode("utf8"),headers=headers,
                                   method="POST")
    try:
        with urllib.request.urlopen(request,timeout=6) as result:
            return _safe_json(result.read(MAX_BODY+1))
    except urllib.error.HTTPError as exc:
        data=exc.read(MAX_BODY)
        raise ValueError("REMOTE_HOLD:"+str(exc.code)+":"+str(_safe_json(data))) from exc


def send(root,worker_pin_path,*,job_id,text,port=8788):
    requester=load_identity(root,"requester")
    worker_pin=normalize_public_jwk(_read_json(worker_pin_path))
    bundle=make_bundle(requester,worker_pin,job_id,text,at=int(time.time()),lifetime=900)
    crossing=bundle["crossing"]["crossing_id"]
    _write_private(Path(root)/"outbox"/(crossing.replace(":","_")+".json"),bundle)
    result=_post(f"http://127.0.0.1:{port}/intake",bundle)
    require(result.get("crossing_id")==crossing,"REMOTE_CROSSING_MISMATCH")
    return {"crossing_id":crossing,"disposition":result["disposition"],
            "requester_source":"LOCAL_SIGNED_KEY","requires_recipient_approval":True}


def poll(root,worker_pin_path,bundle_file,*,port=8788):
    original=_read_json(bundle_file)
    requester=load_identity(root,"requester")
    worker_pin=normalize_public_jwk(_read_json(worker_pin_path))
    response=_post(f"http://127.0.0.1:{port}/result",{"bundle":original})
    if not response.get("result_ready"):
        return response
    proved=verify_return(original,response["admission"],response["final"],
                         pinned_requester_public=requester.public_jwk(),
                         pinned_worker_public=worker_pin,at=int(time.time()))
    _write_private(Path(root)/"received"/(original["crossing"]["crossing_id"].replace(":","_")+
                                          "-verified.json"),{"proof":proved,"receipts":response})
    return {**proved,"receipts_saved":"REQUESTER_OWNER_LOCAL","actual_network_transport":"SSH_TUNNEL_OR_LOOPBACK"}


def main(argv=None):
    ap=argparse.ArgumentParser(description="RADIO HOUSE 004 — owner-local click console")
    sub=ap.add_subparsers(dest="command",required=True)
    for name in ("requester-init","worker-init","identity","serve","send","poll"):
        parser=sub.add_parser(name)
        parser.add_argument("--root",required=True)
        if name=="worker-init":
            parser.add_argument("--requester-pin",required=True)
        if name=="identity":
            parser.add_argument("--role",choices=("worker","requester"),required=True)
        if name=="serve":
            parser.add_argument("--admin-port",type=int,default=8787)
            parser.add_argument("--intake-port",type=int,default=8788)
        if name in ("send","poll"):
            parser.add_argument("--worker-pin",required=True)
            parser.add_argument("--port",type=int,default=8788)
        if name=="send":
            parser.add_argument("--job-id",required=True)
            parser.add_argument("--text",required=True)
        if name=="poll":
            parser.add_argument("--bundle",required=True)
    args=ap.parse_args(argv)
    try:
        if args.command in ("requester-init","worker-init"):
            result=initialize(args.root,"requester" if args.command=="requester-init" else "worker",
                              requester_pin=getattr(args,"requester_pin",None))
        elif args.command=="identity":
            key=load_identity(args.root,args.role)
            result=key.public_jwk()
        elif args.command=="serve":
            return serve(args.root,admin_port=args.admin_port,intake_port=args.intake_port)
        elif args.command=="send":
            result=send(args.root,args.worker_pin,job_id=args.job_id,text=args.text,port=args.port)
        else:
            result=poll(args.root,args.worker_pin,args.bundle,port=args.port)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (ValueError,KeyError,sqlite3.Error,ConnectionError,urllib.error.URLError) as exc:
        print("HOLD:",str(exc)[:200],file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
