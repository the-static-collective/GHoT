#!/usr/bin/env python3
"""Opt-in GHoT worship.stage.preflight adapter.

Consumes a Static Live stage projection at a pre-authorized local package root.
Input is exactly {"packet": "<owner-provisioned-slug>"}. Does not open arbitrary
paths, transmit audio, write files, control playback, stream, or publish songs.
A successful computation receipt DOES NOT assert readiness for the stage.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import wave
from pathlib import Path
from typing import Any

PACKET_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
WAV_NAME = re.compile(r"^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*\.wav$")
MAX_PROJECT_BYTES = 512 * 1024
MAX_WAV_BYTES = 512 * 1024 * 1024
MAX_ASSETS = 40
TOLERANCE_SECONDS = 0.05


class PreflightError(Exception):
    pass


def fail(code: str) -> None:
    raise PreflightError(code)


def resolve_asset(package: Path, filename: Any) -> Path:
    """Reject symlinks, relative traversal, unlisted punctuation and missing files."""
    if not isinstance(filename, str) or not WAV_NAME.fullmatch(filename):
        fail("INVALID_ASSET_REFERENCE")
    candidate = package / filename
    # Reject symlink in every directory component; no realpath-based escape.
    current = package
    for part in Path(filename).parts:
        current = current / part
        if current.is_symlink():
            fail("ASSET_SYMLINK_FORBIDDEN")
    if not candidate.is_file():
        fail("ASSET_NOT_FOUND")
    if not candidate.resolve().is_relative_to(package.resolve()):
        fail("ASSET_OUTSIDE_PACKAGE")
    size = candidate.stat().st_size
    if size < 44 or size > MAX_WAV_BYTES:
        fail("WAV_SIZE_NOT_ACCEPTED")
    return candidate


def audio_info(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            hz = handle.getframerate()
            frames = handle.getnframes()
            sample_bytes = handle.getsampwidth()
            compression = handle.getcomptype()
            if compression != "NONE" or channels not in (1, 2) or hz < 8000 or hz > 192000:
                fail("WAV_FORMAT_NOT_SUPPORTED")
            if sample_bytes not in (2, 3, 4) or frames < 1:
                fail("WAV_FORMAT_NOT_SUPPORTED")
            return {
                "channels": channels,
                "sample_rate": hz,
                "bit_depth": sample_bytes * 8,
                "duration_seconds": round(frames / hz, 6),
            }
    except (wave.Error, EOFError, ValueError, OSError) as exc:
        fail("WAV_UNREADABLE_OR_NOT_PCM")


def preflight(input_value: Any, *, root: str | None = None) -> dict[str, Any]:
    if not isinstance(input_value, dict) or set(input_value) != {"packet"}:
        fail("INVALID_TASK_SHAPE")
    slug = input_value["packet"]
    if not isinstance(slug, str) or not PACKET_NAME.fullmatch(slug):
        fail("INVALID_PACKET_ID")
    configured = root if root is not None else os.environ.get("GHOT_WORSHIP_PACK_ROOT")
    if not configured:
        fail("OWNER_ROOT_NOT_CONFIGURED")
    root_path = Path(configured).expanduser()
    if not root_path.is_dir():
        fail("OWNER_ROOT_UNAVAILABLE")
    root_path = root_path.resolve()
    package = root_path / slug
    if package.is_symlink() or not package.is_dir():
        fail("PACKET_UNAVAILABLE")
    package = package.resolve()
    if package.parent != root_path:
        fail("PACKET_OUTSIDE_OWNER_ROOT")
    projection = package / "projection.json"
    if projection.is_symlink() or not projection.is_file() or projection.stat().st_size > MAX_PROJECT_BYTES:
        fail("PROJECTION_UNAVAILABLE")
    try:
        stage = json.loads(projection.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        fail("PROJECTION_UNREADABLE")
    if not isinstance(stage, dict) or stage.get("version") != "static-live.stage-projection/v0.1":
        fail("INVALID_STATIC_LIVE_PROJECTION")
    if not isinstance(stage.get("enabledStems"), list) or not isinstance(stage.get("cues"), dict):
        fail("INVALID_STATIC_LIVE_PROJECTION")
    if len(stage["enabledStems"]) > MAX_ASSETS:
        fail("TOO_MANY_ASSETS")

    # Refuse undecidable stage status. This is explicit from Static Live,
    # never inferred by GHoT from the existence of audio.
    errors: list[str] = []
    warnings: list[str] = []
    playable = stage.get("playable") is True
    if not playable:
        errors.append("STATIC_LIVE_NOT_PLAYABLE")
    assets: list[tuple[str, str]] = []
    for stem in stage["enabledStems"]:
        if not isinstance(stem, dict) or stem.get("output") != "foh" or not isinstance(stem.get("path"), str):
            errors.append("INVALID_FOH_STEM")
            continue
        assets.append(("foh", stem["path"]))
    cues = stage["cues"]
    for kind in ("click", "voice"):
        if kind in cues:
            if not isinstance(cues[kind], str):
                errors.append("INVALID_PRIVATE_CUE")
            else:
                assets.append((kind, cues[kind]))
    if not any(kind == "click" for kind, _ in assets):
        warnings.append("NO_CLICK_DECLARED")
    if not assets:
        warnings.append("NO_AUDIO_DECLARED")
    if len(assets) > MAX_ASSETS + 2:
        fail("TOO_MANY_ASSETS")

    seen: set[str] = set()
    report: list[dict[str, Any]] = []
    reference: dict[str, Any] | None = None
    for kind, relative in assets:
        if relative in seen:
            errors.append("DUPLICATE_ASSET_REFERENCE")
            continue
        seen.add(relative)
        try:
            info = audio_info(resolve_asset(package, relative))
            # Return only role + audio metadata, not names or absolute paths.
            report.append({"role": kind, **info})
            if reference is None:
                reference = info
            else:
                if info["sample_rate"] != reference["sample_rate"]:
                    errors.append("SAMPLE_RATE_MISMATCH")
                if abs(info["duration_seconds"] - reference["duration_seconds"]) > TOLERANCE_SECONDS:
                    errors.append("DURATION_DRIFT")
        except PreflightError as exc:
            errors.append(exc.args[0])
    # Presence of tracks does not establish authorization to mix or broadcast.
    return {
        "schema": "ghot.worship-stage-preflight/v0",
        "ready_for_rehearsal_review": playable and not errors,
        "source_projection_digest": "sha256:" + hashlib.sha256(projection.read_bytes()).hexdigest(),
        "asset_count": len(report),
        "audio": report,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "claims_not_made": [
            "rights_cleared", "church_approved", "mixed", "streamed",
            "broadcast_ready", "hardware_routed", "soundchecked",
        ],
    }


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            fail("TASK_TOO_LARGE")
        task = json.loads(raw)
        print(json.dumps(preflight(task), separators=(",", ":")))
        return 0
    except (PreflightError, json.JSONDecodeError) as exc:
        # Never echo user-provided file paths or lyric content.
        print(json.dumps({"error": exc.args[0] if isinstance(exc, PreflightError) else "INVALID_JSON"}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
