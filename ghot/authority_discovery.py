#!/usr/bin/env python3
"""GHoT Authority Discovery / Porch Introduction — Experiment 013.

Discovery answers:
    where is an authority porch currently reachable?

Trust answers:
    is this a previously admitted authority particular/public key?

Those questions are intentionally separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

from reference_node import ROOT, persist
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    b64url,
    jcs_bytes,
    normalize_public_jwk,
    particular_for_public_key,
    timestamp_now,
    unb64url,
    verify_p256,
)


DISCOVERY_PORT = 47889
DISCOVERY_MAGIC = "ghot.authority.discover.v0"
HERE_MAGIC = "ghot.authority.here.v0"
ADVERT_ID_DOMAIN = b"GHoT-AuthorityAdvert-v0|"
ADVERT_SIGNATURE_DOMAIN = b"GHoT-AuthorityAdvertSignature-v0|"
ADVERT_SIGNING_DOMAIN = "ghot.authority-advert-signature/v0"

ADVERT_FIELDS = {
    "kind",
    "version",
    "advert_id",
    "authority_id",
    "owner_node_id",
    "world_id",
    "particular",
    "public_key",
    "capability_ref",
    "crossing_schema",
    "receipt_schema",
    "signing_profile",
    "algorithm",
    "lease_port",
    "crossing_path",
    "issued_at",
    "ttl_seconds",
    "signing",
}


def _advert_body(advert: dict[str, Any]) -> dict[str, Any]:
    signing = advert.get("signing") or {}
    return {
        "kind": advert.get("kind"),
        "version": advert.get("version"),
        "authority_id": advert.get("authority_id"),
        "owner_node_id": advert.get("owner_node_id"),
        "world_id": advert.get("world_id"),
        "particular": advert.get("particular"),
        "public_key": normalize_public_jwk(advert.get("public_key") or {}),
        "capability_ref": advert.get("capability_ref"),
        "crossing_schema": advert.get("crossing_schema"),
        "receipt_schema": advert.get("receipt_schema"),
        "signing_profile": advert.get("signing_profile"),
        "algorithm": advert.get("algorithm"),
        "lease_port": advert.get("lease_port"),
        "crossing_path": advert.get("crossing_path"),
        "issued_at": advert.get("issued_at"),
        "ttl_seconds": advert.get("ttl_seconds"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": normalize_public_jwk(signing.get("public_key") or {}),
            "domain": signing.get("domain"),
        },
    }


def derive_advert_id(advert: dict[str, Any]) -> str:
    digest = hashlib.sha256(ADVERT_ID_DOMAIN + jcs_bytes(_advert_body(advert))).hexdigest()
    return "ghot-authority-advert-v0:" + digest


def advert_signature_bytes(advert: dict[str, Any]) -> bytes:
    body = _advert_body(advert)
    return ADVERT_SIGNATURE_DOMAIN + jcs_bytes({
        "advert_id": derive_advert_id(advert),
        **body,
    })


def make_authority_advert(
    base: dict[str, Any],
    *,
    signer: IdentityKey,
    lease_port: int,
    ttl_seconds: int = 15,
    issued_at: str | None = None,
) -> dict[str, Any]:
    public_key = signer.public_jwk()
    particular = signer.particular()
    if base.get("particular") != particular:
        raise ValueError("authority base advert particular does not match signer")
    if normalize_public_jwk(base.get("public_key") or {}) != public_key:
        raise ValueError("authority base advert public key does not match signer")

    advert = {
        "kind": "ghot.authority.advert",
        "version": "0",
        "advert_id": "",
        "authority_id": base["authority_id"],
        "owner_node_id": base["owner_node_id"],
        "world_id": base["world_id"],
        "particular": particular,
        "public_key": public_key,
        "capability_ref": base["capability_ref"],
        "crossing_schema": base["crossing_schema"],
        "receipt_schema": base["receipt_schema"],
        "signing_profile": base["signing_profile"],
        "algorithm": base["algorithm"],
        "lease_port": int(lease_port),
        "crossing_path": "/crossing",
        "issued_at": issued_at or timestamp_now(),
        "ttl_seconds": int(ttl_seconds),
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": public_key,
            "signature": "",
            "domain": ADVERT_SIGNING_DOMAIN,
        },
    }
    advert["advert_id"] = derive_advert_id(advert)
    advert["signing"]["signature"] = signer.sign(advert_signature_bytes(advert))
    return advert


def verify_authority_advert(advert: dict[str, Any]) -> bool:
    try:
        if set(advert) != ADVERT_FIELDS:
            return False
        if advert.get("kind") != "ghot.authority.advert" or advert.get("version") != "0":
            return False
        if advert.get("algorithm") != ALGORITHM:
            return False
        if advert.get("signing_profile") != "relatte.identity-signature/v0":
            return False
        if advert.get("crossing_path") != "/crossing":
            return False
        if not isinstance(advert.get("lease_port"), int):
            return False
        if not isinstance(advert.get("ttl_seconds"), int):
            return False

        public_key = normalize_public_jwk(advert.get("public_key") or {})
        signing = advert.get("signing") or {}
        if set(signing) != {"algorithm", "public_key", "signature", "domain"}:
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != ADVERT_SIGNING_DOMAIN:
            return False
        if normalize_public_jwk(signing.get("public_key") or {}) != public_key:
            return False
        if advert.get("particular") != particular_for_public_key(public_key):
            return False
        if advert.get("advert_id") != derive_advert_id(advert):
            return False

        signature = unb64url(str(signing.get("signature") or ""))
        if len(signature) != 64:
            return False
        return verify_p256(
            public_key,
            advert_signature_bytes(advert),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


class AuthorityTrustStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.path = self.root / "trust" / "authorities.json"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"kind": "ghot.authority.trust-store", "version": "0", "authorities": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"kind": "ghot.authority.trust-store", "version": "0", "authorities": {}}
        if not isinstance(value, dict) or not isinstance(value.get("authorities"), dict):
            return {"kind": "ghot.authority.trust-store", "version": "0", "authorities": {}}
        return value

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(f".tmp-{uuid.uuid4()}")
        temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        data = self._read()
        return [
            value
            for _, value in sorted(data["authorities"].items())
            if isinstance(value, dict)
        ]

    def trust(self, advert: dict[str, Any], *, route: str | None = None) -> dict[str, Any]:
        if not verify_authority_advert(advert):
            raise ValueError("authority advert signature/identity verification failed")
        data = self._read()
        particular = str(advert["particular"])
        record = {
            "kind": "ghot.authority.trust",
            "version": "0",
            "particular": particular,
            "public_key": advert["public_key"],
            "authority_id": advert["authority_id"],
            "world_id": advert["world_id"],
            "admitted_at": timestamp_now(),
            "last_route": route,
            "source": "explicit-operator-introduction",
        }
        data["authorities"][particular] = record
        self._write(data)
        persist("authority-trust", record)
        return record

    def forget(self, particular: str) -> bool:
        data = self._read()
        existed = particular in data["authorities"]
        if existed:
            del data["authorities"][particular]
            self._write(data)
        return existed

    def matches(self, advert: dict[str, Any]) -> bool:
        if not verify_authority_advert(advert):
            return False
        record = self._read()["authorities"].get(str(advert.get("particular")))
        if not isinstance(record, dict):
            return False
        return (
            record.get("public_key") == advert.get("public_key")
            and record.get("authority_id") == advert.get("authority_id")
            and record.get("world_id") == advert.get("world_id")
        )


def discovery_responder(
    advert_factory: Callable[[], dict[str, Any]],
    stop: threading.Event,
    *,
    port: int = DISCOVERY_PORT,
) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    sock.settimeout(1.0)
    try:
        while not stop.is_set():
            try:
                data, address = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                request = json.loads(data.decode("utf-8"))
            except Exception:
                continue
            if request.get("kind") != DISCOVERY_MAGIC:
                continue
            advert = advert_factory()
            response = {
                "kind": HERE_MAGIC,
                "version": "0",
                "advert": advert,
            }
            sock.sendto(json.dumps(response).encode("utf-8"), address)
    finally:
        sock.close()


def discover_authorities(
    timeout: float = 2.0,
    *,
    port: int = DISCOVERY_PORT,
) -> list[dict[str, Any]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.25)
    sock.bind(("", 0))
    request = {
        "kind": DISCOVERY_MAGIC,
        "version": "0",
        "nonce": f"authority-discovery-{uuid.uuid4()}",
    }
    sock.sendto(
        json.dumps(request).encode("utf-8"),
        ("255.255.255.255", port),
    )

    deadline = time.monotonic() + timeout
    seen: dict[str, dict[str, Any]] = {}
    while time.monotonic() < deadline:
        try:
            data, address = sock.recvfrom(65535)
        except socket.timeout:
            continue
        try:
            message = json.loads(data.decode("utf-8"))
        except Exception:
            continue
        if message.get("kind") != HERE_MAGIC:
            continue
        advert = message.get("advert")
        if not isinstance(advert, dict) or not verify_authority_advert(advert):
            continue
        particular = str(advert["particular"])
        seen[particular] = {
            "advert": advert,
            "address": address[0],
            "authority_url": f"http://{address[0]}:{advert['lease_port']}",
        }

    sock.close()
    return list(seen.values())


def fetch_authority_advert(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url.rstrip("/") + "/authority", timeout=5) as response:
        advert = json.loads(response.read().decode("utf-8"))
    if not isinstance(advert, dict) or not verify_authority_advert(advert):
        raise RuntimeError("authority endpoint did not return a valid signed advert")
    return advert


def trusted_observations(
    observations: list[dict[str, Any]],
    *,
    store: AuthorityTrustStore | None = None,
    pinned_particular: str | None = None,
) -> list[dict[str, Any]]:
    trust = store or AuthorityTrustStore()
    pin = pinned_particular or os.environ.get("GHOT_AUTHORITY_PARTICULAR")
    results: list[dict[str, Any]] = []
    for observation in observations:
        advert = observation.get("advert")
        if not isinstance(advert, dict) or not verify_authority_advert(advert):
            continue
        pin_match = bool(pin and advert.get("particular") == pin)
        remembered = trust.matches(advert)
        if pin_match or remembered:
            results.append({
                **observation,
                "trust": "pinned" if pin_match else "remembered",
            })
    results.sort(
        key=lambda item: (
            str(item["advert"].get("particular")),
            str(item.get("authority_url")),
        )
    )
    return results


def resolve_trusted_authorities(
    timeout: float = 2.0,
    *,
    store: AuthorityTrustStore | None = None,
    pinned_particular: str | None = None,
) -> list[dict[str, Any]]:
    return trusted_observations(
        discover_authorities(timeout),
        store=store,
        pinned_particular=pinned_particular,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover and admit GHoT authority porches.")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan")
    scan.add_argument("--timeout", type=float, default=2.0)

    trust = sub.add_parser("trust")
    trust.add_argument("authority_url")

    sub.add_parser("trusted")

    forget = sub.add_parser("forget")
    forget.add_argument("particular")

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--timeout", type=float, default=2.0)

    args = parser.parse_args()
    store = AuthorityTrustStore()

    if args.command == "scan":
        observations = discover_authorities(args.timeout)
        for item in observations:
            item["trusted"] = store.matches(item["advert"])
        print(json.dumps(observations, indent=2))
        return 0

    if args.command == "trust":
        advert = fetch_authority_advert(args.authority_url)
        record = store.trust(advert, route=args.authority_url)
        print(json.dumps(record, indent=2))
        return 0

    if args.command == "trusted":
        print(json.dumps(store.list(), indent=2))
        return 0

    if args.command == "forget":
        removed = store.forget(args.particular)
        print(json.dumps({"particular": args.particular, "forgotten": removed}, indent=2))
        return 0 if removed else 1

    if args.command == "resolve":
        print(json.dumps(resolve_trusted_authorities(args.timeout, store=store), indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
