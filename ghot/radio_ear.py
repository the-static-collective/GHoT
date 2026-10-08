#!/usr/bin/env python3
"""RADIO-EAR-002: bounded receive-only RTL-SDR CLI capture donor for GHoT.

No SoapySDR auto-probe, no TCP driver, no transmitting capability. A successful
rtl_sdr process is only a HOST-REPORTED receiver observation; it cannot attest
that an antenna, external emitter, clock or hardware identity was genuine.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CAPABILITY = "radio.rx.rtlsdr.capture"
SCHEMA = "ghot.radio-ear-iq/v0"
REQUEST_SCHEMA = "ghot.radio-ear-request/v0"
MAX_SAMPLES = 65536
MIN_SAMPLES = 4096
TIMEOUT_SECONDS = 12


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_request(raw: Any) -> dict[str, Any]:
    required = {"schema", "action", "device_index", "frequency_hz", "sample_rate_hz", "complex_samples", "rx_scope"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("RADIO_EAR_EXACT_REQUEST_REQUIRED")
    if raw["schema"] != REQUEST_SCHEMA or raw["action"] != "capture_rx_iq":
        raise ValueError("RADIO_EAR_RECEIVE_ONLY")
    if raw["rx_scope"] != "public-or-otherwise-authorized":
        raise ValueError("RADIO_EAR_SCOPE_UNDECLARED")
    for key, lower, upper in (
        ("device_index", 0, 7),
        ("frequency_hz", 24_000_000, 1_700_000_000),
        ("sample_rate_hz", 250_000, 2_400_000),
        ("complex_samples", MIN_SAMPLES, MAX_SAMPLES),
    ):
        value = raw[key]
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError("RADIO_EAR_INVALID_" + key.upper())
    if raw["complex_samples"] % 8:
        raise ValueError("RADIO_EAR_COMPLEX_SAMPLE_ALIGNMENT")
    return raw


def energy_windows(raw: bytes) -> list[int]:
    """Eight quantized time-window amplitudes, explicitly NOT FFT frequency bins."""
    if len(raw) < 16 or len(raw) % 16:
        raise ValueError("RADIO_EAR_INVALID_IQ_ALIGNMENT")
    samples = len(raw) // 2
    windows = []
    for index in range(8):
        segment = raw[index * (samples // 8) * 2:(index + 1) * (samples // 8) * 2]
        # Offset-binary RTL complex IQ, uncalibrated energy proxy.
        amplitude_sum = sum(abs(value - 128) for value in segment)
        windows.append(min(20, (amplitude_sum + len(segment) * 4) // (len(segment) * 8)))
    return windows


def verify_capture(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("RADIO_EAR_CAPTURE_SCHEMA")
    if value.get("status") != "HOST_REPORTED_RX_CAPTURE" or value.get("mode") != "RECEIVE_ONLY":
        raise ValueError("RADIO_EAR_CAPTURE_STATUS")
    if value.get("origin_assurance") != "host-driver-report-unverified-physical-origin":
        raise ValueError("RADIO_EAR_ORIGIN_CLAIM")
    if value.get("hardware_identity_verified") is not False or value.get("tx_enabled") is not False:
        raise ValueError("RADIO_EAR_FORBIDDEN_AUTHORITY_CLAIM")
    request = validate_request(value.get("request"))
    b64 = value.get("iq_u8_interleaved_base64")
    if not isinstance(b64, str) or len(b64) > (MAX_SAMPLES * 4):
        raise ValueError("RADIO_EAR_INVALID_INLINE_IQ")
    try:
        raw = base64.b64decode(b64, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("RADIO_EAR_INVALID_BASE64") from exc
    if len(raw) != 2 * request["complex_samples"]:
        raise ValueError("RADIO_EAR_TRUNCATED_CAPTURE")
    if _sha(raw) != value.get("iq_sha256"):
        raise ValueError("RADIO_EAR_CAPTURE_HASH_MISMATCH")
    if energy_windows(raw) != value.get("amplitude_windows"):
        raise ValueError("RADIO_EAR_DERIVED_MEASUREMENT_MISMATCH")
    if value.get("sample_format") != "rtl-u8-iq-interleaved" or value.get("sample_count") != request["complex_samples"]:
        raise ValueError("RADIO_EAR_SAMPLE_FORMAT_MISMATCH")
    if value.get("gap_status") != "unknown" or value.get("clock_uncertainty") != "unmeasured":
        raise ValueError("RADIO_EAR_UNSUPPORTED_CERTAINTY")
    backend = value.get("backend")
    if not isinstance(backend, dict) or backend.get("name") != "rtl_sdr-cli" or not isinstance(backend.get("sha256"), str):
        raise ValueError("RADIO_EAR_BACKEND_UNVERIFIED")
    if len(backend["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in backend["sha256"]):
        raise ValueError("RADIO_EAR_BACKEND_DIGEST_INVALID")
    if not isinstance(value.get("started_utc"), str) or not isinstance(value.get("ended_utc"), str):
        raise ValueError("RADIO_EAR_CLOCK_UNKNOWN")
    return value


def capture(request: Any, *, configured_executable: str | None = None) -> dict[str, Any]:
    """Issue one bounded receive-only rtl_sdr invocation; no programmable TX path."""
    validated = validate_request(request)
    executable = configured_executable or os.environ.get("GHOT_RTLSDR_BIN") or shutil.which("rtl_sdr")
    if not executable:
        raise RuntimeError("RADIO_EAR_RTLSDR_NOT_INSTALLED")
    path = Path(executable).expanduser().resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise RuntimeError("RADIO_EAR_BACKEND_UNAVAILABLE")
    backend_digest = _sha(path.read_bytes())
    args = [
        str(path), "-d", str(validated["device_index"]),
        "-f", str(validated["frequency_hz"]),
        "-s", str(validated["sample_rate_hz"]),
        "-n", str(validated["complex_samples"]), "-",
    ]
    started = _timestamp()
    try:
        result = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("RADIO_EAR_TIMEOUT_UNCERTAIN") from exc
    except OSError as exc:
        raise RuntimeError("RADIO_EAR_DRIVER_FAILED") from exc
    ended = _timestamp()
    if result.returncode != 0:
        raise RuntimeError("RADIO_EAR_DRIVER_REFUSED")
    expected_bytes = 2 * validated["complex_samples"]
    if len(result.stdout) != expected_bytes:
        raise RuntimeError("RADIO_EAR_SAMPLE_COUNT_MISMATCH")
    captured = {
        "schema": SCHEMA,
        "status": "HOST_REPORTED_RX_CAPTURE",
        "mode": "RECEIVE_ONLY",
        "tx_enabled": False,
        "hardware_identity_verified": False,
        "origin_assurance": "host-driver-report-unverified-physical-origin",
        "request": validated,
        "started_utc": started,
        "ended_utc": ended,
        "clock_uncertainty": "unmeasured",
        "gap_status": "unknown",
        "sample_format": "rtl-u8-iq-interleaved",
        "sample_count": validated["complex_samples"],
        "iq_sha256": _sha(result.stdout),
        "iq_u8_interleaved_base64": base64.b64encode(result.stdout).decode("ascii"),
        "amplitude_windows": energy_windows(result.stdout),
        "amplitude_kind": "uncalibrated-eight-time-windows-not-spectrum",
        "backend": {
            "name": "rtl_sdr-cli",
            "sha256": backend_digest,
            "command_flags": ["-d", "-f", "-s", "-n", "-"],
            "stderr_sha256": _sha(result.stderr),
        },
    }
    return verify_capture(captured)


def main() -> int:
    try:
        if os.environ.get("GHOT_EXTERNAL_CAPABILITY") != CAPABILITY:
            raise ValueError("RADIO_EAR_GHOT_CAPABILITY_REQUIRED")
        request = json.load(sys.stdin)
        output = capture(request)
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        # Never print raw samples or untrusted radio content to stderr.
        print(f"{type(exc).__name__}: {str(exc)[:140]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
