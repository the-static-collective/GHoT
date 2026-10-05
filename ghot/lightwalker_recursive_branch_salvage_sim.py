#!/usr/bin/env python3
"""Experiment 065 — Recursive Branch Merge / Salvage of Losing Work."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lightwalker_continuation_dag import (
    ContinuationDagStore,
    make_continuation_handoff,
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
from lightwalker_recursive_branch_fork import (
    make_recursive_branch_resolution,
    reconcile_recursive_branches,
    recursive_branch_gate,
    verify_recursive_branch_resolution,
)
from lightwalker_recursive_branch_salvage import (
    attach_salvaged_artifact,
    branch_guarded_handoff,
    derive_salvage_accounting,
    make_losing_branch_salvage,
    make_resolved_branch_progress,
    verify_losing_branch_salvage,
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
        subject_ref=f"capability:{guild_id}-render-065",
        source_ref=f"ghot-node:{guild_id}-065",
        evidence_refs=[f"receipt:{guild_id}-probe-065"],
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
            resource_ref="service:recursive-fork-065",
            terms={
                "unit": "compute-minute",
                "quantity": 100,
                "capability": "render.verified",
            },
            evidence_policy="resolved-recursive-branch",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:065",
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
            quantity=100, cut=6, purpose="065-root-f",
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
            progress_percent=10, partial_result_ref="partial:065-f-10",
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
            quantity=90, cut=8, purpose="065-e",
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
            total_progress_percent=20, partial_result_ref="partial:065-e-20",
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
            quantity=80, cut=10, purpose="065-h-seed",
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
                partial_result_ref=f"partial:065-{current_name}-{current_progress + 10}",
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
                purpose=f"065-{child_name}",
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
            partial_result_ref="partial:065-l-60",
        )
        stop_l, final_l = store_l.stop(
            current_node, checkpoint_l, l["snapshot"], proposals["l"],
            authorizations["l"], reservation_l,
            observed_cut=current_cut, reason="READY_FOR_DISTRIBUTED_CHILD",
        )
        assert final_l["consumed_measure"]["quantity"] == 10
        assert final_l["released_measure"]["quantity"] == 40

        p = providers["p"]
        q = providers["q"]
        store_p_res = GuildReservationStore(root / "reservations-p", steward=p["guild"])
        store_q_res = GuildReservationStore(root / "reservations-q", steward=q["guild"])
        proposal_p, auth_p, reservation_p = reserve(
            store_p_res, p["snapshot"], p["entry"],
            steward=p["guild"], executor=p["worker"],
            quantity=40, cut=current_cut, purpose="065-fork-p",
        )
        proposal_q, auth_q, reservation_q = reserve(
            store_q_res, q["snapshot"], q["entry"],
            steward=q["guild"], executor=q["worker"],
            quantity=40, cut=current_cut, purpose="065-fork-q",
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
            partial_result_ref="artifact:065-p-75",
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
            partial_result_ref="artifact:065-q-80",
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
            purpose="065-pre-resolution-r",
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

        salvage = make_losing_branch_salvage(
            parent_node=current_node,
            parent_checkpoint=checkpoint_l,
            fork=fork,
            resolution=resolution,
            losing_child=loser,
            losing_checkpoint=loser_checkpoint,
            losing_stop=loser_stop,
            losing_reservation=loser_reservation,
            losing_finalization=loser_final,
        )
        assert verify_losing_branch_salvage(
            parent_node=current_node,
            parent_checkpoint=checkpoint_l,
            fork=fork,
            resolution=resolution,
            losing_child=loser,
            losing_checkpoint=loser_checkpoint,
            losing_stop=loser_stop,
            losing_reservation=loser_reservation,
            losing_finalization=loser_final,
            salvage=salvage,
        )
        assert salvage["salvaged_work_measure"]["quantity"] == loser_new_work
        assert salvage["root_progress_credit_measure"]["quantity"] == 0
        assert salvage["artifact_survives"] is True
        assert salvage["continuation_authority"] == "none"

        winning_progress = make_resolved_branch_progress(
            parent_node=current_node,
            parent_checkpoint=checkpoint_l,
            fork=fork,
            resolution=resolution,
            winning_child=winner,
            winning_checkpoint=winner_checkpoint,
            winning_stop=winner_stop,
            winning_reservation=winner_reservation,
            winning_finalization=winner_final,
        )
        assert winning_progress["credited_work_measure"]["quantity"] == (
            winner_new_work
        )
        assert winning_progress["authoritative_progress_percent"] == (
            winner_progress
        )

        # A salvage artifact with forged root credit is rejected by its verifier.
        forged_salvage = dict(salvage)
        forged_salvage["root_progress_credit_measure"] = {
            "unit": "compute-minute",
            "quantity": loser_new_work,
        }
        assert not verify_losing_branch_salvage(
            parent_node=current_node,
            parent_checkpoint=checkpoint_l,
            fork=fork,
            resolution=resolution,
            losing_child=loser,
            losing_checkpoint=loser_checkpoint,
            losing_stop=loser_stop,
            losing_reservation=loser_reservation,
            losing_finalization=loser_final,
            salvage=forged_salvage,
        )

        # The resolved winner now hands its exact root-relative remainder to R.
        remaining = 100 - winner_progress
        store_r_res = GuildReservationStore(
            root / "reservations-r",
            steward=r["guild"],
        )
        proposal_r, auth_r, reservation_r = reserve(
            store_r_res,
            r["snapshot"],
            r["entry"],
            steward=r["guild"],
            executor=r["worker"],
            quantity=remaining,
            cut=current_cut + 2,
            purpose="065-resolved-final-r",
        )

        losing_handoff_refused = refused(
            lambda: branch_guarded_handoff(
                child_store_q if loser_name == "q" else child_store_p,
                parent_fork_node=current_node,
                parent_fork_checkpoint=checkpoint_l,
                parent_fork_stop=stop_l,
                parent_fork_reservation=reservation_l,
                parent_fork_finalization=final_l,
                branches=branches,
                branch_child_node=loser,
                resolution=resolution,
                handoff_args={
                    "node": loser,
                    "checkpoint": loser_checkpoint,
                    "stop": loser_stop,
                    "reservation": loser_reservation,
                    "finalization": loser_final,
                    "next_reservation": reservation_r,
                    "observed_cut": current_cut + 2,
                },
            )
        )
        assert losing_handoff_refused

        winner_handoff = branch_guarded_handoff(
            winner_store,
            parent_fork_node=current_node,
            parent_fork_checkpoint=checkpoint_l,
            parent_fork_stop=stop_l,
            parent_fork_reservation=reservation_l,
            parent_fork_finalization=final_l,
            branches=branches,
            branch_child_node=winner,
            resolution=resolution,
            handoff_args={
                "node": winner,
                "checkpoint": winner_checkpoint,
                "stop": winner_stop,
                "reservation": winner_reservation,
                "finalization": winner_final,
                "next_reservation": reservation_r,
                "observed_cut": current_cut + 2,
            },
        )

        store_r = RecursiveContinuationStore(
            root / "recursive-r",
            steward=r["guild"],
            reservation_store=store_r_res,
        )
        node_r = store_r.resume_child(
            parent_node=winner,
            parent_checkpoint=winner_checkpoint,
            parent_stop=winner_stop,
            parent_reservation=winner_reservation,
            parent_finalization=winner_final,
            handoff=winner_handoff,
            new_snapshot=r["snapshot"],
            new_proposal=proposal_r,
            new_authorization=auth_r,
            new_reservation=reservation_r,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise,
                route_policy,
                bundles,
                reservation_r,
                observed_cut=current_cut + 2,
            ),
            executor=r["worker"],
            observed_cut=current_cut + 2,
        )
        completion_r, execution_r, final_r = store_r.complete(
            node_r,
            r["snapshot"],
            proposal_r,
            auth_r,
            reservation_r,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise,
                route_policy,
                bundles,
                reservation_r,
                observed_cut=current_cut + 3,
                execution_started_at_cut=node_r["resumed_at_cut"],
            ),
            executor=r["worker"],
            observed_cut=current_cut + 3,
            result_ref="result:065-authoritative-complete",
        )
        assert execution_r["success"] is True
        assert final_r["status"] == "CONSUMED"
        assert final_r["consumed_measure"]["quantity"] == remaining
        assert completion_r["total_progress_percent"] == 100
        assert completion_r["full_ancestry_proven"] is True

        attachment = attach_salvaged_artifact(
            salvage,
            completion_r,
        )
        assert attachment["artifact_retained"] is True
        assert attachment["merged_execution"] is False
        assert attachment["root_progress_credit_measure"]["quantity"] == 0

        accounting = derive_salvage_accounting(
            parent_checkpoint=checkpoint_l,
            resolved_progress=winning_progress,
            salvage=salvage,
            terminal_completion=completion_r,
        )
        assert accounting["authoritative_root_total"]["quantity"] == 100
        assert accounting["losing_branch_root_credit_measure"]["quantity"] == 0
        assert accounting["root_progress_double_counted"] is False
        assert accounting["artifact_destroyed"] is False
        assert accounting["execution_merged"] is False
        assert accounting[
            "useful_work_observed_including_salvage"
        ]["quantity"] == 100 + loser_new_work

        print({
            "simulation_passed": True,
            "deep_parent": {
                "guild": "guild:l",
                "hop_index": current_node["hop_index"],
                "checkpoint_progress": checkpoint_l["total_progress_percent"],
                "pre_fork_cumulative_work": 60,
            },
            "branch_work_before_discovery": {
                "p_progress": 75,
                "p_consumed": 15,
                "q_progress": 80,
                "q_consumed": 20,
                "both_work_receipts_terminal": True,
            },
            "fork": {
                "status": fork["status"],
                "both_blocked_before_resolution": True,
                "global_consensus": False,
                "history_deleted": False,
            },
            "resolution": {
                "winner": winner_name,
                "winner_progress": winner_progress,
                "loser": loser_name,
                "loser_salvaged_work": loser_new_work,
                "loser_root_progress_credit": 0,
                "losing_handoff_refused": losing_handoff_refused,
            },
            "salvage": {
                "artifact_ref": salvage["artifact_ref"],
                "artifact_survives": salvage["artifact_survives"],
                "continuation_authority": salvage[
                    "continuation_authority"
                ],
                "attached_as_auxiliary_artifact": attachment[
                    "artifact_retained"
                ],
                "merged_execution": attachment["merged_execution"],
            },
            "accounting": {
                "authoritative_root_total": accounting[
                    "authoritative_root_total"
                ]["quantity"],
                "useful_work_observed_including_salvage": accounting[
                    "useful_work_observed_including_salvage"
                ]["quantity"],
                "root_progress_double_counted": accounting[
                    "root_progress_double_counted"
                ],
                "terminal_remaining_consumed": remaining,
            },
            "laws": [
                "LOSING BRANCH WORK != ZERO WORK",
                "SALVAGE != CONTINUATION AUTHORITY",
                "MERGEABLE ARTIFACT != MERGED EXECUTION",
                "USEFUL OUTPUT MAY SURVIVE A LOSING BRANCH",
                "ROOT PROGRESS MAY COUNT EACH WORK UNIT AT MOST ONCE",
                "FORK RESOLUTION != ARTIFACT DESTRUCTION",
            ],
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
