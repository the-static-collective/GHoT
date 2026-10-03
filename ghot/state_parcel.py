#!/usr/bin/env python3
"""Portable GHoT state parcels — Experiment 018.

A state parcel is a bounded, content-addressed JSON slice exported by one GHoT
BODY. It carries:
- source state kind/version/address;
- a bounded selector + payload;
- migration/version metadata;
- a BODY-signed export receipt;
- a signed reLATTE CrossingEnvelopeV0.

A receiving body may automatically HOLD a valid parcel. It may not automatically
ADMIT it. Owner-local dispositions are HOLD / ADMIT / REJECT / SCAR.

ADMIT stores the parcel in the receiver's local admitted corpus. It does not
rewrite canonical live state.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import urllib.request
import uuid
from pathlib import Path
from typing import Any

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
from state_migration import CURRENT_STATE, StateMigrator, semantic_address


PARCEL_KIND = "ghot.state.parcel"
PARCEL_VERSION = "0"
BUNDLE_KIND = "ghot.state.parcel.bundle"
BUNDLE_VERSION = "0"
INBOX_KIND = "ghot.state.parcel.inbox"
INBOX_VERSION = "0"

EXPORT_RECEIPT_KIND = "ghot.state.parcel.export-receipt"
EXPORT_RECEIPT_VERSION = "0"
EXPORT_RECEIPT_ID_DOMAIN = b"GHoT-StateParcelExportReceipt-v0|"
EXPORT_RECEIPT_SIGNATURE_DOMAIN = b"GHoT-StateParcelExportReceiptSignature-v0|"
EXPORT_RECEIPT_SIGNING_DOMAIN = "ghot.state-parcel-export-receipt-signature/v0"

CROSSING_SCHEMA = "relatte.crossing-envelope/v0"
RECEIPT_SCHEMA = "relatte.receipt/v0"
CAPABILITY_REF = "ghot.state-parcel/v0"
CONTRACT_REF = "ghot.state-parcel-inbox@0"

MAX_PAYLOAD_BYTES = 512 * 1024
DISPOSITIONS = {"HOLD", "ADMIT", "REJECT", "SCAR"}
TERMINAL_DISPOSITIONS = {"ADMIT", "REJECT", "SCAR"}


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


def _write_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative_state_path(root: Path, supplied: str) -> tuple[Path, str]:
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else root / raw
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("state source must remain inside GHOT_HOME") from exc
    if not resolved.is_file():
        raise ValueError(f"state source does not exist: {rel}")
    return resolved, rel.as_posix()


def select_pointer(value: Any, selector: str) -> Any:
    """Bounded RFC6901-style JSON Pointer. '$' selects the whole document."""
    if selector in {"", "$"}:
        return value
    if not selector.startswith("/"):
        raise ValueError("selector must be '$' or an RFC6901-style /pointer")
    current = value
    for raw in selector.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise ValueError(f"selector key not found: {token}")
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit():
                raise ValueError("list selector token must be a non-negative integer")
            index = int(token)
            if index >= len(current):
                raise ValueError("selector list index out of range")
            current = current[index]
        else:
            raise ValueError("selector descends through a scalar value")
    return current


def _parcel_identity_body(parcel: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": parcel.get("kind"),
        "version": parcel.get("version"),
        "created_at": parcel.get("created_at"),
        "source": parcel.get("source"),
        "target": parcel.get("target"),
        "payload": parcel.get("payload"),
        "migration": parcel.get("migration"),
    }


def derive_parcel_digest(parcel: dict[str, Any]) -> str:
    return hashlib.sha256(
        b"GHoT-StateParcel-v0|" + jcs_bytes(identity_safe(_parcel_identity_body(parcel)))
    ).hexdigest()


def derive_parcel_id(parcel: dict[str, Any]) -> str:
    return "ghot-state-parcel-v0:" + derive_parcel_digest(parcel)


def derive_parcel_address(parcel: dict[str, Any]) -> str:
    return "sha256:" + derive_parcel_digest(parcel)


def _export_receipt_body(receipt: dict[str, Any]) -> dict[str, Any]:
    signing = receipt.get("signing") or {}
    return {
        "kind": receipt.get("kind"),
        "version": receipt.get("version"),
        "parcel_id": receipt.get("parcel_id"),
        "parcel_address": receipt.get("parcel_address"),
        "payload_address": receipt.get("payload_address"),
        "source_state_address": receipt.get("source_state_address"),
        "source_particular": receipt.get("source_particular"),
        "target_particular": receipt.get("target_particular"),
        "exported_at": receipt.get("exported_at"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    }


def derive_export_receipt_id(receipt: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        EXPORT_RECEIPT_ID_DOMAIN
        + jcs_bytes(identity_safe(_export_receipt_body(receipt)))
    ).hexdigest()
    return "ghot-state-parcel-export-receipt-v0:" + digest


def export_receipt_signature_bytes(receipt: dict[str, Any]) -> bytes:
    body = identity_safe(_export_receipt_body(receipt))
    return EXPORT_RECEIPT_SIGNATURE_DOMAIN + jcs_bytes({
        "receipt_id": derive_export_receipt_id(receipt),
        **body,
    })


def sign_export_receipt(
    parcel: dict[str, Any],
    *,
    signer: IdentityKey,
) -> dict[str, Any]:
    receipt = {
        "kind": EXPORT_RECEIPT_KIND,
        "version": EXPORT_RECEIPT_VERSION,
        "receipt_id": "",
        "parcel_id": parcel["parcel_id"],
        "parcel_address": parcel["parcel_address"],
        "payload_address": parcel["payload"]["address"],
        "source_state_address": parcel["source"]["state_address"],
        "source_particular": parcel["source"]["particular"],
        "target_particular": parcel["target"]["particular"],
        "exported_at": timestamp_now(),
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": EXPORT_RECEIPT_SIGNING_DOMAIN,
        },
    }
    receipt["receipt_id"] = derive_export_receipt_id(receipt)
    receipt["signing"]["signature"] = signer.sign(
        export_receipt_signature_bytes(receipt)
    )
    return receipt


def verify_export_receipt(receipt: dict[str, Any]) -> bool:
    try:
        if (
            receipt.get("kind") != EXPORT_RECEIPT_KIND
            or receipt.get("version") != EXPORT_RECEIPT_VERSION
        ):
            return False
        signing = receipt.get("signing") or {}
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != EXPORT_RECEIPT_SIGNING_DOMAIN:
            return False
        public_key = signing.get("public_key") or {}
        if receipt.get("source_particular") != particular_for_public_key(public_key):
            return False
        if receipt.get("receipt_id") != derive_export_receipt_id(receipt):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            export_receipt_signature_bytes(receipt),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def migration_metadata(
    root: Path,
    *,
    state_kind: str | None,
    state_version: str | None,
) -> dict[str, Any]:
    receipts = StateMigrator(root).receipts()
    lineage = [
        item["receipt_id"]
        for item in receipts
        if item.get("verified") is True
        and item.get("state_kind") == state_kind
        and item.get("to_version") == state_version
    ]
    lineage.sort()
    return {
        "state_kind": state_kind,
        "state_version": state_version,
        "current_known_version": CURRENT_STATE.get(str(state_kind)),
        "migration_receipt_ids": lineage,
    }


def make_crossing_for_parcel(
    parcel: dict[str, Any],
    *,
    signer: IdentityKey,
    source_node_id: str,
) -> dict[str, Any]:
    target = parcel.get("target") or {}
    envelope = {
        "schema": CROSSING_SCHEMA,
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{source_node_id}",
        "source_history_head": parcel["source"]["state_address"],
        "parents": [],
        "declared_kind": "GHOT_STATE_PARCEL",
        "payload_refs": [parcel["parcel_address"]],
        "requested_effect": {
            "action": "OFFER_STATE",
            "parcel_id": parcel["parcel_id"],
            "requested_disposition": "HOLD",
        },
        "capability_ref": CAPABILITY_REF,
        "privacy_policy": {
            "transport": "trusted-lan-v0",
            "payload_encryption": False,
        },
        "audience_policy": {
            "target_particular": target.get("particular"),
        },
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "portable-state-parcel/v0",
            "parcel_address": parcel["parcel_address"],
            "payload_address": parcel["payload"]["address"],
            "export_receipt_id": parcel["export_receipt"]["receipt_id"],
            "source_verification_profile": "relatte.identity-signature/v0",
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
        if parcel.get("kind") != PARCEL_KIND or parcel.get("version") != PARCEL_VERSION:
            return False
        payload = parcel.get("payload")
        source = parcel.get("source")
        target = parcel.get("target")
        migration = parcel.get("migration")
        receipt = parcel.get("export_receipt")
        if not all(isinstance(item, dict) for item in [payload, source, target, migration, receipt]):
            return False

        value = payload.get("value")
        normalized = identity_safe(value)
        payload_bytes = jcs_bytes(normalized)
        if len(payload_bytes) > MAX_PAYLOAD_BYTES:
            return False
        if payload.get("size_bytes") != len(payload_bytes):
            return False
        if payload.get("address") != semantic_address(normalized):
            return False
        if parcel.get("parcel_id") != derive_parcel_id(parcel):
            return False
        if parcel.get("parcel_address") != derive_parcel_address(parcel):
            return False
        if not verify_export_receipt(receipt):
            return False
        if receipt.get("parcel_id") != parcel.get("parcel_id"):
            return False
        if receipt.get("parcel_address") != parcel.get("parcel_address"):
            return False
        if receipt.get("payload_address") != payload.get("address"):
            return False
        if receipt.get("source_state_address") != source.get("state_address"):
            return False
        if receipt.get("source_particular") != source.get("particular"):
            return False
        if receipt.get("target_particular") != target.get("particular"):
            return False
        return True
    except Exception:
        return False


def verify_bundle(bundle: dict[str, Any]) -> bool:
    try:
        if bundle.get("kind") != BUNDLE_KIND or bundle.get("version") != BUNDLE_VERSION:
            return False
        parcel = bundle.get("parcel")
        crossing = bundle.get("crossing")
        if not isinstance(parcel, dict) or not isinstance(crossing, dict):
            return False
        if not verify_parcel(parcel) or not verify_crossing(crossing):
            return False
        if crossing.get("declared_kind") != "GHOT_STATE_PARCEL":
            return False
        if crossing.get("capability_ref") != CAPABILITY_REF:
            return False
        if crossing.get("source_particular") != parcel["source"]["particular"]:
            return False
        if crossing.get("payload_refs") != [parcel["parcel_address"]]:
            return False
        effect = crossing.get("requested_effect") or {}
        if effect.get("action") != "OFFER_STATE":
            return False
        if effect.get("parcel_id") != parcel["parcel_id"]:
            return False
        audience = crossing.get("audience_policy") or {}
        if audience.get("target_particular") != parcel["target"]["particular"]:
            return False
        extensions = crossing.get("extensions") or {}
        if extensions.get("parcel_address") != parcel["parcel_address"]:
            return False
        if extensions.get("payload_address") != parcel["payload"]["address"]:
            return False
        return True
    except Exception:
        return False


class StateParcelExporter:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.signer = IdentityKey.load_or_create(
            self.root / "identity" / "body-p256.pem"
        )
        self.node_id = _node_id_at(self.root)

    def export(
        self,
        source_path: str,
        *,
        selector: str = "$",
        target_particular: str | None = None,
    ) -> dict[str, Any]:
        path, relative = _relative_state_path(self.root, source_path)
        source_value = _read_json(path)
        if not isinstance(source_value, (dict, list)):
            raise ValueError("state source must be a JSON object or array")

        selected = identity_safe(select_pointer(source_value, selector))
        encoded = jcs_bytes(selected)
        if len(encoded) > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"selected payload exceeds {MAX_PAYLOAD_BYTES} bytes"
            )

        state_kind = source_value.get("kind") if isinstance(source_value, dict) else None
        state_version = (
            source_value.get("version") if isinstance(source_value, dict) else None
        )

        parcel: dict[str, Any] = {
            "kind": PARCEL_KIND,
            "version": PARCEL_VERSION,
            "parcel_id": "",
            "parcel_address": "",
            "created_at": timestamp_now(),
            "source": {
                "node_id": self.node_id,
                "particular": self.signer.particular(),
                "state_path": relative,
                "state_kind": state_kind,
                "state_version": state_version,
                "state_address": semantic_address(identity_safe(source_value)),
            },
            "target": {
                "particular": target_particular,
            },
            "payload": {
                "selector": selector,
                "encoding": "identity-safe-json",
                "address": semantic_address(selected),
                "size_bytes": len(encoded),
                "value": selected,
            },
            "migration": migration_metadata(
                self.root,
                state_kind=state_kind,
                state_version=state_version,
            ),
            "export_receipt": {},
        }
        parcel["parcel_id"] = derive_parcel_id(parcel)
        parcel["parcel_address"] = derive_parcel_address(parcel)
        parcel["export_receipt"] = sign_export_receipt(
            parcel,
            signer=self.signer,
        )
        crossing = make_crossing_for_parcel(
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
            raise RuntimeError("new state parcel bundle failed local verification")
        return bundle


def _receipt_for_disposition(
    *,
    crossing: dict[str, Any],
    parcel: dict[str, Any],
    signer: IdentityKey,
    receiver_node_id: str,
    disposition: str,
    note: str | None,
    pre_ref: str | None,
    post_ref: str | None,
    descendant_refs: list[str] | None = None,
    duplicate: bool = False,
) -> dict[str, Any]:
    disposition = disposition.upper()
    kind_map = {
        "HOLD": "HELD",
        "ADMIT": "ADMITTED",
        "REJECT": "REJECTED",
        "SCAR": "SCARRED",
    }
    semantic_effect = (
        "local-state-change"
        if disposition in {"ADMIT", "SCAR"}
        else "none"
    )
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": "",
        "crossing_id": crossing.get("crossing_id"),
        "world_id": f"ghot-node:{receiver_node_id}",
        "receiver_particular": signer.particular(),
        "kind": kind_map[disposition],
        "semantic_effect": semantic_effect,
        "contract_ref": CONTRACT_REF,
        "pre_state_ref": pre_ref,
        "post_state_ref": post_ref,
        "descendant_refs": descendant_refs or [],
        "residual_refs": [],
        "note": note,
        "created_at": timestamp_now(),
        "extensions": identity_safe({
            "ghot_profile": "portable-state-parcel/v0",
            "parcel_id": parcel["parcel_id"],
            "parcel_address": parcel["parcel_address"],
            "payload_address": parcel["payload"]["address"],
            "source_particular": parcel["source"]["particular"],
            "target_particular": parcel["target"]["particular"],
            "disposition": disposition,
            "duplicate_crossing": duplicate,
            "admission_is_owner_local": True,
            "canonical_state_mutated": False,
        }),
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    return sign_receipt(receipt, signer)


def _ref(value: Any) -> str:
    return semantic_address(identity_safe(value))


class StateParcelInbox:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.base = self.root / "state-parcels"
        self.raw_dir = self.base / "raw"
        self.inbox_dir = self.base / "inbox"
        self.admitted_dir = self.base / "admitted"
        self.scars_dir = self.base / "scars"
        self.receipts_dir = self.base / "receipts"
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

    def _load_queue(self, parcel_id: str) -> dict[str, Any]:
        path = self._queue_path(parcel_id)
        if not path.exists():
            raise ValueError("unknown parcel_id")
        value = _read_json(path)
        if not isinstance(value, dict):
            raise ValueError("invalid parcel queue record")
        return value

    def _store_receipt(self, receipt: dict[str, Any]) -> None:
        _write_atomic(self._receipt_path(receipt["receipt_id"]), receipt)

    def _receipts_for(
        self,
        parcel_id: str,
        *,
        disposition: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.receipts_dir.is_dir():
            return []
        matches = []
        for path in sorted(self.receipts_dir.glob("*.json")):
            try:
                value = _read_json(path)
            except Exception:
                continue
            extensions = value.get("extensions") or {}
            if extensions.get("parcel_id") != parcel_id:
                continue
            if (
                disposition is not None
                and extensions.get("disposition") != disposition
            ):
                continue
            matches.append(value)
        return matches

    def receive(self, bundle: dict[str, Any]) -> dict[str, Any]:
        if not verify_bundle(bundle):
            raise ValueError("invalid state parcel bundle")
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
                "note": "parcel is addressed to another body particular",
                "created_at": timestamp_now(),
                "extensions": identity_safe({
                    "ghot_profile": "portable-state-parcel/v0",
                    "parcel_id": parcel["parcel_id"],
                    "reason": "target-particular-mismatch",
                    "canonical_state_mutated": False,
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
            receipt = _receipt_for_disposition(
                crossing=crossing,
                parcel=parcel,
                signer=self.signer,
                receiver_node_id=self.node_id,
                disposition=queue["status"],
                note="duplicate crossing; parcel state unchanged",
                pre_ref=_ref(queue),
                post_ref=_ref(queue),
                descendant_refs=(
                    [queue["materialized_ref"]]
                    if queue.get("materialized_ref")
                    else []
                ),
                duplicate=True,
            )
            self._store_receipt(receipt)
            return receipt

        _write_atomic(self._raw_path(parcel["parcel_id"]), bundle)
        queue = {
            "kind": INBOX_KIND,
            "version": INBOX_VERSION,
            "parcel_id": parcel["parcel_id"],
            "parcel_address": parcel["parcel_address"],
            "payload_address": parcel["payload"]["address"],
            "crossing_id": crossing["crossing_id"],
            "source_particular": parcel["source"]["particular"],
            "target_particular": target,
            "status": "HOLD",
            "received_at": timestamp_now(),
            "updated_at": timestamp_now(),
            "materialized_ref": None,
            "decision_note": None,
        }
        _write_atomic(queue_path, queue)
        receipt = _receipt_for_disposition(
            crossing=crossing,
            parcel=parcel,
            signer=self.signer,
            receiver_node_id=self.node_id,
            disposition="HOLD",
            note="valid parcel held for owner-local disposition",
            pre_ref=None,
            post_ref=_ref(queue),
        )
        self._store_receipt(receipt)
        return receipt

    def list(self) -> list[dict[str, Any]]:
        if not self.inbox_dir.is_dir():
            return []
        rows = []
        for path in sorted(self.inbox_dir.glob("*.json")):
            try:
                value = _read_json(path)
            except Exception:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def show(self, parcel_id: str) -> dict[str, Any]:
        queue = self._load_queue(parcel_id)
        raw = _read_json(self._raw_path(parcel_id))
        return {
            "queue": queue,
            "bundle": raw,
            "receipts": self._receipts_for(parcel_id),
        }

    def decide(
        self,
        parcel_id: str,
        disposition: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        disposition = disposition.upper()
        if disposition not in DISPOSITIONS:
            raise ValueError("disposition must be HOLD, ADMIT, REJECT, or SCAR")
        queue = self._load_queue(parcel_id)
        bundle = _read_json(self._raw_path(parcel_id))
        if not verify_bundle(bundle):
            raise ValueError("stored parcel bundle no longer verifies")
        parcel = bundle["parcel"]
        crossing = bundle["crossing"]

        current = str(queue.get("status") or "")
        if current in TERMINAL_DISPOSITIONS:
            if current == disposition:
                prior = self._receipts_for(parcel_id, disposition=disposition)
                if prior:
                    return prior[-1]
            raise ValueError(f"parcel already has terminal disposition {current}")

        if disposition == "HOLD":
            queue["updated_at"] = timestamp_now()
            queue["decision_note"] = note
            pre = _ref(self._load_queue(parcel_id))
            _write_atomic(self._queue_path(parcel_id), queue)
            receipt = _receipt_for_disposition(
                crossing=crossing,
                parcel=parcel,
                signer=self.signer,
                receiver_node_id=self.node_id,
                disposition="HOLD",
                note=note or "parcel remains held",
                pre_ref=pre,
                post_ref=_ref(queue),
            )
            self._store_receipt(receipt)
            return receipt

        pre_ref = _ref(queue)
        descendant_refs: list[str] = []
        materialized_ref: str | None = None

        if disposition == "ADMIT":
            admitted = {
                "kind": "ghot.state.parcel.admitted",
                "version": "0",
                "parcel_id": parcel_id,
                "admitted_at": timestamp_now(),
                "source": parcel["source"],
                "migration": parcel["migration"],
                "payload": parcel["payload"],
                "note": note,
                "canonical_state_mutated": False,
            }
            materialized_ref = _ref(admitted)
            _write_atomic(
                self.admitted_dir / f"{_safe_name(parcel_id)}.json",
                admitted,
            )
            descendant_refs.append(materialized_ref)

        elif disposition == "SCAR":
            scar = {
                "kind": "ghot.state.parcel.scar",
                "version": "0",
                "parcel_id": parcel_id,
                "scarred_at": timestamp_now(),
                "source": parcel["source"],
                "payload_address": parcel["payload"]["address"],
                "payload": parcel["payload"]["value"],
                "note": note,
                "active": False,
            }
            materialized_ref = _ref(scar)
            _write_atomic(
                self.scars_dir / f"{_safe_name(parcel_id)}.json",
                scar,
            )
            descendant_refs.append(materialized_ref)

        queue["status"] = disposition
        queue["updated_at"] = timestamp_now()
        queue["materialized_ref"] = materialized_ref
        queue["decision_note"] = note
        _write_atomic(self._queue_path(parcel_id), queue)

        receipt = _receipt_for_disposition(
            crossing=crossing,
            parcel=parcel,
            signer=self.signer,
            receiver_node_id=self.node_id,
            disposition=disposition,
            note=note,
            pre_ref=pre_ref,
            post_ref=_ref(queue),
            descendant_refs=descendant_refs,
        )
        self._store_receipt(receipt)
        return receipt

    def receipts(self) -> list[dict[str, Any]]:
        if not self.receipts_dir.is_dir():
            return []
        result = []
        for path in sorted(self.receipts_dir.glob("*.json")):
            try:
                receipt = _read_json(path)
            except Exception:
                continue
            result.append({
                **receipt,
                "verified": verify_receipt(receipt),
            })
        return result


def send_bundle(bundle: dict[str, Any], base_url: str) -> dict[str, Any]:
    if not verify_bundle(bundle):
        raise ValueError("refusing to send invalid state parcel bundle")
    url = base_url.rstrip("/") + "/state-parcel"
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
        raise RuntimeError("state parcel receiver did not return an object")
    if receipt.get("crossing_id") != bundle["crossing"]["crossing_id"]:
        raise RuntimeError("state parcel receipt crossing_id mismatch")
    if not verify_receipt(receipt):
        raise RuntimeError("state parcel receiver receipt failed signature verification")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Export, cross, and disposition GHoT state parcels.")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export")
    export.add_argument("source_path")
    export.add_argument("--selector", default="$")
    export.add_argument("--target-particular", default=None)
    export.add_argument("--out", default=None)

    verify = sub.add_parser("verify")
    verify.add_argument("bundle_file")

    send = sub.add_parser("send")
    send.add_argument("bundle_file")
    send.add_argument("base_url")

    receive = sub.add_parser("receive")
    receive.add_argument("bundle_file")

    sub.add_parser("inbox")

    show = sub.add_parser("show")
    show.add_argument("parcel_id")

    decide = sub.add_parser("decide")
    decide.add_argument("parcel_id")
    decide.add_argument("disposition", choices=sorted(DISPOSITIONS))
    decide.add_argument("--note", default=None)

    sub.add_parser("receipts")

    args = parser.parse_args()

    if args.command == "export":
        bundle = StateParcelExporter().export(
            args.source_path,
            selector=args.selector,
            target_particular=args.target_particular,
        )
        if args.out:
            out = Path(args.out).expanduser()
            _write_atomic(out, bundle)
            print(json.dumps({
                "bundle_file": str(out),
                "parcel_id": bundle["parcel"]["parcel_id"],
                "parcel_address": bundle["parcel"]["parcel_address"],
                "payload_address": bundle["parcel"]["payload"]["address"],
                "crossing_id": bundle["crossing"]["crossing_id"],
            }, indent=2))
        else:
            print(json.dumps(bundle, indent=2))
        return 0

    if args.command == "verify":
        bundle = _read_json(Path(args.bundle_file).expanduser())
        valid = isinstance(bundle, dict) and verify_bundle(bundle)
        print(json.dumps({"valid": valid}, indent=2))
        return 0 if valid else 1

    if args.command == "send":
        bundle = _read_json(Path(args.bundle_file).expanduser())
        if not isinstance(bundle, dict):
            raise SystemExit("bundle file must contain an object")
        print(json.dumps(send_bundle(bundle, args.base_url), indent=2))
        return 0

    inbox = StateParcelInbox()

    if args.command == "receive":
        bundle = _read_json(Path(args.bundle_file).expanduser())
        if not isinstance(bundle, dict):
            raise SystemExit("bundle file must contain an object")
        print(json.dumps(inbox.receive(bundle), indent=2))
        return 0

    if args.command == "inbox":
        print(json.dumps(inbox.list(), indent=2))
        return 0

    if args.command == "show":
        print(json.dumps(inbox.show(args.parcel_id), indent=2))
        return 0

    if args.command == "decide":
        print(json.dumps(
            inbox.decide(args.parcel_id, args.disposition, note=args.note),
            indent=2,
        ))
        return 0

    if args.command == "receipts":
        print(json.dumps(inbox.receipts(), indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
