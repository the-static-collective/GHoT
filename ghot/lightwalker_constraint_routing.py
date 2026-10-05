#!/usr/bin/env python3
"""Lightwalker Constraint-First Routing / Pareto Frontier 001.

Hard eligibility constraints run before local preference scoring. An
impermissible route cannot compensate for a violation with better performance.
Among eligible routes, the Pareto frontier remains a set of non-dominated
tradeoffs until a separate local preference policy chooses among it.

Core laws:
    CONSTRAINT != PREFERENCE
    INELIGIBLE != LOW SCORE
    PARETO FRONTIER != WINNER
    TRADEOFF != COLLAPSE
    LOCAL POLICY != UNIVERSAL OPTIMUM
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_multi_source_service import verify_multi_source_promise
from lightwalker_route_policy import select_route, verify_route_policy
from lightwalker_route_scoring import (
    make_scored_policy_bound_reroute,
    score_routes,
    verify_route_measurement,
    verify_scoring_policy,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


ATTESTATION_KIND = "ghot.lightwalker.route-constraint-attestation"
ATTESTATION_VERSION = "0"
POLICY_KIND = "ghot.lightwalker.route-constraint-policy"
POLICY_VERSION = "0"
EVALUATION_KIND = "ghot.lightwalker.route-constraint-evaluation"
EVALUATION_VERSION = "0"
FRONTIER_KIND = "ghot.lightwalker.route-pareto-frontier"
FRONTIER_VERSION = "0"
BINDING_KIND = "ghot.lightwalker.constraint-bound-reroute"
BINDING_VERSION = "0"

ATTESTATION_DOMAIN = "ghot.lightwalker-route-constraint-attestation-signature/v0"
POLICY_DOMAIN = "ghot.lightwalker-route-constraint-policy-signature/v0"
ATTESTATION_BYTES = b"GHOT-LightwalkerRouteConstraintAttestation-v0|"
POLICY_BYTES = b"GHOT-LightwalkerRouteConstraintPolicy-v0|"


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


def make_constraint_attestation(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
    *,
    assessor: IdentityKey,
    jurisdiction: str,
    privacy_class: int,
    renewable_evidence_present: bool,
    sovereign_group: str,
    observed_cut: int,
) -> dict[str, Any]:
    from lightwalker_federated_service import verify_remote_capacity_proof

    if not verify_remote_capacity_proof(snapshot, proof):
        raise LightwalkerEconomyError(
            "constraint attestation requires valid remote capacity proof"
        )
    if not isinstance(renewable_evidence_present, bool):
        raise LightwalkerEconomyError(
            "renewable_evidence_present must be boolean"
        )
    body = {
        "kind": ATTESTATION_KIND,
        "version": ATTESTATION_VERSION,
        "authority": "constraint-evidence-only",
        "assessor_particular": assessor.particular(),
        "capacity_guild_id": proof["capacity_guild_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "remote_proof_id": proof["remote_proof_id"],
        "resource_entry_id": proof["resource_entry_id"],
        "observed_cut": _nni(observed_cut, "observed_cut"),
        "facts": {
            "jurisdiction": _nonempty(jurisdiction, "jurisdiction"),
            "privacy_class": _nni(privacy_class, "privacy_class"),
            "renewable_evidence_present": renewable_evidence_present,
            "sovereign_group": _nonempty(
                sovereign_group, "sovereign_group"
            ),
        },
        "eligibility_authority": "none",
        "preference_authority": "none",
        "reservation_authority": "none",
        "laws": [
            "CONSTRAINT EVIDENCE != ELIGIBILITY DECISION",
            "CONSTRAINT != PREFERENCE",
        ],
    }
    return _signed(
        body,
        id_field="attestation_id",
        signer=assessor,
        domain=ATTESTATION_DOMAIN,
        byte_domain=ATTESTATION_BYTES,
    )


def verify_constraint_attestation(
    snapshot: dict[str, Any],
    proof: dict[str, Any],
    attestation: dict[str, Any],
) -> bool:
    try:
        from lightwalker_federated_service import verify_remote_capacity_proof

        if not verify_remote_capacity_proof(snapshot, proof):
            return False
        if attestation.get("kind") != ATTESTATION_KIND:
            return False
        if attestation.get("version") != ATTESTATION_VERSION:
            return False
        if attestation.get("authority") != "constraint-evidence-only":
            return False
        if attestation.get("capacity_guild_id") != proof["capacity_guild_id"]:
            return False
        if attestation.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if attestation.get("remote_proof_id") != proof["remote_proof_id"]:
            return False
        if attestation.get("resource_entry_id") != proof["resource_entry_id"]:
            return False
        facts = attestation.get("facts")
        if not isinstance(facts, dict):
            return False
        if not isinstance(facts.get("jurisdiction"), str):
            return False
        if isinstance(facts.get("privacy_class"), bool) or not isinstance(
            facts.get("privacy_class"), int
        ):
            return False
        if int(facts["privacy_class"]) < 0:
            return False
        if not isinstance(facts.get("renewable_evidence_present"), bool):
            return False
        if not isinstance(facts.get("sovereign_group"), str):
            return False
        for field in (
            "eligibility_authority",
            "preference_authority",
            "reservation_authority",
        ):
            if attestation.get(field) != "none":
                return False
        return _verify_signed(
            attestation,
            id_field="attestation_id",
            particular_field="assessor_particular",
            domain=ATTESTATION_DOMAIN,
            byte_domain=ATTESTATION_BYTES,
        )
    except Exception:
        return False


def make_constraint_policy(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    *,
    promisor: IdentityKey,
    trusted_assessor_particular: str,
    trusted_measurer_particular: str,
    allowed_jurisdictions: list[str],
    min_privacy_class: int,
    require_renewable_evidence: bool,
    max_expected_completion_cuts: int,
    forbidden_sovereign_groups: list[str],
    max_attestation_age_cuts: int,
    created_at_cut: int,
) -> dict[str, Any]:
    if not verify_route_policy(promise, route_policy):
        raise LightwalkerEconomyError("invalid base route policy")
    if promisor.particular() != promise["promisor_particular"]:
        raise LightwalkerEconomyError(
            "constraint policy signer is not promisor"
        )
    if not allowed_jurisdictions:
        raise LightwalkerEconomyError(
            "constraint policy requires at least one allowed jurisdiction"
        )
    jurisdictions = sorted(set(
        _nonempty(item, "allowed_jurisdiction")
        for item in allowed_jurisdictions
    ))
    forbidden = sorted(set(
        _nonempty(item, "forbidden_sovereign_group")
        for item in forbidden_sovereign_groups
    ))
    if not isinstance(require_renewable_evidence, bool):
        raise LightwalkerEconomyError(
            "require_renewable_evidence must be boolean"
        )
    body = {
        "kind": POLICY_KIND,
        "version": POLICY_VERSION,
        "authority": "promisor-hard-eligibility-policy-only",
        "promisor_particular": promisor.particular(),
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "trusted_assessor_particular": _nonempty(
            trusted_assessor_particular,
            "trusted_assessor_particular",
        ),
        "trusted_measurer_particular": _nonempty(
            trusted_measurer_particular,
            "trusted_measurer_particular",
        ),
        "constraints": {
            "allowed_jurisdictions": jurisdictions,
            "min_privacy_class": _nni(
                min_privacy_class, "min_privacy_class"
            ),
            "require_renewable_evidence": require_renewable_evidence,
            "max_expected_completion_cuts": _nni(
                max_expected_completion_cuts,
                "max_expected_completion_cuts",
            ),
            "forbidden_sovereign_groups": forbidden,
        },
        "max_attestation_age_cuts": _nni(
            max_attestation_age_cuts,
            "max_attestation_age_cuts",
        ),
        "created_at_cut": _nni(created_at_cut, "created_at_cut"),
        "preference_authority": "none",
        "score_authority": "none",
        "reservation_authority": "none",
        "admission_authority": "none",
        "laws": [
            "CONSTRAINT != PREFERENCE",
            "INELIGIBLE != LOW SCORE",
            "LOCAL POLICY != UNIVERSAL OPTIMUM",
        ],
    }
    return _signed(
        body,
        id_field="constraint_policy_id",
        signer=promisor,
        domain=POLICY_DOMAIN,
        byte_domain=POLICY_BYTES,
    )


def verify_constraint_policy(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    policy: dict[str, Any],
) -> bool:
    try:
        if not verify_route_policy(promise, route_policy):
            return False
        if policy.get("kind") != POLICY_KIND:
            return False
        if policy.get("version") != POLICY_VERSION:
            return False
        if (
            policy.get("authority")
            != "promisor-hard-eligibility-policy-only"
        ):
            return False
        if policy.get("promise_id") != promise["promise_id"]:
            return False
        if policy.get("route_policy_id") != route_policy["policy_id"]:
            return False
        if policy.get("source_slot_id") != route_policy["source_slot_id"]:
            return False
        if policy.get("promisor_particular") != promise["promisor_particular"]:
            return False
        constraints = policy.get("constraints")
        if not isinstance(constraints, dict):
            return False
        if not constraints.get("allowed_jurisdictions"):
            return False
        if not isinstance(
            constraints.get("require_renewable_evidence"), bool
        ):
            return False
        for field in (
            "preference_authority",
            "score_authority",
            "reservation_authority",
            "admission_authority",
        ):
            if policy.get(field) != "none":
                return False
        return _verify_signed(
            policy,
            id_field="constraint_policy_id",
            particular_field="promisor_particular",
            domain=POLICY_DOMAIN,
            byte_domain=POLICY_BYTES,
        )
    except Exception:
        return False


def _index_by_proof(
    items: list[dict[str, Any]],
    *,
    id_name: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        proof_id = item.get("remote_proof_id")
        if not isinstance(proof_id, str):
            raise LightwalkerEconomyError(
                f"{id_name} lacks remote_proof_id"
            )
        if proof_id in result:
            raise LightwalkerEconomyError(
                f"duplicate {id_name} for candidate proof"
            )
        result[proof_id] = item
    return result


def evaluate_constraints(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    constraint_policy: dict[str, Any],
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    attestations: list[dict[str, Any]],
    *,
    evaluation_cut: int,
    excluded_guild_ids: list[str],
) -> dict[str, Any]:
    if not verify_constraint_policy(
        promise, route_policy, constraint_policy
    ):
        raise LightwalkerEconomyError("invalid constraint policy")
    cut = _nni(evaluation_cut, "evaluation_cut")
    base = select_route(
        promise,
        route_policy,
        candidates,
        evaluation_cut=cut,
        excluded_guild_ids=excluded_guild_ids,
        prior_selection_ids=[],
    )
    candidate_map = {
        item["proof"]["remote_proof_id"]: item
        for item in candidates
    }
    measurement_map = _index_by_proof(
        measurements, id_name="route measurement"
    )
    attestation_map = _index_by_proof(
        attestations, id_name="constraint attestation"
    )
    constraints = constraint_policy["constraints"]
    rows: list[dict[str, Any]] = []

    for base_row in base["candidate_rows"]:
        proof_id = base_row["remote_proof_id"]
        candidate = candidate_map[proof_id]
        failures = list(base_row["ineligibility_reasons"])
        if base_row["capacity_guild_id"] in set(excluded_guild_ids):
            failures.append("EXCLUDED_BY_ROUTE_HISTORY")

        measurement = measurement_map.get(proof_id)
        attestation = attestation_map.get(proof_id)
        if measurement is None:
            failures.append("MISSING_TRUSTED_MEASUREMENT")
        else:
            if measurement.get("measurer_particular") != (
                constraint_policy["trusted_measurer_particular"]
            ):
                failures.append("UNTRUSTED_MEASURER")
            elif not verify_route_measurement(
                candidate["snapshot"],
                candidate["proof"],
                measurement,
            ):
                failures.append("INVALID_ROUTE_MEASUREMENT")

        if attestation is None:
            failures.append("MISSING_CONSTRAINT_ATTESTATION")
        else:
            if attestation.get("assessor_particular") != (
                constraint_policy["trusted_assessor_particular"]
            ):
                failures.append("UNTRUSTED_CONSTRAINT_ASSESSOR")
            elif not verify_constraint_attestation(
                candidate["snapshot"],
                candidate["proof"],
                attestation,
            ):
                failures.append("INVALID_CONSTRAINT_ATTESTATION")

        facts = attestation["facts"] if attestation is not None else {}
        metrics = measurement["metrics"] if measurement is not None else {}

        if attestation is not None:
            age = cut - int(attestation["observed_cut"])
            if age < 0:
                failures.append("ATTESTATION_FROM_FUTURE")
            if age > int(
                constraint_policy["max_attestation_age_cuts"]
            ):
                failures.append("ATTESTATION_TOO_OLD")
            if facts.get("jurisdiction") not in set(
                constraints["allowed_jurisdictions"]
            ):
                failures.append("JURISDICTION_NOT_ALLOWED")
            if int(facts.get("privacy_class", -1)) < int(
                constraints["min_privacy_class"]
            ):
                failures.append("PRIVACY_CLASS_TOO_LOW")
            if (
                constraints["require_renewable_evidence"]
                and facts.get("renewable_evidence_present") is not True
            ):
                failures.append("RENEWABLE_EVIDENCE_REQUIRED")
            if facts.get("sovereign_group") in set(
                constraints["forbidden_sovereign_groups"]
            ):
                failures.append("SOVEREIGN_GROUP_FORBIDDEN")

        if measurement is not None and int(
            metrics.get("expected_completion_cuts", 10**9)
        ) > int(constraints["max_expected_completion_cuts"]):
            failures.append("COMPLETION_DEADLINE_EXCEEDED")

        failures = sorted(set(failures))
        rows.append({
            **base_row,
            "measurement_id": (
                measurement["measurement_id"]
                if measurement is not None
                else None
            ),
            "attestation_id": (
                attestation["attestation_id"]
                if attestation is not None
                else None
            ),
            "constraint_facts": facts if attestation is not None else None,
            "route_metrics": metrics if measurement is not None else None,
            "constraint_status": "ELIGIBLE" if not failures else "INELIGIBLE",
            "constraint_failures": failures,
            "local_score": None,
        })

    eligible_ids = sorted(
        row["remote_proof_id"]
        for row in rows
        if row["constraint_status"] == "ELIGIBLE"
    )
    ineligible_ids = sorted(
        row["remote_proof_id"]
        for row in rows
        if row["constraint_status"] == "INELIGIBLE"
    )
    body = {
        "kind": EVALUATION_KIND,
        "version": EVALUATION_VERSION,
        "authority": "derived-hard-eligibility-only",
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "constraint_policy_id": constraint_policy["constraint_policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "evaluation_cut": cut,
        "candidate_rows": rows,
        "eligible_remote_proof_ids": eligible_ids,
        "ineligible_remote_proof_ids": ineligible_ids,
        "winner": None,
        "score_semantics": None,
        "preference_authority": "none",
        "reservation_authority": "none",
        "laws": [
            "CONSTRAINT != PREFERENCE",
            "INELIGIBLE != LOW SCORE",
            "LOCAL POLICY != UNIVERSAL OPTIMUM",
        ],
    }
    return {**body, "evaluation_id": content_address(body)}


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    am = a["route_metrics"]
    bm = b["route_metrics"]
    no_worse = (
        int(am["latency_ms"]) <= int(bm["latency_ms"])
        and int(am["energy_mwh_per_compute_minute"])
        <= int(bm["energy_mwh_per_compute_minute"])
        and int(am["expected_completion_cuts"])
        <= int(bm["expected_completion_cuts"])
        and int(am["reliability_ppm"])
        >= int(bm["reliability_ppm"])
    )
    strictly_better = (
        int(am["latency_ms"]) < int(bm["latency_ms"])
        or int(am["energy_mwh_per_compute_minute"])
        < int(bm["energy_mwh_per_compute_minute"])
        or int(am["expected_completion_cuts"])
        < int(bm["expected_completion_cuts"])
        or int(am["reliability_ppm"])
        > int(bm["reliability_ppm"])
    )
    return no_worse and strictly_better


def derive_pareto_frontier(
    constraint_evaluation: dict[str, Any],
) -> dict[str, Any]:
    if constraint_evaluation.get("kind") != EVALUATION_KIND:
        raise LightwalkerEconomyError(
            "Pareto frontier requires constraint evaluation"
        )
    eligible = [
        row
        for row in constraint_evaluation["candidate_rows"]
        if row["constraint_status"] == "ELIGIBLE"
    ]
    frontier: list[dict[str, Any]] = []
    dominated: list[dict[str, Any]] = []
    for candidate in eligible:
        dominators = [
            other["remote_proof_id"]
            for other in eligible
            if other["remote_proof_id"] != candidate["remote_proof_id"]
            and _dominates(other, candidate)
        ]
        record = {
            "capacity_guild_id": candidate["capacity_guild_id"],
            "remote_proof_id": candidate["remote_proof_id"],
            "measurement_id": candidate["measurement_id"],
            "objectives": {
                "latency_ms": candidate["route_metrics"]["latency_ms"],
                "reliability_ppm": candidate["route_metrics"]["reliability_ppm"],
                "energy_mwh_per_compute_minute": candidate[
                    "route_metrics"
                ]["energy_mwh_per_compute_minute"],
                "expected_completion_cuts": candidate[
                    "route_metrics"
                ]["expected_completion_cuts"],
            },
            "dominated_by_remote_proof_ids": sorted(dominators),
        }
        if dominators:
            dominated.append(record)
        else:
            frontier.append(record)

    body = {
        "kind": FRONTIER_KIND,
        "version": FRONTIER_VERSION,
        "authority": "derived-pareto-tradeoff-view-only",
        "constraint_evaluation_id": constraint_evaluation["evaluation_id"],
        "promise_id": constraint_evaluation["promise_id"],
        "source_slot_id": constraint_evaluation["source_slot_id"],
        "objective_directions": {
            "latency_ms": "MINIMIZE",
            "reliability_ppm": "MAXIMIZE",
            "energy_mwh_per_compute_minute": "MINIMIZE",
            "expected_completion_cuts": "MINIMIZE",
        },
        "frontier": sorted(
            frontier, key=lambda row: row["remote_proof_id"]
        ),
        "dominated": sorted(
            dominated, key=lambda row: row["remote_proof_id"]
        ),
        "winner": None,
        "local_score": None,
        "preference_authority": "none",
        "reservation_authority": "none",
        "laws": [
            "PARETO FRONTIER != WINNER",
            "TRADEOFF != COLLAPSE",
            "CONSTRAINT != PREFERENCE",
            "LOCAL POLICY != UNIVERSAL OPTIMUM",
        ],
    }
    return {**body, "frontier_id": content_address(body)}


def frontier_candidates(
    frontier: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = {
        row["remote_proof_id"] for row in frontier["frontier"]
    }
    result = [
        item
        for item in candidates
        if item["proof"]["remote_proof_id"] in ids
    ]
    if len(result) != len(ids):
        raise LightwalkerEconomyError(
            "frontier candidate set is incomplete"
        )
    return result


def frontier_measurements(
    frontier: dict[str, Any],
    measurements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = {
        row["measurement_id"] for row in frontier["frontier"]
    }
    result = [
        item for item in measurements if item["measurement_id"] in ids
    ]
    if len(result) != len(ids):
        raise LightwalkerEconomyError(
            "frontier measurement set is incomplete"
        )
    return result


def score_frontier(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    scoring_policy: dict[str, Any],
    constraint_evaluation: dict[str, Any],
    frontier: dict[str, Any],
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    *,
    evaluation_cut: int,
) -> dict[str, Any]:
    if not verify_scoring_policy(
        promise, route_policy, scoring_policy
    ):
        raise LightwalkerEconomyError("invalid local scoring policy")
    if frontier.get("constraint_evaluation_id") != (
        constraint_evaluation["evaluation_id"]
    ):
        raise LightwalkerEconomyError(
            "frontier belongs to another constraint evaluation"
        )
    fc = frontier_candidates(frontier, candidates)
    fm = frontier_measurements(frontier, measurements)
    selection = score_routes(
        promise,
        route_policy,
        scoring_policy,
        fc,
        fm,
        evaluation_cut=_nni(evaluation_cut, "evaluation_cut"),
        excluded_guild_ids=[],
        prior_selection_ids=[],
    )
    return {
        **selection,
        "constraint_evaluation_id": constraint_evaluation["evaluation_id"],
        "frontier_id": frontier["frontier_id"],
        "frontier_only": True,
    }


def make_constraint_bound_reroute(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    *,
    route_policy: dict[str, Any],
    scoring_policy: dict[str, Any],
    constraint_evaluation: dict[str, Any],
    frontier: dict[str, Any],
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
    expected = score_frontier(
        promise,
        route_policy,
        scoring_policy,
        constraint_evaluation,
        frontier,
        candidates,
        measurements,
        evaluation_cut=int(selection["evaluation_cut"]),
    )
    if expected != selection:
        raise LightwalkerEconomyError(
            "selection does not recompute from constraint-first frontier"
        )
    reroute, scored_binding = make_scored_policy_bound_reroute(
        offer,
        acceptance,
        remote_sources,
        promise,
        route_policy=route_policy,
        scoring_policy=scoring_policy,
        candidates=frontier_candidates(frontier, candidates),
        measurements=frontier_measurements(frontier, measurements),
        selection={
            key: value
            for key, value in selection.items()
            if key not in {
                "constraint_evaluation_id",
                "frontier_id",
                "frontier_only",
            }
        },
        admission_response=admission_response,
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
        "authority": "derived-constraint-frontier-reroute-linkage",
        "promise_id": promise["promise_id"],
        "constraint_evaluation_id": constraint_evaluation["evaluation_id"],
        "frontier_id": frontier["frontier_id"],
        "scoring_policy_id": scoring_policy["scoring_policy_id"],
        "selection_id": selection["selection_id"],
        "scored_binding_id": scored_binding["binding_id"],
        "reroute_id": reroute["reroute_id"],
        "selected_capacity_guild_id": selection[
            "selected_candidate"
        ]["capacity_guild_id"],
        "constraint_override_authority": "none",
        "value_authority": "none",
        "reservation_authority": "none",
        "execution_authority": "none",
        "laws": [
            "CONSTRAINT != PREFERENCE",
            "INELIGIBLE != LOW SCORE",
            "PARETO FRONTIER != WINNER",
            "TRADEOFF != COLLAPSE",
            "LOCAL POLICY != UNIVERSAL OPTIMUM",
        ],
    }
    return reroute, {
        **binding_body,
        "binding_id": content_address(binding_body),
    }


__all__ = [
    "derive_pareto_frontier",
    "evaluate_constraints",
    "frontier_candidates",
    "frontier_measurements",
    "make_constraint_attestation",
    "make_constraint_bound_reroute",
    "make_constraint_policy",
    "score_frontier",
    "verify_constraint_attestation",
    "verify_constraint_policy",
]
