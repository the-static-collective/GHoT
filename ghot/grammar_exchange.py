#!/usr/bin/env python3
"""Grammar Exchange Table — Experiment 023.

Discovery reveals only explicitly shared package metadata.
A signed request asks for one exact package address.
Network request receipt does not send a package.
Only an explicit local OFFER creates and crosses a 022 plugin parcel.

Laws:
    INSTALLED != SHAREABLE
    DISCOVERY != REQUEST
    REQUEST != OFFER
    OFFER != INSTALLATION
    RETURN ROAD != REQUESTER IDENTITY
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from merge_plugin import MergePluginStore
from merge_plugin_parcel import (
    MergePluginParcelExporter,
    MergePluginParcelInbox,
    send_bundle,
    verify_package_author,
)
from reference_node import ROOT
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    identity_safe,
    jcs_bytes,
    normalize_public_jwk,
    particular_for_public_key,
    sign_receipt,
    timestamp_now,
    unb64url,
    verify_p256,
    verify_receipt,
)
from state_migration import semantic_address


DISCOVERY_PORT = 47890
HTTP_PORT = 7793
DISCOVERY_MAGIC = "ghot.grammar-exchange.discover.v0"
HERE_MAGIC = "ghot.grammar-exchange.here.v0"

ADVERT_KIND = "ghot.grammar.exchange.advert"
ADVERT_VERSION = "0"
ADVERT_ID_DOMAIN = b"GHoT-GrammarExchangeAdvert-v0|"
ADVERT_SIGNATURE_DOMAIN = b"GHoT-GrammarExchangeAdvertSignature-v0|"
ADVERT_SIGNING_DOMAIN = "ghot.grammar-exchange-advert-signature/v0"

REQUEST_KIND = "ghot.grammar.exchange.request"
REQUEST_VERSION = "0"
REQUEST_ID_DOMAIN = b"GHoT-GrammarExchangeRequest-v0|"
REQUEST_SIGNATURE_DOMAIN = b"GHoT-GrammarExchangeRequestSignature-v0|"
REQUEST_SIGNING_DOMAIN = "ghot.grammar-exchange-request-signature/v0"

CONTRACT_REF = "ghot.grammar-exchange@0"
TERMINAL_REQUEST = {"OFFERED", "DECLINED"}

MAX_ADVERT_PACKAGES = 128
MAX_REQUEST_TTL = 3600


def _safe_name(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _node_id_at(root: Path) -> str:
    path = root / "node-id"
    root.mkdir(parents=True, exist_ok=True)
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = f"node-{uuid.uuid4()}"
    path.write_text(value + "\n", encoding="utf-8")
    return value


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _epoch(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc).timestamp()


def _fresh(created_at: str, ttl_seconds: int, *, at: float | None = None) -> bool:
    try:
        ttl = int(ttl_seconds)
        if ttl <= 0 or ttl > MAX_REQUEST_TTL:
            return False
        created = _epoch(created_at)
        now = time.time() if at is None else float(at)
        return created - 5.0 <= now <= created + ttl
    except Exception:
        return False


def find_author_for_installed_package(
    root: Path,
    *,
    package_id: str,
    package_address: str,
) -> dict[str, Any] | None:
    base = root / "merge-plugin-parcels"
    inbox_dir = base / "inbox"
    raw_dir = base / "raw"
    if not inbox_dir.is_dir():
        return None
    for path in sorted(inbox_dir.glob("*.json")):
        try:
            row = _read_object(path)
        except Exception:
            continue
        if row.get("status") != "INSTALLED":
            continue
        if row.get("package_id") != package_id:
            continue
        if row.get("package_address") != package_address:
            continue
        raw_path = raw_dir / path.name
        if not raw_path.exists():
            continue
        try:
            bundle = _read_object(raw_path)
            parcel = bundle.get("parcel") or {}
            package = parcel.get("package")
            author = parcel.get("author")
            if (
                isinstance(package, dict)
                and isinstance(author, dict)
                and verify_package_author(author, package) is True
            ):
                return identity_safe(author)
        except Exception:
            continue
    return None


class GrammarShareStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.path = self.root / "grammar-exchange" / "shares.json"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "kind": "ghot.grammar.share-store",
                "version": "0",
                "packages": {},
            }
        value = _read_object(self.path)
        packages = value.get("packages")
        if (
            value.get("kind") != "ghot.grammar.share-store"
            or value.get("version") != "0"
            or not isinstance(packages, dict)
        ):
            raise ValueError("invalid grammar share store")
        return value

    def _write(self, value: dict[str, Any]) -> None:
        _write_atomic(self.path, value)

    def _installed_by_id(self) -> dict[str, dict[str, Any]]:
        result = {}
        for item in MergePluginStore(self.root).list_installed():
            package_id = item.get("package_id")
            if isinstance(package_id, str):
                result[package_id] = item
        return result

    def share(self, package_id: str) -> dict[str, Any]:
        installed = self._installed_by_id().get(package_id)
        if installed is None:
            raise ValueError("package must be installed and receipt-valid before sharing")
        package = installed.get("package") or {}
        contract = package.get("contract") or {}
        record = {
            "kind": "ghot.grammar.share",
            "version": "0",
            "package_id": package_id,
            "package_version": installed["package_version"],
            "package_address": installed["package_address"],
            "contract_id": installed["contract_id"],
            "title": contract.get("title"),
            "category": contract.get("category"),
            "shared_at": timestamp_now(),
            "shareable": True,
        }
        data = self._read()
        data["packages"][package_id] = record
        self._write(data)
        return record

    def unshare(self, package_id: str) -> bool:
        data = self._read()
        existed = package_id in data["packages"]
        if existed:
            del data["packages"][package_id]
            self._write(data)
        return existed

    def declared(self) -> list[dict[str, Any]]:
        data = self._read()
        return [
            value
            for _, value in sorted(data["packages"].items())
            if isinstance(value, dict)
        ]

    def active(self) -> list[dict[str, Any]]:
        installed = self._installed_by_id()
        active = []
        for record in self.declared():
            package_id = record.get("package_id")
            current = installed.get(str(package_id))
            if current is None:
                continue
            if current.get("package_address") != record.get("package_address"):
                continue
            author = find_author_for_installed_package(
                self.root,
                package_id=str(package_id),
                package_address=str(record["package_address"]),
            )
            active.append(identity_safe({
                "package_id": record["package_id"],
                "package_version": record["package_version"],
                "package_address": record["package_address"],
                "contract_id": record["contract_id"],
                "title": record.get("title"),
                "category": record.get("category"),
                "author_particular": (
                    author.get("particular")
                    if isinstance(author, dict)
                    else None
                ),
                "shareable": True,
            }))
        active.sort(
            key=lambda item: (
                str(item["package_id"]),
                str(item["package_address"]),
            )
        )
        return active

    def active_exact(
        self,
        *,
        package_id: str,
        package_address: str,
    ) -> dict[str, Any] | None:
        for item in self.active():
            if (
                item["package_id"] == package_id
                and item["package_address"] == package_address
            ):
                return item
        return None


def _advert_body(advert: dict[str, Any]) -> dict[str, Any]:
    signing = advert.get("signing") or {}
    return identity_safe({
        "kind": advert.get("kind"),
        "version": advert.get("version"),
        "node_id": advert.get("node_id"),
        "particular": advert.get("particular"),
        "public_key": normalize_public_jwk(advert.get("public_key") or {}),
        "exchange_port": advert.get("exchange_port"),
        "parcel_port": advert.get("parcel_port"),
        "packages": advert.get("packages"),
        "issued_at": advert.get("issued_at"),
        "ttl_seconds": advert.get("ttl_seconds"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": normalize_public_jwk(signing.get("public_key") or {}),
            "domain": signing.get("domain"),
        },
    })


def derive_advert_id(advert: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        ADVERT_ID_DOMAIN + jcs_bytes(_advert_body(advert))
    ).hexdigest()
    return "ghot-grammar-exchange-advert-v0:" + digest


def advert_signature_bytes(advert: dict[str, Any]) -> bytes:
    body = _advert_body(advert)
    return ADVERT_SIGNATURE_DOMAIN + jcs_bytes({
        "advert_id": derive_advert_id(advert),
        **body,
    })


def make_exchange_advert(
    *,
    root: Path | None = None,
    exchange_port: int = HTTP_PORT,
    parcel_port: int = 7792,
    ttl_seconds: int = 15,
    issued_at: str | None = None,
) -> dict[str, Any]:
    state_root = root or ROOT
    signer = IdentityKey.load_or_create(
        state_root / "identity" / "body-p256.pem"
    )
    packages = GrammarShareStore(state_root).active()
    if len(packages) > MAX_ADVERT_PACKAGES:
        packages = packages[:MAX_ADVERT_PACKAGES]
    public_key = signer.public_jwk()
    advert = {
        "kind": ADVERT_KIND,
        "version": ADVERT_VERSION,
        "advert_id": "",
        "node_id": _node_id_at(state_root),
        "particular": signer.particular(),
        "public_key": public_key,
        "exchange_port": int(exchange_port),
        "parcel_port": int(parcel_port),
        "packages": packages,
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
    advert["signing"]["signature"] = signer.sign(
        advert_signature_bytes(advert)
    )
    return advert


def advert_is_fresh(
    advert: dict[str, Any],
    *,
    at: float | None = None,
) -> bool:
    return _fresh(
        str(advert.get("issued_at") or ""),
        int(advert.get("ttl_seconds") or 0),
        at=at,
    )


def verify_exchange_advert(advert: dict[str, Any]) -> bool:
    try:
        if advert.get("kind") != ADVERT_KIND:
            return False
        if advert.get("version") != ADVERT_VERSION:
            return False
        if not isinstance(advert.get("exchange_port"), int):
            return False
        if not isinstance(advert.get("parcel_port"), int):
            return False
        packages = advert.get("packages")
        if not isinstance(packages, list) or len(packages) > MAX_ADVERT_PACKAGES:
            return False
        seen = set()
        for item in packages:
            if not isinstance(item, dict):
                return False
            key = (item.get("package_id"), item.get("package_address"))
            if key in seen:
                return False
            seen.add(key)
            if not isinstance(item.get("package_id"), str):
                return False
            address = item.get("package_address")
            if (
                not isinstance(address, str)
                or not address.startswith("sha256:")
            ):
                return False
            if item.get("shareable") is not True:
                return False
        public_key = normalize_public_jwk(advert.get("public_key") or {})
        signing = advert.get("signing") or {}
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
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            advert_signature_bytes(advert),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def _request_body(request: dict[str, Any]) -> dict[str, Any]:
    signing = request.get("signing") or {}
    requester = request.get("requester") or {}
    return identity_safe({
        "kind": request.get("kind"),
        "version": request.get("version"),
        "target_particular": request.get("target_particular"),
        "nonce": request.get("nonce"),
        "package_id": request.get("package_id"),
        "package_address": request.get("package_address"),
        "requester": {
            "node_id": requester.get("node_id"),
            "particular": requester.get("particular"),
            "public_key": normalize_public_jwk(
                requester.get("public_key") or {}
            ),
            "return_parcel_port": requester.get("return_parcel_port"),
        },
        "created_at": request.get("created_at"),
        "ttl_seconds": request.get("ttl_seconds"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": normalize_public_jwk(signing.get("public_key") or {}),
            "domain": signing.get("domain"),
        },
    })


def derive_request_id(request: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        REQUEST_ID_DOMAIN + jcs_bytes(_request_body(request))
    ).hexdigest()
    return "ghot-grammar-exchange-request-v0:" + digest


def request_signature_bytes(request: dict[str, Any]) -> bytes:
    body = _request_body(request)
    return REQUEST_SIGNATURE_DOMAIN + jcs_bytes({
        "request_id": derive_request_id(request),
        **body,
    })


def make_exchange_request(
    *,
    root: Path | None,
    advert: dict[str, Any],
    package_id: str,
    package_address: str,
    return_parcel_port: int = 7792,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    if not verify_exchange_advert(advert) or not advert_is_fresh(advert):
        raise ValueError("source exchange advert is invalid or stale")
    if not any(
        item.get("package_id") == package_id
        and item.get("package_address") == package_address
        for item in advert.get("packages") or []
    ):
        raise ValueError("package is not currently advertised as shareable")
    state_root = root or ROOT
    signer = IdentityKey.load_or_create(
        state_root / "identity" / "body-p256.pem"
    )
    public_key = signer.public_jwk()
    request = {
        "kind": REQUEST_KIND,
        "version": REQUEST_VERSION,
        "request_id": "",
        "target_particular": advert["particular"],
        "nonce": f"grammar-request-{uuid.uuid4()}",
        "package_id": package_id,
        "package_address": package_address,
        "requester": {
            "node_id": _node_id_at(state_root),
            "particular": signer.particular(),
            "public_key": public_key,
            "return_parcel_port": int(return_parcel_port),
        },
        "created_at": timestamp_now(),
        "ttl_seconds": min(int(ttl_seconds), MAX_REQUEST_TTL),
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": public_key,
            "signature": "",
            "domain": REQUEST_SIGNING_DOMAIN,
        },
    }
    request["request_id"] = derive_request_id(request)
    request["signing"]["signature"] = signer.sign(
        request_signature_bytes(request)
    )
    return request


def request_is_fresh(
    request: dict[str, Any],
    *,
    at: float | None = None,
) -> bool:
    return _fresh(
        str(request.get("created_at") or ""),
        int(request.get("ttl_seconds") or 0),
        at=at,
    )


def verify_exchange_request(request: dict[str, Any]) -> bool:
    try:
        if request.get("kind") != REQUEST_KIND:
            return False
        if request.get("version") != REQUEST_VERSION:
            return False
        requester = request.get("requester") or {}
        if not isinstance(request.get("nonce"), str) or not request.get("nonce"):
            return False
        public_key = normalize_public_jwk(
            requester.get("public_key") or {}
        )
        if requester.get("particular") != particular_for_public_key(public_key):
            return False
        if not isinstance(requester.get("node_id"), str):
            return False
        port = requester.get("return_parcel_port")
        if not isinstance(port, int) or port <= 0 or port > 65535:
            return False
        address = request.get("package_address")
        if (
            not isinstance(address, str)
            or not address.startswith("sha256:")
        ):
            return False
        signing = request.get("signing") or {}
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != REQUEST_SIGNING_DOMAIN:
            return False
        if normalize_public_jwk(signing.get("public_key") or {}) != public_key:
            return False
        if request.get("request_id") != derive_request_id(request):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            request_signature_bytes(request),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


class GrammarRequestInbox:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.base = self.root / "grammar-exchange"
        self.requests_dir = self.base / "requests"
        self.raw_dir = self.base / "raw-requests"
        self.offers_dir = self.base / "offers"
        self.outgoing_dir = self.base / "outgoing"
        self.signer = IdentityKey.load_or_create(
            self.root / "identity" / "body-p256.pem"
        )
        self.node_id = _node_id_at(self.root)

    def _request_path(self, request_id: str) -> Path:
        return self.requests_dir / f"{_safe_name(request_id)}.json"

    def _raw_path(self, request_id: str) -> Path:
        return self.raw_dir / f"{_safe_name(request_id)}.json"

    def _load(self, request_id: str) -> dict[str, Any]:
        path = self._request_path(request_id)
        if not path.exists():
            raise ValueError("unknown grammar exchange request")
        return _read_object(path)

    def _raw(self, request_id: str) -> dict[str, Any]:
        path = self._raw_path(request_id)
        if not path.exists():
            raise ValueError("raw grammar exchange request missing")
        request = _read_object(path)
        if not verify_exchange_request(request):
            raise ValueError("stored grammar request no longer verifies")
        return request

    def receive(
        self,
        request: dict[str, Any],
        *,
        observed_ip: str,
    ) -> dict[str, Any]:
        if not verify_exchange_request(request):
            raise ValueError("invalid grammar exchange request")
        if not request_is_fresh(request):
            raise ValueError("grammar exchange request is stale")
        if request.get("target_particular") != self.signer.particular():
            raise ValueError("grammar exchange request targets another body")
        share = GrammarShareStore(self.root).active_exact(
            package_id=str(request["package_id"]),
            package_address=str(request["package_address"]),
        )
        if share is None:
            raise ValueError("requested package is not currently shared")

        path = self._request_path(request["request_id"])
        if path.exists():
            record = self._load(request["request_id"])
            return self._receipt(
                request=request,
                record=record,
                duplicate=True,
            )

        _write_atomic(self._raw_path(request["request_id"]), request)
        record = {
            "kind": "ghot.grammar.exchange.request-inbox",
            "version": "0",
            "request_id": request["request_id"],
            "package_id": request["package_id"],
            "package_address": request["package_address"],
            "requester_node_id": request["requester"]["node_id"],
            "requester_particular": request["requester"]["particular"],
            "requester_observed_ip": observed_ip,
            "return_parcel_port": request["requester"]["return_parcel_port"],
            "status": "REQUESTED",
            "received_at": timestamp_now(),
            "updated_at": timestamp_now(),
            "offer_record": None,
            "note": None,
        }
        _write_atomic(path, record)
        return self._receipt(
            request=request,
            record=record,
            duplicate=False,
        )

    def _receipt(
        self,
        *,
        request: dict[str, Any],
        record: dict[str, Any],
        duplicate: bool,
    ) -> dict[str, Any]:
        value = {
            "schema": "relatte.receipt/v0",
            "receipt_id": "",
            "crossing_id": request["request_id"],
            "world_id": f"ghot-node:{self.node_id}",
            "receiver_particular": self.signer.particular(),
            "kind": "REQUESTED",
            "semantic_effect": "none",
            "contract_ref": CONTRACT_REF,
            "pre_state_ref": None,
            "post_state_ref": semantic_address(identity_safe(record)),
            "descendant_refs": [],
            "residual_refs": [],
            "note": "grammar request recorded; no package crossed",
            "created_at": timestamp_now(),
            "extensions": {
                "ghot_profile": "grammar-exchange/v0",
                "request_id": request["request_id"],
                "package_id": request["package_id"],
                "package_address": request["package_address"],
                "duplicate_request": duplicate,
                "package_crossed": False,
                "network_offer": False,
            },
            "signing": {
                "algorithm": "",
                "public_key": {},
                "signature": "",
                "domain": "",
            },
        }
        return sign_receipt(value, self.signer)

    def list(self) -> list[dict[str, Any]]:
        if not self.requests_dir.is_dir():
            return []
        result = []
        for path in sorted(self.requests_dir.glob("*.json")):
            try:
                result.append(_read_object(path))
            except Exception:
                continue
        return result

    def decline(
        self,
        request_id: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        record = self._load(request_id)
        if record["status"] == "OFFERED":
            raise ValueError("offered request cannot later be declined")
        if record["status"] == "DECLINED":
            return record
        record["status"] = "DECLINED"
        record["updated_at"] = timestamp_now()
        record["note"] = note
        _write_atomic(self._request_path(request_id), record)
        return record

    def _installed_package(
        self,
        package_id: str,
        package_address: str,
    ) -> dict[str, Any]:
        for item in MergePluginStore(self.root).list_installed():
            if (
                item.get("package_id") == package_id
                and item.get("package_address") == package_address
            ):
                package = item.get("package")
                if isinstance(package, dict):
                    return package
        raise ValueError("requested package is no longer installed at that address")

    def _verify_return_porch(
        self,
        *,
        observed_ip: str,
        port: int,
        expected_particular: str,
    ) -> str:
        base_url = f"http://{observed_ip}:{port}"
        with urllib.request.urlopen(
            base_url + "/merge-plugin-packages",
            timeout=5,
        ) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("requester parcel porch did not return an object")
        if value.get("receiver_particular") != expected_particular:
            raise ValueError(
                "requester return porch particular does not match signed request"
            )
        if value.get("install_over_network") is not False:
            raise ValueError("requester porch advertises unsafe network install")
        return base_url

    def offer(
        self,
        request_id: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        record = self._load(request_id)
        if record["status"] == "DECLINED":
            raise ValueError("declined request cannot be offered")
        if record["status"] == "OFFERED":
            offer_path = self.offers_dir / f"{_safe_name(request_id)}.json"
            return _read_object(offer_path)

        request = self._raw(request_id)
        if not request_is_fresh(request):
            raise ValueError("grammar request expired before local offer")
        share = GrammarShareStore(self.root).active_exact(
            package_id=record["package_id"],
            package_address=record["package_address"],
        )
        if share is None:
            raise ValueError("requested package is no longer explicitly shared")

        package = self._installed_package(
            record["package_id"],
            record["package_address"],
        )
        return_url = self._verify_return_porch(
            observed_ip=record["requester_observed_ip"],
            port=int(record["return_parcel_port"]),
            expected_particular=record["requester_particular"],
        )
        author = find_author_for_installed_package(
            self.root,
            package_id=record["package_id"],
            package_address=record["package_address"],
        )
        bundle = MergePluginParcelExporter(self.root).export(
            package,
            target_particular=record["requester_particular"],
            author=author,
        )
        held_receipt = send_bundle(bundle, return_url)
        if held_receipt.get("kind") != "HELD":
            raise RuntimeError("requester did not HOLD offered package parcel")
        offer = {
            "kind": "ghot.grammar.exchange.offer",
            "version": "0",
            "request_id": request_id,
            "package_id": record["package_id"],
            "package_address": record["package_address"],
            "parcel_id": bundle["parcel"]["parcel_id"],
            "parcel_address": bundle["parcel"]["parcel_address"],
            "crossing_id": bundle["crossing"]["crossing_id"],
            "requester_particular": record["requester_particular"],
            "return_url": return_url,
            "receiver_receipt_id": held_receipt["receipt_id"],
            "author_particular": (
                (bundle["parcel"].get("author") or {}).get("particular")
            ),
            "offered_at": timestamp_now(),
            "note": note,
            "installed_remotely": False,
        }
        self.offers_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(
            self.offers_dir / f"{_safe_name(request_id)}.json",
            offer,
        )
        record["status"] = "OFFERED"
        record["updated_at"] = timestamp_now()
        record["offer_record"] = semantic_address(identity_safe(offer))
        record["note"] = note
        _write_atomic(self._request_path(request_id), record)
        return offer


def fetch_exchange_advert(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(
        url.rstrip("/") + "/grammar-exchange",
        timeout=5,
    ) as response:
        value = json.loads(response.read().decode("utf-8"))
    if (
        not isinstance(value, dict)
        or not verify_exchange_advert(value)
        or not advert_is_fresh(value)
    ):
        raise RuntimeError("exchange endpoint did not return a valid fresh advert")
    return value


def send_request(
    *,
    source_url: str,
    package_id: str,
    package_address: str,
    root: Path | None = None,
    return_parcel_port: int = 7792,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    advert = fetch_exchange_advert(source_url)
    request = make_exchange_request(
        root=root,
        advert=advert,
        package_id=package_id,
        package_address=package_address,
        return_parcel_port=return_parcel_port,
        ttl_seconds=ttl_seconds,
    )
    data = json.dumps(request).encode("utf-8")
    req = urllib.request.Request(
        source_url.rstrip("/") + "/grammar-request",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        receipt = json.loads(response.read().decode("utf-8"))
    if not isinstance(receipt, dict) or not verify_receipt(receipt):
        raise RuntimeError("grammar request receipt failed verification")
    if receipt.get("crossing_id") != request["request_id"]:
        raise RuntimeError("grammar request receipt id mismatch")
    state_root = root or ROOT
    outgoing = {
        "kind": "ghot.grammar.exchange.outgoing-request",
        "version": "0",
        "request": request,
        "source_url": source_url.rstrip("/"),
        "receipt": receipt,
        "requested_at": timestamp_now(),
    }
    path = (
        state_root
        / "grammar-exchange"
        / "outgoing"
        / f"{_safe_name(request['request_id'])}.json"
    )
    _write_atomic(path, outgoing)
    return outgoing


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
            response = {
                "kind": HERE_MAGIC,
                "version": "0",
                "advert": advert_factory(),
            }
            sock.sendto(json.dumps(response).encode("utf-8"), address)
    finally:
        sock.close()


def discover_exchanges(
    timeout: float = 2.0,
    *,
    port: int = DISCOVERY_PORT,
    host: str = "255.255.255.255",
) -> list[dict[str, Any]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.25)
    sock.bind(("", 0))
    request = {
        "kind": DISCOVERY_MAGIC,
        "version": "0",
        "nonce": f"grammar-exchange-{uuid.uuid4()}",
    }
    sock.sendto(
        json.dumps(request).encode("utf-8"),
        (host, port),
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
        if (
            not isinstance(advert, dict)
            or not verify_exchange_advert(advert)
            or not advert_is_fresh(advert)
        ):
            continue
        particular = str(advert["particular"])
        seen[particular] = {
            "advert": advert,
            "address": address[0],
            "exchange_url": f"http://{address[0]}:{advert['exchange_port']}",
        }
    sock.close()
    return [
        seen[key]
        for key in sorted(seen)
    ]


def inventory(root: Path | None = None) -> dict[str, Any]:
    state_root = root or ROOT
    installed = MergePluginStore(state_root).list_installed()
    held = MergePluginParcelInbox(state_root).list()
    shares = GrammarShareStore(state_root)
    return {
        "kind": "ghot.grammar.exchange.table",
        "version": "0",
        "installed": [
            {
                "package_id": item.get("package_id"),
                "package_version": item.get("package_version"),
                "package_address": item.get("package_address"),
                "contract_id": item.get("contract_id"),
                "shareable": bool(
                    shares.active_exact(
                        package_id=str(item.get("package_id")),
                        package_address=str(item.get("package_address")),
                    )
                ),
            }
            for item in installed
        ],
        "held_foreign": [
            {
                "parcel_id": item.get("parcel_id"),
                "package_id": item.get("package_id"),
                "package_version": item.get("package_version"),
                "package_address": item.get("package_address"),
                "author_particular": item.get("author_particular"),
                "author_signature_status": item.get("author_signature_status"),
                "status": item.get("status"),
            }
            for item in held
        ],
        "declared_shares": shares.declared(),
        "active_shares": shares.active(),
    }


def exchange_handler(
    root: Path,
    *,
    exchange_port: int,
    parcel_port: int,
) -> type[BaseHTTPRequestHandler]:
    inbox = GrammarRequestInbox(root)

    class Handler(BaseHTTPRequestHandler):
        server_version = "GHoTGrammarExchange/0"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send(self, status: int, value: Any) -> None:
            raw = json.dumps(value, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path == "/grammar-exchange":
                self._send(
                    200,
                    make_exchange_advert(
                        root=root,
                        exchange_port=exchange_port,
                        parcel_port=parcel_port,
                    ),
                )
                return
            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path != "/grammar-request":
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 256 * 1024:
                    raise ValueError("invalid grammar request size")
                value = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("grammar request must be an object")
                receipt = inbox.receive(
                    value,
                    observed_ip=self.client_address[0],
                )
                self._send(202, receipt)
            except Exception as exc:
                self._send(
                    400,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )

    return Handler


class GrammarExchangeService:
    def __init__(
        self,
        *,
        root: Path | None = None,
        host: str = "0.0.0.0",
        port: int = HTTP_PORT,
        discovery_port: int = DISCOVERY_PORT,
        parcel_port: int = 7792,
    ) -> None:
        self.root = root or ROOT
        self.host = host
        self.port = port
        self.discovery_port = discovery_port
        self.parcel_port = parcel_port
        self.stop = threading.Event()
        self.server: ThreadingHTTPServer | None = None
        self.http_thread: threading.Thread | None = None
        self.discovery_thread: threading.Thread | None = None

    def advert(self) -> dict[str, Any]:
        live_port = (
            self.server.server_port
            if self.server is not None
            else self.port
        )
        return make_exchange_advert(
            root=self.root,
            exchange_port=live_port,
            parcel_port=self.parcel_port,
        )

    def start(self) -> None:
        self.server = ThreadingHTTPServer(
            (self.host, self.port),
            exchange_handler(
                self.root,
                exchange_port=self.port,
                parcel_port=self.parcel_port,
            ),
        )
        # Rebuild handler if port 0 selected so GET advert reports real port.
        if self.port == 0:
            self.server.server_close()
            self.port = self.server.server_port
            self.server = ThreadingHTTPServer(
                (self.host, self.port),
                exchange_handler(
                    self.root,
                    exchange_port=self.port,
                    parcel_port=self.parcel_port,
                ),
            )
        self.http_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.discovery_thread = threading.Thread(
            target=discovery_responder,
            args=(self.advert, self.stop),
            kwargs={"port": self.discovery_port},
            daemon=True,
        )
        self.http_thread.start()
        self.discovery_thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.server is not None:
            try:
                self.server.shutdown()
            except OSError:
                pass
            self.server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover, request, and explicitly offer shareable merge grammars."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inventory")

    share = sub.add_parser("share")
    share.add_argument("package_id")

    unshare = sub.add_parser("unshare")
    unshare.add_argument("package_id")

    sub.add_parser("shares")

    scan = sub.add_parser("scan")
    scan.add_argument("--timeout", type=float, default=2.0)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=HTTP_PORT)
    serve.add_argument("--discovery-port", type=int, default=DISCOVERY_PORT)
    serve.add_argument("--parcel-port", type=int, default=7792)

    request = sub.add_parser("request")
    request.add_argument("source_url")
    request.add_argument("package_id")
    request.add_argument("package_address")
    request.add_argument("--return-parcel-port", type=int, default=7792)
    request.add_argument("--ttl", type=int, default=300)

    sub.add_parser("requests")

    offer = sub.add_parser("offer")
    offer.add_argument("request_id")
    offer.add_argument("--note", default=None)

    decline = sub.add_parser("decline")
    decline.add_argument("request_id")
    decline.add_argument("--note", default=None)

    args = parser.parse_args()
    shares = GrammarShareStore()
    inbox = GrammarRequestInbox()

    if args.command == "inventory":
        print(json.dumps(inventory(), indent=2))
        return 0
    if args.command == "share":
        print(json.dumps(shares.share(args.package_id), indent=2))
        return 0
    if args.command == "unshare":
        removed = shares.unshare(args.package_id)
        print(json.dumps({
            "package_id": args.package_id,
            "share_removed": removed,
        }, indent=2))
        return 0 if removed else 1
    if args.command == "shares":
        print(json.dumps({
            "declared": shares.declared(),
            "active": shares.active(),
        }, indent=2))
        return 0
    if args.command == "scan":
        print(json.dumps(discover_exchanges(args.timeout), indent=2))
        return 0
    if args.command == "serve":
        service = GrammarExchangeService(
            host=args.host,
            port=args.port,
            discovery_port=args.discovery_port,
            parcel_port=args.parcel_port,
        )
        service.start()
        print(json.dumps({
            "event": "ghot.grammar.exchange.started",
            "http_port": service.server.server_port if service.server else args.port,
            "discovery_port": args.discovery_port,
            "parcel_port": args.parcel_port,
            "laws": [
                "INSTALLED != SHAREABLE",
                "DISCOVERY != REQUEST",
                "REQUEST != OFFER",
                "OFFER != INSTALLATION",
            ],
        }, indent=2))
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            service.close()
            return 0
    if args.command == "request":
        print(json.dumps(send_request(
            source_url=args.source_url,
            package_id=args.package_id,
            package_address=args.package_address,
            return_parcel_port=args.return_parcel_port,
            ttl_seconds=args.ttl,
        ), indent=2))
        return 0
    if args.command == "requests":
        print(json.dumps(inbox.list(), indent=2))
        return 0
    if args.command == "offer":
        print(json.dumps(
            inbox.offer(args.request_id, note=args.note),
            indent=2,
        ))
        return 0
    if args.command == "decline":
        print(json.dumps(
            inbox.decline(args.request_id, note=args.note),
            indent=2,
        ))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
