#!/usr/bin/env python3
"""Experiment 061 — Resume Claim / Fork Prevention."""

from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lightwalker_economy import LightwalkerEconomyError
from lightwalker_execution_resume import ResumedExecutionStore
from lightwalker_federated_service import make_remote_capacity_proof
from lightwalker_guild_authorization import make_resource_proposal
from lightwalker_guild_reservation import GuildReservationStore
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
)
from lightwalker_heterogeneous_exchange import (
    make_exchange_offer,
    make_obligation,
)
from lightwalker_long_running_execution import LongRunningExecutionStore
from lightwalker_multi_source_service import make_multi_source_promise
from lightwalker_policy_composition import make_policy_fragment
from lightwalker_policy_transition import make_policy_transition
from lightwalker_policy_versioning import make_policy_version
from lightwalker_resume_claim import (
    ResumeClaimRegistry,
    bind_completion_to_winning_claim,
    claim_bound_resume,
    make_resume_claim,
    make_resume_claim_resolution,
    reconcile_active_resume_claims,
    resume_claim_gate,
    verify_claim_decision,
    verify_resume_claim,
)
from lightwalker_route_policy import make_route_policy
from lightwalker_transition_composition import derive_temporal_intersection
from relatte_identity import IdentityKey


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def source_treasury(
    guild_id: str,
    steward: IdentityKey,
) -> tuple[dict, dict, dict]:
    entry = make_treasury_entry(
        category="capability",
        position="available",
        subject_ref=f"capability:{guild_id}-render-061",
        source_ref=f"ghot-node:{guild_id}-061",
        evidence_refs=[f"receipt:{guild_id}-probe-061"],
        native_measure={
            "unit": "compute-minute",
            "quantity": 60,
        },
        metadata={"capability": "render.verified"},
    )
    snapshot = make_treasury_snapshot(
        guild_id=guild_id,
        steward=steward,
        entries=[entry],
        sequence=0,
    )
    proof = make_remote_capacity_proof(
        snapshot,
        steward=steward,
        resource_entry_id=entry["entry_id"],
        observed_cut=1,
        valid_through_cut=20,
    )
    return snapshot, entry, proof


def policy_pair(
    *,
    promise: dict,
    route_policy: dict,
    issuer: IdentityKey,
    issuer_role: str,
    policy_name: str,
    assessor: IdentityKey,
    measurer: IdentityKey,
) -> tuple[dict, dict, dict, dict]:
    common = dict(
        promise=promise,
        route_policy=route_policy,
        issuer=issuer,
        issuer_role=issuer_role,
        policy_name=policy_name,
        trusted_assessor_particular=assessor.particular(),
        trusted_measurer_particular=measurer.particular(),
        allowed_jurisdictions=["zone:b"],
        min_privacy_class=2,
        require_renewable_evidence=False,
        max_expected_completion_cuts=8,
        forbidden_sovereign_groups=[],
        max_attestation_age_cuts=8,
    )
    v1 = make_policy_fragment(
        **common,
        created_at_cut=5,
    )
    v2 = make_policy_fragment(
        **common,
        created_at_cut=6,
    )
    version1 = make_policy_version(
        promise,
        route_policy,
        v1,
        issuer=issuer,
        version_number=1,
        effective_from_cut=5,
        declared_at_cut=5,
    )
    version2 = make_policy_version(
        promise,
        route_policy,
        v2,
        issuer=issuer,
        version_number=2,
        effective_from_cut=7,
        declared_at_cut=6,
        previous_version=version1,
    )
    return v1, v2, version1, version2


def bundle(
    role: str,
    previous_version: dict,
    current_version: dict,
    transition: dict,
) -> dict:
    return {
        "issuer_role": role,
        "previous_version": previous_version,
        "current_version": current_version,
        "transition": transition,
    }


def reserve(
    store: GuildReservationStore,
    snapshot: dict,
    entry: dict,
    *,
    steward: IdentityKey,
    executor: IdentityKey,
    quantity: int,
    cut: int,
    purpose: str,
) -> tuple[dict, dict, dict]:
    proposal = make_resource_proposal(
        snapshot,
        proposer=steward,
        resource_entry_id=entry["entry_id"],
        requested_quantity=quantity,
        requested_unit="compute-minute",
        purpose_ref=purpose,
        proposed_at_cut=cut,
    )
    authorization, reservation = store.reserve_and_authorize(
        snapshot,
        proposal,
        executor_particular=executor.particular(),
        authorized_at_cut=cut,
        expires_after_cut=15,
    )
    return proposal, authorization, reservation


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild_a = IdentityKey.load_or_create(root / "guild-a" / "body.pem")
        guild_b = IdentityKey.load_or_create(root / "guild-b" / "body.pem")
        guild_c = IdentityKey.load_or_create(root / "guild-c" / "body.pem")
        guild_e = IdentityKey.load_or_create(root / "guild-e" / "body.pem")
        guild_f = IdentityKey.load_or_create(root / "guild-f" / "body.pem")
        guild_g = IdentityKey.load_or_create(root / "guild-g" / "body.pem")

        worker_e = IdentityKey.load_or_create(root / "worker-e" / "body.pem")
        worker_f = IdentityKey.load_or_create(root / "worker-f" / "body.pem")
        worker_g = IdentityKey.load_or_create(root / "worker-g" / "body.pem")

        customer = IdentityKey.load_or_create(root / "customer" / "body.pem")
        customer_assessor = IdentityKey.load_or_create(
            root / "customer-assessor" / "body.pem"
        )
        promisor_assessor = IdentityKey.load_or_create(
            root / "promisor-assessor" / "body.pem"
        )
        measurer = IdentityKey.load_or_create(root / "measurer" / "body.pem")

        treasury_b, entry_b, proof_b = source_treasury("guild:b", guild_b)
        treasury_c, entry_c, proof_c = source_treasury("guild:c", guild_c)
        treasury_f, entry_f, proof_f = source_treasury("guild:f", guild_f)
        treasury_e, entry_e, proof_e = source_treasury("guild:e", guild_e)
        treasury_g, entry_g, proof_g = source_treasury("guild:g", guild_g)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref="service:resume-claim-061",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="winning-resume-claim-lineage",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:061",
            terms={"deliverable": "signed review"},
            evidence_policy="signed-performance",
        )
        offer = make_exchange_offer(
            offeror_particular=guild_a.particular(),
            offeror_obligation=service,
            acceptor_obligation=consideration,
            orientation_refs=[],
            valid_through_cut=20,
        )
        original_sources = [
            {"snapshot": treasury_b, "proof": proof_b, "quantity": 30},
            {"snapshot": treasury_c, "proof": proof_c, "quantity": 30},
        ]
        promise = make_multi_source_promise(
            offer,
            original_sources,
            promisor=guild_a,
            promised_at_cut=2,
        )
        source_b = next(
            row
            for row in promise["sources"]
            if row["capacity_guild_id"] == "guild:b"
        )
        route_policy = make_route_policy(
            offer,
            original_sources,
            promise,
            source_slot_id=source_b["source_id"],
            promisor=guild_a,
            ordered_guild_ids=[
                "guild:b",
                "guild:f",
                "guild:e",
                "guild:g",
            ],
            required_capability="render.verified",
            max_proof_age_cuts=20,
            max_failover_hops=4,
            created_at_cut=2,
        )

        _, _, cv1, cv2 = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-resume-claim-boundary",
            assessor=customer_assessor,
            measurer=measurer,
        )
        _, _, pv1, pv2 = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-resume-claim-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
        )
        customer_transition = make_policy_transition(
            promise,
            route_policy,
            previous_version=cv1,
            current_version=cv2,
            issuer=customer,
            mode="GRACE_UNTIL_CUT",
            grace_until_cut=12,
            declared_at_cut=6,
        )
        promisor_transition = make_policy_transition(
            promise,
            route_policy,
            previous_version=pv1,
            current_version=pv2,
            issuer=guild_a,
            mode="GRACE_UNTIL_CUT",
            grace_until_cut=12,
            declared_at_cut=6,
        )
        bundles = [
            bundle("customer", cv1, cv2, customer_transition),
            bundle("promisor", pv1, pv2, promisor_transition),
        ]

        # Source F run: 30 units -> checkpoint at 40% -> 12 units represented.
        store_f = GuildReservationStore(root / "reservations-f", steward=guild_f)
        proposal_f, auth_f, reservation_f = reserve(
            store_f,
            treasury_f,
            entry_f,
            steward=guild_f,
            executor=worker_f,
            quantity=30,
            cut=6,
            purpose="061-source-f",
        )
        temporal_f6 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            reservation_f,
            observed_cut=6,
        )
        long_f = LongRunningExecutionStore(
            root / "long-f",
            steward=guild_f,
            reservation_store=store_f,
        )
        run_f = long_f.start(
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=temporal_f6,
            executor=worker_f,
            observed_cut=6,
        )
        temporal_f7 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            reservation_f,
            observed_cut=7,
            execution_started_at_cut=6,
        )
        checkpoint_f = long_f.checkpoint(
            run_f,
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=temporal_f7,
            executor=worker_f,
            observed_cut=7,
            progress_percent=40,
            partial_result_ref="partial:061-f-40",
        )
        pause_f = long_f.pause(
            run_f,
            observed_cut=7,
            reason="READY_FOR_RESUME_CLAIM",
        )
        stop_f = long_f.stop(
            run_f,
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            observed_cut=7,
            reason="RELEASE_FOR_RESUME_CLAIM",
        )
        assert stop_f["reservation_status"] == "RELEASED"

        # E and G both independently possess valid exact-remaining authority.
        candidates = {}
        for guild_id, guild, worker, treasury, entry, proof in (
            ("guild:e", guild_e, worker_e, treasury_e, entry_e, proof_e),
            ("guild:g", guild_g, worker_g, treasury_g, entry_g, proof_g),
        ):
            store = GuildReservationStore(
                root / f"reservations-{guild_id[-1]}",
                steward=guild,
            )
            proposal, authorization, reservation = reserve(
                store,
                treasury,
                entry,
                steward=guild,
                executor=worker,
                quantity=18,
                cut=8,
                purpose=f"061-candidate-{guild_id}",
            )
            claim = make_resume_claim(
                run_f,
                checkpoint_f,
                stop_f,
                treasury,
                proposal,
                authorization,
                reservation,
                claimant=guild,
                claimed_at_cut=8,
            )
            assert verify_resume_claim(
                run_f,
                checkpoint_f,
                stop_f,
                treasury,
                proposal,
                authorization,
                reservation,
                claim,
            )
            candidates[claim["resume_claim_id"]] = {
                "guild_id": guild_id,
                "guild": guild,
                "worker": worker,
                "treasury": treasury,
                "entry": entry,
                "proof": proof,
                "store": store,
                "proposal": proposal,
                "authorization": authorization,
                "reservation": reservation,
                "claim": claim,
            }

        claims = [item["claim"] for item in candidates.values()]

        # One source-owner-local registry: concurrent claim attempts serialize
        # to exactly one ACTIVE result. The loser remains a signed decision.
        registry = ResumeClaimRegistry(
            root / "claim-registry",
            source_steward=guild_f,
        )

        def consider(item: dict) -> dict:
            return registry.consider(
                run_f,
                checkpoint_f,
                stop_f,
                item["treasury"],
                item["proposal"],
                item["authorization"],
                item["reservation"],
                item["claim"],
                observed_cut=8,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            decisions = list(pool.map(
                consider,
                list(candidates.values()),
            ))

        active = [d for d in decisions if d["status"] == "ACTIVE"]
        losing = [d for d in decisions if d["status"] == "LOSING"]
        assert len(active) == 1
        assert len(losing) == 1
        active_decision = active[0]
        losing_decision = losing[0]
        winner = candidates[active_decision["resume_claim_id"]]
        loser = candidates[losing_decision["resume_claim_id"]]

        assert verify_claim_decision(
            run_f,
            checkpoint_f,
            stop_f,
            winner["claim"],
            active_decision,
        )
        assert verify_claim_decision(
            run_f,
            checkpoint_f,
            stop_f,
            loser["claim"],
            losing_decision,
        )
        assert losing_decision["claim_deleted"] is False
        assert losing_decision["active_resume_claim_id"] == (
            active_decision["resume_claim_id"]
        )

        # Losing claimant cannot resume merely because its local reservation is valid.
        loser_temporal8 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            loser["reservation"],
            observed_cut=8,
        )
        loser_resume_refused = refused(
            lambda: claim_bound_resume(
                ResumedExecutionStore(
                    root / "loser-resume",
                    steward=loser["guild"],
                    reservation_store=loser["store"],
                ),
                claim=loser["claim"],
                claim_decision=losing_decision,
                all_active_decisions=[active_decision],
                old_run=run_f,
                old_checkpoint=checkpoint_f,
                resume_kwargs={
                    "old_run": run_f,
                    "old_checkpoint": checkpoint_f,
                    "old_pause": pause_f,
                    "old_stop": stop_f,
                    "old_authorization": auth_f,
                    "new_snapshot": loser["treasury"],
                    "new_proposal": loser["proposal"],
                    "new_authorization": loser["authorization"],
                    "new_reservation": loser["reservation"],
                    "promise": promise,
                    "route_policy": route_policy,
                    "bundles": bundles,
                    "supplied_temporal_intersection": loser_temporal8,
                    "executor": loser["worker"],
                    "observed_cut": 8,
                },
            )
        )
        assert loser_resume_refused

        # The losing resource owner explicitly releases its unused reservation.
        loser_release = loser["store"].release(
            loser["treasury"],
            loser["proposal"],
            loser["authorization"],
            loser["reservation"],
            observed_cut=8,
            reason="RESUME_CLAIM_NOT_SELECTED",
        )
        assert loser_release["status"] == "RELEASED"

        # Winning claimant resumes through the claim gate.
        winner_temporal8 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            winner["reservation"],
            observed_cut=8,
        )
        resumed_store = ResumedExecutionStore(
            root / "winner-resume",
            steward=winner["guild"],
            reservation_store=winner["store"],
        )
        resume, claim_binding = claim_bound_resume(
            resumed_store,
            claim=winner["claim"],
            claim_decision=active_decision,
            all_active_decisions=[active_decision],
            old_run=run_f,
            old_checkpoint=checkpoint_f,
            resume_kwargs={
                "old_run": run_f,
                "old_checkpoint": checkpoint_f,
                "old_pause": pause_f,
                "old_stop": stop_f,
                "old_authorization": auth_f,
                "new_snapshot": winner["treasury"],
                "new_proposal": winner["proposal"],
                "new_authorization": winner["authorization"],
                "new_reservation": winner["reservation"],
                "promise": promise,
                "route_policy": route_policy,
                "bundles": bundles,
                "supplied_temporal_intersection": winner_temporal8,
                "executor": winner["worker"],
                "observed_cut": 8,
            },
        )
        assert claim_binding["resume_claim_id"] == (
            active_decision["resume_claim_id"]
        )
        assert claim_binding["claim_gate_status"] == "ELIGIBLE_ACTIVE"

        # Continue under fresh gates.
        temporal_w9 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            winner["reservation"],
            observed_cut=9,
            execution_started_at_cut=8,
        )
        resumed_checkpoint = resumed_store.checkpoint(
            resume,
            winner["treasury"],
            winner["proposal"],
            winner["authorization"],
            winner["reservation"],
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=temporal_w9,
            executor=winner["worker"],
            observed_cut=9,
            total_progress_percent=70,
            partial_result_ref="partial:061-winner-70",
        )
        assert resumed_checkpoint["total_progress_percent"] == 70

        temporal_w10 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            winner["reservation"],
            observed_cut=10,
            execution_started_at_cut=8,
        )
        completion, execution, finalization = resumed_store.complete(
            resume,
            winner["treasury"],
            winner["proposal"],
            winner["authorization"],
            winner["reservation"],
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=temporal_w10,
            executor=winner["worker"],
            observed_cut=10,
            result_ref="result:061-winning-resume-complete",
        )
        assert execution["success"] is True
        assert finalization["status"] == "CONSUMED"
        completion_binding = bind_completion_to_winning_claim(
            claim_binding,
            completion,
        )
        assert completion_binding["winning_continuation_named"] is True
        assert completion_binding["resume_claim_id"] == (
            winner["claim"]["resume_claim_id"]
        )
        assert completion_binding["losing_claims_deleted"] is False

        # Disconnected replica pressure test: each F-owned replica sees only one
        # claim, so both can locally issue ACTIVE receipts. Exchange reveals a fork.
        replica_e = ResumeClaimRegistry(
            root / "replica-e",
            source_steward=guild_f,
        )
        replica_g = ResumeClaimRegistry(
            root / "replica-g",
            source_steward=guild_f,
        )
        item_e = next(
            item for item in candidates.values()
            if item["guild_id"] == "guild:e"
        )
        item_g = next(
            item for item in candidates.values()
            if item["guild_id"] == "guild:g"
        )
        active_e = replica_e.consider(
            run_f,
            checkpoint_f,
            stop_f,
            item_e["treasury"],
            item_e["proposal"],
            item_e["authorization"],
            item_e["reservation"],
            item_e["claim"],
            observed_cut=8,
        )
        active_g = replica_g.consider(
            run_f,
            checkpoint_f,
            stop_f,
            item_g["treasury"],
            item_g["proposal"],
            item_g["authorization"],
            item_g["reservation"],
            item_g["claim"],
            observed_cut=8,
        )
        assert active_e["status"] == "ACTIVE"
        assert active_g["status"] == "ACTIVE"

        fork = reconcile_active_resume_claims(
            run_f,
            checkpoint_f,
            [item_e["claim"], item_g["claim"]],
            [active_e, active_g],
        )
        assert fork["status"] == "FORK"
        assert fork["global_consensus"] is False
        assert fork["claim_deleted"] is False

        blocked_e = resume_claim_gate(
            run_f,
            checkpoint_f,
            item_e["claim"],
            [active_e, active_g],
        )
        blocked_g = resume_claim_gate(
            run_f,
            checkpoint_f,
            item_g["claim"],
            [active_e, active_g],
        )
        assert blocked_e["status"] == "BLOCKED_FORK"
        assert blocked_g["status"] == "BLOCKED_FORK"

        resolution = make_resume_claim_resolution(
            run_f,
            checkpoint_f,
            fork,
            [item_e["claim"], item_g["claim"]],
            source_steward=guild_f,
        )
        resolved_e = resume_claim_gate(
            run_f,
            checkpoint_f,
            item_e["claim"],
            [active_e, active_g],
            resolution=resolution,
        )
        resolved_g = resume_claim_gate(
            run_f,
            checkpoint_f,
            item_g["claim"],
            [active_e, active_g],
            resolution=resolution,
        )
        statuses = {resolved_e["status"], resolved_g["status"]}
        assert statuses == {"ELIGIBLE_RESOLVED", "SUPERSEDED"}
        assert resolution["claim_deleted"] is False
        assert resolution["global_consensus"] is False

        print({
            "simulation_passed": True,
            "atomic_registry": {
                "active_claims": 1,
                "losing_claims": 1,
                "winner_guild": winner["guild_id"],
                "loser_guild": loser["guild_id"],
                "loser_resume_refused": loser_resume_refused,
                "loser_claim_deleted": False,
            },
            "winning_continuation": {
                "resume_claim_id": winner["claim"]["resume_claim_id"],
                "resume_id": resume["resume_id"],
                "completion_id": completion["resumed_completion_id"],
                "winning_continuation_named": True,
                "total_progress": completion["total_progress_percent"],
            },
            "distributed_fork": {
                "active_receipts_seen": 2,
                "status": fork["status"],
                "both_blocked_before_resolution": True,
                "resolution_rule": resolution["rule"],
                "resolved_statuses": sorted(statuses),
                "global_consensus": False,
                "claims_deleted": False,
            },
            "laws": [
                "RESUMABLE STATE != MULTIPLE CONTINUATION AUTHORITY",
                "ONE CHECKPOINT -> AT MOST ONE ACTIVE RESUME CLAIM",
                "CLAIM != EXECUTION",
                "LOSING CLAIM != HISTORY DELETION",
                "FORK DETECTION != GLOBAL CONSENSUS",
                "COMPLETION MUST NAME THE WINNING CONTINUATION LINEAGE",
            ],
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
