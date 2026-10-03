#!/usr/bin/env python3
"""GHoT Executor Pantry.

Discovers useful local executables and translates them into bounded GHoT
capabilities. Discovery never grants arbitrary shell execution.

This module uses only the Python standard library.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

EXECUTORS: dict[str, dict[str, Any]] = {
    "python": {
        "commands": ["python3", "python"],
        "version_args": ["--version"],
        "capabilities": ["runtime.python.version"],
    },
    "git": {
        "commands": ["git"],
        "version_args": ["--version"],
        "capabilities": ["runtime.git.version"],
    },
    "ffmpeg": {
        "commands": ["ffmpeg"],
        "version_args": ["-version"],
        "capabilities": ["runtime.ffmpeg.version"],
    },
    "ffprobe": {
        "commands": ["ffprobe"],
        "version_args": ["-version"],
        "capabilities": ["runtime.ffprobe.version", "media.probe"],
    },
    "llama.cpp": {
        "commands": ["llama-cli", "main"],
        "version_args": ["--version"],
        "capabilities": ["runtime.llama.version"],
    },
    "whisper.cpp": {
        "commands": ["whisper-cli", "whisper"],
        "version_args": ["--help"],
        "capabilities": ["runtime.whisper.available"],
    },
    "piper": {
        "commands": ["piper"],
        "version_args": ["--help"],
        "capabilities": ["runtime.piper.available"],
    },
    "imagemagick": {
        "commands": ["magick", "convert"],
        "version_args": ["-version"],
        "capabilities": ["runtime.imagemagick.version"],
    },
}


def _first_command(commands: list[str]) -> tuple[str | None, str | None]:
    for command in commands:
        path = shutil.which(command)
        if path:
            return command, path
    return None, None


def _bounded_version(path: str, args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            [path, *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3,
            check=False,
        )
        text = (proc.stdout or "").strip()
        if not text:
            return None
        return text.splitlines()[0][:500]
    except (OSError, subprocess.SubprocessError):
        return None


def probe_executors() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name, spec in EXECUTORS.items():
        command, path = _first_command(spec["commands"])
        available = path is not None
        records.append({
            "kind": "ghot.executor",
            "version": "0",
            "name": name,
            "available": available,
            "command": command,
            "path": path,
            "reported_version": (
                _bounded_version(path, spec["version_args"])
                if path else None
            ),
            "capabilities": list(spec["capabilities"]) if available else [],
        })
    return records


def derive_offers(executors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    offers: list[dict[str, Any]] = []
    for executor in executors:
        if not executor.get("available"):
            continue
        for capability in executor.get("capabilities", []):
            offers.append({
                "kind": "ghot.offer",
                "version": "0",
                "capability": capability,
                "available": True,
                "executor": executor["name"],
                "limits": {
                    "remote_shell": False,
                    "bounded_adapter_only": True,
                },
            })
    return offers


def pantry_report() -> dict[str, Any]:
    executors = probe_executors()
    return {
        "kind": "ghot.pantry",
        "version": "0",
        "host": platform.node(),
        "executors": executors,
        "offers": derive_offers(executors),
    }


def _executor_for_capability(capability: str) -> tuple[dict[str, Any], str]:
    for name, spec in EXECUTORS.items():
        if capability not in spec["capabilities"]:
            continue
        command, path = _first_command(spec["commands"])
        if not path:
            raise RuntimeError(f"executor unavailable for capability: {capability}")
        return spec, path
    raise ValueError(f"unknown pantry capability: {capability}")


def _runtime_report(capability: str) -> dict[str, Any]:
    spec, path = _executor_for_capability(capability)
    return {
        "capability": capability,
        "path": path,
        "reported_version": _bounded_version(path, spec["version_args"]),
    }


def _media_probe(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, (str, dict)):
        raise ValueError("media.probe input must be a path string or {path: ...}")

    raw_path = payload if isinstance(payload, str) else payload.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("media.probe requires a local file path")

    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"not a local file: {path}")

    _, ffprobe = _executor_for_capability("media.probe")
    proc = subprocess.run(
        [
            ffprobe,
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )

    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "ffprobe failed").strip()[:1000])

    parsed = json.loads(proc.stdout)
    return {
        "path": str(path),
        "probe": parsed,
    }


def execute_adapter(capability: str, payload: Any) -> Any:
    if capability == "media.probe":
        return _media_probe(payload)

    runtime_caps = {
        "runtime.python.version",
        "runtime.git.version",
        "runtime.ffmpeg.version",
        "runtime.ffprobe.version",
        "runtime.llama.version",
        "runtime.whisper.available",
        "runtime.piper.available",
        "runtime.imagemagick.version",
    }
    if capability in runtime_caps:
        return _runtime_report(capability)

    raise ValueError(f"unsupported pantry capability: {capability}")


if __name__ == "__main__":
    print(json.dumps(pantry_report(), indent=2))
