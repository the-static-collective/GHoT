#!/usr/bin/env python3
"""Experiment 066 — Work-Region Provenance / Non-Overlapping Salvage."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ice_cube import build_work, render_pgm, work_address
from lightwalker_continuation_dag import (
    ContinuationDagStore,
    make_continuation_handoff,
)
from lightwalker_economy import LightwalkerEconomyError, content_address
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
from lightwalker_recursive_branch_fork import (
    make_recursive_branch_resolution,
    reconcile_recursive_branches,
    recursive_branch_gate,
    verify_recursive_branch_resolution,
)
from lightwalker_recursive_branch_salvage import branch_guarded_handoff
from lightwalker_work_region_salvage import (
    derive_non_overlapping_region_salvage,
    derive_region_composed_completion,
    make_branch_region_work_receipt,
    make_pixel_region_plan,
    make_region_coverage_attestation,
    make_region_execution_evidence,
    make_salvaged_region_admission,
    missing_region_ids,
    region_claim_set,
    region_ids_for_indices,
    verify_branch_region_work_receipt,
    verify_region_coverage_attestation,
    verify_region_execution_evidence,
    verify_salvaged_region_admission,
)
from lightwalker_recursive_continuation import RecursiveContinuationStore
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
        subject_ref=f"capability:{guild_id}-render-066",
        source_ref=f"ghot-node:{guild_id}-066",
        evidence_refs=[f"receipt:{guild_id}-probe-066"],
        native_measure={"unit": "compute-minute", "quantity": 100},
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
        valid_through_cut=50,
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
        expires_after_cut=50,
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
) -> tuple[dict, dict, dict]:
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
        max_expected_completion_cuts=20,
        forbidden_sovereign_groups=[],
        max_attestation_age_cuts=20,
    )
    fragment1 = make_policy_fragment(**common, created_at_cut=5)
    fragment2 = make_policy_fragment(**common, created_at_cut=6)
    version1 = make_policy_version(
        promise,
        route_policy,
        fragment1,
        issuer=issuer,
        version_number=1,
        effective_from_cut=5,
        declared_at_cut=5,
    )
    version2 = make_policy_version(
        promise,
        route_policy,
        fragment2,
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
        grace_until_cut=40,
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
        customer = IdentityKey.load_or_create(root / "customer" / "body.pem")
        customer_assessor = IdentityKey.load_or_create(
            root / "customer-assessor" / "body.pem"
        )
        promisor_assessor = IdentityKey.load_or_create(
            root / "promisor-assessor" / "body.pem"
        )
        measurer = IdentityKey.load_or_create(root / "measurer" / "body.pem")

        render_work = build_work(
            width=10,
            height=10,
            max_halley_iter=8,
            fiber_count=20,
        )
        render_work_address = work_address(render_work)

        provider_names = ["f", "e", "h", "j", "k", "l", "p", "q", "r"]
        providers: dict[str, dict] = {}
        for name in provider_names:
            guild = IdentityKey.load_or_create(root / f"guild-{name}" / "body.pem")
            worker = IdentityKey.load_or_create(root / f"worker-{name}" / "body.pem")
            snapshot, entry, proof = source_treasury(f"guild:{name}", guild)
            providers[name] = {
                "guild": guild,
                "worker": worker,
                "snapshot": snapshot,
                "entry": entry,
                "proof": proof,
            }

        treasury_b, _, proof_b = source_treasury("guild:b", guild_b)
        treasury_c, _, proof_c = source_treasury("guild:c", guild_c)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref=render_work_address,
            terms={
                "unit": "compute-minute",
                "quantity": 100,
                "capability": "render.verified",
            },
            evidence_policy="exact-pixel-region-provenance",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:066",
            terms={"deliverable": "signed review"},
            evidence_policy="signed-performance",
        )
        offer = make_exchange_offer(
            offeror_particular=guild_a.particular(),
            offeror_obligation=service,
            acceptor_obligation=consideration,
            orientation_refs=[],
            valid_through_cut=50,
        )
        original_sources = [
            {"snapshot": treasury_b, "proof": proof_b, "quantity": 50},
            {"snapshot": treasury_c, "proof": proof_c, "quantity": 50},
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
            ordered_guild_ids=["guild:b"] + [
                f"guild:{name}" for name in provider_names
            ],
            required_capability="render.verified",
            max_proof_age_cuts=50,
            max_failover_hops=12,
            created_at_cut=2,
        )

        cv1, cv2, ct = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-recursive-fork-boundary",
            assessor=customer_assessor,
            measurer=measurer,
        )
        pv1, pv2, pt = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-recursive-fork-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
        )
        bundles = [
            bundle("customer", cv1, cv2, ct),
            bundle("promisor", pv1, pv2, pt),
        ]

        # F -> E gives the 062 seed ancestry at 20%.
        f = providers["f"]
        store_f = GuildReservationStore(root / "reservations-f", steward=f["guild"])
        proposal_f, auth_f, reservation_f = reserve(
            store_f, f["snapshot"], f["entry"],
            steward=f["guild"], executor=f["worker"],
            quantity=100, cut=6, purpose="066-root-f",
        )
        long_f = LongRunningExecutionStore(
            root / "long-f",
            steward=f["guild"],
            reservation_store=store_f,
        )
        run_f = long_f.start(
            f["snapshot"], proposal_f, auth_f, reservation_f,
            promise=promise, route_policy=route_policy, bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_f, observed_cut=6
            ),
            executor=f["worker"], observed_cut=6,
        )
        checkpoint_f = long_f.checkpoint(
            run_f, f["snapshot"], proposal_f, auth_f, reservation_f,
            promise=promise, route_policy=route_policy, bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_f,
                observed_cut=7, execution_started_at_cut=6,
            ),
            executor=f["worker"], observed_cut=7,
            progress_percent=10, partial_result_ref="partial:066-f-10",
        )
        pause_f = long_f.pause(run_f, observed_cut=7, reason="HANDOFF_TO_E")
        stop_f = long_f.stop(
            run_f, f["snapshot"], proposal_f, auth_f, reservation_f,
            observed_cut=7, reason="HANDOFF_TO_E",
        )
        final_f = store_f.finalization(reservation_f["reservation_id"])
        assert final_f is not None and final_f["consumed_measure"]["quantity"] == 10

        e = providers["e"]
        store_e = GuildReservationStore(root / "reservations-e", steward=e["guild"])
        proposal_e, auth_e, reservation_e = reserve(
            store_e, e["snapshot"], e["entry"],
            steward=e["guild"], executor=e["worker"],
            quantity=90, cut=8, purpose="066-e",
        )
        resumed_e_store = ResumedExecutionStore(
            root / "resumed-e",
            steward=e["guild"],
            reservation_store=store_e,
        )
        resume_e = resumed_e_store.resume(
            old_run=run_f, old_checkpoint=checkpoint_f, old_pause=pause_f,
            old_stop=stop_f, old_authorization=auth_f,
            new_snapshot=e["snapshot"], new_proposal=proposal_e,
            new_authorization=auth_e, new_reservation=reservation_e,
            promise=promise, route_policy=route_policy, bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_e, observed_cut=8
            ),
            executor=e["worker"], observed_cut=8,
        )
        checkpoint_e = resumed_e_store.checkpoint(
            resume_e, e["snapshot"], proposal_e, auth_e, reservation_e,
            promise=promise, route_policy=route_policy, bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_e,
                observed_cut=9, execution_started_at_cut=8,
            ),
            executor=e["worker"], observed_cut=9,
            total_progress_percent=20, partial_result_ref="partial:066-e-20",
        )
        stop_e = resumed_e_store.stop(
            resume_e, e["snapshot"], proposal_e, auth_e, reservation_e,
            observed_cut=10, reason="HANDOFF_TO_H",
        )
        final_e = store_e.finalization(reservation_e["reservation_id"])
        assert final_e is not None and final_e["consumed_measure"]["quantity"] == 10

        h = providers["h"]
        store_h_res = GuildReservationStore(root / "reservations-h", steward=h["guild"])
        proposal_h, auth_h, reservation_h = reserve(
            store_h_res, h["snapshot"], h["entry"],
            steward=h["guild"], executor=h["worker"],
            quantity=80, cut=10, purpose="066-h-seed",
        )
        handoff_e_h = make_continuation_handoff(
            resume_e, checkpoint_e, stop_e, reservation_e, final_e, reservation_h,
            steward=e["guild"], observed_cut=10,
        )
        seed_062_store = ContinuationDagStore(
            root / "seed-h-062",
            steward=h["guild"],
            reservation_store=store_h_res,
        )
        node_h = seed_062_store.resume_from_handoff(
            parent_resume=resume_e, parent_checkpoint=checkpoint_e,
            parent_stop=stop_e, parent_reservation=reservation_e,
            parent_finalization=final_e, handoff=handoff_e_h,
            new_snapshot=h["snapshot"], new_proposal=proposal_h,
            new_authorization=auth_h, new_reservation=reservation_h,
            promise=promise, route_policy=route_policy, bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_h, observed_cut=10
            ),
            executor=h["worker"], observed_cut=10,
        )

        region_plan = make_pixel_region_plan(
            render_work,
            continuation_lineage_id=node_h["continuation_lineage_id"],
        )
        assert region_plan["region_count"] == 100
        assert region_plan["work_address"] == render_work_address

        recursive_stores: dict[str, RecursiveContinuationStore] = {}
        reservation_stores: dict[str, GuildReservationStore] = {"h": store_h_res}
        proposals: dict[str, dict] = {"h": proposal_h}
        authorizations: dict[str, dict] = {"h": auth_h}
        reservations: dict[str, dict] = {"h": reservation_h}

        h_store = RecursiveContinuationStore(
            root / "recursive-h",
            steward=h["guild"],
            reservation_store=store_h_res,
        )
        h_store.register_seed(node_h)
        recursive_stores["h"] = h_store

        current_name = "h"
        current_node = node_h
        current_progress = 20
        current_cut = 11

        # Build to deep parent L at hop 5 / 50%.
        for child_name in ["j", "k", "l"]:
            parent = providers[current_name]
            parent_store = recursive_stores[current_name]
            parent_reservation = reservations[current_name]
            checkpoint = parent_store.checkpoint(
                current_node,
                parent["snapshot"],
                proposals[current_name],
                authorizations[current_name],
                parent_reservation,
                promise=promise, route_policy=route_policy, bundles=bundles,
                supplied_temporal_intersection=derive_temporal_intersection(
                    promise, route_policy, bundles, parent_reservation,
                    observed_cut=current_cut,
                    execution_started_at_cut=(
                        10 if current_name == "h"
                        else current_node["resumed_at_cut"]
                    ),
                ),
                executor=parent["worker"], observed_cut=current_cut,
                total_progress_percent=current_progress + 10,
                partial_result_ref=f"partial:066-{current_name}-{current_progress + 10}",
            )
            stop, finalization = parent_store.stop(
                current_node, checkpoint,
                parent["snapshot"], proposals[current_name],
                authorizations[current_name], parent_reservation,
                observed_cut=current_cut,
                reason=f"HANDOFF_TO_{child_name.upper()}",
            )
            child = providers[child_name]
            child_store_res = GuildReservationStore(
                root / f"reservations-{child_name}", steward=child["guild"]
            )
            child_quantity = 100 - (current_progress + 10)
            child_proposal, child_auth, child_reservation = reserve(
                child_store_res, child["snapshot"], child["entry"],
                steward=child["guild"], executor=child["worker"],
                quantity=child_quantity, cut=current_cut,
                purpose=f"066-{child_name}",
            )
            handoff = parent_store.handoff(
                current_node, checkpoint, stop, parent_reservation,
                finalization, child_reservation,
                observed_cut=current_cut,
            )
            child_store = RecursiveContinuationStore(
                root / f"recursive-{child_name}",
                steward=child["guild"],
                reservation_store=child_store_res,
            )
            child_node = child_store.resume_child(
                parent_node=current_node, parent_checkpoint=checkpoint,
                parent_stop=stop, parent_reservation=parent_reservation,
                parent_finalization=finalization, handoff=handoff,
                new_snapshot=child["snapshot"], new_proposal=child_proposal,
                new_authorization=child_auth, new_reservation=child_reservation,
                promise=promise, route_policy=route_policy, bundles=bundles,
                supplied_temporal_intersection=derive_temporal_intersection(
                    promise, route_policy, bundles, child_reservation,
                    observed_cut=current_cut,
                ),
                executor=child["worker"], observed_cut=current_cut,
            )
            recursive_stores[child_name] = child_store
            reservation_stores[child_name] = child_store_res
            proposals[child_name] = child_proposal
            authorizations[child_name] = child_auth
            reservations[child_name] = child_reservation
            current_name = child_name
            current_node = child_node
            current_progress += 10
            current_cut += 1

        assert current_name == "l"
        assert current_node["hop_index"] == 5
        assert current_node["prior_progress_percent"] == 50

        # L reaches 60%, stops, and its terminal evidence is copied to two
        # disconnected L-owned replicas.
        l = providers["l"]
        store_l = recursive_stores["l"]
        reservation_l = reservations["l"]
        checkpoint_l = store_l.checkpoint(
            current_node, l["snapshot"], proposals["l"],
            authorizations["l"], reservation_l,
            promise=promise, route_policy=route_policy, bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_l,
                observed_cut=current_cut,
                execution_started_at_cut=current_node["resumed_at_cut"],
            ),
            executor=l["worker"], observed_cut=current_cut,
            total_progress_percent=60,
            partial_result_ref="partial:066-l-60",
        )
        stop_l, final_l = store_l.stop(
            current_node, checkpoint_l, l["snapshot"], proposals["l"],
            authorizations["l"], reservation_l,
            observed_cut=current_cut, reason="READY_FOR_DISTRIBUTED_CHILD",
        )
        assert final_l["consumed_measure"]["quantity"] == 10
        assert final_l["released_measure"]["quantity"] == 40

        parent_region_ids = region_ids_for_indices(
            region_plan,
            list(range(60)),
        )
        parent_coverage = make_region_coverage_attestation(
            render_work,
            region_plan,
            current_node,
            checkpoint_l,
            region_ids=parent_region_ids,
            signer=l["guild"],
        )
        assert verify_region_coverage_attestation(
            render_work,
            region_plan,
            current_node,
            checkpoint_l,
            parent_coverage,
        )
        aggregate_progress_not_region_proof = refused(
            lambda: make_region_coverage_attestation(
                render_work,
                region_plan,
                current_node,
                checkpoint_l,
                region_ids=region_ids_for_indices(
                    region_plan,
                    list(range(59)),
                ),
                signer=l["guild"],
            )
        )
        assert aggregate_progress_not_region_proof

        p = providers["p"]
        q = providers["q"]
        store_p_res = GuildReservationStore(root / "reservations-p", steward=p["guild"])
        store_q_res = GuildReservationStore(root / "reservations-q", steward=q["guild"])
        proposal_p, auth_p, reservation_p = reserve(
            store_p_res, p["snapshot"], p["entry"],
            steward=p["guild"], executor=p["worker"],
            quantity=40, cut=current_cut, purpose="066-fork-p",
        )
        proposal_q, auth_q, reservation_q = reserve(
            store_q_res, q["snapshot"], q["entry"],
            steward=q["guild"], executor=q["worker"],
            quantity=40, cut=current_cut, purpose="066-fork-q",
        )

        replica_a = RecursiveContinuationStore(
            root / "replica-a",
            steward=l["guild"],
            reservation_store=reservation_stores["l"],
        )
        replica_b = RecursiveContinuationStore(
            root / "replica-b",
            steward=l["guild"],
            reservation_store=reservation_stores["l"],
        )
        replica_a.register_stopped_replica(
            current_node, checkpoint_l, stop_l, reservation_l, final_l
        )
        replica_b.register_stopped_replica(
            current_node, checkpoint_l, stop_l, reservation_l, final_l
        )

        handoff_p = replica_a.handoff(
            current_node, checkpoint_l, stop_l, reservation_l,
            final_l, reservation_p, observed_cut=current_cut,
        )
        handoff_q = replica_b.handoff(
            current_node, checkpoint_l, stop_l, reservation_l,
            final_l, reservation_q, observed_cut=current_cut,
        )
        assert handoff_p["recursive_handoff_id"] != handoff_q["recursive_handoff_id"]

        child_store_p = RecursiveContinuationStore(
            root / "child-p",
            steward=p["guild"],
            reservation_store=store_p_res,
        )
        child_store_q = RecursiveContinuationStore(
            root / "child-q",
            steward=q["guild"],
            reservation_store=store_q_res,
        )
        child_p = child_store_p.resume_child(
            parent_node=current_node, parent_checkpoint=checkpoint_l,
            parent_stop=stop_l, parent_reservation=reservation_l,
            parent_finalization=final_l, handoff=handoff_p,
            new_snapshot=p["snapshot"], new_proposal=proposal_p,
            new_authorization=auth_p, new_reservation=reservation_p,
            promise=promise, route_policy=route_policy, bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_p,
                observed_cut=current_cut,
            ),
            executor=p["worker"], observed_cut=current_cut,
        )
        child_q = child_store_q.resume_child(
            parent_node=current_node, parent_checkpoint=checkpoint_l,
            parent_stop=stop_l, parent_reservation=reservation_l,
            parent_finalization=final_l, handoff=handoff_q,
            new_snapshot=q["snapshot"], new_proposal=proposal_q,
            new_authorization=auth_q, new_reservation=reservation_q,
            promise=promise, route_policy=route_policy, bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_q,
                observed_cut=current_cut,
            ),
            executor=q["worker"], observed_cut=current_cut,
        )
        assert child_p["hop_index"] == 6
        assert child_q["hop_index"] == 6

        # Both contradictory children perform real checkpointed work before
        # the fork is discovered. P reaches 75%; Q reaches 80%.
        checkpoint_p = child_store_p.checkpoint(
            child_p,
            p["snapshot"],
            proposal_p,
            auth_p,
            reservation_p,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise,
                route_policy,
                bundles,
                reservation_p,
                observed_cut=current_cut + 1,
                execution_started_at_cut=child_p["resumed_at_cut"],
            ),
            executor=p["worker"],
            observed_cut=current_cut + 1,
            total_progress_percent=75,
            partial_result_ref="artifact:066-p-75",
        )
        stop_p, final_p = child_store_p.stop(
            child_p,
            checkpoint_p,
            p["snapshot"],
            proposal_p,
            auth_p,
            reservation_p,
            observed_cut=current_cut + 1,
            reason="FORK_DISCOVERED_AFTER_USEFUL_WORK",
        )
        assert final_p["status"] == "PARTIALLY_CONSUMED"
        assert final_p["consumed_measure"]["quantity"] == 15
        assert final_p["released_measure"]["quantity"] == 25

        checkpoint_q = child_store_q.checkpoint(
            child_q,
            q["snapshot"],
            proposal_q,
            auth_q,
            reservation_q,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise,
                route_policy,
                bundles,
                reservation_q,
                observed_cut=current_cut + 1,
                execution_started_at_cut=child_q["resumed_at_cut"],
            ),
            executor=q["worker"],
            observed_cut=current_cut + 1,
            total_progress_percent=80,
            partial_result_ref="artifact:066-q-80",
        )
        stop_q, final_q = child_store_q.stop(
            child_q,
            checkpoint_q,
            q["snapshot"],
            proposal_q,
            auth_q,
            reservation_q,
            observed_cut=current_cut + 1,
            reason="FORK_DISCOVERED_AFTER_USEFUL_WORK",
        )
        assert final_q["status"] == "PARTIALLY_CONSUMED"
        assert final_q["consumed_measure"]["quantity"] == 20
        assert final_q["released_measure"]["quantity"] == 20

        p_region_ids = region_ids_for_indices(
            region_plan,
            list(range(60, 75)),
        )
        q_region_ids = region_ids_for_indices(
            region_plan,
            list(range(60, 70)) + list(range(75, 85)),
        )
        receipt_p = make_branch_region_work_receipt(
            render_work,
            region_plan,
            child_p,
            checkpoint_p,
            stop_p,
            reservation_p,
            final_p,
            region_ids=p_region_ids,
            signer=p["guild"],
        )
        receipt_q = make_branch_region_work_receipt(
            render_work,
            region_plan,
            child_q,
            checkpoint_q,
            stop_q,
            reservation_q,
            final_q,
            region_ids=q_region_ids,
            signer=q["guild"],
        )
        assert verify_branch_region_work_receipt(
            render_work,
            region_plan,
            child_p,
            checkpoint_p,
            stop_p,
            reservation_p,
            final_p,
            receipt_p,
        )
        assert verify_branch_region_work_receipt(
            render_work,
            region_plan,
            child_q,
            checkpoint_q,
            stop_q,
            reservation_q,
            final_q,
            receipt_q,
        )

        tampered_receipt_p = dict(receipt_p)
        tampered_receipt_p["region_claims"] = [
            dict(row) for row in receipt_p["region_claims"]
        ]
        tampered_receipt_p["region_claims"][0]["value"] = (
            int(tampered_receipt_p["region_claims"][0]["value"]) ^ 1
        )
        tampered_region_value_refused = not verify_branch_region_work_receipt(
            render_work,
            region_plan,
            child_p,
            checkpoint_p,
            stop_p,
            reservation_p,
            final_p,
            tampered_receipt_p,
        )
        assert tampered_region_value_refused

        bundle_p = {
            "child_node": child_p,
            "checkpoint": checkpoint_p,
            "stop": stop_p,
            "reservation": reservation_p,
            "finalization": final_p,
            "receipt": receipt_p,
        }
        bundle_q = {
            "child_node": child_q,
            "checkpoint": checkpoint_q,
            "stop": stop_q,
            "reservation": reservation_q,
            "finalization": final_q,
            "receipt": receipt_q,
        }

        branches = [
            {
                "handoff": handoff_p,
                "next_reservation": reservation_p,
                "child_node": child_p,
            },
            {
                "handoff": handoff_q,
                "next_reservation": reservation_q,
                "child_node": child_q,
            },
        ]
        fork = reconcile_recursive_branches(
            current_node,
            checkpoint_l,
            stop_l,
            reservation_l,
            final_l,
            branches,
        )
        assert fork["status"] == "FORK"
        assert fork["global_consensus"] is False
        assert fork["history_deleted"] is False

        gate_p = recursive_branch_gate(
            current_node,
            checkpoint_l,
            stop_l,
            reservation_l,
            final_l,
            branches,
            child_p,
        )
        gate_q = recursive_branch_gate(
            current_node,
            checkpoint_l,
            stop_l,
            reservation_l,
            final_l,
            branches,
            child_q,
        )
        assert gate_p["status"] == "BLOCKED_FORK"
        assert gate_q["status"] == "BLOCKED_FORK"

        # Even after useful work exists, neither stopped descendant may spawn
        # another accepted continuation until the fork is resolved.
        r = providers["r"]
        store_r_res_pre = GuildReservationStore(
            root / "reservations-r-pre",
            steward=r["guild"],
        )
        proposal_r_pre, auth_r_pre, reservation_r_pre = reserve(
            store_r_res_pre,
            r["snapshot"],
            r["entry"],
            steward=r["guild"],
            executor=r["worker"],
            quantity=25,
            cut=current_cut + 1,
            purpose="066-pre-resolution-r",
        )
        p_handoff_blocked = refused(
            lambda: branch_guarded_handoff(
                child_store_p,
                parent_fork_node=current_node,
                parent_fork_checkpoint=checkpoint_l,
                parent_fork_stop=stop_l,
                parent_fork_reservation=reservation_l,
                parent_fork_finalization=final_l,
                branches=branches,
                branch_child_node=child_p,
                resolution=None,
                handoff_args={
                    "node": child_p,
                    "checkpoint": checkpoint_p,
                    "stop": stop_p,
                    "reservation": reservation_p,
                    "finalization": final_p,
                    "next_reservation": reservation_r_pre,
                    "observed_cut": current_cut + 1,
                },
            )
        )
        assert p_handoff_blocked
        pre_release = store_r_res_pre.release(
            r["snapshot"],
            proposal_r_pre,
            auth_r_pre,
            reservation_r_pre,
            observed_cut=current_cut + 1,
            reason="FORK_UNRESOLVED",
        )
        assert pre_release["status"] == "RELEASED"

        resolution = make_recursive_branch_resolution(
            current_node,
            checkpoint_l,
            fork,
            parent_steward=l["guild"],
        )
        assert verify_recursive_branch_resolution(
            current_node,
            checkpoint_l,
            fork,
            resolution,
        )

        if resolution["winning_child_node_id"] == child_p["recursive_node_id"]:
            winner_name = "p"
            winner = child_p
            winner_store = child_store_p
            winner_checkpoint = checkpoint_p
            winner_stop = stop_p
            winner_final = final_p
            winner_reservation = reservation_p
            winner_progress = 75
            winner_new_work = 15

            loser_name = "q"
            loser = child_q
            loser_checkpoint = checkpoint_q
            loser_stop = stop_q
            loser_final = final_q
            loser_reservation = reservation_q
            loser_new_work = 20
        else:
            winner_name = "q"
            winner = child_q
            winner_store = child_store_q
            winner_checkpoint = checkpoint_q
            winner_stop = stop_q
            winner_final = final_q
            winner_reservation = reservation_q
            winner_progress = 80
            winner_new_work = 20

            loser_name = "p"
            loser = child_p
            loser_checkpoint = checkpoint_p
            loser_stop = stop_p
            loser_final = final_p
            loser_reservation = reservation_p
            loser_new_work = 15

        resolved_winner = recursive_branch_gate(
            current_node,
            checkpoint_l,
            stop_l,
            reservation_l,
            final_l,
            branches,
            winner,
            resolution=resolution,
        )
        resolved_loser = recursive_branch_gate(
            current_node,
            checkpoint_l,
            stop_l,
            reservation_l,
            final_l,
            branches,
            loser,
            resolution=resolution,
        )
        assert resolved_winner["status"] == "ELIGIBLE_RESOLVED"
        assert resolved_loser["status"] == "SUPERSEDED"

        if winner_name == "p":
            winning_bundle = bundle_p
            losing_bundle = bundle_q
        else:
            winning_bundle = bundle_q
            losing_bundle = bundle_p

        nonoverlap = derive_non_overlapping_region_salvage(
            render_work,
            region_plan,
            current_node,
            checkpoint_l,
            parent_coverage,
            fork,
            resolution,
            winning_bundle,
            losing_bundle,
        )
        assert nonoverlap["overlap_region_count"] == 10
        assert nonoverlap["reusable_region_count"] in {5, 10}
        assert nonoverlap["root_region_coverage_credit_count"] == 0
        assert nonoverlap[
            "continuation_progress_credit_measure"
        ]["quantity"] == 0

        admission = make_salvaged_region_admission(
            render_work,
            region_plan,
            current_node,
            checkpoint_l,
            parent_coverage,
            fork,
            resolution,
            winning_bundle,
            losing_bundle,
            nonoverlap,
            parent_steward=l["guild"],
        )
        assert verify_salvaged_region_admission(
            render_work,
            region_plan,
            current_node,
            checkpoint_l,
            parent_coverage,
            fork,
            resolution,
            winning_bundle,
            losing_bundle,
            nonoverlap,
            admission,
        )
        assert admission["root_region_coverage_credit_count"] == (
            nonoverlap["reusable_region_count"]
        )
        assert admission[
            "continuation_progress_credit_measure"
        ]["quantity"] == 0

        forged_nonoverlap = dict(nonoverlap)
        forged_nonoverlap["reusable_region_count"] = (
            int(nonoverlap["reusable_region_count"]) + 1
        )
        overlapping_salvage_admission_refused = refused(
            lambda: make_salvaged_region_admission(
                render_work,
                region_plan,
                current_node,
                checkpoint_l,
                parent_coverage,
                fork,
                resolution,
                winning_bundle,
                losing_bundle,
                forged_nonoverlap,
                parent_steward=l["guild"],
            )
        )
        assert overlapping_salvage_admission_refused

        winning_receipt = winning_bundle["receipt"]
        losing_receipt = losing_bundle["receipt"]
        remaining_region_ids = missing_region_ids(
            region_plan,
            parent_coverage,
            winning_receipt,
            admission,
        )
        assert len(remaining_region_ids) == 15

        r = providers["r"]
        claim_set_r = region_claim_set(
            render_work,
            region_plan,
            region_ids=remaining_region_ids,
            executor_particular=r["worker"].particular(),
        )
        store_r_regions = GuildReservationStore(
            root / "region-reservations-r",
            steward=r["guild"],
        )
        proposal_r, auth_r, reservation_r = reserve(
            store_r_regions,
            r["snapshot"],
            r["entry"],
            steward=r["guild"],
            executor=r["worker"],
            quantity=len(remaining_region_ids),
            cut=current_cut + 2,
            purpose=claim_set_r["region_claim_set_id"],
        )
        execution_r, final_r = store_r_regions.execute_reserved(
            r["snapshot"],
            proposal_r,
            auth_r,
            reservation_r,
            executor=r["worker"],
            observed_cut=current_cut + 2,
            simulate_success=True,
            result_ref=claim_set_r["region_claim_set_id"],
        )
        terminal_region_evidence = make_region_execution_evidence(
            render_work,
            region_plan,
            claim_set_r,
            r["snapshot"],
            proposal_r,
            auth_r,
            reservation_r,
            execution_r,
            final_r,
        )
        assert verify_region_execution_evidence(
            render_work,
            region_plan,
            claim_set_r,
            r["snapshot"],
            proposal_r,
            auth_r,
            reservation_r,
            execution_r,
            final_r,
            terminal_region_evidence,
        )
        assert terminal_region_evidence["region_count"] == 15
        assert final_r["consumed_measure"]["quantity"] == 15

        composition = derive_region_composed_completion(
            render_work,
            region_plan,
            current_node,
            checkpoint_l,
            parent_coverage,
            fork,
            resolution,
            winning_bundle,
            losing_bundle,
            nonoverlap,
            admission,
            terminal_region_evidence,
        )
        canonical_render, _ = render_pgm(render_work)
        assert composition["canonical_render_address"] == content_address(
            canonical_render
        )
        assert composition["authoritative_region_coverage_count"] == 100
        assert composition["useful_region_work_observed"] == 110
        assert composition["salvaged_regions_reexecuted"] == 0
        assert composition["root_region_double_counted"] is False
        assert composition["work_complete"] is True
        assert composition["execution_merged"] is False

        print({
            "simulation_passed": True,
            "root_region_plan": {
                "work_address": render_work_address,
                "width": region_plan["width"],
                "height": region_plan["height"],
                "region_count": region_plan["region_count"],
                "aggregate_progress_not_region_proof": (
                    aggregate_progress_not_region_proof
                ),
            },
            "pre_fork_coverage": {
                "checkpoint_progress": 60,
                "exact_region_count": parent_coverage["region_count"],
                "attestation_verified": True,
            },
            "branch_regions": {
                "p_progress": 75,
                "p_region_count": receipt_p["region_count"],
                "q_progress": 80,
                "q_region_count": receipt_q["region_count"],
                "deliberate_overlap": 10,
                "tampered_region_value_refused": (
                    tampered_region_value_refused
                ),
            },
            "resolution": {
                "winner": winner_name,
                "loser": loser_name,
                "overlap_regions_not_credited": nonoverlap[
                    "overlap_region_count"
                ],
                "reusable_losing_regions": nonoverlap[
                    "reusable_region_count"
                ],
                "overlapping_salvage_admission_refused": (
                    overlapping_salvage_admission_refused
                ),
            },
            "region_completion": {
                "salvaged_region_credit": admission[
                    "root_region_coverage_credit_count"
                ],
                "continuation_progress_credit": admission[
                    "continuation_progress_credit_measure"
                ]["quantity"],
                "fresh_regions_executed_by_r": terminal_region_evidence[
                    "region_count"
                ],
                "authoritative_region_coverage": composition[
                    "authoritative_region_coverage_count"
                ],
                "useful_region_work_observed": composition[
                    "useful_region_work_observed"
                ],
                "salvaged_regions_reexecuted": composition[
                    "salvaged_regions_reexecuted"
                ],
                "render_reconstructed_exactly": (
                    composition["canonical_render_address"]
                    == content_address(canonical_render)
                ),
                "root_region_double_counted": composition[
                    "root_region_double_counted"
                ],
            },
            "laws": [
                "PROGRESS PERCENT != WORK REGION",
                "NON-OVERLAP MUST BE PROVEN",
                "SALVAGED REGION != SALVAGED AUTHORITY",
                "REUSE != DOUBLE CREDIT",
                "ARTIFACT IDENTITY MUST SURVIVE LINEAGE CHANGE",
                "REGION COMPOSITION MAY COMPLETE WORK WITHOUT REEXECUTION",
            ],
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
