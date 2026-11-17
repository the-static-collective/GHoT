#!/usr/bin/env python3
"""HUMKIN Orchard opt-in public snapshot relay for a GHoT host.

A tiny, reversible and explicitly-invoked adapter. Uses the GHoT P-256
IdentityKey implementation and Power Field, but a separate HUMKIN-specific
private key: signing in to HUMKIN must NOT silently expose a GHoT BODY identity.

REAL capabilities:
  signed registration; public projection; bounded catalog integrity audit;
  voluntary server-relayed live HOME responses while this command is running.

NOT claimed: full reLATTE lease dispatch, native Android background service,
continuous public HTTP hosting, CPU proof-of-work, money or tradable HUM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from power_field import probe_power
from relatte_identity import IdentityKey

ENDPOINT = "https://kbhqacsdvjsstzyplqij.supabase.co/functions/v1/humkin-orchard-network"
CATALOG = "https://humkin.abundent.org/fm/rotation.json"
ROOT = Path(os.environ.get("GHOT_HOME", ".ghot"))
CONFIG = ROOT / "humkin" / "listener.json"
PRIVATE = ROOT / "identity" / "humkin-orchard-p256.pem"
MAX_BYTES = 100000
ALLOWED_THINGS = re.compile(r"^[a-z0-9-]{3,50}$")
_ORIGIN = "https://humkin.abundent.org"


class BridgeError(RuntimeError):
    pass


def compact(data: Any) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def encode_home(room: str, stage: int = 0, things: list[str] | None = None) -> dict[str, Any]:
    room = str(room).strip().replace("<", "").replace(">", "")[:32] or "A Little Listening Room"
    return {
        "room": room,
        "stage": max(0, min(6, int(stage))),
        "things": [x for x in (things or []) if ALLOWED_THINGS.fullmatch(x)][:24],
        "minutes": 0,  # We do not fabricate audio playback from a desktop service.
    }


def key_material(key: IdentityKey) -> tuple[str, dict[str, str]]:
    jwk = key.public_jwk()  # exact kty, crv, x, y order for the HUMKIN pilot.
    identity = hashlib.sha256(compact(jwk).encode("utf-8")).hexdigest()
    return identity, jwk


def load_config() -> dict[str, Any]:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"name": "A Neighbor", "public": False, "home": encode_home("A Little Listening Room")}


def save_config(data: dict[str, Any]) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(CONFIG)


def request(method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = compact(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json", "Origin": _ORIGIN}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise BridgeError("Server response exceeded size budget")
            return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            reason = json.loads(exc.read(5000).decode("utf-8")).get("error")
        except Exception:
            reason = None
        raise BridgeError(str(reason or ("HTTP " + str(exc.code)))) from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise BridgeError("Network unavailable: " + str(exc)) from exc


def signed(key: IdentityKey, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    actor, _ = key_material(key)
    packet = {
        "actor": actor, "nonce": secrets.token_hex(16), "action": action,
        "ts": int(time.time() * 1000), "payload": payload or {},
    }
    body = {"packet": packet, "signature": key.sign(compact(packet).encode("utf-8"))}
    return request("POST", ENDPOINT, body)


def check_power() -> tuple[bool, str]:
    observation = probe_power()
    status = observation.get("willingness", "conserve")
    if status in {"critical", "conserve"}:
        return False, "GHoT power pressure " + str(status) + "; will HOLD volunteer processing"
    return True, str(status)


def catalog_check() -> tuple[int, str]:
    source = urllib.parse.urlparse(CATALOG)
    if source.scheme != "https":
        raise BridgeError("Catalog must use HTTPS")
    req = urllib.request.Request(CATALOG, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as response:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise BridgeError("Catalog exceeded 100KB work budget")
    try:
        catalog = json.loads(raw)
    except ValueError as exc:
        raise BridgeError("Catalog is not valid JSON") from exc
    tracks = catalog.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 1000:
        raise BridgeError("Unexpected catalog size")
    ids: set[str] = set()
    for track in tracks:
        if not isinstance(track, dict):
            raise BridgeError("Catalog record must be an object")
        tid, title, src = (track.get(k) for k in ("id", "title", "src"))
        if not isinstance(tid, str) or not tid or tid in ids:
            raise BridgeError("Invalid or duplicate track ID")
        if not isinstance(title, str) or not title or not isinstance(src, str):
            raise BridgeError("Missing track title or URL")
        media = urllib.parse.urlparse(urllib.parse.urljoin(CATALOG, src))
        if media.scheme != "https" or media.netloc != source.netloc:
            raise BridgeError("Off-origin or insecure audio URL")
        ids.add(tid)
    return len(tracks), hashlib.sha256(raw).hexdigest()


def enroll(key: IdentityKey, display: str) -> dict[str, Any]:
    _, jwk = key_material(key)
    return signed(key, "register", {"jwk": jwk, "name": display[:32] or "A Neighbor"})


def cmd_enroll(args: argparse.Namespace, key: IdentityKey) -> None:
    config = load_config()
    config["name"] = args.name[:32] if args.name else config.get("name", "A Neighbor")
    result = enroll(key, config["name"])
    save_config(config)
    print(json.dumps({"registered": result.get("registered"), "node": key_material(key)[0],
                      "network_artifacts": len(result.get("artifacts", []))}, indent=2))


def cmd_publish(args: argparse.Namespace, key: IdentityKey) -> None:
    config = load_config()
    if args.public and not args.confirm_public:
        raise BridgeError("Explicit public publication requires --confirm-public")
    config["home"] = encode_home(args.room or config.get("home", {}).get("room", "A Listening Room"),
                                 args.stage if args.stage is not None else config.get("home", {}).get("stage", 0),
                                 config.get("home", {}).get("things", []))
    config["public"] = bool(args.public)
    result = signed(key, "publish", {
        "name": config.get("name", "A Neighbor"),
        "home": config["home"],
        "public": config["public"]
    })
    save_config(config)
    print(json.dumps({"public": result.get("published"), "home": result.get("home")}, indent=2))


def cmd_audit(args: argparse.Namespace, key: IdentityKey) -> None:
    if not args.consent:
        raise BridgeError("Voluntary work requires --consent")
    allowed, reason = check_power()
    if not allowed:
        raise BridgeError(reason)
    offer = signed(key, "challenge", {"capability": "radio.catalog.audit.v1", "consent": True})["offer"]
    if offer.get("capability") != "radio.catalog.audit.v1":
        raise BridgeError("Unsupported work offer; refuse")
    count, digest = catalog_check()
    completed = signed(key, "complete", {"challenge_id": offer["id"], "digest": digest})
    print(json.dumps({
        "server_validated": bool(completed.get("ok")),
        "track_count": count,
        "receipt": completed.get("receipt"),
        "scope": "Catalog consistency, not proof of unique CPU work"
    }, indent=2))


def cmd_state(args: argparse.Namespace, key: IdentityKey) -> None:
    state = signed(key, "state")
    print(json.dumps({
        "id": key_material(key)[0],
        "home": state.get("node", {}).get("home"),
        "public": state.get("node", {}).get("is_public"),
        "objects": state.get("artifacts", []),
        "inbox": state.get("inbox", []),
        "receipts": state.get("receipts", []),
    }, indent=2))


def cmd_world(args: argparse.Namespace, key: IdentityKey) -> None:
    print(json.dumps(request("GET", ENDPOINT + "?mode=world"), indent=2))


def cmd_serve(args: argparse.Namespace, key: IdentityKey) -> None:
    config = load_config()
    if not args.consent or not config.get("public"):
        raise BridgeError("Must explicitly set a public HOME and invoke serve --consent")
    if args.minutes < 1 or args.minutes > 15:
        raise BridgeError("Foreground service must be between one and fifteen minutes")
    print("Offering 15-second foreground checks via the HUMKIN relay. Ctrl+C to STOP.")
    end = time.monotonic() + args.minutes * 60
    last_beat = 0.0
    served = 0
    try:
        while time.monotonic() < end:
            allowed, reason = check_power()
            if not allowed:
                print(reason)
                break
            if time.monotonic() - last_beat >= 45:
                signed(key, "heartbeat", {"serve": True})
                last_beat = time.monotonic()
            offer = signed(key, "poll_live", {"capability": "foreground.home.snapshot.v1"})
            for task in offer.get("requests", [])[:3]:
                answer = signed(key, "serve_live", {"request_id": task["id"], "home": config["home"]})
                if answer.get("served", {}).get("served"):
                    served += 1
                    print("SERVED", task["id"], "(sanitized public room only)")
            time.sleep(min(15.0, max(0.0, end - time.monotonic())))
    except KeyboardInterrupt:
        print("Operator STOP; ending the voluntary service.")
    finally:
        try:
            signed(key, "heartbeat", {"serve": False})
        except BridgeError:
            pass  # The last lease expires by itself after 120s.
    print(json.dumps({"served": served, "note": "A bounded voluntary run, not perpetual hosting"}))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Opt-in HUMKIN Orchard connector for GHoT")
    subs = p.add_subparsers(dest="cmd", required=True)
    enroll_p = subs.add_parser("enroll", help="Register separate, durable HUMKIN key locally")
    enroll_p.add_argument("--name", default="A Neighbor")
    publish_p = subs.add_parser("publish", help="Publish or withdraw your sanitized home")
    publish_p.add_argument("--public", action="store_true")
    publish_p.add_argument("--confirm-public", action="store_true")
    publish_p.add_argument("--room")
    publish_p.add_argument("--stage", type=int)
    subs.add_parser("state", help="Read your signed, server-owned artifact inventory")
    subs.add_parser("world", help="View voluntarily public listening rooms")
    audit_p = subs.add_parser("audit", help="Run tiny, one-shot catalog check")
    audit_p.add_argument("--consent", action="store_true")
    serve_p = subs.add_parser("serve", help="Offer small public HOME snapshots for a bounded foreground period")
    serve_p.add_argument("--minutes", type=int, default=5)
    serve_p.add_argument("--consent", action="store_true")
    return p


def main() -> int:
    args = parser().parse_args()
    if args.cmd in {"audit", "serve"} and not args.consent:
        print("Explicit --consent required; no background work started.", file=sys.stderr)
        return 2
    # Avoid creating a key as a side effect of listing the world.
    if args.cmd == "world":
        cmd_world(args, None)
        return 0
    if args.cmd != "enroll" and not PRIVATE.exists():
        print("No HUMKIN-specific key. Run enroll to create one.", file=sys.stderr)
        return 2
    key = IdentityKey.load_or_create(PRIVATE)
    try:
        {
            "enroll": cmd_enroll,
            "publish": cmd_publish,
            "audit": cmd_audit,
            "state": cmd_state,
            "serve": cmd_serve,
        }[args.cmd](args, key)
        return 0
    except (BridgeError, urllib.error.URLError, KeyError, ValueError) as e:
        print("WORK HELD / REFUSED:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
