#!/usr/bin/env python3
"""PostEmahh'n MAIL-002: sealed portable PDF mail, opaque LAN relay, print door.

Uses P-256 ECDH / HKDF-SHA256 / AES-256-GCM (cryptography dependency)
and existing GHoT reLATTE P-256 crossings/receipts. Recipient keys stay local.

Security scope: authenticated ciphertext, not public hosted email, anonymous
transport, station TLS, key recovery, or actual physical print completion.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from postemahhn_mail import (
    ADDRESS_RE, STATION_RE, address, canonical_contact, digest, load_json,
    pdf_ok, write_json,
)
from relatte_identity import (
    IdentityKey, b64url, jcs_bytes, normalize_public_jwk, particular_for_public_key,
    sign_crossing, sign_receipt, timestamp_now, unb64url,
    verify_crossing, verify_receipt,
)

PROFILE = "postemahhn.sealed-mail/v1"
MAX_CIPHERTEXT = 5 * 1024 * 1024 + 16
MAX_JSON = 8 * 1024 * 1024
HEX_RE = re.compile(r"^[0-9a-f]{64}$")
RELAY_LIMIT = 32


def public_ec(jwk: dict[str, Any]) -> ec.EllipticCurvePublicKey:
    key = normalize_public_jwk(jwk)
    x = int.from_bytes(unb64url(key["x"]), "big")
    y = int.from_bytes(unb64url(key["y"]), "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()


def jwk_ec(key: ec.EllipticCurvePublicKey) -> dict[str, str]:
    n = key.public_numbers()
    return {
        "kty": "EC", "crv": "P-256",
        "x": b64url(n.x.to_bytes(32, "big")),
        "y": b64url(n.y.to_bytes(32, "big")),
    }


def private_ec(key: IdentityKey) -> ec.EllipticCurvePrivateKey:
    value = serialization.load_pem_private_key(key.private_key_path.read_bytes(), password=None)
    if not isinstance(value, ec.EllipticCurvePrivateKey) or not isinstance(value.curve, ec.SECP256R1):
        raise ValueError("recipient private key must be P-256")
    if jwk_ec(value.public_key()) != key.public_jwk():
        raise ValueError("owner encryption and signing keys do not match")
    return value


def envelope_header(recipient: dict[str, Any], sender: IdentityKey,
                    ephemeral: ec.EllipticCurvePublicKey, salt: bytes,
                    nonce: bytes) -> dict[str, str | dict]:
    return {
        "profile": PROFILE, "recipient_address": recipient["address"],
        "sender_particular": sender.particular(),
        "ephemeral_public_key": jwk_ec(ephemeral),
        "salt": b64url(salt), "nonce": b64url(nonce),
        "media_type": "application/pdf", "message_id": str(uuid.uuid4()),
    }


def derive_key(shared: bytes, salt: bytes, recipient_address: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        info=b"postemahhn.mail-002.aes-gcm|" + recipient_address.encode("ascii"),
    ).derive(shared)


def make_sealed(pdf: bytes, recipient_contact: dict[str, Any],
                sender: IdentityKey) -> dict[str, Any]:
    pdf_ok(pdf)
    contact = canonical_contact(recipient_contact)
    ephemeral = ec.generate_private_key(ec.SECP256R1())
    salt, nonce = os.urandom(16), os.urandom(12)
    header = envelope_header(contact, sender, ephemeral.public_key(), salt, nonce)
    shared = ephemeral.exchange(ec.ECDH(), public_ec(contact["public_key"]))
    cipher = AESGCM(derive_key(shared, salt, contact["address"]))
    ciphertext = cipher.encrypt(nonce, pdf, jcs_bytes(header))
    sealed = {"header": header, "ciphertext": b64url(ciphertext)}
    parcel_hash = digest(jcs_bytes(sealed))
    crossing = sign_crossing({
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "", "protocol_version": "0",
        "source_particular": sender.particular(),
        "source_world": "postemahhn-encrypted-mail-sender",
        "declared_kind": "POSTEMAHHN_SEALED_MAIL_V1",
        "payload_refs": [{"sha256": parcel_hash, "media_type": "application/vnd.postemahhn.sealed+json"}],
        "requested_effect": {
            "action": "DELIVER_ENCRYPTED_TO_HOLD",
            "recipient_address": contact["address"], "parcel_hash": parcel_hash,
        },
        "created_at": timestamp_now(),
        "extensions": {"postemahhn_profile": PROFILE}, "signing": {},
    }, sender)
    return {"schema": "postemahhn.sealed-parcel/v1", "recipient": contact,
            "sealed": sealed, "crossing": crossing}


def verify_sealed(parcel: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(parcel, dict) or set(parcel) != {"schema", "recipient", "sealed", "crossing"}:
        raise ValueError("invalid sealed parcel fields")
    if parcel["schema"] != "postemahhn.sealed-parcel/v1":
        raise ValueError("unexpected sealed parcel profile")
    recipient = canonical_contact(parcel["recipient"])
    sealed = parcel["sealed"]
    if not isinstance(sealed, dict) or set(sealed) != {"header", "ciphertext"}:
        raise ValueError("invalid sealed envelope")
    h = sealed["header"]
    if not isinstance(h, dict) or set(h) != {
        "profile", "recipient_address", "sender_particular", "ephemeral_public_key",
        "salt", "nonce", "media_type", "message_id",
    }:
        raise ValueError("invalid sealed envelope header")
    if (h["profile"] != PROFILE or h["recipient_address"] != recipient["address"]
            or h["media_type"] != "application/pdf"):
        raise ValueError("envelope addressing mismatch")
    try:
        public_ec(h["ephemeral_public_key"])
        if len(unb64url(h["salt"])) != 16 or len(unb64url(h["nonce"])) != 12:
            raise ValueError("invalid HKDF salt or AES nonce")
        cipher_bytes = unb64url(sealed["ciphertext"])
        if not 16 <= len(cipher_bytes) <= MAX_CIPHERTEXT:
            raise ValueError("invalid encrypted length")
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError("invalid encrypted envelope") from exc
    crossing = parcel["crossing"]
    if not verify_crossing(crossing):
        raise ValueError("invalid sender crossing signature")
    if crossing.get("source_particular") != particular_for_public_key(
        crossing["signing"]["public_key"]
    ) or h["sender_particular"] != crossing["source_particular"]:
        raise ValueError("source identity mismatch")
    parcel_hash = digest(jcs_bytes(sealed))
    if (crossing.get("declared_kind") != "POSTEMAHHN_SEALED_MAIL_V1"
            or crossing.get("extensions") != {"postemahhn_profile": PROFILE}
            or crossing.get("payload_refs") != [{
                "sha256": parcel_hash,
                "media_type": "application/vnd.postemahhn.sealed+json",
            }]
            or crossing.get("requested_effect") != {
                "action": "DELIVER_ENCRYPTED_TO_HOLD",
                "recipient_address": recipient["address"], "parcel_hash": parcel_hash,
            }):
        raise ValueError("envelope not bound to sender crossing")
    return recipient["address"], crossing["crossing_id"]


def open_sealed(parcel: dict[str, Any], owner: IdentityKey) -> bytes:
    recipient_address, _ = verify_sealed(parcel)
    if address(owner.public_jwk()) != recipient_address:
        raise ValueError("recipient key does not own address")
    h = parcel["sealed"]["header"]
    shared = private_ec(owner).exchange(ec.ECDH(), public_ec(h["ephemeral_public_key"]))
    key = derive_key(shared, unb64url(h["salt"]), recipient_address)
    try:
        pdf = AESGCM(key).decrypt(
            unb64url(h["nonce"]), unb64url(parcel["sealed"]["ciphertext"]),
            jcs_bytes(h),
        )
    except InvalidTag as e:
        raise ValueError("authenticated PDF decryption failed") from e
    pdf_ok(pdf)
    return pdf


def stage_release(parcel: dict[str, Any], owner: IdentityKey, station_id: str,
                  ttl_seconds: int = 900) -> dict[str, Any]:
    if not isinstance(station_id, str) or not STATION_RE.fullmatch(station_id):
        raise ValueError("invalid station identifier")
    if not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 3600:
        raise ValueError("invalid release duration")
    pdf = open_sealed(parcel, owner)
    _, cid = verify_sealed(parcel)
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    return sign_receipt({
        "schema": "relatte.receipt/v0", "receipt_id": "", "crossing_id": cid,
        "world_id": "postemahhn-wallet:" + address(owner.public_jwk()),
        "receiver_particular": owner.particular(),
        "kind": "VERIFIED", "semantic_effect": "none",
        "created_at": timestamp_now(),
        "note": "Recipient authorized export to one named print station; no paper effect",
        "extensions": {"postemahhn_sealed_release": {
            "profile": PROFILE, "address": address(owner.public_jwk()),
            "artifact_sha256": digest(pdf), "station_id": station_id,
            "action": "STAGE_PRINT_READY", "physical_print_claimed": False,
            "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }}, "signing": {},
    }, owner)


def accept_at_station(parcel: dict[str, Any], pdf: bytes, release: dict[str, Any],
                      station_id: str, trusted_recipient_address: str,
                      spool: Path, now: datetime | None = None) -> Path:
    """Station receives decrypted PDF directly from owner; no printing occurs."""
    recipient_address, cid = verify_sealed(parcel)
    if (not isinstance(trusted_recipient_address, str)
            or not ADDRESS_RE.fullmatch(trusted_recipient_address)
            or trusted_recipient_address != recipient_address):
        raise ValueError("trusted address mismatch")
    if not isinstance(station_id, str) or not STATION_RE.fullmatch(station_id):
        raise ValueError("invalid station identifier")
    owner_public = parcel["recipient"]["public_key"]
    if not verify_receipt(
        release, expected_public_key=owner_public,
        expected_receiver_particular=particular_for_public_key(owner_public),
    ):
        raise ValueError("release signature or owner trust invalid")
    if (release.get("crossing_id") != cid or release.get("kind") != "VERIFIED"
            or release.get("semantic_effect") != "none"):
        raise ValueError("release does not authorize this crossing")
    ext = release.get("extensions")
    body = ext.get("postemahhn_sealed_release") if isinstance(ext, dict) else None
    if not isinstance(body, dict) or set(body) != {
        "profile", "address", "artifact_sha256", "station_id", "action",
        "physical_print_claimed", "expires_at",
    }:
        raise ValueError("invalid signed print-release extension")
    pdf_ok(pdf)
    if (body["profile"] != PROFILE or body["address"] != recipient_address
            or body["station_id"] != station_id
            or body["action"] != "STAGE_PRINT_READY"
            or body["physical_print_claimed"] is not False
            or body["artifact_sha256"] != digest(pdf)):
        raise ValueError("print release boundaries not satisfied")
    try:
        expires = datetime.strptime(
            body["expires_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        created = datetime.fromisoformat(release["created_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError, KeyError) as e:
        raise ValueError("invalid release timestamps") from e
    clock = now or datetime.now(timezone.utc)
    if (clock > expires or clock < created - timedelta(seconds=60)
            or expires <= created or (expires - created).total_seconds() > 3601):
        raise ValueError("expired or invalid release")
    spool.mkdir(parents=True, exist_ok=True, mode=0o700)
    if spool.is_symlink():
        raise ValueError("print spool cannot be a symlink")
    job_id = "pm-print-" + digest(release["receipt_id"].encode())[:40]
    target = spool / job_id
    if target.is_symlink():
        raise ValueError("symlinked print job refused")
    if target.exists():
        if not target.is_dir() or (target / "document.pdf").is_symlink():
            raise ValueError("existing job is not a safe directory")
        if (target / "document.pdf").read_bytes() != pdf:
            raise ValueError("existing print job differs")
        if load_json(target / "release.json") != release:
            raise ValueError("existing release differs")
        return target
    temp = Path(tempfile.mkdtemp(prefix=".incoming-", dir=spool))
    try:
        (temp / "document.pdf").write_bytes(pdf)
        write_json(temp / "release.json", release)
        write_json(temp / "manifest.json", {
            "schema": "postemahhn.print-hold/v1", "state": "HELD",
            "station_id": station_id, "address": recipient_address,
            "crossing_id": cid, "sha256": digest(pdf),
            "physical_print_claimed": False,
        })
        temp.rename(target)
        return target
    finally:
        if temp.exists():
            shutil.rmtree(temp)


class OpaqueRelay:
    """Relay has zero recipient signing or decrypt keys; it stores opaque JSON."""
    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.Lock()

    def put(self, parcel: dict[str, Any]) -> tuple[str, str]:
        addr, cid = verify_sealed(parcel)
        if len(jcs_bytes(parcel)) > MAX_JSON:
            raise ValueError("parcel exceeds relay size limit")
        path = self.root / addr
        with self.lock:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            if path.is_symlink():
                raise ValueError("relay mailbox symlink refused")
            key = digest(cid.encode("utf-8"))
            target = path / (key + ".json")
            if target.is_symlink():
                raise ValueError("relay parcel symlink refused")
            if target.exists():
                if load_json(target) != parcel:
                    raise ValueError("duplicate mail differs")
                return addr, key
            if len(list(path.glob("*.json"))) >= RELAY_LIMIT:
                raise ValueError("recipient relay quota exceeded")
            with target.open("x", encoding="utf-8") as file:
                file.write(json.dumps(parcel, sort_keys=True) + "\n")
            return addr, key

    def list_ids(self, addr: str) -> list[str]:
        if not ADDRESS_RE.fullmatch(addr):
            raise ValueError("invalid mailbox address")
        path = self.root / addr
        if not path.is_dir() or path.is_symlink():
            return []
        return sorted(p.stem for p in path.glob("*.json") if not p.is_symlink())

    def get(self, addr: str, parcel_id: str) -> dict[str, Any]:
        if not ADDRESS_RE.fullmatch(addr) or not HEX_RE.fullmatch(parcel_id):
            raise ValueError("invalid parcel locator")
        path = self.root / addr / (parcel_id + ".json")
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError("opaque parcel missing")
        parcel = load_json(path)
        verify_addr, cid = verify_sealed(parcel)
        if verify_addr != addr or digest(cid.encode("utf-8")) != parcel_id:
            raise ValueError("stored parcel locator mismatch")
        return parcel


def relay_handler(store: OpaqueRelay):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, payload: Any):
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/v1/mail":
                return self._reply(404, {"error": "not-found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_JSON:
                    return self._reply(413, {"error": "size"})
                parcel = json.loads(self.rfile.read(size))
                addr, key = store.put(parcel)
                self._reply(202, {"state": "STORED_OPAQUE", "address": addr, "parcel_id": key})
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                self._reply(400, {"error": "invalid-parcel"})

        def do_GET(self):
            parts = urlsplit(self.path).path.strip("/").split("/")
            try:
                if len(parts) == 3 and parts[:2] == ["v1", "mail"]:
                    return self._reply(200, {"parcel_ids": store.list_ids(parts[2])})
                if len(parts) == 4 and parts[:2] == ["v1", "mail"]:
                    return self._reply(200, store.get(parts[2], parts[3]))
                self._reply(404, {"error": "not-found"})
            except FileNotFoundError:
                self._reply(404, {"error": "not-found"})
            except (ValueError, KeyError, TypeError):
                self._reply(400, {"error": "invalid-request"})

        def log_message(self, *args):
            pass
    return Handler


def send_http(url: str, parcel: dict[str, Any]) -> dict[str, Any]:
    verify_sealed(parcel)
    payload = jcs_bytes(parcel)
    if len(payload) > MAX_JSON:
        raise ValueError("parcel too large")
    req = Request(url.rstrip("/") + "/v1/mail", data=payload,
                  headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=10) as response:
        return json.load(response)


def fetch_http(url: str, recipient_address: str) -> list[dict[str, Any]]:
    if not ADDRESS_RE.fullmatch(recipient_address):
        raise ValueError("invalid recipient address")
    root = url.rstrip("/") + "/v1/mail/" + recipient_address
    with urlopen(root, timeout=10) as response:
        ids = json.load(response)["parcel_ids"]
    parcels = []
    for key in ids:
        if not isinstance(key, str) or not HEX_RE.fullmatch(key):
            raise ValueError("invalid relay parcel identifier")
        with urlopen(root + "/" + key, timeout=10) as response:
            value = json.load(response)
        addr, cid = verify_sealed(value)
        if addr != recipient_address or digest(cid.encode()) != key:
            raise ValueError("relay substituted parcel content")
        parcels.append(value)
    return parcels


def approved_relay_bind(host: str, allow_insecure_lan: bool) -> str:
    # V0 has public opaque GET/list endpoints: require explicit LAN opt-in.
    if host not in {"127.0.0.1", "localhost", "::1"} and not allow_insecure_lan:
        raise ValueError("non-loopback relay requires explicit --allow-insecure-lan")
    return host


def main() -> None:
    parser = argparse.ArgumentParser(description="PostEmahh'n encrypted MAIL-002 pilot")
    sub = parser.add_subparsers(dest="cmd", required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("--pdf", type=Path, required=True)
    seal.add_argument("--to", type=Path, required=True)
    seal.add_argument("--sender-key", type=Path, required=True)
    seal.add_argument("--out", type=Path, required=True)
    srv = sub.add_parser("serve")
    srv.add_argument("--root", type=Path, required=True)
    srv.add_argument("--port", type=int, default=7789)
    srv.add_argument("--bind", default="127.0.0.1")
    srv.add_argument("--allow-insecure-lan", action="store_true")
    push = sub.add_parser("send")
    push.add_argument("--url", required=True)
    push.add_argument("--parcel", type=Path, required=True)
    pull = sub.add_parser("fetch")
    pull.add_argument("--url", required=True)
    pull.add_argument("--address", required=True)
    pull.add_argument("--out-dir", type=Path, required=True)
    op = sub.add_parser("open")
    op.add_argument("--parcel", type=Path, required=True)
    op.add_argument("--recipient-key", type=Path, required=True)
    op.add_argument("--out", type=Path, required=True)
    release = sub.add_parser("authorize")
    release.add_argument("--parcel", type=Path, required=True)
    release.add_argument("--recipient-key", type=Path, required=True)
    release.add_argument("--station", required=True)
    release.add_argument("--out", type=Path, required=True)
    station = sub.add_parser("stage")
    station.add_argument("--parcel", type=Path, required=True)
    station.add_argument("--pdf", type=Path, required=True)
    station.add_argument("--release", type=Path, required=True)
    station.add_argument("--station", required=True)
    station.add_argument("--trusted-address", required=True)
    station.add_argument("--spool", type=Path, required=True)
    args = parser.parse_args()
    if args.cmd == "seal":
        p = make_sealed(args.pdf.read_bytes(), load_json(args.to),
                        IdentityKey.load_or_create(args.sender_key))
        if args.out.exists():
            raise ValueError("parcel output exists")
        write_json(args.out, p)
        print(json.dumps({"state": "SEALED", "address": p["recipient"]["address"],
                          "crossing_id": p["crossing"]["crossing_id"]}, indent=2))
    elif args.cmd == "serve":
        if args.port < 0 or args.port > 65535:
            raise ValueError("invalid port")
        host = approved_relay_bind(args.bind, args.allow_insecure_lan)
        with ThreadingHTTPServer((host, args.port), relay_handler(OpaqueRelay(args.root))) as server:
            print(json.dumps({"bind": host, "port": server.server_port, "content": "opaque", "authenticated": False, "tls": False}), flush=True)
            server.serve_forever()
    elif args.cmd == "send":
        print(json.dumps(send_http(args.url, load_json(args.parcel)), indent=2))
    elif args.cmd == "fetch":
        parcels = fetch_http(args.url, args.address)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for p in parcels:
            _, cid = verify_sealed(p)
            write_json(args.out_dir / (digest(cid.encode()) + ".json"), p)
        print(json.dumps({"received_opaque": len(parcels), "out_dir": str(args.out_dir)}))
    elif args.cmd == "open":
        pdf = open_sealed(load_json(args.parcel), IdentityKey(args.recipient_key))
        if args.out.exists():
            raise ValueError("output exists")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(pdf)
        print(json.dumps({"opened": str(args.out), "sha256": digest(pdf)}))
    elif args.cmd == "authorize":
        r = stage_release(load_json(args.parcel), IdentityKey(args.recipient_key), args.station)
        if args.out.exists():
            raise ValueError("release output exists")
        write_json(args.out, r)
        print(json.dumps({"release": str(args.out), "receipt_id": r["receipt_id"]}))
    elif args.cmd == "stage":
        bundle = accept_at_station(load_json(args.parcel), args.pdf.read_bytes(),
                                   load_json(args.release), args.station,
                                   args.trusted_address, args.spool)
        print(json.dumps({"bundle": str(bundle), "state": "HELD", "printed": False}))


if __name__ == "__main__":
    main()
