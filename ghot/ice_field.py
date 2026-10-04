#!/usr/bin/env python3
"""GHoT Ice Field — Experiment 033.

A verified Ice Cube pantry can expose a bounded deterministic neighborhood of
new mathematical work. Those WANTs are not jobs until local scheduling selects
them.

    PANTRY != WANT
    WANT != SCHEDULE
    SCHEDULE != EXECUTION
    EXECUTION != RETURN
    RETURN != ADMISSION
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from energy_scheduler import schedule
from ice_cube import ICE_CUBE_CAPABILITY, lucas, work_address
from reference_node import ROOT
from relatte_identity import identity_safe, jcs_bytes, timestamp_now


FIELD_KIND = "ghot.ice-field"
FIELD_VERSION = "0"
WANT_KIND = "ghot.ice-field.want"
WANT_VERSION = "0"
WANT_DOMAIN = b"GHoT-IceFieldWant-v0|"
DEFAULT_DELTA = Decimal("0.0625")


def _safe_name(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object required: {path}")
    return value


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _clone_work(work: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(work))


def adjacent_work_specs(
    specimen: dict[str, Any],
    *,
    delta: Decimal = DEFAULT_DELTA,
) -> list[dict[str, Any]]:
    work = specimen.get("work")
    if not isinstance(work, dict):
        raise ValueError("Ice Cube specimen has no work object")

    index = int(work["lucas_index"])
    c = work.get("c") or {}
    c_re = Decimal(str(c.get("re", "0")))
    c_im = Decimal(str(c.get("im", "0")))

    mutations: list[tuple[str, dict[str, Any]]] = []

    next_scale = _clone_work(work)
    next_scale["lucas_index"] = index + 1
    next_scale["period"] = lucas(index + 1)
    mutations.append(("lucas-next", next_scale))

    for relation, new_re, new_im in (
        ("c-real-minus", c_re - delta, c_im),
        ("c-real-plus", c_re + delta, c_im),
        ("c-imag-minus", c_re, c_im - delta),
        ("c-imag-plus", c_re, c_im + delta),
    ):
        child = _clone_work(work)
        child["c"] = {
            "re": _decimal_text(new_re),
            "im": _decimal_text(new_im),
        }
        mutations.append((relation, child))

    result: list[dict[str, Any]] = []
    for relation, child in mutations:
        result.append({
            "relation": relation,
            "work": identity_safe(child),
            "work_address": work_address(child),
        })
    return result


def _want_body(want: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": want.get("kind"),
        "version": want.get("version"),
        "parent_specimen_id": want.get("parent_specimen_id"),
        "parent_specimen_address": want.get("parent_specimen_address"),
        "relation": want.get("relation"),
        "work": want.get("work"),
        "work_address": want.get("work_address"),
    }


def derive_want_id(want: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        WANT_DOMAIN + jcs_bytes(identity_safe(_want_body(want)))
    ).hexdigest()
    return "ghot-ice-field-want-v0:" + digest


def work_to_capability_payload(
    work: dict[str, Any],
    *,
    return_url: str | None = None,
    return_particular: str | None = None,
    return_chunk_size: int | None = None,
) -> dict[str, Any]:
    render = work.get("render") or {}
    torus = work.get("mapping_torus") or {}
    halley = work.get("halley") or {}
    c = work.get("c") or {}
    payload = {
        "lucas_index": int(work["lucas_index"]),
        "c_re": str(c.get("re", "0")),
        "c_im": str(c.get("im", "0")),
        "width": int(render.get("width", 96)),
        "height": int(render.get("height", 96)),
        "max_halley_iter": int(render.get("max_halley_iter", 12)),
        "tolerance": str(halley.get("tolerance", "1e-9")),
        "fiber_count": int(torus.get("fiber_count", 72)),
    }
    if return_url is not None or return_particular is not None:
        if not return_url or not return_particular:
            raise ValueError("return_url and return_particular must be supplied together")
        payload["return_url"] = return_url
        payload["return_particular"] = return_particular
        if return_chunk_size is not None:
            payload["return_chunk_size"] = int(return_chunk_size)
    return payload


class IceFieldStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or ROOT).resolve()
        self.base = self.root / "ice-field"
        self.wants_dir = self.base / "wants"
        self.catalog_path = (
            self.root
            / "knowledge"
            / "plugins"
            / "ghot.plugin.verified-ice-cube"
            / "verified-ice-cubes.v0.json"
        )

    def _catalog(self) -> dict[str, Any]:
        if not self.catalog_path.exists():
            return {
                "kind": "ghot.verified-ice-cube-catalog",
                "version": "0",
                "entries": [],
                "merged_parcels": [],
            }
        value = _read_object(self.catalog_path)
        if value.get("kind") != "ghot.verified-ice-cube-catalog":
            raise ValueError("unexpected Ice Cube catalog kind")
        return value

    def _result_candidates(self, specimen_id: str) -> list[Path]:
        safe = _safe_name(specimen_id)
        return [
            self.root / "ice-cubes" / "returned" / safe / "result.return.v0.json",
            self.root / "ice-cubes" / "outgoing" / safe / "result.v0.json",
        ]

    def _load_result(self, specimen_id: str) -> dict[str, Any] | None:
        for path in self._result_candidates(specimen_id):
            if path.exists():
                value = _read_object(path)
                if value.get("specimen_id") == specimen_id:
                    return value
        return None

    def _want_path(self, want_id: str) -> Path:
        return self.wants_dir / f"{_safe_name(want_id)}.json"

    def wants(self) -> list[dict[str, Any]]:
        if not self.wants_dir.is_dir():
            return []
        result = []
        for path in sorted(self.wants_dir.glob("*.json")):
            try:
                want = _read_object(path)
            except Exception:
                continue
            if want.get("want_id") != derive_want_id(want):
                continue
            result.append(want)
        result.sort(key=lambda item: str(item.get("want_id")))
        return result

    def load(self, want_id: str) -> dict[str, Any]:
        path = self._want_path(want_id)
        if not path.exists():
            raise ValueError("unknown Ice Field want")
        want = _read_object(path)
        if want.get("want_id") != derive_want_id(want):
            raise ValueError("Ice Field want identity mismatch")
        return want

    def _save(self, want: dict[str, Any]) -> dict[str, Any]:
        _write_atomic(self._want_path(str(want["want_id"])), want)
        return want

    def refresh(self) -> dict[str, Any]:
        catalog = self._catalog()
        entries = [
            item for item in (catalog.get("entries") or [])
            if isinstance(item, dict)
        ]
        known_work = {
            str(item.get("work_address"))
            for item in entries
            if item.get("work_address")
        }
        existing_by_work = {
            str(item["work_address"]): item
            for item in self.wants()
            if item.get("work_address")
        }

        created: list[str] = []
        satisfied: list[str] = []
        unresolved_results: list[str] = []

        for work_addr, want in existing_by_work.items():
            desired = "satisfied" if work_addr in known_work else want.get("status", "open")
            if desired != want.get("status"):
                want["status"] = desired
                want["updated_at"] = timestamp_now()
                self._save(want)
                if desired == "satisfied":
                    satisfied.append(str(want["want_id"]))

        for entry in entries:
            specimen_id = str(entry.get("specimen_id") or "")
            if not specimen_id:
                continue
            result = self._load_result(specimen_id)
            if result is None:
                unresolved_results.append(specimen_id)
                continue
            specimen = result.get("specimen")
            if not isinstance(specimen, dict):
                unresolved_results.append(specimen_id)
                continue

            for neighbor in adjacent_work_specs(specimen):
                child_address = str(neighbor["work_address"])
                if child_address in known_work or child_address in existing_by_work:
                    continue
                want = {
                    "kind": WANT_KIND,
                    "version": WANT_VERSION,
                    "want_id": "",
                    "parent_specimen_id": specimen_id,
                    "parent_specimen_address": entry.get("specimen_address"),
                    "relation": neighbor["relation"],
                    "work": neighbor["work"],
                    "work_address": child_address,
                    "status": "open",
                    "created_at": timestamp_now(),
                    "updated_at": timestamp_now(),
                    "last_schedule": None,
                }
                want["want_id"] = derive_want_id(want)
                self._save(want)
                existing_by_work[child_address] = want
                created.append(str(want["want_id"]))

        current = self.wants()
        return {
            "kind": FIELD_KIND,
            "version": FIELD_VERSION,
            "pantry_entries": len(entries),
            "known_work_addresses": len(known_work),
            "want_count": len(current),
            "open_count": sum(item.get("status") == "open" for item in current),
            "satisfied_count": sum(item.get("status") == "satisfied" for item in current),
            "created": created,
            "newly_satisfied": satisfied,
            "unresolved_result_specimens": sorted(set(unresolved_results)),
        }

    def dispatch(
        self,
        want_id: str,
        *,
        return_url: str,
        return_particular: str,
        timeout: float = 2.0,
        return_chunk_size: int | None = None,
    ) -> dict[str, Any]:
        want = self.load(want_id)
        if want.get("status") == "satisfied":
            raise ValueError("Ice Field want is already satisfied")

        payload = work_to_capability_payload(
            want["work"],
            return_url=return_url,
            return_particular=return_particular,
            return_chunk_size=return_chunk_size,
        )
        result = schedule(
            ICE_CUBE_CAPABILITY,
            payload,
            urgency="background",
            deferrable=True,
            timeout=timeout,
            prefer_surplus_for_background=True,
            trigger=f"ice-field.want:{want_id}",
        )

        want["last_schedule"] = {
            "observed_at": timestamp_now(),
            "status": result.get("status"),
            "energy_plan_id": (result.get("energy_plan") or {}).get("energy_plan_id"),
            "action": (result.get("energy_plan") or {}).get("action"),
            "selected_node_id": (
                ((result.get("energy_plan") or {}).get("selected") or {}).get("node_id")
            ),
            "hold_id": (result.get("hold") or {}).get("hold_id"),
            "receipt_id": (
                (((result.get("execution") or {}).get("receipt")) or {}).get("receipt_id")
            ),
        }
        status = result.get("status")
        if status == "held":
            want["status"] = "held"
        elif status == "ok":
            want["status"] = "returned-hold"
        else:
            want["status"] = "open"
        want["updated_at"] = timestamp_now()
        self._save(want)
        return result

    def choose_open(self) -> dict[str, Any] | None:
        open_wants = [
            item for item in self.wants()
            if item.get("status") in {"open", "held", "returned-hold"}
        ]
        if not open_wants:
            return None
        relation_order = {
            "lucas-next": 0,
            "c-real-minus": 1,
            "c-real-plus": 2,
            "c-imag-minus": 3,
            "c-imag-plus": 4,
        }
        open_wants.sort(key=lambda item: (
            relation_order.get(str(item.get("relation")), 99),
            str(item.get("parent_specimen_id")),
            str(item.get("work_address")),
        ))
        return open_wants[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Grow and dispatch the GHoT Ice Field.")
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh")
    refresh.add_argument("--root", type=Path, default=Path(".ghot"))

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--root", type=Path, default=Path(".ghot"))

    dispatch = sub.add_parser("dispatch")
    dispatch.add_argument("want_id")
    dispatch.add_argument("--root", type=Path, default=Path(".ghot"))
    dispatch.add_argument("--return-url", required=True)
    dispatch.add_argument("--return-particular", required=True)
    dispatch.add_argument("--timeout", type=float, default=2.0)

    args = parser.parse_args()
    store = IceFieldStore(args.root)

    if args.command == "refresh":
        print(json.dumps(store.refresh(), indent=2))
        return 0
    if args.command == "list":
        print(json.dumps(store.wants(), indent=2))
        return 0
    if args.command == "dispatch":
        print(json.dumps(store.dispatch(
            args.want_id,
            return_url=args.return_url,
            return_particular=args.return_particular,
            timeout=args.timeout,
        ), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
