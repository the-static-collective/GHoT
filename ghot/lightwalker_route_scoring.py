#!/usr/bin/env python3
"""Lightwalker Route Scoring / Multi-Factor Selection 001.

Signed measurements describe route conditions. A promisor-local weighting policy
may derive a preference score from those measurements. Neither the measurements,
the score, nor the preference create remote authority.

Core laws:
    SCORE != VALUE
    SCORE != AUTHORITY
    MEASUREMENT != PREFERENCE
    PREFERENCE != ADMISSION
    LOWER COST != UNIVERSALLY BETTER
    POLICY WEIGHTS ARE LOCAL
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_federated_reroute import make_reroute
from lightwalker_federated_service import verify_remote_capacity_proof
from lightwalker_multi_source_service import verify_multi_source_promise
from lightwalker_route_policy import (
    make_owner_admission_response,
    select_route,
    verify_owner_admission_response,
    verify_route_policy,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


MEASUREMENT_KIND = "ghot.lightwalker.route-measurement"
MEASUREMENT_VERSION = "0"
SCORING_POLICY_KIND = "ghot.lightwalker.route-scoring-policy"
SCORING_POLICY_VERSION = "0"
SELECTION_KIND = "ghot.lightwalker.scored-route-selection"
SELECTION_VERSION = "0"
BINDING_KIND = "ghot.lightwalker.scored-policy-bound-reroute"
BINDING_VERSION = "0"

MEASUREMENT_DOMAIN = "ghot.lightwalker-route-measurement-signature/v0"
SCORING_POLICY_DOMAIN = "ghot.lightwalker-route-scoring-policy-signature/v0"
MEASUREMENT_BYTES = b"GHOT-LightwalkerRouteMeasurement-v0|"
SCORING_POLICY_BYTES = b"GHOT-LightwalkerRouteScoringPolicy-v0|"

_WEIGHT_KEYS = (
    "freshness",
    "quantity_headroom",
    "reliability",
    "latency",
    "energy",
    "completion_window",
)


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nni(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(
            f"{name} must be a non-negative integer"
        )
    return value


def _signed(
    body: dict[str, Any],
    *,
    id_field: str,
    signer: IdentityKey,
    domain: str,
    byte_domain: bytes,
) -> dict[str, Any]:
    item_id = content_address(body)
    value = {
        **body,
        id_field: item_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": domain,
        },
    }
    value["signing"]["signature"] = signer.sign(
        byte_domain + canonical_bytes({id_field: item_id, **body})
    )
    return value


def _verify_signed(
    value: dict[str, Any],
    *,
    id_field: str,
    particular_field: str,
    domain: str,
    byte_domain: bytes,
) -> bool:
    try:
        signing = value.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != domain:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != value.get(
            particular_field
        ):
            return False
        body = {
            key: item
            for key, item in value.items()
            if key not in {id_field, "signing"}
        }
        item_id = value.get(id_field)
        if not isinstance(item_id, str) or content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            byte_domain
            + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def make_route_measurement(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
    *,
    measurer: IdentityKey,
    latency_ms: int,
    reliability_ppm: int,
    energy_mwh_per_compute_minute: int,
    expected_completion_cuts: int,
    observed_cut: int,
) -> dict[str, Any]:
    if not verify_remote_capacity_proof(snapshot, proof):
        raise LightwalkerEconomyError(
            "route measurement requires valid remote capacity proof"
        )
    reliability = _nni(reliability_ppm, "reliability_ppm")
    if reliability > 1_000_000:
        raise LightwalkerEconomyError(
            "reliability_ppm must be <= 1000000"
        )
    body = {
        "kind": MEASUREMENT_KIND,
        "version": MEASUREMENT_VERSION,
        "authority": "measurement-evidence-only",
        "measurer_particular": measurer.particular(),
        "capacity_guild_id": proof["capacity_guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "remote_proof_id": proof["remote_proof_id"],
        "resource_entry_id": proof["resource_entry_id"],
        "observed_cut": _nni(observed_cut, "observed_cut"),
        "metrics": {
            "latency_ms": _nni(latency_ms, "latency_ms"),
            "reliability_ppm": reliability,
            "energy_mwh_per_compute_minute": _nni(
                energy_mwh_per_compute_minute,
                "energy_mwh_per_compute_minute",
            ),
            "expected_completion_cuts": _nni(
                expected_completion_cuts,
                "expected_completion_cuts",
            ),
        },
        "score": None,
        "preference_authority": "none",
        "reservation_authority": "none",
        "execution_authority": "none",
        "laws": [
            "MEASUREMENT != PREFERENCE",
            "SCORE != AUTHORITY",
        ],
    }
    return _signed(
        body,
        id_field="measurement_id",
        signer=measurer,
        domain=MEASUREMENT_DOMAIN,
        byte_domain=MEASUREMENT_BYTES,
    )


def verify_route_measurement(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
    measurement: dict[str, Any],
) -> bool:
    try:
        if not verify_remote_capacity_proof(snapshot, proof):
            return False
        if measurement.get("kind") != MEASUREMENT_KIND:
            return False
        if measurement.get("version") != MEASUREMENT_VERSION:
            return False
        if measurement.get("authority") != "measurement-evidence-only":
            return False
        if measurement.get("capacity_guild_id") != proof["capacity_guild_id"]:
            return False
        if measurement.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if measurement.get("remote_proof_id") != proof["remote_proof_id"]:
            return False
        if measurement.get("resource_entry_id") != proof["resource_entry_id"]:
            return False
        metrics = measurement.get("metrics")
        if not isinstance(metrics, dict):
            return False
        if int(metrics.get("reliability_ppm", -1)) > 1_000_000:
            return False
        for key in (
            "latency_ms",
            "reliability_ppm",
            "energy_mwh_per_compute_minute",
            "expected_completion_cuts",
        ):
            if isinstance(metrics.get(key), bool) or not isinstance(
                metrics.get(key), int
            ) or int(metrics[key]) < 0:
                return False
        if measurement.get("score") is not None:
            return False
        if measurement.get("preference_authority") != "none":
            return False
        if measurement.get("reservation_authority") != "none":
            return False
        if measurement.get("execution_authority") != "none":
            return False
        return _verify_signed(
            measurement,
            id_field="measurement_id",
            particular_field="measurer_particular",
            domain=MEASUREMENT_DOMAIN,
            byte_domain=MEASUREMENT_BYTES,
        )
    except Exception:
        return False


def _normalize_weights(weights: dict[str, Any]) -> dict[str, int]:
    if not isinstance(weights, dict):
        raise LightwalkerEconomyError("weights must be an object")
    if set(weights) != set(_WEIGHT_KEYS):
        raise LightwalkerEconomyError(
            "weights must declare the exact scoring dimensions"
        )
    normalized = {
        key: _nni(weights[key], f"weight.{key}")
        for key in _WEIGHT_KEYS
    }
    if not any(normalized.values()):
        raise LightwalkerEconomyError(
            "at least one scoring weight must be non-zero"
        )
    return normalized


def make_scoring_policy(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    *,
    promisor: IdentityKey,
    trusted_measurer_particular: str,
    profile_name: str,
    weights: dict[str, Any],
    max_measurement_age_cuts: int,
    created_at_cut: int,
) -> dict[str, Any]:
    if not verify_route_policy(promise, route_policy):
        raise LightwalkerEconomyError("invalid base route policy")
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError(
            "scoring policy signer is not promisor"
        )
    body = {
        "kind": SCORING_POLICY_KIND,
        "version": SCORING_POLICY_VERSION,
        "authority": "promisor-local-preference-only",
        "promisor_particular": promisor.particular(),
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "profile_name": _nonempty(profile_name, "profile_name"),
        "trusted_measurer_particular": _nonempty(
            trusted_measurer_particular,
            "trusted_measurer_particular",
        ),
        "weights": _normalize_weights(weights),
        "max_measurement_age_cuts": _nni(
            max_measurement_age_cuts,
            "max_measurement_age_cuts",
        ),
        "created_at_cut": _nni(created_at_cut, "created_at_cut"),
        "score_semantics": "local-comparison-only",
        "value_authority": "none",
        "reservation_authority": "none",
        "execution_authority": "none",
        "admission_authority": "none",
        "laws": [
            "SCORE != VALUE",
            "SCORE != AUTHORITY",
            "MEASUREMENT != PREFERENCE",
            "PREFERENCE != ADMISSION",
            "LOWER COST != UNIVERSALLY BETTER",
            "POLICY WEIGHTS ARE LOCAL",
        ],
    }
    return _signed(
        body,
        id_field="scoring_policy_id",
        signer=promisor,
        domain=SCORING_POLICY_DOMAIN,
        byte_domain=SCORING_POLICY_BYTES,
    )


def verify_scoring_policy(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    scoring_policy: dict[str, Any],
) -> bool:
    try:
        if not verify_route_policy(promise, route_policy):
            return False
        if scoring_policy.get("kind") != SCORING_POLICY_KIND:
            return False
        if scoring_policy.get("version") != SCORING_POLICY_VERSION:
            return False
        if (
            scoring_policy.get("authority")
            != "promisor-local-preference-only"
        ):
            return False
        if scoring_policy.get("promise_id") != promise["promise_id"]:
            return False
        if (
            scoring_policy.get("route_policy_id")
            != route_policy["policy_id"]
        ):
            return False
        if (
            scoring_policy.get("source_slot_id")
            != route_policy["source_slot_id"]
        ):
            return False
        if (
            scoring_policy.get("promisor_particular")
            != promise["promisor_particular"]
        ):
            return False
        _normalize_weights(scoring_policy["weights"])
        if scoring_policy.get("score_semantics") != "local-comparison-only":
            return False
        for field in (
            "value_authority",
            "reservation_authority",
            "execution_authority",
            "admission_authority",
        ):
            if scoring_policy.get(field) != "none":
                return False
        return _verify_signed(
            scoring_policy,
            id_field="scoring_policy_id",
            particular_field="promisor_particular",
            domain=SCORING_POLICY_DOMAIN,
            byte_domain=SCORING_POLICY_BYTES,
        )
    except Exception:
        return False


def _measurement_map(
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    *,
    trusted_measurer_particular: str,
) -> dict[str, dict[str, Any]]:
    candidate_by_proof = {
        item["proof"]["remote_proof_id"]: item
        for item in candidates
    }
    result: dict[str, dict[str, Any]] = {}
    for measurement in measurements:
        proof_id = measurement.get("remote_proof_id")
        candidate = candidate_by_proof.get(proof_id)
        if candidate is None:
            raise LightwalkerEconomyError(
                "measurement references non-candidate proof"
            )
        if proof_id in result:
            raise LightwalkerEconomyError(
                "duplicate measurement for candidate proof"
            )
        if measurement.get("measurer_particular") != (
            trusted_measurer_particular
        ):
            raise LightwalkerEconomyError(
                "measurement signer is not trusted by local scoring policy"
            )
        if not verify_route_measurement(
            candidate["snapshot"],
            candidate["proof"],
            measurement,
        ):
            raise LightwalkerEconomyError("invalid route measurement")
        result[proof_id] = measurement
    return result


def score_routes(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    scoring_policy: dict[str, Any],
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    *,
    evaluation_cut: int,
    excluded_guild_ids: list[str],
    prior_selection_ids: list[str] | None = None,
) -> dict[str, Any]:
    if not verify_scoring_policy(
        promise, route_policy, scoring_policy
    ):
        raise LightwalkerEconomyError("invalid scoring policy")
    cut = _nni(evaluation_cut, "evaluation_cut")
    base = select_route(
        promise,
        route_policy,
        candidates,
        evaluation_cut=cut,
        excluded_guild_ids=excluded_guild_ids,
        prior_selection_ids=prior_selection_ids,
    )
    measurement_by_proof = _measurement_map(
        candidates,
        measurements,
        trusted_measurer_particular=scoring_policy[
            "trusted_measurer_particular"
        ],
    )
    weights = scoring_policy["weights"]
    rows: list[dict[str, Any]] = []

    for candidate in base["candidate_rows"]:
        proof_id = candidate["remote_proof_id"]
        row = {
            **candidate,
            "measurement_id": None,
            "measurement_observed_cut": None,
            "measurement_age_cuts": None,
            "score_eligible": False,
            "score_ineligibility_reasons": [],
            "signals": None,
            "weighted_contributions": None,
            "local_score": None,
        }
        reasons = list(candidate["ineligibility_reasons"])
        if candidate["capacity_guild_id"] in set(excluded_guild_ids):
            reasons.append("EXCLUDED_BY_ROUTE_HISTORY")
        measurement = measurement_by_proof.get(proof_id)
        if measurement is None:
            reasons.append("MISSING_TRUSTED_MEASUREMENT")
        else:
            age = cut - int(measurement["observed_cut"])
            row["measurement_id"] = measurement["measurement_id"]
            row["measurement_observed_cut"] = int(
                measurement["observed_cut"]
            )
            row["measurement_age_cuts"] = age
            if age < 0:
                reasons.append("MEASUREMENT_FROM_FUTURE")
            if age > int(
                scoring_policy["max_measurement_age_cuts"]
            ):
                reasons.append("MEASUREMENT_TOO_OLD")

        if not reasons and measurement is not None:
            metrics = measurement["metrics"]
            freshness = max(
                0,
                int(route_policy["max_proof_age_cuts"])
                - int(candidate["proof_age_cuts"]),
            )
            headroom = max(
                0,
                int(candidate["native_measure"]["quantity"])
                - int(base["required_measure"]["quantity"]),
            )
            signals = {
                "freshness": freshness,
                "quantity_headroom": headroom,
                "reliability": int(
                    metrics["reliability_ppm"]
                ) // 1000,
                "latency": int(metrics["latency_ms"]),
                "energy": int(
                    metrics["energy_mwh_per_compute_minute"]
                ),
                "completion_window": int(
                    metrics["expected_completion_cuts"]
                ),
            }
            contributions = {
                "freshness": weights["freshness"]
                * signals["freshness"],
                "quantity_headroom": weights["quantity_headroom"]
                * signals["quantity_headroom"],
                "reliability": weights["reliability"]
                * signals["reliability"],
                "latency": -weights["latency"]
                * signals["latency"],
                "energy": -weights["energy"]
                * signals["energy"],
                "completion_window": -weights["completion_window"]
                * signals["completion_window"],
            }
            row["signals"] = signals
            row["weighted_contributions"] = contributions
            row["local_score"] = sum(contributions.values())
            row["score_eligible"] = True

        row["score_ineligibility_reasons"] = sorted(set(reasons))
        rows.append(row)

    eligible = [row for row in rows if row["score_eligible"]]
    order = {
        guild_id: index
        for index, guild_id in enumerate(route_policy["ordered_guild_ids"])
    }
    eligible.sort(
        key=lambda row: (
            -int(row["local_score"]),
            order.get(row["capacity_guild_id"], 10**9),
            row["remote_proof_id"],
        )
    )
    selected = eligible[0] if eligible else None
    body = {
        "kind": SELECTION_KIND,
        "version": SELECTION_VERSION,
        "authority": "derived-local-preference-recommendation-only",
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "scoring_policy_id": scoring_policy["scoring_policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "evaluation_cut": cut,
        "excluded_guild_ids": sorted(set(excluded_guild_ids)),
        "prior_selection_ids": list(prior_selection_ids or []),
        "candidate_rows": sorted(
            rows,
            key=lambda row: (
                order.get(row["capacity_guild_id"], 10**9),
                row["remote_proof_id"],
            ),
        ),
        "selection_status": (
            "SELECTED" if selected is not None else "NO_ELIGIBLE_ROUTE"
        ),
        "selected_candidate": selected,
        "required_measure": base["required_measure"],
        "score_semantics": "local-comparison-only",
        "value_authority": "none",
        "reservation_authority": "none",
        "execution_authority": "none",
        "owner_admission_required": True,
        "laws": [
            "SCORE != VALUE",
            "SCORE != AUTHORITY",
            "MEASUREMENT != PREFERENCE",
            "PREFERENCE != ADMISSION",
            "LOWER COST != UNIVERSALLY BETTER",
            "POLICY WEIGHTS ARE LOCAL",
        ],
    }
    return {**body, "selection_id": content_address(body)}


def verify_scored_selection(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    scoring_policy: dict[str, Any],
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    selection: dict[str, Any],
) -> bool:
    try:
        expected = score_routes(
            promise,
            route_policy,
            scoring_policy,
            candidates,
            measurements,
            evaluation_cut=int(selection["evaluation_cut"]),
            excluded_guild_ids=list(selection["excluded_guild_ids"]),
            prior_selection_ids=list(selection["prior_selection_ids"]),
        )
        return expected == selection
    except Exception:
        return False


def make_scored_policy_bound_reroute(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    *,
    route_policy: dict[str, Any],
    scoring_policy: dict[str, Any],
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    selection: dict[str, Any],
    admission_response: dict[str, Any],
    original_source_id: str,
    original_snapshot: dict[str, Any],
    original_proof: dict[str, Any],
    original_request: dict[str, Any],
    original_proposal: dict[str, Any],
    original_authorization: dict[str, Any],
    original_reservation: dict[str, Any],
    original_grant: dict[str, Any],
    original_finalization: dict[str, Any],
    substitute_snapshot: dict[str, Any],
    substitute_proof: dict[str, Any],
    promisor: IdentityKey,
    rerouted_at_cut: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not verify_multi_source_promise(
        offer, remote_sources, promise
    ):
        raise LightwalkerEconomyError("invalid original service promise")
    if not verify_scored_selection(
        promise,
        route_policy,
        scoring_policy,
        candidates,
        measurements,
        selection,
    ):
        raise LightwalkerEconomyError(
            "scored selection does not recompute from evidence and local policy"
        )
    selected = selection.get("selected_candidate")
    if not isinstance(selected, dict):
        raise LightwalkerEconomyError("no selected route")
    if selected["snapshot_id"] != substitute_snapshot["snapshot_id"]:
        raise LightwalkerEconomyError("selected snapshot mismatch")
    if selected["remote_proof_id"] != substitute_proof["remote_proof_id"]:
        raise LightwalkerEconomyError("selected proof mismatch")
    if not verify_owner_admission_response(
        selection, admission_response
    ):
        raise LightwalkerEconomyError(
            "invalid owner-local admission response"
        )
    if admission_response.get("disposition") != "ADMITTABLE":
        raise LightwalkerEconomyError(
            "selected owner did not admit route"
        )

    reroute = make_reroute(
        offer,
        acceptance,
        remote_sources,
        promise,
        original_source_id=original_source_id,
        original_snapshot=original_snapshot,
        original_proof=original_proof,
        original_request=original_request,
        original_proposal=original_proposal,
        original_authorization=original_authorization,
        original_reservation=original_reservation,
        original_grant=original_grant,
        original_finalization=original_finalization,
        substitute_snapshot=substitute_snapshot,
        substitute_proof=substitute_proof,
        promisor=promisor,
        rerouted_at_cut=rerouted_at_cut,
    )
    binding_body = {
        "kind": BINDING_KIND,
        "version": BINDING_VERSION,
        "authority": "derived-scored-reroute-linkage",
        "promise_id": promise["promise_id"],
        "source_slot_id": original_source_id,
        "route_policy_id": route_policy["policy_id"],
        "scoring_policy_id": scoring_policy["scoring_policy_id"],
        "selection_id": selection["selection_id"],
        "owner_admission_response_id": admission_response[
            "admission_response_id"
        ],
        "reroute_id": reroute["reroute_id"],
        "selected_capacity_guild_id": selected[
            "capacity_guild_id"
        ],
        "selected_remote_proof_id": selected["remote_proof_id"],
        "selected_local_score": selected["local_score"],
        "score_semantics": "local-comparison-only",
        "value_authority": "none",
        "reservation_authority": "none",
        "execution_authority": "none",
        "laws": [
            "SCORE != VALUE",
            "SCORE != AUTHORITY",
            "PREFERENCE != ADMISSION",
            "POLICY WEIGHTS ARE LOCAL",
        ],
    }
    return reroute, {
        **binding_body,
        "binding_id": content_address(binding_body),
    }


__all__ = [
    "make_owner_admission_response",
    "make_route_measurement",
    "make_scored_policy_bound_reroute",
    "make_scoring_policy",
    "score_routes",
    "verify_route_measurement",
    "verify_scored_selection",
    "verify_scoring_policy",
]
