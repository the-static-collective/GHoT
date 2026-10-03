#!/usr/bin/env python3
"""Destination-side launch preflight — Experiment 027.

A Static-OS shell may route a typed launch descriptor here after the user
selects it. Preflight revalidates current context and may produce a fresh inert
invocation proposal.

Preflight never executes the operation and never grants consent or authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from composition_want import exact_source_match
from curious_doors import ReadOnlyCuriosityStore
from grammar_exchange import fetch_exchange_advert
from launch_descriptor import (
    APP_COMPOSITION_WANTS,
    APP_MERGE_PANTRY,
    APP_PLUGIN_PARCEL,
    ROUTES,
    verify_launch_descriptor,
)
from merge_plugin_parcel import verify_bundle as verify_plugin_bundle
from reference_node import ROOT
from relatte_identity import identity_safe, timestamp_now
from state_migration import semantic_address


PREFLIGHT_KIND = "ghot.launch.preflight"
PREFLIGHT_VERSION = "0"


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _safe_name(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _proposal(argv: list[str]) -> dict[str, Any]:
    return {
        "kind": "ghot.launch.invocation-proposal",
        "version": "0",
        "argv": argv,
        "executes": False,
        "authorization_granted": False,
        "consent_granted": False,
        "requires_separate_operator_action": True,
        "execution_revalidation_required": True,
    }


def _resolution(
    descriptor: dict[str, Any],
    *,
    status: str,
    checks: list[dict[str, Any]],
    proposal: dict[str, Any] | None = None,
    note: str | None = None,
    network_read_performed: bool = False,
) -> dict[str, Any]:
    return identity_safe({
        "kind": PREFLIGHT_KIND,
        "version": PREFLIGHT_VERSION,
        "launch_id": descriptor.get("launch_id"),
        "destination": descriptor.get("destination"),
        "status": status,
        "checks": checks,
        "proposal": proposal,
        "note": note,
        "preflighted_at": timestamp_now(),
        "destination_revalidated": status in {"ready", "stale"},
        "network_read_performed": network_read_performed,
        "executes": False,
        "authorization_granted": False,
        "consent_granted": False,
        "permission_transfer": False,
        "execution_revalidation_required": True,
    })


def _check(
    name: str,
    passed: bool,
    *,
    detail: Any = None,
) -> dict[str, Any]:
    return identity_safe({
        "name": name,
        "passed": bool(passed),
        "detail": detail,
    })


def _candidate(
    store: ReadOnlyCuriosityStore,
    *,
    want_id: str,
    candidate_id: str,
) -> dict[str, Any] | None:
    want = store.load_want(want_id)
    pool = [
        item
        for item in (want.get("candidates") or [])
        if isinstance(item, dict)
    ]
    for observation in store.observations(want_id=want_id):
        pool.extend(
            item
            for item in (observation.get("candidates") or [])
            if isinstance(item, dict)
        )
    matches = [
        item
        for item in pool
        if item.get("candidate_id") == candidate_id
    ]
    return matches[-1] if matches else None


def _plugin_parcel(
    root: Path,
    parcel_id: str,
) -> dict[str, Any]:
    safe = _safe_name(parcel_id)
    inbox_path = (
        root / "merge-plugin-parcels" / "inbox" / f"{safe}.json"
    )
    raw_path = (
        root / "merge-plugin-parcels" / "raw" / f"{safe}.json"
    )
    validation_path = (
        root / "merge-plugin-parcels" / "validation" / f"{safe}.json"
    )
    if not inbox_path.exists() or not raw_path.exists():
        raise ValueError("merge plugin parcel is not locally present")

    queue = _read_object(inbox_path)
    bundle = _read_object(raw_path)
    if not verify_plugin_bundle(bundle):
        raise ValueError("stored merge plugin parcel no longer verifies")
    parcel = bundle.get("parcel") or {}
    if parcel.get("parcel_id") != parcel_id:
        raise ValueError("merge plugin parcel id mismatch")

    validation = (
        _read_object(validation_path)
        if validation_path.exists()
        else None
    )
    return {
        "queue": queue,
        "bundle": bundle,
        "parcel": parcel,
        "validation": validation,
    }


def _preflight_composition_wants(
    descriptor: dict[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    destination = descriptor["destination"]
    operation = str(destination["operation"])
    context = descriptor["context"]
    want_id = str(context.get("want_id") or "")
    store = ReadOnlyCuriosityStore(root)
    checks: list[dict[str, Any]] = []

    try:
        want = store.load_want(want_id)
    except Exception as exc:
        return _resolution(
            descriptor,
            status="stale",
            checks=[
                _check(
                    "want-still-exists",
                    False,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            ],
            note="destination can no longer resolve the referenced WANT",
        )

    checks.append(_check(
        "want-still-exists",
        True,
        detail=want_id,
    ))

    if operation == "show-want":
        return _resolution(
            descriptor,
            status="ready",
            checks=checks,
            proposal=_proposal([
                "python3",
                "ghot/composition_want.py",
                "show",
                want_id,
            ]),
        )

    try:
        inspection = store.inspect(str(want["parcel_id"]))
    except Exception as exc:
        return _resolution(
            descriptor,
            status="blocked",
            checks=checks + [
                _check(
                    "local-gap-evidence-verifies",
                    False,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            ],
            note="local admitted evidence could not be revalidated",
        )

    compatible = list(
        inspection.get("compatible_contract_ids") or []
    )
    gap_open = not compatible
    checks.append(_check(
        "composition-gap-still-open",
        gap_open,
        detail={"compatible_contract_ids": compatible},
    ))
    if not gap_open:
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="a compatible local grammar now satisfies this gap",
        )

    if operation == "refresh-candidates":
        return _resolution(
            descriptor,
            status="ready",
            checks=checks,
            proposal=_proposal([
                "python3",
                "ghot/composition_want.py",
                "refresh",
                want_id,
                "--scan",
            ]),
        )

    if operation != "request-candidate":
        return _resolution(
            descriptor,
            status="blocked",
            checks=checks,
            note="unsupported Composition Wants operation",
        )

    candidate_id = str(context.get("candidate_id") or "")
    candidate = _candidate(
        store,
        want_id=want_id,
        candidate_id=candidate_id,
    )
    checks.append(_check(
        "candidate-belongs-to-want-history",
        candidate is not None,
        detail=candidate_id,
    ))
    if candidate is None:
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="candidate no longer belongs to verified WANT history",
        )

    bound_fields = (
        "package_id",
        "package_address",
        "contract_id",
        "source_particular",
    )
    context_matches = all(
        context.get(field) == candidate.get(field)
        for field in bound_fields
    )
    checks.append(_check(
        "descriptor-context-matches-candidate",
        context_matches,
        detail={
            field: candidate.get(field)
            for field in bound_fields
        },
    ))
    if not context_matches:
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="launch context no longer matches candidate evidence",
        )

    exchange_url = str(candidate.get("exchange_url") or "")
    try:
        advert = fetch_exchange_advert(exchange_url)
    except Exception as exc:
        return _resolution(
            descriptor,
            status="blocked",
            checks=checks + [
                _check(
                    "fresh-source-advert-reachable",
                    False,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            ],
            note="destination could not revalidate current remote share state",
            network_read_performed=True,
        )

    checks.append(_check(
        "fresh-source-advert-reachable",
        True,
        detail=advert.get("advert_id"),
    ))
    source_matches = (
        advert.get("particular")
        == candidate.get("source_particular")
    )
    checks.append(_check(
        "source-body-identity-unchanged",
        source_matches,
        detail=advert.get("particular"),
    ))
    if not source_matches:
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="candidate source BODY identity changed",
            network_read_performed=True,
        )

    package = next(
        (
            item
            for item in (advert.get("packages") or [])
            if (
                item.get("package_id") == candidate.get("package_id")
                and item.get("package_address")
                == candidate.get("package_address")
            )
        ),
        None,
    )
    checks.append(_check(
        "exact-package-still-shared",
        isinstance(package, dict),
        detail=candidate.get("package_address"),
    ))
    if not isinstance(package, dict):
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="candidate package is no longer currently shared",
            network_read_performed=True,
        )

    contract_matches = (
        package.get("contract_id")
        == candidate.get("contract_id")
    )
    source_shape_matches = exact_source_match(
        package.get("source"),
        want.get("source"),
    )
    checks.extend([
        _check(
            "contract-identity-unchanged",
            contract_matches,
            detail=package.get("contract_id"),
        ),
        _check(
            "source-shape-still-matches-gap",
            source_shape_matches,
            detail=package.get("source"),
        ),
    ])
    if not contract_matches or not source_shape_matches:
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="candidate contract/source shape changed",
            network_read_performed=True,
        )

    return _resolution(
        descriptor,
        status="ready",
        checks=checks,
        proposal=_proposal([
            "python3",
            "ghot/composition_want.py",
            "request",
            want_id,
            candidate_id,
        ]),
        network_read_performed=True,
    )


def _preflight_plugin_parcel(
    descriptor: dict[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    operation = str(descriptor["destination"]["operation"])
    context = descriptor["context"]
    parcel_id = str(context.get("plugin_parcel_id") or "")
    checks: list[dict[str, Any]] = []

    try:
        current = _plugin_parcel(root, parcel_id)
    except Exception as exc:
        return _resolution(
            descriptor,
            status="stale",
            checks=[
                _check(
                    "plugin-parcel-still-verifies",
                    False,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            ],
            note="destination can no longer resolve the plugin parcel",
        )

    queue = current["queue"]
    parcel = current["parcel"]
    status = queue.get("status")
    checks.append(_check(
        "plugin-parcel-still-verifies",
        True,
        detail=parcel_id,
    ))

    package_matches = (
        context.get("package_address")
        == parcel.get("package_address")
    )
    checks.append(_check(
        "package-address-unchanged",
        package_matches,
        detail=parcel.get("package_address"),
    ))
    if not package_matches:
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="plugin parcel package address changed",
        )

    expected_status = context.get("expected_status")
    status_matches = status == expected_status
    checks.append(_check(
        "expected-parcel-status-still-current",
        status_matches,
        detail={"expected": expected_status, "current": status},
    ))
    if not status_matches and operation != "show-parcel":
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="plugin parcel advanced since descriptor creation",
        )

    if operation == "show-parcel":
        return _resolution(
            descriptor,
            status="ready",
            checks=checks,
            proposal=_proposal([
                "python3",
                "ghot/merge_plugin_parcel.py",
                "show",
                parcel_id,
            ]),
        )

    if operation == "validate-parcel":
        hold = status == "HOLD"
        checks.append(_check(
            "parcel-is-currently-hold",
            hold,
            detail=status,
        ))
        if not hold:
            return _resolution(
                descriptor,
                status="stale",
                checks=checks,
                note="only a current HOLD may be validated",
            )
        return _resolution(
            descriptor,
            status="ready",
            checks=checks,
            proposal=_proposal([
                "python3",
                "ghot/merge_plugin_parcel.py",
                "validate",
                parcel_id,
            ]),
        )

    if operation != "install-parcel":
        return _resolution(
            descriptor,
            status="blocked",
            checks=checks,
            note="unsupported merge plugin parcel operation",
        )

    validated = status == "VALIDATED"
    checks.append(_check(
        "parcel-is-currently-validated",
        validated,
        detail=status,
    ))
    if not validated:
        return _resolution(
            descriptor,
            status="stale",
            checks=checks,
            note="only a current VALIDATED parcel may be installed",
        )

    validation = current.get("validation")
    validation_valid = (
        isinstance(validation, dict)
        and queue.get("validation_address")
        == semantic_address(identity_safe(validation))
        and validation.get("package_address")
        == parcel.get("package_address")
        and validation.get("installable") is True
    )
    checks.append(_check(
        "validation-report-still-binds-package",
        validation_valid,
        detail=queue.get("validation_address"),
    ))
    if not validation_valid:
        return _resolution(
            descriptor,
            status="blocked",
            checks=checks,
            note="local validation evidence no longer supports install",
        )

    return _resolution(
        descriptor,
        status="ready",
        checks=checks,
        proposal=_proposal([
            "python3",
            "ghot/merge_plugin_parcel.py",
            "install",
            parcel_id,
        ]),
    )


def _preflight_merge_pantry(
    descriptor: dict[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    operation = str(descriptor["destination"]["operation"])
    context = descriptor["context"]
    parcel_id = str(context.get("parcel_id") or "")
    store = ReadOnlyCuriosityStore(root)
    if operation != "inspect-parcel":
        return _resolution(
            descriptor,
            status="blocked",
            checks=[],
            note="unsupported merge pantry operation",
        )
    try:
        inspection = store.inspect(parcel_id)
    except Exception as exc:
        return _resolution(
            descriptor,
            status="stale",
            checks=[
                _check(
                    "admitted-parcel-still-inspectable",
                    False,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            ],
            note="merge pantry can no longer inspect this parcel",
        )
    return _resolution(
        descriptor,
        status="ready",
        checks=[
            _check(
                "admitted-parcel-still-inspectable",
                True,
                detail={
                    "compatible_contract_ids": inspection.get(
                        "compatible_contract_ids"
                    )
                },
            )
        ],
        proposal=_proposal([
            "python3",
            "ghot/merge_contract_pantry.py",
            "inspect",
            parcel_id,
        ]),
    )


def preflight_launch(
    descriptor: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    state_root = root or ROOT
    if not verify_launch_descriptor(descriptor):
        return _resolution(
            descriptor,
            status="blocked",
            checks=[
                _check(
                    "descriptor-verifies",
                    False,
                    detail="launch descriptor failed content/policy verification",
                )
            ],
            note="descriptor is invalid",
        )

    destination = descriptor["destination"]
    app_id = str(destination["app_id"])
    checks = [
        _check(
            "descriptor-verifies",
            True,
            detail=descriptor["launch_id"],
        ),
        _check(
            "route-is-known",
            app_id in ROUTES,
            detail=app_id,
        ),
    ]

    try:
        if app_id == APP_COMPOSITION_WANTS:
            result = _preflight_composition_wants(
                descriptor,
                root=state_root,
            )
        elif app_id == APP_PLUGIN_PARCEL:
            result = _preflight_plugin_parcel(
                descriptor,
                root=state_root,
            )
        elif app_id == APP_MERGE_PANTRY:
            result = _preflight_merge_pantry(
                descriptor,
                root=state_root,
            )
        else:
            return _resolution(
                descriptor,
                status="blocked",
                checks=checks,
                note="no destination adapter owns this app id",
            )
    except Exception as exc:
        return _resolution(
            descriptor,
            status="blocked",
            checks=checks,
            note=f"{type(exc).__name__}: {exc}",
        )

    result["checks"] = checks + list(result.get("checks") or [])
    return identity_safe(result)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Revalidate a typed launch descriptor at its owning destination "
            "without executing it."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("descriptor_file")

    preflight = sub.add_parser("preflight")
    preflight.add_argument("descriptor_file")

    args = parser.parse_args()
    descriptor = _read_object(
        Path(args.descriptor_file).expanduser()
    )

    if args.command == "verify":
        valid = verify_launch_descriptor(descriptor)
        print(json.dumps({"valid": valid}, indent=2))
        return 0 if valid else 1

    result = preflight_launch(descriptor)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
