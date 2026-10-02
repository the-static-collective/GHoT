#!/usr/bin/env python3
"""GHoT Power Field — Experiment 007.

Zero-dependency resource-pressure probe and power policy.

The BODY may change what it is willing to offer without changing identity.
Automatic V0 probes target Linux sysfs plus portable stdlib load metrics.
Manual environment hints cover solar/experimental rigs:

    GHOT_POWER_SOURCE=solar
    GHOT_RENEWABLE_SURPLUS=1
    GHOT_BATTERY_PERCENT=82
    GHOT_CHARGING=1
    GHOT_THERMAL_C=54
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any


HEAVY_PREFIXES = (
    "llm.infer.large",
    "render.",
    "video.render",
    "media.transcode.video",
    "image.generate",
    "image.render",
)

MEDIUM_PREFIXES = (
    "llm.infer.",
    "speech.transcribe",
    "speech.synthesize",
    "media.transcode.audio",
    "image.transform",
)

ESSENTIAL_PREFIXES = (
    "system.",
    "sensor.",
    "storage.hold",
    "actuator.safety",
)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _read_float(path: Path, scale: float = 1.0) -> float | None:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return float(raw) / scale
    except ValueError:
        return None


def _env_float(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _linux_power() -> dict[str, Any]:
    root = Path("/sys/class/power_supply")
    batteries: list[dict[str, Any]] = []
    external: list[dict[str, Any]] = []

    if not root.is_dir():
        return {"batteries": batteries, "external_sources": external}

    for item in sorted(root.iterdir()):
        kind = (_read_text(item / "type") or "").lower()
        name = item.name
        if kind == "battery":
            capacity = _read_float(item / "capacity")
            status = (_read_text(item / "status") or "").lower()
            batteries.append({
                "name": name,
                "percent": capacity,
                "status": status or None,
                "charging": status in {"charging", "full"},
            })
            continue

        online_raw = _read_text(item / "online")
        online = online_raw == "1" if online_raw is not None else None
        external.append({
            "name": name,
            "type": kind or None,
            "online": online,
        })

    return {"batteries": batteries, "external_sources": external}


def _linux_thermal_c() -> float | None:
    root = Path("/sys/class/thermal")
    if not root.is_dir():
        return None

    readings: list[float] = []
    for zone in root.glob("thermal_zone*"):
        value = _read_float(zone / "temp", scale=1000.0)
        if value is not None and -20.0 <= value <= 150.0:
            readings.append(value)
    return max(readings) if readings else None


def _load() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    try:
        one, five, fifteen = os.getloadavg()
        return {
            "load_1m": round(one, 3),
            "load_5m": round(five, 3),
            "load_15m": round(fifteen, 3),
            "load_per_cpu_1m": round(one / cpu_count, 3),
        }
    except (AttributeError, OSError):
        return {
            "load_1m": None,
            "load_5m": None,
            "load_15m": None,
            "load_per_cpu_1m": None,
        }


def _derive_source(
    batteries: list[dict[str, Any]],
    external_sources: list[dict[str, Any]],
) -> tuple[str | None, bool | None]:
    for source in external_sources:
        if source.get("online") is True:
            kind = str(source.get("type") or source.get("name") or "external").lower()
            if "mains" in kind or kind == "ac":
                return "ac", True
            if "usb" in kind:
                return "usb", True
            return kind, True

    if batteries:
        charging = any(battery.get("charging") is True for battery in batteries)
        if charging:
            return "external", True
        return "battery", False

    return None, None


def _aggregate_battery(batteries: list[dict[str, Any]]) -> float | None:
    values = [
        float(battery["percent"])
        for battery in batteries
        if isinstance(battery.get("percent"), (int, float))
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def thermal_state(temperature_c: float | None) -> str:
    if temperature_c is None:
        return "unknown"
    if temperature_c >= 95:
        return "critical"
    if temperature_c >= 85:
        return "hot"
    if temperature_c >= 75:
        return "warm"
    return "normal"


def derive_willingness(power: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    battery = power.get("battery_percent")
    source = str(power.get("source") or "").lower()
    renewable_surplus = power.get("renewable_surplus") is True
    temp = power.get("temperature_c")
    load_per_cpu = power.get("load_per_cpu_1m")

    state = "normal"

    if renewable_surplus:
        state = "abundant"
        reasons.append("renewable surplus declared")

    if isinstance(battery, (int, float)) and source == "battery":
        if battery <= 10:
            state = "critical"
            reasons.append(f"battery {battery}% <= critical threshold 10%")
        elif battery <= 25 and state != "critical":
            state = "conserve"
            reasons.append(f"battery {battery}% <= conserve threshold 25%")

    thermal = thermal_state(temp if isinstance(temp, (int, float)) else None)
    if thermal == "critical":
        state = "critical"
        reasons.append(f"temperature {temp}C is critical")
    elif thermal == "hot" and state != "critical":
        state = "conserve"
        reasons.append(f"temperature {temp}C is hot")

    if isinstance(load_per_cpu, (int, float)):
        if load_per_cpu >= 4.0:
            state = "critical"
            reasons.append(f"1m load/cpu {load_per_cpu} >= 4.0")
        elif load_per_cpu >= 2.0 and state not in {"critical"}:
            if state == "abundant":
                state = "normal"
            else:
                state = "conserve"
            reasons.append(f"1m load/cpu {load_per_cpu} >= 2.0")

    if not reasons:
        if source in {"ac", "mains", "usb", "solar", "external"}:
            reasons.append(f"external power source: {source}")
        else:
            reasons.append("no V0 power-pressure threshold crossed")

    return state, reasons


def probe_power() -> dict[str, Any]:
    linux = _linux_power() if platform.system() == "Linux" else {
        "batteries": [],
        "external_sources": [],
    }
    battery = _aggregate_battery(linux["batteries"])
    source, charging = _derive_source(
        linux["batteries"],
        linux["external_sources"],
    )
    temperature = _linux_thermal_c() if platform.system() == "Linux" else None

    # Explicit operator/hardware-agent hints override incomplete OS probes.
    hinted_battery = _env_float("GHOT_BATTERY_PERCENT")
    if hinted_battery is not None:
        battery = max(0.0, min(100.0, hinted_battery))

    hinted_source = os.environ.get("GHOT_POWER_SOURCE")
    if hinted_source:
        source = hinted_source.strip().lower()

    hinted_charging = _env_bool("GHOT_CHARGING")
    if hinted_charging is not None:
        charging = hinted_charging

    hinted_thermal = _env_float("GHOT_THERMAL_C")
    if hinted_thermal is not None:
        temperature = hinted_thermal

    renewable_surplus = _env_bool("GHOT_RENEWABLE_SURPLUS")
    load = _load()

    record = {
        "battery_percent": battery,
        "charging": charging,
        "source": source,
        "renewable_surplus": renewable_surplus,
        "temperature_c": temperature,
        "thermal_state": thermal_state(temperature),
        **load,
        "probe": {
            "platform": platform.system(),
            "linux_batteries": linux["batteries"],
            "linux_external_sources": linux["external_sources"],
            "manual_hints": {
                "battery_percent": hinted_battery is not None,
                "source": bool(hinted_source),
                "charging": hinted_charging is not None,
                "thermal_c": hinted_thermal is not None,
                "renewable_surplus": renewable_surplus is not None,
            },
        },
    }

    willingness, reasons = derive_willingness(record)
    record["willingness"] = willingness
    record["willingness_reasons"] = reasons
    return record


def capability_power_class(capability: str) -> str:
    if capability.startswith(ESSENTIAL_PREFIXES):
        return "essential"
    if capability.startswith(HEAVY_PREFIXES):
        return "heavy"
    if capability.startswith(MEDIUM_PREFIXES):
        return "medium"
    if capability.startswith("runtime.") or capability == "media.probe":
        return "light"
    return "medium"


def apply_power_policy(
    offers: list[dict[str, Any]],
    power: dict[str, Any],
) -> list[dict[str, Any]]:
    willingness = str(power.get("willingness") or "normal")
    adjusted: list[dict[str, Any]] = []

    for original in offers:
        offer = dict(original)
        capability = str(offer.get("capability") or "")
        power_class = capability_power_class(capability)
        reasons: list[str] = []

        available = bool(offer.get("available", False))
        if available and willingness == "conserve" and power_class == "heavy":
            available = False
            reasons.append("withdrawn: heavy capability under conserve willingness")
        elif available and willingness == "critical" and power_class != "essential":
            available = False
            reasons.append("withdrawn: non-essential capability under critical willingness")

        offer["available"] = available
        offer["power"] = {
            "class": power_class,
            "willingness": willingness,
            "policy_reasons": reasons,
        }
        adjusted.append(offer)

    return adjusted


def main() -> int:
    power = probe_power()
    print(json.dumps(power, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
