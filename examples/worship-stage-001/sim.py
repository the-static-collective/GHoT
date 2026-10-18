#!/usr/bin/env python3
"""Deterministic offline GHoT x Static Live proof. No church machines involved."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import wave
from pathlib import Path


def make_pcm(path: Path, *, rate: int = 48000, seconds: int = 1, channels: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * channels * rate * seconds)


def projection(*, playable: bool = True, click: str = "stems/click.wav") -> dict:
    return {
        "version": "static-live.stage-projection/v0.1",
        "song": {"title": "Synthetic rehearsal title"},
        "configuration": {"label": "Synthetic Sunday"},
        "playable": playable,
        "enabledStems": [
            {"id": "pad", "kind": "always", "path": "stems/pad.wav", "output": "foh"},
        ],
        "cues": {"click": click},
    }


def main() -> int:
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root.parents[1] / "ghot"))
    with tempfile.TemporaryDirectory(prefix="ghot-worship-stage-") as tmp:
        tmp_path = Path(tmp)
        storage = tmp_path / "packages"
        pack = storage / "sunday-001"
        pack.mkdir(parents=True)
        make_pcm(pack / "stems/pad.wav")
        make_pcm(pack / "stems/click.wav", channels=1)
        (pack / "projection.json").write_text(json.dumps(projection()), encoding="utf-8")

        old = {key: os.environ.get(key) for key in (
            "GHOT_ADAPTER_MANIFESTS", "GHOT_WORSHIP_PACK_ROOT", "GHOT_HOME",
        )}
        os.environ["GHOT_ADAPTER_MANIFESTS"] = str(root / "adapter-manifest.json")
        os.environ["GHOT_WORSHIP_PACK_ROOT"] = str(storage)
        os.environ["GHOT_HOME"] = str(tmp_path / "ghot")
        try:
            from executor_pantry import derive_offers, execute_adapter, probe_executors
            from reference_node import execute
            registry = probe_executors()
            offered = derive_offers(registry)
            capability = next(item for item in offered
                              if item["capability"] == "worship.stage.preflight")
            assert capability["limits"]["bounded_adapter_only"] is True
            assert capability["limits"]["network"] is False
            assert capability["limits"]["remote_shell"] is False

            task, receipt = execute("worship.stage.preflight", {"packet": "sunday-001"})
            assert task["capability"] == "worship.stage.preflight"
            assert receipt["status"] == "ok", receipt
            result = receipt["output"]["result"]
            assert result["ready_for_rehearsal_review"] is True, result
            assert result["asset_count"] == 2
            assert result["audio"][1]["role"] == "click"
            assert "synthetic" not in json.dumps(result).lower()
            assert str(tmp_path) not in json.dumps(result)

            # This task ran successfully, but rejected a misaligned click.
            make_pcm(pack / "stems/click.wav", rate=44100, seconds=2, channels=1)
            _, bad = execute("worship.stage.preflight", {"packet": "sunday-001"})
            assert bad["status"] == "ok"
            assert bad["output"]["result"]["ready_for_rehearsal_review"] is False
            assert "SAMPLE_RATE_MISMATCH" in bad["output"]["result"]["errors"]
            assert "DURATION_DRIFT" in bad["output"]["result"]["errors"]

            # Restore click, but Static Live's own 'playable' guard remains supreme.
            make_pcm(pack / "stems/click.wav", channels=1)
            (pack / "projection.json").write_text(json.dumps(projection(playable=False)), encoding="utf-8")
            _, unplayable = execute("worship.stage.preflight", {"packet": "sunday-001"})
            assert unplayable["status"] == "ok"
            assert unplayable["output"]["result"]["ready_for_rehearsal_review"] is False
            assert "STATIC_LIVE_NOT_PLAYABLE" in unplayable["output"]["result"]["errors"]

            # Remote-submitted paths never address arbitrary host files.
            for dangerous in ("../other", "/etc", "sunday-001/../other", "", "Sunday With Spaces"):
                _, denied = execute("worship.stage.preflight", {"packet": dangerous})
                assert denied["status"] == "error", denied
                assert "INVALID_PACKET_ID" in denied["error"]

            # Even a correctly configured package cannot dereference an audio symlink.
            outside = tmp_path / "private.wav"
            make_pcm(outside)
            (pack / "projection.json").write_text(json.dumps(projection(click="stems/redirect.wav")), encoding="utf-8")
            (pack / "stems/redirect.wav").symlink_to(outside)
            _, symlink = execute("worship.stage.preflight", {"packet": "sunday-001"})
            assert symlink["status"] == "ok"
            assert "ASSET_SYMLINK_FORBIDDEN" in symlink["output"]["result"]["errors"]
            assert symlink["output"]["result"]["ready_for_rehearsal_review"] is False

            # Without an explicitly configured owner root, capability execution refuses.
            del os.environ["GHOT_WORSHIP_PACK_ROOT"]
            _, unset = execute("worship.stage.preflight", {"packet": "sunday-001"})
            assert unset["status"] == "error"
            assert "OWNER_ROOT_NOT_CONFIGURED" in unset["error"]
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    print(json.dumps({
        "status": "PASS",
        "exercise": "worship.stage.preflight x real GHoT capability/receipt",
        "tested": [
            "opt-in offer", "aligned WAV", "missing live function",
            "sample-rate/duration mismatch", "invalid paths",
            "symlink escape", "owner root missing", "no private song text in report",
        ],
        "law": "TASK RECEIPT != STAGE READINESS",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
