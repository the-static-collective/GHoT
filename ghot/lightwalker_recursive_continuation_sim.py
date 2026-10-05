#!/usr/bin/env python3
"""Experiment 063 — Recursive Continuation Kernel / Arbitrary-Depth Resume."""

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
from lightwalker_recursive_continuation import (
    RecursiveContinuationStore,
    compact_recursive_lineage,
    derive_recursive_lineage,
    verify_compact_recursive_lineage,
    verify_recursive_completion,
    verify_recursive_node,
    verify_recursive_view,
)
from lightwalker_route_policy import make_route_policy
from lightwalker_transition_composition import derive_temporal_intersection
from relatte_identity import IdentityKey


def refused(fn) -> bool:
    try:
        fn()
    except (LightwalkerEconomyError, FileExistsError):
        return True
    return False


def source_treasury(
    guild_id: str,
    steward: IdentityKey,
) -> tuple[dict, dict, dict]:
    entry = make_treasury_entry(
        category="capability",
        position="available",
        subject_ref=f"capability:{guild_id}-render-063",
        source_ref=f"ghot-node:{guild_id}-063",
        evidence_refs=[f"receipt:{guild_id}-probe-063"],
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

        # Ten sequential sovereign work owners: F + E + H + J + K + L + M + N + P + Q.
        provider_names = ["f", "e", "h", "j", "k", "l", "m", "n", "p", "q"]
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

        treasury_b, entry_b, proof_b = source_treasury("guild:b", guild_b)
        treasury_c, entry_c, proof_c = source_treasury("guild:c", guild_c)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref="service:recursive-continuation-063",
            terms={
                "unit": "compute-minute",
                "quantity": 100,
                "capability": "render.verified",
            },
            evidence_policy="recursive-root-relative-ancestry",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:063",
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
            policy_name="customer-recursive-boundary",
            assessor=customer_assessor,
            measurer=measurer,
        )
        pv1, pv2, pt = policy_pair(
            promise=promise,
            route_policy=route_policy,
            issuer=guild_a,
            issuer_role="promisor",
            policy_name="promisor-recursive-boundary",
            assessor=promisor_assessor,
            measurer=measurer,
        )
        bundles = [
            bundle("customer", cv1, cv2, ct),
            bundle("promisor", pv1, pv2, pt),
        ]

        # Root F: 100 reserved, checkpoint at 10%, consume 10 / release 90.
        f = providers["f"]
        store_f = GuildReservationStore(root / "reservations-f", steward=f["guild"])
        proposal_f, auth_f, reservation_f = reserve(
            store_f,
            f["snapshot"],
            f["entry"],
            steward=f["guild"],
            executor=f["worker"],
            quantity=100,
            cut=6,
            purpose="063-root-f",
        )
        long_f = LongRunningExecutionStore(
            root / "long-f",
            steward=f["guild"],
            reservation_store=store_f,
        )
        run_f = long_f.start(
            f["snapshot"],
            proposal_f,
            auth_f,
            reservation_f,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_f, observed_cut=6
            ),
            executor=f["worker"],
            observed_cut=6,
        )
        checkpoint_f = long_f.checkpoint(
            run_f,
            f["snapshot"],
            proposal_f,
            auth_f,
            reservation_f,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise,
                route_policy,
                bundles,
                reservation_f,
                observed_cut=7,
                execution_started_at_cut=6,
            ),
            executor=f["worker"],
            observed_cut=7,
            progress_percent=10,
            partial_result_ref="partial:063-f-10",
        )
        pause_f = long_f.pause(run_f, observed_cut=7, reason="HANDOFF_TO_E")
        stop_f = long_f.stop(
            run_f,
            f["snapshot"],
            proposal_f,
            auth_f,
            reservation_f,
            observed_cut=7,
            reason="HANDOFF_TO_E",
        )
        final_f = store_f.finalization(reservation_f["reservation_id"])
        assert final_f is not None and verify_finalization(reservation_f, final_f)
        assert final_f["consumed_measure"]["quantity"] == 10
        assert final_f["released_measure"]["quantity"] == 90

        # E: 90 reserved, resume at 10%, checkpoint at 20%, consume 10 / release 80.
        e = providers["e"]
        store_e = GuildReservationStore(root / "reservations-e", steward=e["guild"])
        proposal_e, auth_e, reservation_e = reserve(
            store_e,
            e["snapshot"],
            e["entry"],
            steward=e["guild"],
            executor=e["worker"],
            quantity=90,
            cut=8,
            purpose="063-hop1-e",
        )
        resumed_e_store = ResumedExecutionStore(
            root / "resumed-e",
            steward=e["guild"],
            reservation_store=store_e,
        )
        resume_e = resumed_e_store.resume(
            old_run=run_f,
            old_checkpoint=checkpoint_f,
            old_pause=pause_f,
            old_stop=stop_f,
            old_authorization=auth_f,
            new_snapshot=e["snapshot"],
            new_proposal=proposal_e,
            new_authorization=auth_e,
            new_reservation=reservation_e,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_e, observed_cut=8
            ),
            executor=e["worker"],
            observed_cut=8,
        )
        checkpoint_e = resumed_e_store.checkpoint(
            resume_e,
            e["snapshot"],
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
                observed_cut=9,
                execution_started_at_cut=8,
            ),
            executor=e["worker"],
            observed_cut=9,
            total_progress_percent=20,
            partial_result_ref="partial:063-e-20",
        )
        stop_e = resumed_e_store.stop(
            resume_e,
            e["snapshot"],
            proposal_e,
            auth_e,
            reservation_e,
            observed_cut=10,
            reason="HANDOFF_TO_H",
        )
        final_e = store_e.finalization(reservation_e["reservation_id"])
        assert final_e is not None and verify_finalization(reservation_e, final_e)
        assert final_e["consumed_measure"]["quantity"] == 10
        assert final_e["released_measure"]["quantity"] == 80

        # H: 062 seed node at hop 2, starting from root-relative progress 20%.
        h = providers["h"]
        store_h_res = GuildReservationStore(
            root / "reservations-h",
            steward=h["guild"],
        )
        proposal_h, auth_h, reservation_h = reserve(
            store_h_res,
            h["snapshot"],
            h["entry"],
            steward=h["guild"],
            executor=h["worker"],
            quantity=80,
            cut=10,
            purpose="063-seed-h",
        )
        handoff_e_h = make_continuation_handoff(
            resume_e,
            checkpoint_e,
            stop_e,
            reservation_e,
            final_e,
            reservation_h,
            steward=e["guild"],
            observed_cut=10,
        )
        seed_store_062 = ContinuationDagStore(
            root / "seed-h-062",
            steward=h["guild"],
            reservation_store=store_h_res,
        )
        node_h = seed_store_062.resume_from_handoff(
            parent_resume=resume_e,
            parent_checkpoint=checkpoint_e,
            parent_stop=stop_e,
            parent_reservation=reservation_e,
            parent_finalization=final_e,
            handoff=handoff_e_h,
            new_snapshot=h["snapshot"],
            new_proposal=proposal_h,
            new_authorization=auth_h,
            new_reservation=reservation_h,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise, route_policy, bundles, reservation_h, observed_cut=10
            ),
            executor=h["worker"],
            observed_cut=10,
        )

        recursive_stores: dict[str, RecursiveContinuationStore] = {}
        reservation_stores: dict[str, GuildReservationStore] = {"h": store_h_res}
        proposals: dict[str, dict] = {"h": proposal_h}
        authorizations: dict[str, dict] = {"h": auth_h}
        reservations: dict[str, dict] = {"h": reservation_h}

        store_h = RecursiveContinuationStore(
            root / "recursive-h",
            steward=h["guild"],
            reservation_store=store_h_res,
        )
        store_h.register_seed(node_h)
        recursive_stores["h"] = store_h

        current_name = "h"
        current_node = node_h
        edges: list[dict] = []
        consumed_by_provider = {"f": 10, "e": 10}
        duplicate_child_refused = False

        # H -> J -> K -> L -> M -> N -> P -> Q.
        recursive_children = ["j", "k", "l", "m", "n", "p", "q"]
        current_progress = 20
        current_cut = 11

        for child_index, child_name in enumerate(recursive_children):
            parent = providers[current_name]
            parent_store = recursive_stores[current_name]
            parent_reservation_store = reservation_stores[current_name]
            parent_reservation = reservations[current_name]
            parent_proposal = proposals[current_name]
            parent_authorization = authorizations[current_name]

            target_progress = current_progress + 10
            checkpoint = parent_store.checkpoint(
                current_node,
                parent["snapshot"],
                parent_proposal,
                parent_authorization,
                parent_reservation,
                promise=promise,
                route_policy=route_policy,
                bundles=bundles,
                supplied_temporal_intersection=derive_temporal_intersection(
                    promise,
                    route_policy,
                    bundles,
                    parent_reservation,
                    observed_cut=current_cut,
                    execution_started_at_cut=(
                        10 if current_name == "h"
                        else current_node["resumed_at_cut"]
                    ),
                ),
                executor=parent["worker"],
                observed_cut=current_cut,
                total_progress_percent=target_progress,
                partial_result_ref=(
                    f"partial:063-{current_name}-{target_progress}"
                ),
            )
            stop, finalization = parent_store.stop(
                current_node,
                checkpoint,
                parent["snapshot"],
                parent_proposal,
                parent_authorization,
                parent_reservation,
                observed_cut=current_cut,
                reason=f"HANDOFF_TO_{child_name.upper()}",
            )
            assert finalization["status"] == "PARTIALLY_CONSUMED"
            assert finalization["consumed_measure"]["quantity"] == 10
            consumed_by_provider[current_name] = 10

            child = providers[child_name]
            child_store_res = GuildReservationStore(
                root / f"reservations-{child_name}",
                steward=child["guild"],
            )
            child_quantity = 100 - target_progress
            child_proposal, child_auth, child_reservation = reserve(
                child_store_res,
                child["snapshot"],
                child["entry"],
                steward=child["guild"],
                executor=child["worker"],
                quantity=child_quantity,
                cut=current_cut,
                purpose=f"063-recursive-{child_name}",
            )

            handoff = parent_store.handoff(
                current_node,
                checkpoint,
                stop,
                parent_reservation,
                finalization,
                child_reservation,
                observed_cut=current_cut,
            )

            # On the first recursive edge, prove a second valid child cannot be
            # accepted for the same checkpoint after the first handoff wins.
            if child_index == 0:
                alt_guild = IdentityKey.load_or_create(
                    root / "guild-alt" / "body.pem"
                )
                alt_worker = IdentityKey.load_or_create(
                    root / "worker-alt" / "body.pem"
                )
                alt_snapshot, alt_entry, _ = source_treasury(
                    "guild:alt",
                    alt_guild,
                )
                alt_store = GuildReservationStore(
                    root / "reservations-alt",
                    steward=alt_guild,
                )
                alt_proposal, alt_auth, alt_reservation = reserve(
                    alt_store,
                    alt_snapshot,
                    alt_entry,
                    steward=alt_guild,
                    executor=alt_worker,
                    quantity=child_quantity,
                    cut=current_cut,
                    purpose="063-duplicate-child-pressure",
                )
                duplicate_child_refused = refused(
                    lambda: parent_store.handoff(
                        current_node,
                        checkpoint,
                        stop,
                        parent_reservation,
                        finalization,
                        alt_reservation,
                        observed_cut=current_cut,
                    )
                )
                assert duplicate_child_refused
                alt_release = alt_store.release(
                    alt_snapshot,
                    alt_proposal,
                    alt_auth,
                    alt_reservation,
                    observed_cut=current_cut,
                    reason="DUPLICATE_CHILD_NOT_ACCEPTED",
                )
                assert alt_release["status"] == "RELEASED"

            child_store = RecursiveContinuationStore(
                root / f"recursive-{child_name}",
                steward=child["guild"],
                reservation_store=child_store_res,
            )
            child_node = child_store.resume_child(
                parent_node=current_node,
                parent_checkpoint=checkpoint,
                parent_stop=stop,
                parent_reservation=parent_reservation,
                parent_finalization=finalization,
                handoff=handoff,
                new_snapshot=child["snapshot"],
                new_proposal=child_proposal,
                new_authorization=child_auth,
                new_reservation=child_reservation,
                promise=promise,
                route_policy=route_policy,
                bundles=bundles,
                supplied_temporal_intersection=derive_temporal_intersection(
                    promise,
                    route_policy,
                    bundles,
                    child_reservation,
                    observed_cut=current_cut,
                ),
                executor=child["worker"],
                observed_cut=current_cut,
            )
            assert verify_recursive_node(child_node)
            assert child_node["hop_index"] == target_progress // 10
            assert len(child_node["checkpoint_ancestry"]) == (
                child_node["hop_index"]
            )
            assert child_node["source_work_measure"]["quantity"] == 100
            assert child_node["prior_work_measure"]["quantity"] == target_progress
            assert child_node["remaining_work_measure"]["quantity"] == child_quantity

            edges.append({
                "parent_node": current_node,
                "checkpoint": checkpoint,
                "stop": stop,
                "reservation": parent_reservation,
                "finalization": finalization,
                "handoff": handoff,
                "child_node": child_node,
            })
            recursive_stores[child_name] = child_store
            reservation_stores[child_name] = child_store_res
            proposals[child_name] = child_proposal
            authorizations[child_name] = child_auth
            reservations[child_name] = child_reservation

            current_name = child_name
            current_node = child_node
            current_progress = target_progress
            current_cut += 1

        # Q is hop 9 at 90% and owns the final 10 units.
        assert current_name == "q"
        assert current_node["hop_index"] == 9
        assert current_node["prior_progress_percent"] == 90
        assert current_node["remaining_work_measure"]["quantity"] == 10

        active_view = derive_recursive_lineage(node_h, edges)
        assert verify_recursive_view(active_view)
        assert active_view["status"] == "ACTIVE"
        assert active_view["recursive_depth"] == 9
        assert active_view["live_leaf_count"] == 1
        assert active_view["tip_node_id"] == current_node["recursive_node_id"]
        assert active_view["root_source_work_measure"]["quantity"] == 100

        q = providers["q"]
        q_store = recursive_stores["q"]
        q_reservation = reservations["q"]
        completion, execution_q, final_q = q_store.complete(
            current_node,
            q["snapshot"],
            proposals["q"],
            authorizations["q"],
            q_reservation,
            promise=promise,
            route_policy=route_policy,
            bundles=bundles,
            supplied_temporal_intersection=derive_temporal_intersection(
                promise,
                route_policy,
                bundles,
                q_reservation,
                observed_cut=current_cut,
                execution_started_at_cut=current_node["resumed_at_cut"],
            ),
            executor=q["worker"],
            observed_cut=current_cut,
            result_ref="result:063-recursive-complete",
        )
        assert execution_q["success"] is True
        assert final_q["status"] == "CONSUMED"
        assert final_q["consumed_measure"]["quantity"] == 10
        assert verify_recursive_completion(current_node, completion)
        consumed_by_provider["q"] = 10

        complete_view = derive_recursive_lineage(
            node_h,
            edges,
            completion=completion,
        )
        assert verify_recursive_view(complete_view)
        assert complete_view["status"] == "COMPLETED"
        assert complete_view["live_leaf_count"] == 0
        assert complete_view["recursive_depth"] == 9
        assert len(complete_view["checkpoint_ancestry"]) == 9

        compact = compact_recursive_lineage(complete_view)
        assert verify_compact_recursive_lineage(complete_view, compact)
        assert compact["ancestry_count"] == 9
        assert compact["recursive_depth"] == 9
        assert compact["history_erased"] is False
        assert compact["execution_authority"] == "none"
        assert compact["sufficient_for_new_resume"] is False

        tampered_view = dict(complete_view)
        tampered_view["recursive_depth"] = 8
        assert not verify_recursive_view(tampered_view)

        total_consumed = sum(consumed_by_provider.values())
        assert total_consumed == 100
        assert set(consumed_by_provider) == set(provider_names)

        print({
            "simulation_passed": True,
            "root": {
                "measure": 100,
                "f_progress": 10,
                "e_progress": 20,
                "seed_h_hop": 2,
            },
            "recursive_kernel": {
                "terminal_hop": current_node["hop_index"],
                "checkpoint_ancestry_count": len(
                    current_node["checkpoint_ancestry"]
                ),
                "recursive_edges": len(edges),
                "duplicate_child_refused": duplicate_child_refused,
                "root_measure_invariant": (
                    current_node["source_work_measure"]["quantity"] == 100
                ),
            },
            "completion": {
                "status": complete_view["status"],
                "total_progress": completion["total_progress_percent"],
                "full_ancestry_proven": completion["full_ancestry_proven"],
                "ancestor_work_double_counted": (
                    completion["ancestor_work_double_counted"]
                ),
                "total_consumed": total_consumed,
            },
            "compaction": {
                "ancestry_count": compact["ancestry_count"],
                "history_erased": compact["history_erased"],
                "execution_authority": compact["execution_authority"],
                "sufficient_for_new_resume": compact[
                    "sufficient_for_new_resume"
                ],
            },
            "laws": [
                "DEPTH != AUTHORITY",
                "RECURSION != HISTORY COLLAPSE",
                "EACH EDGE MUST PROVE ITS PARENT",
                "ROOT MEASURE MUST REMAIN INVARIANT",
                "ONLY ONE LIVE LEAF PER ACCEPTED BRANCH",
                "COMPACTION MAY SHORTEN PROOF TRANSPORT WITHOUT ERASING ANCESTRY",
            ],
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
