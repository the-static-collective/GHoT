#!/usr/bin/env python3
"""Composition gaps and explicit wants — Experiment 024.

024 grounds every gap in one concrete locally ADMITTED state parcel.

Flow:
    admitted parcel
      -> local 020 pantry inspection
      -> exact missing source grammar => GAP
      -> observed exact-shape remote packages => CANDIDATES
      -> explicit local WANT
      -> explicit candidate-specific REQUEST through 023

No ranking, recommendation, automatic request, offer, crossing, or install.

Laws:
    GAP != REQUEST
    CANDIDATE != RECOMMENDATION
    WANT != AUTHORITY
    ONE CANDIDATE != AUTOMATIC CHOICE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Iterable

from grammar_exchange import (
    advert_is_fresh,
    discover_exchanges,
    fetch_exchange_advert,
    send_request,
    verify_exchange_advert,
)
from merge_contract_pantry import MergeContractPantry
from reference_node import ROOT
from relatte_identity import identity_safe, jcs_bytes, timestamp_now
from state_migration import semantic_address


GAP_KIND = "ghot.composition.gap"
GAP_VERSION = "0"
GAP_ID_DOMAIN = b"GHoT-CompositionGap-v0|"

WANT_KIND = "ghot.composition.want"
WANT_VERSION = "0"
WANT_ID_DOMAIN = b"GHoT-CompositionWant-v0|"

REQUEST_LINK_KIND = "ghot.composition.want-request-link"
REQUEST_LINK_VERSION = "0"
REQUEST_LINK_ID_DOMAIN = b"GHoT-CompositionWantRequestLink-v0|"

CANDIDATE_ID_DOMAIN = b"GHoT-CompositionCandidate-v0|"


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
        raise ValueError(f"JSON object required: {path}")
    return value


def source_shape(value: dict[str, Any] | None) -> dict[str, Any]:
    source = value or {}
    return identity_safe({
        "state_kind": source.get("state_kind"),
        "state_version": source.get("state_version"),
        "selector": source.get("selector"),
        "payload_type": source.get("payload_type"),
    })


def exact_source_match(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> bool:
    return source_shape(left) == source_shape(right)


def _gap_identity(gap: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": gap.get("kind"),
        "version": gap.get("version"),
        "parcel_id": gap.get("parcel_id"),
        "parcel_address": gap.get("parcel_address"),
        "payload_address": gap.get("payload_address"),
        "admitted_ref": gap.get("admitted_ref"),
        "source": gap.get("source"),
    }


def derive_gap_id(gap: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        GAP_ID_DOMAIN + jcs_bytes(identity_safe(_gap_identity(gap)))
    ).hexdigest()
    return "ghot-composition-gap-v0:" + digest


def _candidate_identity(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_particular": candidate.get("source_particular"),
        "package_id": candidate.get("package_id"),
        "package_version": candidate.get("package_version"),
        "package_address": candidate.get("package_address"),
        "contract_id": candidate.get("contract_id"),
        "source": candidate.get("source"),
    }


def derive_candidate_id(candidate: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        CANDIDATE_ID_DOMAIN
        + jcs_bytes(identity_safe(_candidate_identity(candidate)))
    ).hexdigest()
    return "ghot-composition-candidate-v0:" + digest


def _want_body(want: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": want.get("kind"),
        "version": want.get("version"),
        "gap_id": want.get("gap_id"),
        "parcel_id": want.get("parcel_id"),
        "parcel_address": want.get("parcel_address"),
        "payload_address": want.get("payload_address"),
        "admitted_ref": want.get("admitted_ref"),
        "source": want.get("source"),
        "candidates": want.get("candidates"),
        "created_at": want.get("created_at"),
        "note": want.get("note"),
    }


def derive_want_id(want: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        WANT_ID_DOMAIN + jcs_bytes(identity_safe(_want_body(want)))
    ).hexdigest()
    return "ghot-composition-want-v0:" + digest


def _request_link_body(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": link.get("kind"),
        "version": link.get("version"),
        "want_id": link.get("want_id"),
        "gap_id": link.get("gap_id"),
        "candidate_id": link.get("candidate_id"),
        "request_id": link.get("request_id"),
        "request_receipt_id": link.get("request_receipt_id"),
        "source_particular": link.get("source_particular"),
        "package_id": link.get("package_id"),
        "package_address": link.get("package_address"),
        "requested_at": link.get("requested_at"),
    }


def derive_request_link_id(link: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        REQUEST_LINK_ID_DOMAIN
        + jcs_bytes(identity_safe(_request_link_body(link)))
    ).hexdigest()
    return "ghot-composition-want-request-link-v0:" + digest


def candidates_from_observations(
    *,
    required_source: dict[str, Any],
    observations: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    for observation in observations:
        advert = observation.get("advert")
        exchange_url = observation.get("exchange_url")
        if (
            not isinstance(advert, dict)
            or not isinstance(exchange_url, str)
            or not exchange_url
            or not verify_exchange_advert(advert)
            or not advert_is_fresh(advert)
        ):
            continue

        for package in advert.get("packages") or []:
            if not isinstance(package, dict):
                continue
            if not exact_source_match(
                required_source,
                package.get("source"),
            ):
                continue

            candidate = identity_safe({
                "candidate_id": "",
                "match": "exact-source-shape",
                "source_particular": advert.get("particular"),
                "source_node_id": advert.get("node_id"),
                "exchange_url": exchange_url.rstrip("/"),
                "advert_id": advert.get("advert_id"),
                "advert_issued_at": advert.get("issued_at"),
                "advert_address": semantic_address(advert),
                "package_id": package.get("package_id"),
                "package_version": package.get("package_version"),
                "package_address": package.get("package_address"),
                "contract_id": package.get("contract_id"),
                "title": package.get("title"),
                "category": package.get("category"),
                "source": source_shape(package.get("source")),
                "target": package.get("target"),
                "operation_kind": package.get("operation_kind"),
                "author_particular": package.get("author_particular"),
            })
            candidate["candidate_id"] = derive_candidate_id(candidate)

            existing = by_id.get(candidate["candidate_id"])
            if existing is None:
                by_id[candidate["candidate_id"]] = candidate
                continue

            # Same source identity + package address observed by more than one
            # road. Keep a deterministic route snapshot without implying that
            # one road is preferred.
            if str(candidate["exchange_url"]) < str(existing["exchange_url"]):
                by_id[candidate["candidate_id"]] = candidate

    return [
        by_id[key]
        for key in sorted(by_id)
    ]


def collect_observations(
    *,
    exchange_urls: list[str] | None = None,
    scan: bool = False,
    timeout: float = 2.0,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for url in exchange_urls or []:
        clean = url.rstrip("/")
        advert = fetch_exchange_advert(clean)
        key = (str(advert.get("particular")), clean)
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "advert": advert,
            "exchange_url": clean,
            "source": "explicit-url",
        })

    if scan:
        for item in discover_exchanges(timeout):
            advert = item.get("advert")
            url = item.get("exchange_url")
            if not isinstance(advert, dict) or not isinstance(url, str):
                continue
            clean = url.rstrip("/")
            key = (str(advert.get("particular")), clean)
            if key in seen:
                continue
            seen.add(key)
            result.append({
                "advert": advert,
                "exchange_url": clean,
                "source": "lan-discovery",
            })

    result.sort(
        key=lambda item: (
            str((item.get("advert") or {}).get("particular")),
            str(item.get("exchange_url")),
        )
    )
    return result


class CompositionWantStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.pantry = MergeContractPantry(self.root)
        self.base = self.root / "composition-wants"
        self.wants_dir = self.base / "wants"
        self.request_links_dir = self.base / "request-links"

    def inspect_gap(
        self,
        parcel_id: str,
        *,
        observations: Iterable[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        inspection = self.pantry.inspect(parcel_id)
        source = source_shape(inspection.get("source"))
        compatible = list(inspection.get("compatible_contract_ids") or [])

        gap = {
            "kind": GAP_KIND,
            "version": GAP_VERSION,
            "gap_id": "",
            "parcel_id": inspection["parcel_id"],
            "parcel_address": inspection["parcel_address"],
            "payload_address": inspection["payload_address"],
            "admitted_ref": inspection["admitted_ref"],
            "source": source,
            "local_compatible_contract_ids": compatible,
            "status": (
                "satisfied-local"
                if compatible
                else "gap"
            ),
            "candidates": (
                []
                if compatible
                else candidates_from_observations(
                    required_source=source,
                    observations=observations,
                )
            ),
            "observed_at": timestamp_now(),
        }
        gap["gap_id"] = derive_gap_id(gap)
        gap["candidate_count"] = len(gap["candidates"])
        return identity_safe(gap)

    def declare_want(
        self,
        parcel_id: str,
        *,
        observations: Iterable[dict[str, Any]] = (),
        note: str | None = None,
    ) -> dict[str, Any]:
        gap = self.inspect_gap(
            parcel_id,
            observations=observations,
        )
        if gap["status"] != "gap":
            raise ValueError(
                "parcel already has a compatible local merge grammar"
            )

        want = {
            "kind": WANT_KIND,
            "version": WANT_VERSION,
            "want_id": "",
            "gap_id": gap["gap_id"],
            "parcel_id": gap["parcel_id"],
            "parcel_address": gap["parcel_address"],
            "payload_address": gap["payload_address"],
            "admitted_ref": gap["admitted_ref"],
            "source": gap["source"],
            "candidates": gap["candidates"],
            "created_at": timestamp_now(),
            "note": note,
        }
        want["want_id"] = derive_want_id(want)
        self.wants_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(
            self.wants_dir / f"{_safe_name(want['want_id'])}.json",
            want,
        )
        return want

    def wants(self) -> list[dict[str, Any]]:
        if not self.wants_dir.is_dir():
            return []
        result = []
        for path in sorted(self.wants_dir.glob("*.json")):
            try:
                want = _read_object(path)
            except Exception:
                continue
            links = self.request_links(want_id=str(want.get("want_id")))
            result.append({
                **want,
                "request_links": links,
            })
        return result

    def load_want(self, want_id: str) -> dict[str, Any]:
        path = self.wants_dir / f"{_safe_name(want_id)}.json"
        if not path.exists():
            raise ValueError("unknown composition want")
        want = _read_object(path)
        if want.get("want_id") != derive_want_id(want):
            raise ValueError("composition want content address mismatch")
        return want

    def request_links(
        self,
        *,
        want_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.request_links_dir.is_dir():
            return []
        result = []
        for path in sorted(self.request_links_dir.glob("*.json")):
            try:
                link = _read_object(path)
            except Exception:
                continue
            if (
                link.get("link_id") != derive_request_link_id(link)
                or (
                    want_id is not None
                    and link.get("want_id") != want_id
                )
            ):
                continue
            result.append(link)
        return result

    def show(self, want_id: str) -> dict[str, Any]:
        want = self.load_want(want_id)
        current = self.pantry.inspect(str(want["parcel_id"]))
        return {
            "want": want,
            "current_local_inspection": current,
            "request_links": self.request_links(want_id=want_id),
        }

    def _revalidate_want_gap(
        self,
        want: dict[str, Any],
    ) -> dict[str, Any]:
        inspection = self.pantry.inspect(str(want["parcel_id"]))

        if inspection.get("parcel_address") != want.get("parcel_address"):
            raise ValueError("wanted parcel address changed")
        if inspection.get("payload_address") != want.get("payload_address"):
            raise ValueError("wanted payload address changed")
        if inspection.get("admitted_ref") != want.get("admitted_ref"):
            raise ValueError("wanted admitted materialization changed")
        if not exact_source_match(
            inspection.get("source"),
            want.get("source"),
        ):
            raise ValueError("wanted source grammar shape changed")
        if inspection.get("compatible_contract_ids"):
            raise ValueError(
                "composition gap is now satisfied by a local grammar"
            )
        return inspection

    def request_candidate(
        self,
        want_id: str,
        candidate_id: str,
        *,
        return_parcel_port: int = 7792,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        want = self.load_want(want_id)
        self._revalidate_want_gap(want)

        candidate = next(
            (
                item
                for item in want.get("candidates") or []
                if item.get("candidate_id") == candidate_id
            ),
            None,
        )
        if not isinstance(candidate, dict):
            raise ValueError(
                "candidate is not part of this durable want snapshot"
            )

        source_url = str(candidate["exchange_url"]).rstrip("/")
        advert = fetch_exchange_advert(source_url)
        if advert.get("particular") != candidate.get("source_particular"):
            raise ValueError("candidate source BODY identity changed")

        package = next(
            (
                item
                for item in advert.get("packages") or []
                if (
                    item.get("package_id") == candidate.get("package_id")
                    and item.get("package_address")
                    == candidate.get("package_address")
                )
            ),
            None,
        )
        if not isinstance(package, dict):
            raise ValueError(
                "candidate package is no longer currently advertised"
            )
        if package.get("contract_id") != candidate.get("contract_id"):
            raise ValueError("candidate contract identity changed")
        if not exact_source_match(
            package.get("source"),
            want.get("source"),
        ):
            raise ValueError(
                "candidate no longer matches the composition gap"
            )

        outgoing = send_request(
            source_url=source_url,
            package_id=str(candidate["package_id"]),
            package_address=str(candidate["package_address"]),
            root=self.root,
            return_parcel_port=return_parcel_port,
            ttl_seconds=ttl_seconds,
        )
        request = outgoing["request"]
        receipt = outgoing["receipt"]

        link = {
            "kind": REQUEST_LINK_KIND,
            "version": REQUEST_LINK_VERSION,
            "link_id": "",
            "want_id": want["want_id"],
            "gap_id": want["gap_id"],
            "candidate_id": candidate["candidate_id"],
            "request_id": request["request_id"],
            "request_receipt_id": receipt["receipt_id"],
            "source_particular": candidate["source_particular"],
            "package_id": candidate["package_id"],
            "package_address": candidate["package_address"],
            "requested_at": timestamp_now(),
        }
        link["link_id"] = derive_request_link_id(link)
        self.request_links_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(
            self.request_links_dir / f"{_safe_name(link['link_id'])}.json",
            link,
        )
        return {
            "want": want,
            "candidate": candidate,
            "outgoing_request": outgoing,
            "link": link,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Notice concrete missing composition grammars, persist explicit "
            "wants, and request only an explicitly chosen observed candidate."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("parcel_id")
    inspect.add_argument("--exchange-url", action="append", default=[])
    inspect.add_argument("--scan", action="store_true")
    inspect.add_argument("--timeout", type=float, default=2.0)

    want = sub.add_parser("want")
    want.add_argument("parcel_id")
    want.add_argument("--exchange-url", action="append", default=[])
    want.add_argument("--scan", action="store_true")
    want.add_argument("--timeout", type=float, default=2.0)
    want.add_argument("--note", default=None)

    sub.add_parser("wants")

    show = sub.add_parser("show")
    show.add_argument("want_id")

    request = sub.add_parser("request")
    request.add_argument("want_id")
    request.add_argument("candidate_id")
    request.add_argument("--return-parcel-port", type=int, default=7792)
    request.add_argument("--ttl", type=int, default=300)

    args = parser.parse_args()
    store = CompositionWantStore()

    if args.command in {"inspect", "want"}:
        observations = collect_observations(
            exchange_urls=args.exchange_url,
            scan=args.scan,
            timeout=args.timeout,
        )
        if args.command == "inspect":
            print(json.dumps(
                store.inspect_gap(
                    args.parcel_id,
                    observations=observations,
                ),
                indent=2,
            ))
            return 0
        print(json.dumps(
            store.declare_want(
                args.parcel_id,
                observations=observations,
                note=args.note,
            ),
            indent=2,
        ))
        return 0

    if args.command == "wants":
        print(json.dumps(store.wants(), indent=2))
        return 0

    if args.command == "show":
        print(json.dumps(store.show(args.want_id), indent=2))
        return 0

    if args.command == "request":
        print(json.dumps(
            store.request_candidate(
                args.want_id,
                args.candidate_id,
                return_parcel_port=args.return_parcel_port,
                ttl_seconds=args.ttl,
            ),
            indent=2,
        ))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
