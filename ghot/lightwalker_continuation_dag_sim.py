#!/usr/bin/env python3
"""Experiment 062 — Continuation DAG / Multi-Hop Resume Lineage."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lightwalker_continuation_dag import (
    ContinuationDagStore,
    derive_continuation_dag,
    make_continuation_handoff,
    verify_continuation_completion,
    verify_continuation_handoff,
    verify_continuation_node,
)
from lightwalker_economy import LightwalkerEconomyError
from lightwalker_execution_resume import ResumedExecutionStore
from lightwalker_federated_service import make_remote_capacity_proof
from lightwalker_guild_authorization import make_resource_proposal
from lightwalker_guild_reservation import (
    GuildReservationStore,
    verify_finalization,
)
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
        subject_ref=f"capability:{guild_id}-render-062",
        source_ref=f"ghot-node:{guild_id}-062",
        evidence_refs=[f"receipt:{guild_id}-probe-062"],
        native_measure={"unit": "compute-minute", "quantity": 60},
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
        expires_after_cut=16,
    )
    return proposal, authorization, reservation


def policy_pair(
    *,
    promise: dict,
    route_policy: dict,
    issuer: IdentityKey,
    issuer_role: str,
    policy_name: str,
    assessor: IdentityKey,
    measurer: IdentityKey,
) -> tuple[dict, dict]:
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
        max_expected_completion_cuts=10,
        forbidden_sovereign_groups=[],
        max_attestation_age_cuts=10,
    )
    v1 = make_policy_fragment(**common, created_at_cut=5)
    v2 = make_policy_fragment(**common, created_at_cut=6)
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
    transition = make_policy_transition(
        promise,
        route_policy,
        previous_version=version1,
        current_version=version2,
        issuer=issuer,
        mode="GRACE_UNTIL_CUT",
        grace_until_cut=15,
        declared_at_cut=6,
    )
    return version1, version2, transition


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


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild_a = IdentityKey.load_or_create(root / "guild-a" / "body.pem")
        guild_b = IdentityKey.load_or_create(root / "guild-b" / "body.pem")
        guild_c = IdentityKey.load_or_create(root / "guild-c" / "body.pem")
        guild_f = IdentityKey.load_or_create(root / "guild-f" / "body.pem")
        guild_e = IdentityKey.load_or_create(root / "guild-e" / "body.pem")
        guild_h = IdentityKey.load_or_create(root / "guild-h" / "body.pem")
        guild_g = IdentityKey.load_or_create(root / "guild-g" / "body.pem")

        worker_f = IdentityKey.load_or_create(root / "worker-f" / "body.pem")
        worker_e = IdentityKey.load_or_create(root / "worker-e" / "body.pem")
        worker_h = IdentityKey.load_or_create(root / "worker-h" / "body.pem")
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
        treasury_h, entry_h, proof_h = source_treasury("guild:h", guild_h)
        treasury_g, entry_g, proof_g = source_treasury("guild:g", guild_g)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref="service:continuation-dag-062",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="full-multihop-ancestry",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:062",
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
                "guild:h",
                "guild:g",
            ],
            required_capability="render.verified",
            max_proof_age_cuts=20,
            max_failover_hops=5,
            created_at_cut=2,
        )

        cv1, cv2, ct = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-dag-boundary",
            assessor=customer_assessor,
            measurer=measurer,
        )
        pv1, pv2, pt = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-dag-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
        )
        bundles = [
            bundle("customer", cv1, cv2, ct),
            bundle("promisor", pv1, pv2, pt),
        ]

        # Hop 0 — F owns the original 30 units and reaches 40%.
        store_f = GuildReservationStore(root / "reservations-f", steward=guild_f)
        proposal_f, auth_f, reservation_f = reserve(
            store_f,
            treasury_f,
            entry_f,
            steward=guild_f,
            executor=worker_f,
            quantity=30,
            cut=6,
            purpose="062-root-f",
        )
        temporal_f6 = derive_temporal_intersection(
            promise, route_policy, bundles, reservation_f, observed_cut=6
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
            partial_result_ref="partial:062-f-40",
        )
        pause_f = long_f.pause(
            run_f,
            observed_cut=7,
            reason="HANDOFF_TO_E",
        )
        stop_f = long_f.stop(
            run_f,
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            observed_cut=7,
            reason="HANDOFF_TO_E",
        )
        final_f = store_f.finalization(reservation_f["reservation_id"])
        assert final_f is not None
        assert verify_finalization(reservation_f, final_f)
        assert final_f["status"] == "PARTIALLY_CONSUMED"
        assert final_f["consumed_measure"]["quantity"] == 12
        assert final_f["released_measure"]["quantity"] == 18

        # Hop 1 — E receives exactly the remaining 18 units and reaches 70%.
        store_e = GuildReservationStore(root / "reservations-e", steward=guild_e)
        proposal_e, auth_e, reservation_e = reserve(
            store_e,
            treasury_e,
            entry_e,
            steward=guild_e,
            executor=worker_e,
            quantity=18,
            cut=8,
            purpose="062-hop1-e",
        )
        temporal_e8 = derive_temporal_intersection(
            promise, route_policy, bundles, reservation_e, observed_cut=8
        )
        resumed_e_store = ResumedExecutionStore(
            root / "resumed-e",
            steward=guild_e,
            reservation_store=store_e,
        )
        resume_e = resumed_e_store.resume(
            old_run=run_f,
            old_checkpoint=checkpoint_f,
            old_pause=pause_f,
            old_stop=stop_f,
            old_authorization=auth_f,
            new_snapshot=treasury_e,
            new_proposal=proposal_e,
            new_authorization=auth_e,
            new_reservation=reservation_e,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=temporal_e8,
            executor=worker_e,
            observed_cut=8,
        )
        temporal_e9 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            reservation_e,
            observed_cut=9,
            execution_started_at_cut=8,
        )
        checkpoint_e = resumed_e_store.checkpoint(
            resume_e,
            treasury_e,
            proposal_e,
            auth_e,
            reservation_e,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=temporal_e9,
            executor=worker_e,
            observed_cut=9,
            total_progress_percent=70,
            partial_result_ref="partial:062-e-70",
        )
        assert checkpoint_e["prior_progress_percent"] == 40
        assert checkpoint_e["new_work_progress_percent"] == 30
        assert checkpoint_e["total_progress_percent"] == 70

        stop_e = resumed_e_store.stop(
            resume_e,
            treasury_e,
            proposal_e,
            auth_e,
            reservation_e,
            observed_cut=10,
            reason="HANDOFF_TO_H",
        )
        final_e = store_e.finalization(reservation_e["reservation_id"])
        assert final_e is not None
        assert verify_finalization(reservation_e, final_e)
        assert final_e["status"] == "PARTIALLY_CONSUMED"
        assert final_e["consumed_measure"]["quantity"] == 9
        assert final_e["released_measure"]["quantity"] == 9

        e_after_stop_refused = refused(
            lambda: resumed_e_store.checkpoint(
                resume_e,
                treasury_e,
                proposal_e,
                auth_e,
                reservation_e,
                promise=promise,
                route_policy=route_policy,
                bundles=bundles,
                supplied_temporal_intersection=derive_temporal_intersection(
                    promise,
                    route_policy,
                    bundles,
                    reservation_e,
                    observed_cut=10,
                    execution_started_at_cut=8,
                ),
                executor=worker_e,
                observed_cut=10,
                total_progress_percent=80,
                partial_result_ref="partial:062-e-80-must-not-exist",
            )
        )
        assert e_after_stop_refused

        # Hop 2 candidates — H is chosen for the exact root-relative remainder 9.
        store_h = GuildReservationStore(root / "reservations-h", steward=guild_h)
        proposal_h, auth_h, reservation_h = reserve(
            store_h,
            treasury_h,
            entry_h,
            steward=guild_h,
            executor=worker_h,
            quantity=9,
            cut=10,
            purpose="062-hop2-h",
        )
        store_g = GuildReservationStore(root / "reservations-g", steward=guild_g)
        proposal_g, auth_g, reservation_g = reserve(
            store_g,
            treasury_g,
            entry_g,
            steward=guild_g,
            executor=worker_g,
            quantity=9,
            cut=10,
            purpose="062-wrong-next-g",
        )

        handoff = make_continuation_handoff(
            resume_e,
            checkpoint_e,
            stop_e,
            reservation_e,
            final_e,
            reservation_h,
            steward=guild_e,
            observed_cut=10,
        )
        assert verify_continuation_handoff(
            resume_e,
            checkpoint_e,
            stop_e,
            reservation_e,
            final_e,
            reservation_h,
            handoff,
        )
        assert handoff["cumulative_work_measure"]["quantity"] == 21
        assert handoff["remaining_work_measure"]["quantity"] == 9

        dag_h_store = ContinuationDagStore(
            root / "dag-h",
            steward=guild_h,
            reservation_store=store_h,
        )
        wrong_next_refused = refused(
            lambda: ContinuationDagStore(
                root / "dag-g",
                steward=guild_g,
                reservation_store=store_g,
            ).resume_from_handoff(
                parent_resume=resume_e,
                parent_checkpoint=checkpoint_e,
                parent_stop=stop_e,
                parent_reservation=reservation_e,
                parent_finalization=final_e,
                handoff=handoff,
                new_snapshot=treasury_g,
                new_proposal=proposal_g,
                new_authorization=auth_g,
                new_reservation=reservation_g,
                promise=promise,
                route_policy=route_policy,
                bundles=bundles,
                supplied_temporal_intersection=derive_temporal_intersection(
                    promise,
                    route_policy,
                    bundles,
                    reservation_g,
                    observed_cut=10,
                ),
                executor=worker_g,
                observed_cut=10,
            )
        )
        assert wrong_next_refused

        temporal_h10 = derive_temporal_intersection(
            promise, route_policy, bundles, reservation_h, observed_cut=10
        )
        node_h = dag_h_store.resume_from_handoff(
            parent_resume=resume_e,
            parent_checkpoint=checkpoint_e,
            parent_stop=stop_e,
            parent_reservation=reservation_e,
            parent_finalization=final_e,
            handoff=handoff,
            new_snapshot=treasury_h,
            new_proposal=proposal_h,
            new_authorization=auth_h,
            new_reservation=reservation_h,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=temporal_h10,
            executor=worker_h,
            observed_cut=10,
        )
        assert verify_continuation_node(node_h)
        assert node_h["prior_progress_percent"] == 70
        assert node_h["prior_work_measure"]["quantity"] == 21
        assert node_h["remaining_work_measure"]["quantity"] == 9
        assert node_h["checkpoint_ancestry"] == [
            checkpoint_f["checkpoint_id"],
            checkpoint_e["resumed_checkpoint_id"],
        ]

        active_dag = derive_continuation_dag(
            run_f,
            checkpoint_f,
            resume_e,
            checkpoint_e,
            stop_e,
            handoff,
            [node_h],
        )
        assert active_dag["status"] == "ACTIVE"
        assert active_dag["live_leaf_count"] == 1
        assert active_dag["live_leaf_ids"] == [node_h["continuation_node_id"]]
        assert active_dag["resource_reservations_distinct"] is True

        multiple_live_leaf_view_refused = refused(
            lambda: derive_continuation_dag(
                run_f,
                checkpoint_f,
                resume_e,
                checkpoint_e,
                stop_e,
                handoff,
                [node_h, dict(node_h)],
            )
        )
        assert multiple_live_leaf_view_refused

        temporal_h11 = derive_temporal_intersection(
            promise,
            route_policy,
            bundles,
            reservation_h,
            observed_cut=11,
            execution_started_at_cut=10,
        )
        completion_h, execution_h, final_h = dag_h_store.complete(
            node_h,
            treasury_h,
            proposal_h,
            auth_h,
            reservation_h,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=temporal_h11,
            executor=worker_h,
            observed_cut=11,
            result_ref="result:062-h-complete",
        )
        assert execution_h["success"] is True
        assert final_h["status"] == "CONSUMED"
        assert final_h["consumed_measure"]["quantity"] == 9
        assert verify_continuation_completion(node_h, completion_h)
        assert completion_h["ancestor_work_measure"]["quantity"] == 21
        assert completion_h["new_work_measure"]["quantity"] == 9
        assert completion_h["total_work_measure"]["quantity"] == 30
        assert completion_h["full_ancestry_proven"] is True
        assert completion_h["ancestor_work_double_counted"] is False

        complete_dag = derive_continuation_dag(
            run_f,
            checkpoint_f,
            resume_e,
            checkpoint_e,
            stop_e,
            handoff,
            [node_h],
            completion=completion_h,
        )
        assert complete_dag["status"] == "COMPLETED"
        assert complete_dag["live_leaf_count"] == 0
        assert complete_dag["terminal_leaf_id"] == (
            completion_h["continuation_completion_id"]
        )

        total_consumed = (
            int(final_f["consumed_measure"]["quantity"])
            + int(final_e["consumed_measure"]["quantity"])
            + int(final_h["consumed_measure"]["quantity"])
        )
        assert total_consumed == 30

        print({
            "simulation_passed": True,
            "root": {
                "guild": "guild:f",
                "progress": 40,
                "consumed": 12,
                "released": 18,
            },
            "hop_1": {
                "guild": "guild:e",
                "total_progress": 70,
                "new_root_relative_progress": 30,
                "consumed": 9,
                "released": 9,
                "stopped_branch_cannot_continue": e_after_stop_refused,
            },
            "hop_2": {
                "guild": "guild:h",
                "prior_progress": 70,
                "remaining_authority": 9,
                "wrong_next_resource_refused": wrong_next_refused,
                "completed": completion_h["service_complete"],
            },
            "dag": {
                "checkpoint_ancestry": node_h["checkpoint_ancestry"],
                "active_live_leaf_count": active_dag["live_leaf_count"],
                "multiple_live_leaf_view_refused": (
                    multiple_live_leaf_view_refused
                ),
                "final_status": complete_dag["status"],
                "full_ancestry_proven": completion_h[
                    "full_ancestry_proven"
                ],
            },
            "accounting": {
                "f_consumed": 12,
                "e_consumed": 9,
                "h_consumed": 9,
                "total_consumed": total_consumed,
                "root_measure": 30,
                "double_counted": False,
            },
            "laws": [
                "CONTINUATION LINEAGE != RESOURCE LINEAGE",
                "MULTI-HOP RESUME != RESTART CHAIN",
                "ANCESTOR CHECKPOINTS MAY NOT BE DOUBLE-COUNTED",
                "EACH HOP REQUIRES NEW LOCAL AUTHORITY",
                "ONLY ONE LIVE LEAF PER CONTINUATION BRANCH",
                "COMPLETION MUST PROVE THE FULL RESUME ANCESTRY",
            ],
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
