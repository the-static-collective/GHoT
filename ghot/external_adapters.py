#!/usr/bin/env python3
"""Generic opt-in external adapter manifests for GHoT.

GHoT does not scan arbitrary repositories. A local owner explicitly names
manifest files through GHOT_ADAPTER_MANIFESTS. The manifest owns the mapping
from one bounded capability to one stdin/stdout JSON process.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

MANIFEST_ENV = "GHOT_ADAPTER_MANIFESTS"
ADAPTER_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
CAPABILITY_RE = re.compile(r"^[A-Za-z0-9._-]{1,160}$")


def _manifest_paths() -> list[Path]:
    raw = os.environ.get(MANIFEST_ENV, "").strip()
    if not raw:
        return []
    paths: list[Path] = []
    for part in raw.split(os.pathsep):
        if not part.strip():
            continue
        candidate = Path(part).expanduser().resolve()
        if candidate.is_dir():
            candidate = candidate / "adapter-manifest.json"
        paths.append(candidate)
    return paths


def _nonempty(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(code)
    return value


def _string_list(value: Any, code: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(code)
    return list(value)


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"external adapter manifest not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("INVALID_EXTERNAL_ADAPTER_MANIFEST")
    if value.get("schema") != "ghot.external-adapter-manifest/v0":
        raise ValueError("INVALID_EXTERNAL_ADAPTER_MANIFEST_SCHEMA")
    adapter_id = _nonempty(value.get("adapter_id"), "INVALID_EXTERNAL_ADAPTER_ID")
    if not ADAPTER_ID_RE.fullmatch(adapter_id):
        raise ValueError("INVALID_EXTERNAL_ADAPTER_ID")
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError("INVALID_EXTERNAL_ADAPTER_CAPABILITIES")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in capabilities:
        if not isinstance(item, dict):
            raise ValueError("INVALID_EXTERNAL_ADAPTER_CAPABILITY")
        capability = _nonempty(
            item.get("capability"), "INVALID_EXTERNAL_ADAPTER_CAPABILITY"
        )
        if not CAPABILITY_RE.fullmatch(capability) or capability in seen:
            raise ValueError("INVALID_EXTERNAL_ADAPTER_CAPABILITY")
        seen.add(capability)
        if item.get("protocol") != "stdin-json/stdout-json-v0":
            raise ValueError("INVALID_EXTERNAL_ADAPTER_PROTOCOL")
        command = _nonempty(item.get("command"), "INVALID_EXTERNAL_ADAPTER_COMMAND")
        args = _string_list(item.get("args", []), "INVALID_EXTERNAL_ADAPTER_ARGS")
        timeout = item.get("timeout_seconds", 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 120:
            raise ValueError("INVALID_EXTERNAL_ADAPTER_TIMEOUT")
        limits = item.get("limits", {})
        if not isinstance(limits, dict):
            raise ValueError("INVALID_EXTERNAL_ADAPTER_LIMITS")
        normalized.append({
            "capability": capability,
            "protocol": "stdin-json/stdout-json-v0",
            "command": command,
            "args": args,
            "timeout_seconds": float(timeout),
            "limits": json.loads(json.dumps(limits)),
        })

    return {
        "schema": "ghot.external-adapter-manifest/v0",
        "adapter_id": adapter_id,
        "manifest_path": str(path),
        "manifest_dir": str(path.parent),
        "capabilities": normalized,
    }


def load_manifests() -> list[dict[str, Any]]:
    manifests = [_load_manifest(path) for path in _manifest_paths()]
    ids = [item["adapter_id"] for item in manifests]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_EXTERNAL_ADAPTER_ID")
    return manifests


def _resolve_command(spec: dict[str, Any], manifest: dict[str, Any]) -> tuple[str | None, list[str]]:
    command = spec["command"]
    command_path = shutil.which(command)
    if command_path is None:
        possible = (Path(manifest["manifest_dir"]) / command).resolve()
        if possible.is_file():
            command_path = str(possible)

    resolved_args: list[str] = []
    for raw in spec["args"]:
        if raw.startswith("-"):
            resolved_args.append(raw)
            continue
        candidate = (Path(manifest["manifest_dir"]) / raw).resolve()
        resolved_args.append(str(candidate) if candidate.exists() else raw)
    return command_path, resolved_args


def external_executor_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for manifest in load_manifests():
        capability_limits: dict[str, Any] = {}
        available_caps: list[str] = []
        command_paths: set[str] = set()
        capability_specs: list[dict[str, Any]] = []
        for spec in manifest["capabilities"]:
            command_path, resolved_args = _resolve_command(spec, manifest)
            available = command_path is not None
            if available:
                available_caps.append(spec["capability"])
                command_paths.add(command_path)
            capability_limits[spec["capability"]] = {
                "remote_shell": False,
                "bounded_adapter_only": True,
                **spec["limits"],
            }
            capability_specs.append({
                "capability": spec["capability"],
                "available": available,
                "command": command_path,
                "args": resolved_args,
                "protocol": spec["protocol"],
                "timeout_seconds": spec["timeout_seconds"],
            })

        records.append({
            "kind": "ghot.executor",
            "version": "0",
            "name": f"external:{manifest['adapter_id']}",
            "available": bool(available_caps),
            "command": None,
            "path": next(iter(command_paths), None) if len(command_paths) == 1 else None,
            "reported_version": None,
            "capabilities": available_caps,
            "capability_limits": capability_limits,
            "external_adapter": {
                "adapter_id": manifest["adapter_id"],
                "manifest_path": manifest["manifest_path"],
                "capability_specs": capability_specs,
            },
        })
    return records


def find_external_capability(capability: str) -> tuple[dict[str, Any], dict[str, Any], str, list[str]] | None:
    matches: list[tuple[dict[str, Any], dict[str, Any], str, list[str]]] = []
    for manifest in load_manifests():
        for spec in manifest["capabilities"]:
            if spec["capability"] != capability:
                continue
            command_path, args = _resolve_command(spec, manifest)
            if command_path is None:
                raise RuntimeError(
                    f"external adapter command unavailable for capability: {capability}"
                )
            matches.append((manifest, spec, command_path, args))
    if len(matches) > 1:
        raise RuntimeError(f"multiple external adapters offer capability: {capability}")
    return matches[0] if matches else None


def execute_external_adapter(capability: str, payload: Any) -> dict[str, Any]:
    match = find_external_capability(capability)
    if match is None:
        raise ValueError(f"unknown external adapter capability: {capability}")
    manifest, spec, command_path, args = match

    try:
        completed = subprocess.run(
            [command_path, *args],
            cwd=manifest["manifest_dir"],
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=spec["timeout_seconds"],
            env={
                **os.environ,
                "LC_ALL": "C",
                "GHOT_EXTERNAL_CAPABILITY": capability,
                "GHOT_EXTERNAL_ADAPTER_ID": manifest["adapter_id"],
            },
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"external adapter execution failed: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or "").strip()[:2000]
        raise RuntimeError(
            f"external adapter refused capability {capability}: {detail or completed.returncode}"
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("external adapter returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("external adapter returned non-object JSON")

    return {
        "kind": "ghot.external-adapter.result",
        "version": "0",
        "adapter_id": manifest["adapter_id"],
        "capability": capability,
        "manifest_path": manifest["manifest_path"],
        "result": result,
        "laws": [
            "MANIFEST != AUTHORITY",
            "CAPABILITY != EXECUTION",
            "GHOT != DONOR SEMANTICS",
            "ADAPTER PROCESS != ARBITRARY SHELL",
        ],
    }
