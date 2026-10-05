#!/usr/bin/env python3
"""Lightwalker Policy Composition / Constraint Intersection 001.

Independent signed policies remain independent. Composition derives the set of
routes satisfying every policy without rewriting, ranking, or overriding the
source policies.

Core laws:
    POLICY A != POLICY B
    INTERSECTION != POLICY REWRITE
    CONFLICT != AUTOMATIC OVERRIDE
    MORE RESTRICTIVE != MORE AUTHORITATIVE
    NO SATISFYING ROUTE != PERMISSION TO RELAX CONSTRAINTS
    POLICY PROVENANCE MUST SURVIVE COMPOSITION
"""

from __future__ import annotations

from typing import Any

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_constraint_routing import verify_constraint_attestation
from lightwalker_multi_source_service import verify_multi_source_promise
from lightwalker_route_policy import (
    select_route,
    verify_owner_admission_response,
    verify_route_policy,
)
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


POLICY_KIND = "ghot.lightwalker.constraint-policy-fragment"
POLICY_VERSION = "0"
INTERSECTION_KIND = "ghot.lightwalker.constraint-policy-intersection"
INTERSECTION_VERSION = "0"
EVALUATION_KIND = "ghot.lightwalker.composed-constraint-evaluation"
EVALUATION_VERSION = "0"
FRONTIER_KIND = "ghot.lightwalker.composed-pareto-frontier"
FRONTIER_VERSION = "0"
BINDING_KIND = "ghot.lightwalker.composed-policy-bound-reroute"
BINDING_VERSION = "0"

POLICY_DOMAIN = "ghot.lightwalker-constraint-policy-fragment-signature/v0"
POLICY_BYTES = b"GHOT-LightwalkerConstraintPolicyFragment-v0|"


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


def _normalize_constraints(
    *,
    allowed_jurisdictions: list[str],
    min_privacy_class: int,
    require_renewable_evidence: bool,
    max_expected_completion_cuts: int,
    forbidden_sovereign_groups: list[str],
) -> dict[str, Any]:
    if not allowed_jurisdictions:
        raise LightwalkerEconomyError(
            "policy requires at least one allowed jurisdiction"
        )
    if not isinstance(require_renewable_evidence, bool):
        raise LightwalkerEconomyError(
            "require_renewable_evidence must be boolean"
        )
    return {
        "allowed_jurisdictions": sorted(
            set(
                _nonempty(item, "allowed_jurisdiction")
                for item in allowed_jurisdictions
            )
        ),
        "min_privacy_class": _nni(
            min_privacy_class, "min_privacy_class"
        ),
        "require_renewable_evidence": require_renewable_evidence,
        "max_expected_completion_cuts": _nni(
            max_expected_completion_cuts,
            "max_expected_completion_cuts",
        ),
        "forbidden_sovereign_groups": sorted(
            set(
                _nonempty(item, "forbidden_sovereign_group")
                for item in forbidden_sovereign_groups
            )
        ),
    }


def make_policy_fragment(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    *,
    issuer: IdentityKey,
    issuer_role: str,
    policy_name: str,
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
    body = {
        "kind": POLICY_KIND,
        "version": POLICY_VERSION,
        "authority": "issuer-local-hard-eligibility-policy-only",
        "issuer_particular": issuer.particular(),
        "issuer_role": _nonempty(issuer_role, "issuer_role"),
        "policy_name": _nonempty(policy_name, "policy_name"),
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
        "constraints": _normalize_constraints(
            allowed_jurisdictions=allowed_jurisdictions,
            min_privacy_class=min_privacy_class,
            require_renewable_evidence=require_renewable_evidence,
            max_expected_completion_cuts=max_expected_completion_cuts,
            forbidden_sovereign_groups=forbidden_sovereign_groups,
        ),
        "max_attestation_age_cuts": _nni(
            max_attestation_age_cuts,
            "max_attestation_age_cuts",
        ),
        "created_at_cut": _nni(created_at_cut, "created_at_cut"),
        "override_authority": "none",
        "rewrite_authority": "none",
        "relaxation_authority": "none",
        "reservation_authority": "none",
        "laws": [
            "POLICY A != POLICY B",
            "MORE RESTRICTIVE != MORE AUTHORITATIVE",
            "POLICY PROVENANCE MUST SURVIVE COMPOSITION",
        ],
    }
    return _signed(
        body,
        id_field="policy_id",
        signer=issuer,
        domain=POLICY_DOMAIN,
        byte_domain=POLICY_BYTES,
    )


def verify_policy_fragment(
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
            != "issuer-local-hard-eligibility-policy-only"
        ):
            return False
        if policy.get("promise_id") != promise["promise_id"]:
            return False
        if policy.get("route_policy_id") != route_policy["policy_id"]:
            return False
        if policy.get("source_slot_id") != route_policy["source_slot_id"]:
            return False
        constraints = policy.get("constraints")
        if not isinstance(constraints, dict):
            return False
        normalized = _normalize_constraints(
            allowed_jurisdictions=list(
                constraints["allowed_jurisdictions"]
            ),
            min_privacy_class=int(
                constraints["min_privacy_class"]
            ),
            require_renewable_evidence=constraints[
                "require_renewable_evidence"
            ],
            max_expected_completion_cuts=int(
                constraints["max_expected_completion_cuts"]
            ),
            forbidden_sovereign_groups=list(
                constraints["forbidden_sovereign_groups"]
            ),
        )
        if normalized != constraints:
            return False
        for field in (
            "override_authority",
            "rewrite_authority",
            "relaxation_authority",
            "reservation_authority",
        ):
            if policy.get(field) != "none":
                return False
        return _verify_signed(
            policy,
            id_field="policy_id",
            particular_field="issuer_particular",
            domain=POLICY_DOMAIN,
            byte_domain=POLICY_BYTES,
        )
    except Exception:
        return False


def compose_policy_intersection(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    policies: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(policies) < 2:
        raise LightwalkerEconomyError(
            "policy composition requires at least two policies"
        )
    ids: set[str] = set()
    provenance: list[dict[str, Any]] = []
    allowed_sets: list[set[str]] = []
    min_privacy = 0
    renewable = False
    max_completion: int | None = None
    forbidden: set[str] = set()
    measurers: set[str] = set()

    for policy in policies:
        if not verify_policy_fragment(
            promise, route_policy, policy
        ):
            raise LightwalkerEconomyError(
                "invalid policy fragment in composition"
            )
        policy_id = policy["policy_id"]
        if policy_id in ids:
            raise LightwalkerEconomyError(
                "duplicate policy fragment"
            )
        ids.add(policy_id)
        constraints = policy["constraints"]
        allowed_sets.append(set(constraints["allowed_jurisdictions"]))
        min_privacy = max(
            min_privacy, int(constraints["min_privacy_class"])
        )
        renewable = (
            renewable
            or bool(constraints["require_renewable_evidence"])
        )
        completion = int(
            constraints["max_expected_completion_cuts"]
        )
        max_completion = (
            completion
            if max_completion is None
            else min(max_completion, completion)
        )
        forbidden.update(
            constraints["forbidden_sovereign_groups"]
        )
        measurers.add(policy["trusted_measurer_particular"])
        provenance.append(
            {
                "policy_id": policy_id,
                "issuer_particular": policy["issuer_particular"],
                "issuer_role": policy["issuer_role"],
                "policy_name": policy["policy_name"],
                "constraints": constraints,
                "trusted_assessor_particular": policy[
                    "trusted_assessor_particular"
                ],
                "trusted_measurer_particular": policy[
                    "trusted_measurer_particular"
                ],
            }
        )

    allowed = set.intersection(*allowed_sets)
    static_conflicts: list[str] = []
    if not allowed:
        static_conflicts.append(
            "ALLOWED_JURISDICTIONS_DISJOINT"
        )
    if len(measurers) != 1:
        static_conflicts.append(
            "PARETO_MEASURER_TRUST_ROOTS_DIVERGE"
        )

    effective_summary = {
        "allowed_jurisdictions": sorted(allowed),
        "min_privacy_class": min_privacy,
        "require_renewable_evidence": renewable,
        "max_expected_completion_cuts": (
            int(max_completion)
            if max_completion is not None
            else 0
        ),
        "forbidden_sovereign_groups": sorted(forbidden),
    }
    body = {
        "kind": INTERSECTION_KIND,
        "version": INTERSECTION_VERSION,
        "authority": "derived-policy-intersection-only",
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "policy_ids": sorted(ids),
        "policy_provenance": sorted(
            provenance, key=lambda row: row["policy_id"]
        ),
        "effective_summary": effective_summary,
        "static_conflicts": sorted(static_conflicts),
        "status": (
            "CONFLICT" if static_conflicts else "COMPOSABLE"
        ),
        "source_policies_rewritten": False,
        "override_authority": "none",
        "relaxation_authority": "none",
        "reservation_authority": "none",
        "laws": [
            "POLICY A != POLICY B",
            "INTERSECTION != POLICY REWRITE",
            "CONFLICT != AUTOMATIC OVERRIDE",
            "MORE RESTRICTIVE != MORE AUTHORITATIVE",
            "NO SATISFYING ROUTE != PERMISSION TO RELAX CONSTRAINTS",
            "POLICY PROVENANCE MUST SURVIVE COMPOSITION",
        ],
    }
    return {**body, "intersection_id": content_address(body)}


def _candidate_map(
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        proof_id = candidate["proof"]["remote_proof_id"]
        if proof_id in result:
            raise LightwalkerEconomyError(
                "duplicate candidate proof"
            )
        result[proof_id] = candidate
    return result


def _find_measurement(
    measurements: list[dict[str, Any]],
    proof_id: str,
    measurer: str,
) -> dict[str, Any] | None:
    rows = [
        item
        for item in measurements
        if item.get("remote_proof_id") == proof_id
        and item.get("measurer_particular") == measurer
    ]
    if len(rows) > 1:
        raise LightwalkerEconomyError(
            "duplicate measurement for proof and measurer"
        )
    return rows[0] if rows else None


def _find_attestation(
    attestations: list[dict[str, Any]],
    proof_id: str,
    assessor: str,
) -> dict[str, Any] | None:
    rows = [
        item
        for item in attestations
        if item.get("remote_proof_id") == proof_id
        and item.get("assessor_particular") == assessor
    ]
    if len(rows) > 1:
        raise LightwalkerEconomyError(
            "duplicate attestation for proof and assessor"
        )
    return rows[0] if rows else None


def _policy_verdict(
    policy: dict[str, Any],
    candidate: dict[str, Any],
    *,
    measurements: list[dict[str, Any]],
    attestations: list[dict[str, Any]],
    evaluation_cut: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    proof = candidate["proof"]
    proof_id = proof["remote_proof_id"]
    failures: list[str] = []

    measurement = _find_measurement(
        measurements,
        proof_id,
        policy["trusted_measurer_particular"],
    )
    if measurement is None:
        failures.append("MISSING_TRUSTED_MEASUREMENT")
    elif not verify_route_measurement(
        candidate["snapshot"], proof, measurement
    ):
        failures.append("INVALID_ROUTE_MEASUREMENT")

    attestation = _find_attestation(
        attestations,
        proof_id,
        policy["trusted_assessor_particular"],
    )
    if attestation is None:
        failures.append("MISSING_TRUSTED_CONSTRAINT_ATTESTATION")
        facts: dict[str, Any] = {}
    elif not verify_constraint_attestation(
        candidate["snapshot"], proof, attestation
    ):
        failures.append("INVALID_CONSTRAINT_ATTESTATION")
        facts = {}
    else:
        facts = attestation["facts"]
        age = evaluation_cut - int(attestation["observed_cut"])
        if age < 0:
            failures.append("ATTESTATION_FROM_FUTURE")
        if age > int(policy["max_attestation_age_cuts"]):
            failures.append("ATTESTATION_TOO_OLD")

    constraints = policy["constraints"]
    if facts:
        if facts["jurisdiction"] not in set(
            constraints["allowed_jurisdictions"]
        ):
            failures.append("JURISDICTION_NOT_ALLOWED")
        if int(facts["privacy_class"]) < int(
            constraints["min_privacy_class"]
        ):
            failures.append("PRIVACY_CLASS_TOO_LOW")
        if (
            constraints["require_renewable_evidence"]
            and facts["renewable_evidence_present"] is not True
        ):
            failures.append("RENEWABLE_EVIDENCE_REQUIRED")
        if facts["sovereign_group"] in set(
            constraints["forbidden_sovereign_groups"]
        ):
            failures.append("SOVEREIGN_GROUP_FORBIDDEN")

    if measurement is not None and verify_route_measurement(
        candidate["snapshot"], proof, measurement
    ):
        if int(measurement["metrics"]["expected_completion_cuts"]) > int(
            constraints["max_expected_completion_cuts"]
        ):
            failures.append("COMPLETION_DEADLINE_EXCEEDED")

    verdict = {
        "policy_id": policy["policy_id"],
        "issuer_particular": policy["issuer_particular"],
        "issuer_role": policy["issuer_role"],
        "policy_name": policy["policy_name"],
        "status": "PASS" if not failures else "FAIL",
        "failures": sorted(set(failures)),
        "attestation_id": (
            attestation["attestation_id"]
            if attestation is not None
            else None
        ),
        "measurement_id": (
            measurement["measurement_id"]
            if measurement is not None
            else None
        ),
    }
    return verdict, measurement


def evaluate_policy_intersection(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    policies: list[dict[str, Any]],
    intersection: dict[str, Any],
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    attestations: list[dict[str, Any]],
    *,
    evaluation_cut: int,
    excluded_guild_ids: list[str],
) -> dict[str, Any]:
    expected = compose_policy_intersection(
        promise, route_policy, policies
    )
    if expected != intersection:
        raise LightwalkerEconomyError(
            "intersection does not recompute from source policies"
        )
    cut = _nni(evaluation_cut, "evaluation_cut")
    base = select_route(
        promise,
        route_policy,
        candidates,
        evaluation_cut=cut,
        excluded_guild_ids=excluded_guild_ids,
        prior_selection_ids=[],
    )
    cmap = _candidate_map(candidates)
    policy_by_id = {
        policy["policy_id"]: policy for policy in policies
    }
    rows: list[dict[str, Any]] = []

    for base_row in base["candidate_rows"]:
        candidate = cmap[base_row["remote_proof_id"]]
        failures = list(base_row["ineligibility_reasons"])
        if base_row["capacity_guild_id"] in set(
            excluded_guild_ids
        ):
            failures.append("EXCLUDED_BY_ROUTE_HISTORY")

        verdicts: list[dict[str, Any]] = []
        shared_measurement: dict[str, Any] | None = None
        for policy_id in intersection["policy_ids"]:
            verdict, measurement = _policy_verdict(
                policy_by_id[policy_id],
                candidate,
                measurements=measurements,
                attestations=attestations,
                evaluation_cut=cut,
            )
            verdicts.append(verdict)
            if verdict["status"] == "FAIL":
                failures.append(
                    "POLICY_FAILED:" + policy_id
                )
            if measurement is not None:
                if shared_measurement is None:
                    shared_measurement = measurement
                elif (
                    shared_measurement["measurement_id"]
                    != measurement["measurement_id"]
                ):
                    failures.append(
                        "PARETO_MEASUREMENT_PROVENANCE_DIVERGED"
                    )

        if intersection["status"] == "CONFLICT":
            failures.append("STATIC_POLICY_CONFLICT")

        overall = "ELIGIBLE" if not failures else "INELIGIBLE"
        rows.append(
            {
                **base_row,
                "policy_verdicts": sorted(
                    verdicts, key=lambda row: row["policy_id"]
                ),
                "intersection_status": overall,
                "intersection_failures": sorted(set(failures)),
                "route_metrics": (
                    shared_measurement["metrics"]
                    if shared_measurement is not None
                    else None
                ),
                "measurement_id": (
                    shared_measurement["measurement_id"]
                    if shared_measurement is not None
                    else None
                ),
                "local_score": None,
            }
        )

    eligible = sorted(
        row["remote_proof_id"]
        for row in rows
        if row["intersection_status"] == "ELIGIBLE"
    )
    body = {
        "kind": EVALUATION_KIND,
        "version": EVALUATION_VERSION,
        "authority": "derived-multi-policy-eligibility-only",
        "promise_id": promise["promise_id"],
        "route_policy_id": route_policy["policy_id"],
        "intersection_id": intersection["intersection_id"],
        "source_slot_id": route_policy["source_slot_id"],
        "evaluation_cut": cut,
        "candidate_rows": rows,
        "eligible_remote_proof_ids": eligible,
        "result": (
            "SATISFYING_ROUTES"
            if eligible
            else "NO_SATISFYING_ROUTE"
        ),
        "winner": None,
        "score_semantics": None,
        "source_policies_rewritten": False,
        "override_authority": "none",
        "relaxation_authority": "none",
        "reservation_authority": "none",
        "policy_provenance": intersection["policy_provenance"],
        "laws": [
            "POLICY A != POLICY B",
            "INTERSECTION != POLICY REWRITE",
            "CONFLICT != AUTOMATIC OVERRIDE",
            "MORE RESTRICTIVE != MORE AUTHORITATIVE",
            "NO SATISFYING ROUTE != PERMISSION TO RELAX CONSTRAINTS",
            "POLICY PROVENANCE MUST SURVIVE COMPOSITION",
        ],
    }
    return {**body, "evaluation_id": content_address(body)}


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    am = a["route_metrics"]
    bm = b["route_metrics"]
    if am is None or bm is None:
        return False
    no_worse = (
        int(am["latency_ms"]) <= int(bm["latency_ms"])
        and int(am["energy_mwh_per_compute_minute"])
        <= int(bm["energy_mwh_per_compute_minute"])
        and int(am["expected_completion_cuts"])
        <= int(bm["expected_completion_cuts"])
        and int(am["reliability_ppm"])
        >= int(bm["reliability_ppm"])
    )
    strictly = (
        int(am["latency_ms"]) < int(bm["latency_ms"])
        or int(am["energy_mwh_per_compute_minute"])
        < int(bm["energy_mwh_per_compute_minute"])
        or int(am["expected_completion_cuts"])
        < int(bm["expected_completion_cuts"])
        or int(am["reliability_ppm"])
        > int(bm["reliability_ppm"])
    )
    return no_worse and strictly


def derive_composed_frontier(
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    if evaluation.get("kind") != EVALUATION_KIND:
        raise LightwalkerEconomyError(
            "composed frontier requires composed evaluation"
        )
    if evaluation.get("result") != "SATISFYING_ROUTES":
        raise LightwalkerEconomyError(
            "no satisfying route; policy constraints may not be relaxed"
        )
    eligible = [
        row
        for row in evaluation["candidate_rows"]
        if row["intersection_status"] == "ELIGIBLE"
    ]
    frontier: list[dict[str, Any]] = []
    dominated: list[dict[str, Any]] = []
    for row in eligible:
        dominators = [
            other["remote_proof_id"]
            for other in eligible
            if other["remote_proof_id"] != row["remote_proof_id"]
            and _dominates(other, row)
        ]
        record = {
            "capacity_guild_id": row["capacity_guild_id"],
            "remote_proof_id": row["remote_proof_id"],
            "measurement_id": row["measurement_id"],
            "objectives": row["route_metrics"],
            "dominated_by_remote_proof_ids": sorted(dominators),
        }
        if dominators:
            dominated.append(record)
        else:
            frontier.append(record)
    body = {
        "kind": FRONTIER_KIND,
        "version": FRONTIER_VERSION,
        "authority": "derived-composed-pareto-view-only",
        "evaluation_id": evaluation["evaluation_id"],
        "intersection_id": evaluation["intersection_id"],
        "promise_id": evaluation["promise_id"],
        "source_slot_id": evaluation["source_slot_id"],
        "frontier": sorted(
            frontier, key=lambda row: row["remote_proof_id"]
        ),
        "dominated": sorted(
            dominated, key=lambda row: row["remote_proof_id"]
        ),
        "winner": None,
        "local_score": None,
        "policy_provenance": evaluation["policy_provenance"],
        "override_authority": "none",
        "reservation_authority": "none",
        "laws": [
            "POLICY PROVENANCE MUST SURVIVE COMPOSITION",
            "PARETO FRONTIER != WINNER",
            "INTERSECTION != POLICY REWRITE",
        ],
    }
    return {**body, "frontier_id": content_address(body)}


def _subset_candidates(
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
            "frontier candidate set incomplete"
        )
    return result


def _subset_measurements(
    frontier: dict[str, Any],
    measurements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = {
        row["measurement_id"] for row in frontier["frontier"]
    }
    result = [
        item for item in measurements
        if item.get("measurement_id") in ids
    ]
    if len(result) != len(ids):
        raise LightwalkerEconomyError(
            "frontier measurement set incomplete"
        )
    return result


def score_composed_frontier(
    promise: dict[str, Any],
    route_policy: dict[str, Any],
    scoring_policy: dict[str, Any],
    evaluation: dict[str, Any],
    frontier: dict[str, Any],
    candidates: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    *,
    evaluation_cut: int,
) -> dict[str, Any]:
    if not verify_scoring_policy(
        promise, route_policy, scoring_policy
    ):
        raise LightwalkerEconomyError(
            "invalid local scoring policy"
        )
    if frontier.get("evaluation_id") != evaluation["evaluation_id"]:
        raise LightwalkerEconomyError(
            "frontier belongs to another composed evaluation"
        )
    selection = score_routes(
        promise,
        route_policy,
        scoring_policy,
        _subset_candidates(frontier, candidates),
        _subset_measurements(frontier, measurements),
        evaluation_cut=_nni(evaluation_cut, "evaluation_cut"),
        excluded_guild_ids=[],
        prior_selection_ids=[],
    )
    return {
        **selection,
        "intersection_id": evaluation["intersection_id"],
        "composed_evaluation_id": evaluation["evaluation_id"],
        "composed_frontier_id": frontier["frontier_id"],
        "policy_provenance": evaluation["policy_provenance"],
    }


def make_composed_policy_bound_reroute(
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    remote_sources: list[dict[str, Any]],
    promise: dict[str, Any],
    *,
    route_policy: dict[str, Any],
    scoring_policy: dict[str, Any],
    evaluation: dict[str, Any],
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
    if not verify_multi_source_promise(
        offer, remote_sources, promise
    ):
        raise LightwalkerEconomyError(
            "invalid original service promise"
        )
    expected = score_composed_frontier(
        promise,
        route_policy,
        scoring_policy,
        evaluation,
        frontier,
        candidates,
        measurements,
        evaluation_cut=int(selection["evaluation_cut"]),
    )
    if expected != selection:
        raise LightwalkerEconomyError(
            "selection does not recompute from composed policy frontier"
        )
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
    selected = selection["selected_candidate"]
    if selected["snapshot_id"] != substitute_snapshot["snapshot_id"]:
        raise LightwalkerEconomyError(
            "selected substitute snapshot mismatch"
        )
    if selected["remote_proof_id"] != substitute_proof["remote_proof_id"]:
        raise LightwalkerEconomyError(
            "selected substitute proof mismatch"
        )

    base_selection = {
        key: value
        for key, value in selection.items()
        if key not in {
            "intersection_id",
            "composed_evaluation_id",
            "composed_frontier_id",
            "policy_provenance",
        }
    }
    reroute, scored_binding = make_scored_policy_bound_reroute(
        offer,
        acceptance,
        remote_sources,
        promise,
        route_policy=route_policy,
        scoring_policy=scoring_policy,
        candidates=_subset_candidates(frontier, candidates),
        measurements=_subset_measurements(frontier, measurements),
        selection=base_selection,
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
        "authority": "derived-composed-policy-reroute-linkage",
        "promise_id": promise["promise_id"],
        "intersection_id": evaluation["intersection_id"],
        "evaluation_id": evaluation["evaluation_id"],
        "frontier_id": frontier["frontier_id"],
        "scoring_policy_id": scoring_policy["scoring_policy_id"],
        "selection_id": selection["selection_id"],
        "scored_binding_id": scored_binding["binding_id"],
        "reroute_id": reroute["reroute_id"],
        "selected_capacity_guild_id": selected["capacity_guild_id"],
        "policy_ids": sorted(
            row["policy_id"]
            for row in evaluation["policy_provenance"]
        ),
        "policy_provenance": evaluation["policy_provenance"],
        "source_policies_rewritten": False,
        "override_authority": "none",
        "relaxation_authority": "none",
        "reservation_authority": "none",
        "execution_authority": "none",
        "laws": [
            "POLICY A != POLICY B",
            "INTERSECTION != POLICY REWRITE",
            "CONFLICT != AUTOMATIC OVERRIDE",
            "MORE RESTRICTIVE != MORE AUTHORITATIVE",
            "NO SATISFYING ROUTE != PERMISSION TO RELAX CONSTRAINTS",
            "POLICY PROVENANCE MUST SURVIVE COMPOSITION",
        ],
    }
    return reroute, {
        **binding_body,
        "binding_id": content_address(binding_body),
    }


__all__ = [
    "compose_policy_intersection",
    "derive_composed_frontier",
    "evaluate_policy_intersection",
    "make_composed_policy_bound_reroute",
    "make_policy_fragment",
    "score_composed_frontier",
    "verify_policy_fragment",
]
