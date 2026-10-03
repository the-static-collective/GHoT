#!/usr/bin/env python3
"""Portable declarative merge-plugin package parcels — Experiment 022.

A plugin package may cross between bodies without being remotely installed.

Transport:
  package -> plugin parcel -> signed reLATTE crossing -> remote HOLD

Receiver-local continuation:
  HOLD -> VALIDATE -> explicit INSTALL -> 021 BODY install receipt

The parcel may optionally carry an author signature over the exact package
content address. Author identity is independent from transport sender identity;
an unsigned package may still be transported, inspected, validated, and
explicitly installed locally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
import urllib.request
from pathlib import Path
from typing import Any

from lan_node import discover_peers
from merge_plugin import (
    MergePluginStore,
    package_address,
    run_conformance,
    validate_package,
    verify_install_receipt,
)
from reference_node import ROOT
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    identity_safe,
    jcs_bytes,
    particular_for_public_key,
    sign_crossing,
    sign_receipt,
    timestamp_now,
    unb64url,
    verify_crossing,
    verify_p256,
    verify_receipt,
)
from state_merge import MERGE_CONTRACTS
from state_migration import semantic_address


PARCEL_KIND = "ghot.merge-plugin.parcel"
PARCEL_VERSION = "0"
BUNDLE_KIND = "ghot.merge-plugin.parcel.bundle"
BUNDLE_VERSION = "0"
INBOX_KIND = "ghot.merge-plugin.parcel.inbox"
INBOX_VERSION = "0"

CROSSING_SCHEMA = "relatte.crossing-envelope/v0"
RECEIPT_SCHEMA = "relatte.receipt/v0"
CAPABILITY_REF = "ghot.merge-plugin-package/v0"
CONTRACT_REF = "ghot.merge-plugin-parcel-inbox@0"

AUTHOR_SIGNATURE_DOMAIN = "ghot.merge-plugin-author-signature/v0"
AUTHOR_SIGNATURE_BYTES_DOMAIN = b"GHoT-MergePluginAuthorSignature-v0|"

TERMINAL = {"INSTALLED", "REJECT"}
LOCAL_STATUSES = {"HOLD", "VALIDATED", "INSTALLED", "REJECT"}


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


def _author_body(author: dict[str, Any]) -> dict[str, Any]:
    signing = author.get("signing") or {}
    return {
        "kind": author.get("kind"),
        "version": author.get("version"),
        "package_id": author.get("package_id"),
        "package_version": author.get("package_version"),
        "package_address": author.get("package_address"),
        "particular": author.get("particular"),
        "signed_at": author.get("signed_at"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    }


def author_signature_bytes(author: dict[str, Any]) -> bytes:
    return AUTHOR_SIGNATURE_BYTES_DOMAIN + jcs_bytes(
        identity_safe(_author_body(author))
    )


def sign_package_author(
    package: dict[str, Any],
    signer: IdentityKey,
) -> dict[str, Any]:
    checked = validate_package(package)
    author = {
        "kind": "ghot.merge-plugin.author-signature",
        "version": "0",
        "package_id": checked["package_id"],
        "package_version": checked["package_version"],
        "package_address": checked["package_address"],
        "particular": signer.particular(),
        "signed_at": timestamp_now(),
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": AUTHOR_SIGNATURE_DOMAIN,
        },
    }
    author["signing"]["signature"] = signer.sign(
        author_signature_bytes(author)
    )
    return author


def verify_package_author(
    author: dict[str, Any] | None,
    package: dict[str, Any],
) -> bool | None:
    if author is None:
        return None
    try:
        checked = validate_package(package)
        if author.get("kind") != "ghot.merge-plugin.author-signature":
            return False
        if author.get("version") != "0":
            return False
        if author.get("package_id") != checked["package_id"]:
            return False
        if author.get("package_version") != checked["package_version"]:
            return False
        if author.get("package_address") != checked["package_address"]:
            return False
        signing = author.get("signing") or {}
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != AUTHOR_SIGNATURE_DOMAIN:
            return False
        public_key = signing.get("public_key") or {}
        if author.get("particular") != particular_for_public_key(public_key):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            author_signature_bytes(author),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def _parcel_identity_body(parcel: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": parcel.get("kind"),
        "version": parcel.get("version"),
        "created_at": parcel.get("created_at"),
        "source": parcel.get("source"),
        "target": parcel.get("target"),
        "package_id": parcel.get("package_id"),
        "package_version": parcel.get("package_version"),
        "package_address": parcel.get("package_address"),
        "package": parcel.get("package"),
        "author": parcel.get("author"),
    }


def parcel_digest(parcel: dict[str, Any]) -> str:
    return hashlib.sha256(
        b"GHoT-MergePluginParcel-v0|"
        + jcs_bytes(identity_safe(_parcel_identity_body(parcel)))
    ).hexdigest()


def derive_parcel_id(parcel: dict[str, Any]) -> str:
    return "ghot-merge-plugin-parcel-v0:" + parcel_digest(parcel)


def derive_parcel_address(parcel: dict[str, Any]) -> str:
    return "sha256:" + parcel_digest(parcel)


def make_crossing(
    parcel: dict[str, Any],
    *,
    signer: IdentityKey,
    source_node_id: str,
) -> dict[str, Any]:
    envelope = {
        "schema": CROSSING_SCHEMA,
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{source_node_id}",
        "source_history_head": parcel["package_address"],
        "parents": [],
        "declared_kind": "GHOT_MERGE_PLUGIN_PACKAGE",
        "payload_refs": [parcel["parcel_address"]],
        "requested_effect": {
            "action": "OFFER_MERGE_PLUGIN_PACKAGE",
            "parcel_id": parcel["parcel_id"],
            "requested_disposition": "HOLD",
        },
        "capability_ref": CAPABILITY_REF,
        "privacy_policy": {
            "transport": "trusted-lan-v0",
            "payload_encryption": False,
        },
        "audience_policy": {
            "target_particular": parcel["target"]["particular"],
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "portable-merge-plugin-package/v0",
            "parcel_address": parcel["parcel_address"],
            "package_id": parcel["package_id"],
            "package_address": parcel["package_address"],
            "author_particular": (
                (parcel.get("author") or {}).get("particular")
            ),
        },
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    return sign_crossing(identity_safe(envelope), signer)


def verify_parcel(parcel: dict[str, Any]) -> bool:
    try:
        if parcel.get("kind") != PARCEL_KIND:
            return False
        if parcel.get("version") != PARCEL_VERSION:
            return False
        package = parcel.get("package")
        if not isinstance(package, dict):
            return False
        checked = validate_package(package)
        if parcel.get("package_id") != checked["package_id"]:
            return False
        if parcel.get("package_version") != checked["package_version"]:
            return False
        if parcel.get("package_address") != checked["package_address"]:
            return False
        author = parcel.get("author")
        author_status = verify_package_author(author, package)
        if author is not None and author_status is not True:
            return False
        if parcel.get("parcel_id") != derive_parcel_id(parcel):
            return False
        if parcel.get("parcel_address") != derive_parcel_address(parcel):
            return False
        source = parcel.get("source") or {}
        target = parcel.get("target") or {}
        if not isinstance(source.get("particular"), str):
            return False
        if not isinstance(source.get("node_id"), str):
            return False
        target_particular = target.get("particular")
        if target_particular is not None and not isinstance(target_particular, str):
            return False
        return True
    except Exception:
        return False


def verify_bundle(bundle: dict[str, Any]) -> bool:
    try:
        if bundle.get("kind") != BUNDLE_KIND:
            return False
        if bundle.get("version") != BUNDLE_VERSION:
            return False
        parcel = bundle.get("parcel")
        crossing = bundle.get("crossing")
        if not isinstance(parcel, dict) or not isinstance(crossing, dict):
            return False
        if not verify_parcel(parcel):
            return False
        if not verify_crossing(crossing):
            return False
        if crossing.get("declared_kind") != "GHOT_MERGE_PLUGIN_PACKAGE":
            return False
        if crossing.get("capability_ref") != CAPABILITY_REF:
            return False
        if crossing.get("source_particular") != parcel["source"]["particular"]:
            return False
        if crossing.get("payload_refs") != [parcel["parcel_address"]]:
            return False
        effect = crossing.get("requested_effect") or {}
        if effect.get("action") != "OFFER_MERGE_PLUGIN_PACKAGE":
            return False
        if effect.get("parcel_id") != parcel["parcel_id"]:
            return False
        audience = crossing.get("audience_policy") or {}
        if audience.get("target_particular") != parcel["target"]["particular"]:
            return False
        ext = crossing.get("extensions") or {}
        if ext.get("parcel_address") != parcel["parcel_address"]:
            return False
        if ext.get("package_id") != parcel["package_id"]:
            return False
        if ext.get("package_address") != parcel["package_address"]:
            return False
        return True
    except Exception:
        return False


class MergePluginParcelExporter:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.signer = IdentityKey.load_or_create(
            self.root / "identity" / "body-p256.pem"
        )
        self.node_id = _node_id_at(self.root)

    def export(
        self,
        package: dict[str, Any],
        *,
        target_particular: str | None = None,
        author_sign: bool = False,
    ) -> dict[str, Any]:
        checked = validate_package(package)
        normalized = checked["normalized"]
        author = (
            sign_package_author(normalized, self.signer)
            if author_sign
            else None
        )
        parcel = {
            "kind": PARCEL_KIND,
            "version": PARCEL_VERSION,
            "parcel_id": "",
            "parcel_address": "",
            "created_at": timestamp_now(),
            "source": {
                "node_id": self.node_id,
                "particular": self.signer.particular(),
            },
            "target": {
                "particular": target_particular,
            },
            "package_id": checked["package_id"],
            "package_version": checked["package_version"],
            "package_address": checked["package_address"],
            "package": normalized,
            "author": author,
        }
        parcel["parcel_id"] = derive_parcel_id(parcel)
        parcel["parcel_address"] = derive_parcel_address(parcel)
        crossing = make_crossing(
            parcel,
            signer=self.signer,
            source_node_id=self.node_id,
        )
        bundle = {
            "kind": BUNDLE_KIND,
            "version": BUNDLE_VERSION,
            "parcel": parcel,
            "crossing": crossing,
        }
        if not verify_bundle(bundle):
            raise RuntimeError("new merge plugin parcel failed local verification")
        return bundle


def _receipt(
    *,
    crossing: dict[str, Any],
    parcel: dict[str, Any],
    signer: IdentityKey,
    node_id: str,
    disposition: str,
    note: str | None,
    pre_ref: str | None,
    post_ref: str | None,
    duplicate: bool = False,
    validation_address: str | None = None,
    install_receipt_id: str | None = None,
) -> dict[str, Any]:
    kind_map = {
        "HOLD": "HELD",
        "VALIDATED": "VALIDATED",
        "INSTALLED": "INSTALLED",
        "REJECT": "REJECTED",
    }
    semantic_effect = (
        "local-state-change"
        if disposition == "INSTALLED"
        else "none"
    )
    value = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": "",
        "crossing_id": crossing.get("crossing_id"),
        "world_id": f"ghot-node:{node_id}",
        "receiver_particular": signer.particular(),
        "kind": kind_map[disposition],
        "semantic_effect": semantic_effect,
        "contract_ref": CONTRACT_REF,
        "pre_state_ref": pre_ref,
        "post_state_ref": post_ref,
        "descendant_refs": (
            [install_receipt_id]
            if install_receipt_id
            else []
        ),
        "residual_refs": [],
        "note": note,
        "created_at": timestamp_now(),
        "extensions": identity_safe({
            "ghot_profile": "portable-merge-plugin-package/v0",
            "parcel_id": parcel["parcel_id"],
            "parcel_address": parcel["parcel_address"],
            "package_id": parcel["package_id"],
            "package_address": parcel["package_address"],
            "author_particular": (
                (parcel.get("author") or {}).get("particular")
            ),
            "author_signature_status": (
                "verified"
                if parcel.get("author")
                else "unsigned"
            ),
            "disposition": disposition,
            "duplicate_crossing": duplicate,
            "validation_address": validation_address,
            "install_receipt_id": install_receipt_id,
            "network_install": False,
        }),
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    return sign_receipt(value, signer)


def _ref(value: Any) -> str:
    return semantic_address(identity_safe(value))


class MergePluginParcelInbox:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.base = self.root / "merge-plugin-parcels"
        self.raw_dir = self.base / "raw"
        self.inbox_dir = self.base / "inbox"
        self.receipts_dir = self.base / "receipts"
        self.validation_dir = self.base / "validation"
        self.signer = IdentityKey.load_or_create(
            self.root / "identity" / "body-p256.pem"
        )
        self.node_id = _node_id_at(self.root)

    def _queue_path(self, parcel_id: str) -> Path:
        return self.inbox_dir / f"{_safe_name(parcel_id)}.json"

    def _raw_path(self, parcel_id: str) -> Path:
        return self.raw_dir / f"{_safe_name(parcel_id)}.json"

    def _receipt_path(self, receipt_id: str) -> Path:
        return self.receipts_dir / f"{_safe_name(receipt_id)}.json"

    def _validation_path(self, parcel_id: str) -> Path:
        return self.validation_dir / f"{_safe_name(parcel_id)}.json"

    def _load_queue(self, parcel_id: str) -> dict[str, Any]:
        path = self._queue_path(parcel_id)
        if not path.exists():
            raise ValueError("unknown merge plugin parcel")
        return _read_object(path)

    def _load_bundle(self, parcel_id: str) -> dict[str, Any]:
        path = self._raw_path(parcel_id)
        if not path.exists():
            raise ValueError("merge plugin parcel raw bundle missing")
        bundle = _read_object(path)
        if not verify_bundle(bundle):
            raise ValueError("stored merge plugin parcel no longer verifies")
        return bundle

    def _store_receipt(self, receipt: dict[str, Any]) -> None:
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(self._receipt_path(receipt["receipt_id"]), receipt)

    def receive(self, bundle: dict[str, Any]) -> dict[str, Any]:
        if not verify_bundle(bundle):
            raise ValueError("invalid merge plugin parcel bundle")
        parcel = bundle["parcel"]
        crossing = bundle["crossing"]
        target = parcel["target"].get("particular")

        if target is not None and target != self.signer.particular():
            receipt = {
                "schema": RECEIPT_SCHEMA,
                "receipt_id": "",
                "crossing_id": crossing["crossing_id"],
                "world_id": f"ghot-node:{self.node_id}",
                "receiver_particular": self.signer.particular(),
                "kind": "REFUSED",
                "semantic_effect": "none",
                "contract_ref": CONTRACT_REF,
                "pre_state_ref": None,
                "post_state_ref": None,
                "descendant_refs": [],
                "residual_refs": [],
                "note": "merge plugin parcel addressed to another body",
                "created_at": timestamp_now(),
                "extensions": identity_safe({
                    "ghot_profile": "portable-merge-plugin-package/v0",
                    "parcel_id": parcel["parcel_id"],
                    "package_id": parcel["package_id"],
                    "reason": "target-particular-mismatch",
                    "network_install": False,
                }),
                "signing": {
                    "algorithm": "",
                    "public_key": {},
                    "signature": "",
                    "domain": "",
                },
            }
            return sign_receipt(receipt, self.signer)

        queue_path = self._queue_path(parcel["parcel_id"])
        if queue_path.exists():
            queue = self._load_queue(parcel["parcel_id"])
            disposition = str(queue["status"])
            if disposition not in LOCAL_STATUSES:
                raise ValueError("invalid local merge plugin parcel status")
            receipt = _receipt(
                crossing=crossing,
                parcel=parcel,
                signer=self.signer,
                node_id=self.node_id,
                disposition=disposition,
                note="duplicate crossing; local package state unchanged",
                pre_ref=_ref(queue),
                post_ref=_ref(queue),
                duplicate=True,
                validation_address=queue.get("validation_address"),
                install_receipt_id=queue.get("install_receipt_id"),
            )
            self._store_receipt(receipt)
            return receipt

        _write_atomic(self._raw_path(parcel["parcel_id"]), bundle)
        queue = {
            "kind": INBOX_KIND,
            "version": INBOX_VERSION,
            "parcel_id": parcel["parcel_id"],
            "parcel_address": parcel["parcel_address"],
            "package_id": parcel["package_id"],
            "package_version": parcel["package_version"],
            "package_address": parcel["package_address"],
            "crossing_id": crossing["crossing_id"],
            "source_particular": parcel["source"]["particular"],
            "target_particular": target,
            "author_particular": (
                (parcel.get("author") or {}).get("particular")
            ),
            "author_signature_status": (
                "verified"
                if parcel.get("author")
                else "unsigned"
            ),
            "status": "HOLD",
            "received_at": timestamp_now(),
            "updated_at": timestamp_now(),
            "validation_address": None,
            "install_receipt_id": None,
            "decision_note": None,
        }
        _write_atomic(queue_path, queue)
        receipt = _receipt(
            crossing=crossing,
            parcel=parcel,
            signer=self.signer,
            node_id=self.node_id,
            disposition="HOLD",
            note="valid merge plugin package held for local inspection",
            pre_ref=None,
            post_ref=_ref(queue),
        )
        self._store_receipt(receipt)
        return receipt

    def list(self) -> list[dict[str, Any]]:
        if not self.inbox_dir.is_dir():
            return []
        result = []
        for path in sorted(self.inbox_dir.glob("*.json")):
            try:
                result.append(_read_object(path))
            except Exception:
                continue
        return result

    def show(self, parcel_id: str) -> dict[str, Any]:
        queue = self._load_queue(parcel_id)
        bundle = self._load_bundle(parcel_id)
        validation = None
        validation_path = self._validation_path(parcel_id)
        if validation_path.exists():
            validation = _read_object(validation_path)
        return {
            "queue": queue,
            "bundle": bundle,
            "validation": validation,
        }

    def validate_local(self, parcel_id: str) -> dict[str, Any]:
        queue = self._load_queue(parcel_id)
        if queue["status"] in TERMINAL:
            raise ValueError(
                f"merge plugin parcel already terminal: {queue['status']}"
            )
        bundle = self._load_bundle(parcel_id)
        parcel = bundle["parcel"]
        package = parcel["package"]
        checked = validate_package(package)
        conformance = run_conformance(package)
        report = {
            "kind": "ghot.merge-plugin.parcel.validation",
            "version": "0",
            "parcel_id": parcel_id,
            "parcel_address": parcel["parcel_address"],
            "package_id": checked["package_id"],
            "package_address": checked["package_address"],
            "author_signature_status": (
                "verified"
                if parcel.get("author")
                else "unsigned"
            ),
            "validated_at": timestamp_now(),
            "conformance": conformance,
            "installable": bool(conformance["passed"]),
        }
        validation_address = _ref(report)
        _write_atomic(self._validation_path(parcel_id), report)

        pre = _ref(queue)
        queue["status"] = "VALIDATED"
        queue["updated_at"] = timestamp_now()
        queue["validation_address"] = validation_address
        _write_atomic(self._queue_path(parcel_id), queue)

        receipt = _receipt(
            crossing=bundle["crossing"],
            parcel=parcel,
            signer=self.signer,
            node_id=self.node_id,
            disposition="VALIDATED",
            note="package validated locally; not installed",
            pre_ref=pre,
            post_ref=_ref(queue),
            validation_address=validation_address,
        )
        self._store_receipt(receipt)
        return {
            "validation": report,
            "receipt": receipt,
        }

    def install_local(
        self,
        parcel_id: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        queue = self._load_queue(parcel_id)
        if queue["status"] != "VALIDATED":
            raise ValueError(
                "merge plugin parcel must be explicitly VALIDATED before INSTALL"
            )
        bundle = self._load_bundle(parcel_id)
        parcel = bundle["parcel"]
        validation = _read_object(self._validation_path(parcel_id))
        if queue.get("validation_address") != _ref(validation):
            raise ValueError("validation report changed after validation")
        if validation.get("package_address") != parcel["package_address"]:
            raise ValueError("validation package address mismatch")
        if validation.get("installable") is not True:
            raise ValueError("validation did not declare package installable")

        store = MergePluginStore(self.root)
        install_receipt = store.install(
            parcel["package"],
            builtin_contract_ids=set(MERGE_CONTRACTS),
        )
        if not verify_install_receipt(install_receipt):
            raise RuntimeError("021 install receipt failed verification")

        pre = _ref(queue)
        queue["status"] = "INSTALLED"
        queue["updated_at"] = timestamp_now()
        queue["install_receipt_id"] = install_receipt["receipt_id"]
        queue["decision_note"] = note
        _write_atomic(self._queue_path(parcel_id), queue)

        receipt = _receipt(
            crossing=bundle["crossing"],
            parcel=parcel,
            signer=self.signer,
            node_id=self.node_id,
            disposition="INSTALLED",
            note=note or "validated package explicitly installed locally",
            pre_ref=pre,
            post_ref=_ref(queue),
            validation_address=queue.get("validation_address"),
            install_receipt_id=install_receipt["receipt_id"],
        )
        self._store_receipt(receipt)
        return {
            "install_receipt": install_receipt,
            "parcel_receipt": receipt,
        }

    def reject_local(
        self,
        parcel_id: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        queue = self._load_queue(parcel_id)
        if queue["status"] in TERMINAL:
            if queue["status"] == "REJECT":
                return self.show(parcel_id)
            raise ValueError("installed merge plugin parcel cannot be rejected")
        bundle = self._load_bundle(parcel_id)
        parcel = bundle["parcel"]
        pre = _ref(queue)
        queue["status"] = "REJECT"
        queue["updated_at"] = timestamp_now()
        queue["decision_note"] = note
        _write_atomic(self._queue_path(parcel_id), queue)
        receipt = _receipt(
            crossing=bundle["crossing"],
            parcel=parcel,
            signer=self.signer,
            node_id=self.node_id,
            disposition="REJECT",
            note=note or "merge plugin package rejected locally",
            pre_ref=pre,
            post_ref=_ref(queue),
            validation_address=queue.get("validation_address"),
        )
        self._store_receipt(receipt)
        return receipt

    def receipts(self) -> list[dict[str, Any]]:
        if not self.receipts_dir.is_dir():
            return []
        result = []
        for path in sorted(self.receipts_dir.glob("*.json")):
            try:
                receipt = _read_object(path)
            except Exception:
                continue
            result.append({
                **receipt,
                "verified": verify_receipt(receipt),
            })
        return result


def send_bundle(bundle: dict[str, Any], base_url: str) -> dict[str, Any]:
    if not verify_bundle(bundle):
        raise ValueError("refusing to send invalid merge plugin parcel")
    url = base_url.rstrip("/") + "/merge-plugin-package"
    data = json.dumps(bundle).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        receipt = json.loads(response.read().decode("utf-8"))
    if not isinstance(receipt, dict):
        raise RuntimeError("merge plugin receiver did not return an object")
    if receipt.get("crossing_id") != bundle["crossing"]["crossing_id"]:
        raise RuntimeError("merge plugin receipt crossing_id mismatch")
    if not verify_receipt(receipt):
        raise RuntimeError("merge plugin receiver receipt failed verification")
    return receipt


def send_bundle_to_node(
    bundle: dict[str, Any],
    selected_node_id: str,
    *,
    timeout: float = 2.0,
) -> dict[str, Any]:
    if not verify_bundle(bundle):
        raise ValueError("refusing to send invalid merge plugin parcel")
    peers = discover_peers(timeout)
    peer = next(
        (
            item
            for item in peers
            if item.get("node_id") == selected_node_id
        ),
        None,
    )
    if peer is None:
        raise RuntimeError("selected body is not currently discoverable")
    base_url = peer.get("state_parcel_url")
    if not isinstance(base_url, str) or not base_url:
        raise RuntimeError("selected body does not advertise a parcel porch")
    body_record = peer.get("body") or {}
    identity = body_record.get("identity") or {}
    discovered_particular = identity.get("particular")
    target_particular = bundle["parcel"]["target"].get("particular")
    if not isinstance(discovered_particular, str) or not discovered_particular:
        raise RuntimeError("selected body has no usable cryptographic identity")
    if target_particular != discovered_particular:
        raise RuntimeError(
            "plugin parcel target particular does not match discovered body"
        )
    return send_bundle(bundle, base_url)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cross declarative merge plugin packages without remote install."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export")
    export.add_argument("package_file")
    export.add_argument("--target-particular", default=None)
    export.add_argument("--author-sign", action="store_true")
    export.add_argument("--out", default=None)

    verify = sub.add_parser("verify")
    verify.add_argument("bundle_file")

    send = sub.add_parser("send")
    send.add_argument("bundle_file")
    send.add_argument("base_url")

    send_node = sub.add_parser("send-node")
    send_node.add_argument("bundle_file")
    send_node.add_argument("node_id")
    send_node.add_argument("--timeout", type=float, default=2.0)

    receive = sub.add_parser("receive")
    receive.add_argument("bundle_file")

    sub.add_parser("inbox")

    show = sub.add_parser("show")
    show.add_argument("parcel_id")

    validate = sub.add_parser("validate")
    validate.add_argument("parcel_id")

    install = sub.add_parser("install")
    install.add_argument("parcel_id")
    install.add_argument("--note", default=None)

    reject = sub.add_parser("reject")
    reject.add_argument("parcel_id")
    reject.add_argument("--note", default=None)

    sub.add_parser("receipts")

    args = parser.parse_args()

    if args.command == "export":
        package = _read_object(Path(args.package_file).expanduser())
        bundle = MergePluginParcelExporter().export(
            package,
            target_particular=args.target_particular,
            author_sign=args.author_sign,
        )
        if args.out:
            out = Path(args.out).expanduser()
            _write_atomic(out, bundle)
            print(json.dumps({
                "bundle_file": str(out),
                "parcel_id": bundle["parcel"]["parcel_id"],
                "parcel_address": bundle["parcel"]["parcel_address"],
                "package_id": bundle["parcel"]["package_id"],
                "package_address": bundle["parcel"]["package_address"],
                "author_signature_status": (
                    "verified"
                    if bundle["parcel"].get("author")
                    else "unsigned"
                ),
                "crossing_id": bundle["crossing"]["crossing_id"],
            }, indent=2))
        else:
            print(json.dumps(bundle, indent=2))
        return 0

    if args.command == "verify":
        bundle = _read_object(Path(args.bundle_file).expanduser())
        valid = verify_bundle(bundle)
        print(json.dumps({"valid": valid}, indent=2))
        return 0 if valid else 1

    if args.command == "send":
        bundle = _read_object(Path(args.bundle_file).expanduser())
        print(json.dumps(send_bundle(bundle, args.base_url), indent=2))
        return 0

    if args.command == "send-node":
        bundle = _read_object(Path(args.bundle_file).expanduser())
        print(json.dumps(
            send_bundle_to_node(
                bundle,
                args.node_id,
                timeout=args.timeout,
            ),
            indent=2,
        ))
        return 0

    inbox = MergePluginParcelInbox()

    if args.command == "receive":
        bundle = _read_object(Path(args.bundle_file).expanduser())
        print(json.dumps(inbox.receive(bundle), indent=2))
        return 0
    if args.command == "inbox":
        print(json.dumps(inbox.list(), indent=2))
        return 0
    if args.command == "show":
        print(json.dumps(inbox.show(args.parcel_id), indent=2))
        return 0
    if args.command == "validate":
        print(json.dumps(inbox.validate_local(args.parcel_id), indent=2))
        return 0
    if args.command == "install":
        print(json.dumps(
            inbox.install_local(args.parcel_id, note=args.note),
            indent=2,
        ))
        return 0
    if args.command == "reject":
        print(json.dumps(
            inbox.reject_local(args.parcel_id, note=args.note),
            indent=2,
        ))
        return 0
    if args.command == "receipts":
        print(json.dumps(inbox.receipts(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
