#!/usr/bin/env python3
"""GHoT boot presence / startup receipt — Experiment 016.

A startup manifest describes what woke.
A startup receipt proves that the current GHoT body key witnessed that manifest.
Neither object grants lease authority or proves future health.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from reference_node import ROOT, body, node_id
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    b64url,
    jcs_bytes,
    timestamp_now,
    unb64url,
    verify_p256,
)


MANIFEST_KIND = "ghot.boot.manifest"
MANIFEST_VERSION = "0"
RECEIPT_KIND = "ghot.startup.receipt"
RECEIPT_VERSION = "0"
RECEIPT_ID_DOMAIN = b"GHoT-StartupReceipt-v0|"
RECEIPT_SIGNATURE_DOMAIN = b"GHoT-StartupReceiptSignature-v0|"
RECEIPT_SIGNING_DOMAIN = "ghot.startup-receipt-signature/v0"

SUPPORTED_STATE = {
    "ghot.organ.state": {"0"},
    "ghot.field": {"0"},
}


def stable_json_bytes(value: Any) -> bytes:
    return jcs_bytes(value)


def sha256_address(value: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json_bytes(value)).hexdigest()


def repo_revision(repo_root: Path) -> dict[str, Any]:
    git = shutil.which("git")
    if git is None or not (repo_root / ".git").exists():
        return {
            "available": False,
            "commit": None,
            "dirty": None,
            "error": "git metadata unavailable",
        }
    try:
        commit = subprocess.run(
            [git, "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        ).stdout.strip()
        dirty_result = subprocess.run(
            [git, "-C", str(repo_root), "status", "--porcelain"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        )
        return {
            "available": True,
            "commit": commit,
            "dirty": bool(dirty_result.stdout.strip()),
            "error": None,
        }
    except Exception as exc:
        return {
            "available": False,
            "commit": None,
            "dirty": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def dependency_readiness() -> dict[str, Any]:
    required = {
        "python": {
            "available": True,
            "path": sys.executable,
            "version": platform.python_version(),
        },
        "openssl": {
            "available": shutil.which("openssl") is not None,
            "path": shutil.which("openssl"),
        },
    }
    optional_names = [
        "git",
        "ffmpeg",
        "ffprobe",
        "llama-cli",
        "whisper-cli",
        "piper",
        "magick",
    ]
    optional = {
        name: {
            "available": shutil.which(name) is not None,
            "path": shutil.which(name),
        }
        for name in optional_names
    }
    return {
        "required": required,
        "optional": optional,
        "required_ready": all(
            item.get("available") is True
            for item in required.values()
        ),
    }


def inspect_state(root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    paths = [
        root / "organ" / "state.v0.json",
        root / "field.v0.json",
    ]
    migration_required = False

    for path in paths:
        if not path.exists():
            checks.append({
                "path": str(path),
                "status": "absent",
                "kind": None,
                "version": None,
            })
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            checks.append({
                "path": str(path),
                "status": "invalid",
                "kind": None,
                "version": None,
                "error": f"{type(exc).__name__}: {exc}",
            })
            migration_required = True
            continue

        kind = value.get("kind") if isinstance(value, dict) else None
        version = value.get("version") if isinstance(value, dict) else None
        supported = (
            isinstance(kind, str)
            and isinstance(version, str)
            and version in SUPPORTED_STATE.get(kind, set())
        )
        checks.append({
            "path": str(path),
            "status": "compatible" if supported else "migration-required",
            "kind": kind,
            "version": version,
        })
        if not supported:
            migration_required = True

    return {
        "status": "migration-required" if migration_required else "compatible",
        "migration_required": migration_required,
        "checks": checks,
        "automatic_migrations_applied": [],
    }


def infer_boot_surface() -> dict[str, Any]:
    surface = os.environ.get("GHOT_BOOT_SURFACE", "direct")
    instance = os.environ.get("GHOT_BOOT_INSTANCE")
    return {
        "surface": surface,
        "instance": instance,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
    }


def health_from(
    *,
    manifest: dict[str, Any],
    runtime_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[dict[str, Any]] = []
    dependencies = manifest.get("dependencies") or {}
    state = manifest.get("state") or {}
    body_record = manifest.get("body") or {}
    identity = body_record.get("identity") or {}

    if dependencies.get("required_ready") is not True:
        reasons.append({
            "kind": "required-dependency-unavailable",
            "detail": "one or more required dependencies are unavailable",
        })
    if identity.get("available") is not True:
        reasons.append({
            "kind": "body-identity-unavailable",
            "detail": identity.get("error") or "body identity unavailable",
        })
    if state.get("migration_required") is True:
        reasons.append({
            "kind": "state-migration-required",
            "detail": "one or more durable state records require migration or repair",
        })

    services: dict[str, Any] = {}
    runtime_errors: list[Any] = []
    if isinstance(runtime_state, dict):
        services = runtime_state.get("services") or {}
        runtime_errors = runtime_state.get("errors") or []
        for name, service in services.items():
            if isinstance(service, dict) and service.get("state") == "failed":
                reasons.append({
                    "kind": "service-failed",
                    "service": name,
                    "detail": service.get("error"),
                })
        for item in runtime_errors:
            reasons.append({
                "kind": "runtime-error",
                "detail": item,
            })

    if any(
        reason["kind"] in {
            "required-dependency-unavailable",
            "body-identity-unavailable",
            "state-migration-required",
        }
        for reason in reasons
    ):
        status = "blocked"
    elif reasons:
        status = "degraded"
    else:
        status = "healthy"

    return {
        "kind": "ghot.health",
        "version": "0",
        "status": status,
        "observed_at": timestamp_now(),
        "node_id": manifest.get("node_id"),
        "particular": (body_record.get("identity") or {}).get("particular"),
        "boot_id": manifest.get("boot_id"),
        "cycle": runtime_state.get("cycle") if isinstance(runtime_state, dict) else None,
        "services": services,
        "reasons": reasons,
    }


def create_boot_manifest(
    *,
    root: Path | None = None,
    repo_root: Path | None = None,
    body_record: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    state_root = root or ROOT
    code_root = repo_root or Path(__file__).resolve().parents[1]
    record = body_record or body()
    manifest = {
        "kind": MANIFEST_KIND,
        "version": MANIFEST_VERSION,
        "boot_id": f"boot-{uuid.uuid4()}",
        "created_at": created_at or timestamp_now(),
        "node_id": record.get("node_id") or node_id(),
        "body": {
            "identity": record.get("identity"),
            "power": record.get("power"),
            "offers": record.get("offers"),
        },
        "code": {
            "repo_root": str(code_root),
            "entrypoint": str(code_root / "ghot" / "organ.py"),
            "python": sys.executable,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "revision": repo_revision(code_root),
        },
        "boot_surface": infer_boot_surface(),
        "state_home": str(state_root),
        "state": inspect_state(state_root),
        "dependencies": dependency_readiness(),
    }
    manifest["manifest_address"] = sha256_address(manifest)
    return manifest


def _receipt_body(receipt: dict[str, Any]) -> dict[str, Any]:
    signing = receipt.get("signing") or {}
    return {
        "kind": receipt.get("kind"),
        "version": receipt.get("version"),
        "boot_id": receipt.get("boot_id"),
        "manifest_address": receipt.get("manifest_address"),
        "node_id": receipt.get("node_id"),
        "particular": receipt.get("particular"),
        "created_at": receipt.get("created_at"),
        "initial_health": receipt.get("initial_health"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    }


def derive_startup_receipt_id(receipt: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        RECEIPT_ID_DOMAIN + stable_json_bytes(_receipt_body(receipt))
    ).hexdigest()
    return "ghot-startup-receipt-v0:" + digest


def startup_receipt_signature_bytes(receipt: dict[str, Any]) -> bytes:
    body = _receipt_body(receipt)
    return RECEIPT_SIGNATURE_DOMAIN + stable_json_bytes({
        "receipt_id": derive_startup_receipt_id(receipt),
        **body,
    })


def sign_startup_receipt(
    manifest: dict[str, Any],
    *,
    signer: IdentityKey,
) -> dict[str, Any]:
    identity = (manifest.get("body") or {}).get("identity") or {}
    particular = signer.particular()
    if identity.get("particular") != particular:
        raise ValueError("boot manifest identity does not match startup signer")
    receipt = {
        "kind": RECEIPT_KIND,
        "version": RECEIPT_VERSION,
        "receipt_id": "",
        "boot_id": manifest["boot_id"],
        "manifest_address": manifest["manifest_address"],
        "node_id": manifest["node_id"],
        "particular": particular,
        "created_at": timestamp_now(),
        "initial_health": health_from(manifest=manifest, runtime_state=None),
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": RECEIPT_SIGNING_DOMAIN,
        },
    }
    receipt["receipt_id"] = derive_startup_receipt_id(receipt)
    receipt["signing"]["signature"] = signer.sign(
        startup_receipt_signature_bytes(receipt)
    )
    return receipt


def verify_startup_receipt(receipt: dict[str, Any]) -> bool:
    try:
        signing = receipt.get("signing") or {}
        if receipt.get("kind") != RECEIPT_KIND or receipt.get("version") != RECEIPT_VERSION:
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != RECEIPT_SIGNING_DOMAIN:
            return False
        public_key = signing.get("public_key") or {}
        from relatte_identity import particular_for_public_key

        if receipt.get("particular") != particular_for_public_key(public_key):
            return False
        if receipt.get("receipt_id") != derive_startup_receipt_id(receipt):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            startup_receipt_signature_bytes(receipt),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


class PresenceStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.startup_root = self.root / "startup"
        self.manifest_path = self.startup_root / "manifest.v0.json"
        self.latest_receipt_path = self.startup_root / "receipt.v0.json"
        self.receipts_dir = self.startup_root / "receipts"

    def wake(
        self,
        *,
        repo_root: Path | None = None,
        body_record: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        manifest = create_boot_manifest(
            root=self.root,
            repo_root=repo_root,
            body_record=body_record,
        )
        _write_atomic(self.manifest_path, manifest)

        try:
            signer = IdentityKey.load_or_create(
                self.root / "identity" / "body-p256.pem"
            )
            receipt = sign_startup_receipt(manifest, signer=signer)
        except Exception as exc:
            failure = {
                "kind": "ghot.startup.receipt.failure",
                "version": "0",
                "boot_id": manifest["boot_id"],
                "manifest_address": manifest["manifest_address"],
                "observed_at": timestamp_now(),
                "error": f"{type(exc).__name__}: {exc}",
            }
            _write_atomic(
                self.startup_root / "receipt-failure.v0.json",
                failure,
            )
            if self.latest_receipt_path.exists():
                self.latest_receipt_path.unlink()
            return manifest, None

        _write_atomic(self.latest_receipt_path, receipt)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(
            self.receipts_dir / (
                receipt["receipt_id"].replace(":", "_") + ".json"
            ),
            receipt,
        )
        return manifest, receipt

    def manifest(self) -> dict[str, Any] | None:
        if not self.manifest_path.exists():
            return None
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    def receipt(self) -> dict[str, Any] | None:
        if not self.latest_receipt_path.exists():
            return None
        try:
            value = json.loads(
                self.latest_receipt_path.read_text(encoding="utf-8")
            )
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    def runtime_state(self) -> dict[str, Any] | None:
        path = self.root / "organ" / "state.v0.json"
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    def health(self) -> dict[str, Any]:
        manifest = self.manifest()
        if manifest is None:
            return {
                "kind": "ghot.health",
                "version": "0",
                "status": "blocked",
                "observed_at": timestamp_now(),
                "reasons": [{
                    "kind": "boot-manifest-missing",
                    "detail": "no startup manifest has been persisted",
                }],
            }
        health = health_from(
            manifest=manifest,
            runtime_state=self.runtime_state(),
        )
        receipt = self.receipt()
        if receipt is None:
            health["status"] = "blocked"
            health["reasons"].append({
                "kind": "startup-receipt-missing",
                "detail": "body did not produce a signed startup receipt",
            })
        elif not verify_startup_receipt(receipt):
            health["status"] = "blocked"
            health["reasons"].append({
                "kind": "startup-receipt-invalid",
                "detail": "persisted startup receipt failed signature verification",
            })
        return health

    def presence(self) -> dict[str, Any]:
        return {
            "kind": "ghot.presence",
            "version": "0",
            "manifest": self.manifest(),
            "startup_receipt": self.receipt(),
            "health": self.health(),
        }
