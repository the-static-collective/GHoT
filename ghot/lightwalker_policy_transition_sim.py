#!/usr/bin/env python3
"""Experiment 056 — Policy Transition Modes / Grace / Migration."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_economy import LightwalkerEconomyError
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
from lightwalker_multi_source_service import make_multi_source_promise
from lightwalker_policy_composition import make_policy_fragment
from lightwalker_policy_transition import (
    derive_transition_decision,
    make_migration_receipt,
    make_policy_transition,
    verify_policy_transition,
)
from lightwalker_policy_versioning import (
    derive_active_policy_set,
    make_policy_version,
)
from lightwalker_route_policy import make_route_policy
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
        subject_ref=f"capability:{guild_id}-render-056",
        source_ref=f"ghot-node:{guild_id}-056",
        evidence_refs=[f"receipt:{guild_id}-probe-056"],
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
    proposer: IdentityKey,
    executor: IdentityKey,
    quantity: int,
    authorized_at_cut: int,
    expires_after_cut: int,
    purpose: str,
) -> tuple[dict, dict, dict]:
    proposal = make_resource_proposal(
        snapshot,
        proposer=proposer,
        resource_entry_id=entry["entry_id"],
        requested_quantity=quantity,
        requested_unit="compute-minute",
        purpose_ref=purpose,
        proposed_at_cut=authorized_at_cut,
    )
    authorization, reservation = store.reserve_and_authorize(
        snapshot,
        proposal,
        executor_particular=executor.particular(),
        authorized_at_cut=authorized_at_cut,
        expires_after_cut=expires_after_cut,
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
        customer = IdentityKey.load_or_create(root / "customer" / "body.pem")
        assessor = IdentityKey.load_or_create(root / "assessor" / "body.pem")
        measurer = IdentityKey.load_or_create(root / "measurer" / "body.pem")
        worker_e = IdentityKey.load_or_create(root / "worker-e" / "body.pem")
        worker_f = IdentityKey.load_or_create(root / "worker-f" / "body.pem")

        treasury_b, entry_b, proof_b = source_treasury("guild:b", guild_b)
        treasury_c, entry_c, proof_c = source_treasury("guild:c", guild_c)
        treasury_e, entry_e, proof_e = source_treasury("guild:e", guild_e)
        treasury_f, entry_f, proof_f = source_treasury("guild:f", guild_f)

        service = make_obligation(
            obligation_type="future-compute-service",
            resource_ref="service:transition-modes-056",
            terms={
                "unit": "compute-minute",
                "quantity": 60,
                "capability": "render.verified",
            },
            evidence_policy="transition-mode-aware",
        )
        consideration = make_obligation(
            obligation_type="service-consideration",
            resource_ref="consideration:056",
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
            ordered_guild_ids=["guild:b", "guild:f", "guild:e"],
            required_capability="render.verified",
            max_proof_age_cuts=20,
            max_failover_hops=3,
            created_at_cut=2,
        )

        customer_v1 = make_policy_fragment(
            promise,
            route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-transition-boundary",
            trusted_assessor_particular=assessor.particular(),
            trusted_measurer_particular=measurer.particular(),
            allowed_jurisdictions=["zone:b"],
            min_privacy_class=3,
            require_renewable_evidence=False,
            max_expected_completion_cuts=5,
            forbidden_sovereign_groups=[],
            max_attestation_age_cuts=5,
            created_at_cut=5,
        )
        customer_v2 = make_policy_fragment(
            promise,
            route_policy,
            issuer=customer,
            issuer_role="customer",
            policy_name="customer-transition-boundary",
            trusted_assessor_particular=assessor.particular(),
            trusted_measurer_particular=measurer.particular(),
            allowed_jurisdictions=["zone:b"],
            min_privacy_class=3,
            require_renewable_evidence=False,
            max_expected_completion_cuts=5,
            forbidden_sovereign_groups=["group:f"],
            max_attestation_age_cuts=5,
            created_at_cut=7,
        )
        version_v1 = make_policy_version(
            promise,
            route_policy,
            customer_v1,
            issuer=customer,
            version_number=1,
            effective_from_cut=5,
            declared_at_cut=5,
        )
        version_v2 = make_policy_version(
            promise,
            route_policy,
            customer_v2,
            issuer=customer,
            version_number=2,
            effective_from_cut=7,
            declared_at_cut=7,
            previous_version=version_v1,
        )

        policy_set_v2 = derive_active_policy_set(
            promise,
            route_policy,
            [customer_v1, customer_v2],
            [version_v1, version_v2],
            observed_cut=7,
        )

        store_f = GuildReservationStore(root / "reservations-f", steward=guild_f)
        proposal_f, auth_f, reservation_f = reserve(
            store_f,
            treasury_f,
            entry_f,
            proposer=guild_f,
            executor=worker_f,
            quantity=10,
            authorized_at_cut=6,
            expires_after_cut=12,
            purpose="transition-specimen:f-old",
        )
        proposal_f_new, auth_f_new, reservation_f_new = reserve(
            store_f,
            treasury_f,
            entry_f,
            proposer=guild_f,
            executor=worker_f,
            quantity=10,
            authorized_at_cut=7,
            expires_after_cut=12,
            purpose="transition-specimen:f-new",
        )

        transitions = {
            "immediate": make_policy_transition(
                promise,
                route_policy,
                previous_version=version_v1,
                current_version=version_v2,
                issuer=customer,
                mode="IMMEDIATE_REVALIDATION",
                declared_at_cut=7,
            ),
            "grace": make_policy_transition(
                promise,
                route_policy,
                previous_version=version_v1,
                current_version=version_v2,
                issuer=customer,
                mode="GRACE_UNTIL_CUT",
                grace_until_cut=8,
                declared_at_cut=7,
            ),
            "finish": make_policy_transition(
                promise,
                route_policy,
                previous_version=version_v1,
                current_version=version_v2,
                issuer=customer,
                mode="FINISH_IN_FLIGHT_ONLY",
                declared_at_cut=7,
            ),
            "new_work": make_policy_transition(
                promise,
                route_policy,
                previous_version=version_v1,
                current_version=version_v2,
                issuer=customer,
                mode="NEW_WORK_ONLY",
                declared_at_cut=7,
            ),
            "migrate": make_policy_transition(
                promise,
                route_policy,
                previous_version=version_v1,
                current_version=version_v2,
                issuer=customer,
                mode="MIGRATE_BEFORE_EXECUTION",
                declared_at_cut=7,
            ),
        }
        for transition in transitions.values():
            assert verify_policy_transition(
                promise,
                route_policy,
                version_v1,
                version_v2,
                transition,
            )
            assert transition["resource_owner_authority"] == "none"
            assert transition["execution_authority"] == "none"

        immediate = derive_transition_decision(
            transitions["immediate"],
            reservation_f,
            observed_cut=7,
        )
        assert immediate["action"] == "REVALIDATE_NOW"
        assert immediate["revalidation_required"] is True
        assert immediate["legacy_path_open"] is False

        grace7 = derive_transition_decision(
            transitions["grace"],
            reservation_f,
            observed_cut=7,
        )
        grace8 = derive_transition_decision(
            transitions["grace"],
            reservation_f,
            observed_cut=8,
        )
        grace9 = derive_transition_decision(
            transitions["grace"],
            reservation_f,
            observed_cut=9,
        )
        assert grace7["action"] == "ALLOW_LEGACY_DURING_GRACE"
        assert grace8["legacy_path_open"] is True
        assert grace8["enforcement_deferred_until_cut"] == 8
        assert grace9["action"] == "REVALIDATE_AFTER_GRACE"
        assert grace9["legacy_path_open"] is False
        assert grace9["revalidation_required"] is True

        finish_started = derive_transition_decision(
            transitions["finish"],
            reservation_f,
            observed_cut=7,
            execution_started_at_cut=6,
        )
        finish_not_started = derive_transition_decision(
            transitions["finish"],
            reservation_f,
            observed_cut=7,
            execution_started_at_cut=None,
        )
        finish_expired = derive_transition_decision(
            transitions["finish"],
            reservation_f,
            observed_cut=13,
            execution_started_at_cut=6,
        )
        assert finish_started["action"] == "ALLOW_FINISH_IN_FLIGHT"
        assert finish_started["legacy_path_open"] is True
        assert finish_not_started["action"] == "BLOCK_NOT_IN_FLIGHT"
        assert finish_expired["legacy_path_open"] is False
        assert finish_expired["revalidation_required"] is True

        new_work_old = derive_transition_decision(
            transitions["new_work"],
            reservation_f,
            observed_cut=7,
        )
        new_work_new = derive_transition_decision(
            transitions["new_work"],
            reservation_f_new,
            observed_cut=7,
        )
        new_work_expired = derive_transition_decision(
            transitions["new_work"],
            reservation_f,
            observed_cut=13,
        )
        assert new_work_old["action"] == "ALLOW_PREEXISTING_RESERVATION"
        assert new_work_old["legacy_path_open"] is True
        assert (
            new_work_new["action"]
            == "CURRENT_POLICY_REQUIRED_FOR_NEW_WORK"
        )
        assert new_work_new["legacy_path_open"] is False
        assert new_work_expired["legacy_path_open"] is False

        migrate = derive_transition_decision(
            transitions["migrate"],
            reservation_f,
            observed_cut=7,
        )
        assert migrate["action"] == "MIGRATION_REQUIRED"
        assert migrate["migration_required"] is True
        assert migrate["legacy_path_open"] is False

        fake_finalization = {
            "reservation_id": reservation_f["reservation_id"],
            "status": "ACTIVE",
            "finalization_id": "sha256:" + "0" * 64,
        }
        migration_before_owner_release_refused = refused(
            lambda: make_migration_receipt(
                transitions["migrate"],
                migrate,
                old_reservation=reservation_f,
                old_finalization=fake_finalization,
                new_reservation=reservation_f_new,
                current_policy_set_id=policy_set_v2["policy_set_id"],
            )
        )
        assert migration_before_owner_release_refused

        release_f = store_f.release(
            treasury_f,
            proposal_f,
            auth_f,
            reservation_f,
            observed_cut=7,
            reason="TRANSITION_REQUIRES_MIGRATION",
        )
        assert release_f["status"] == "RELEASED"

        store_e = GuildReservationStore(root / "reservations-e", steward=guild_e)
        proposal_e, auth_e, reservation_e = reserve(
            store_e,
            treasury_e,
            entry_e,
            proposer=guild_e,
            executor=worker_e,
            quantity=10,
            authorized_at_cut=8,
            expires_after_cut=13,
            purpose="transition-specimen:e-migrated",
        )
        migration = make_migration_receipt(
            transitions["migrate"],
            migrate,
            old_reservation=reservation_f,
            old_finalization=release_f,
            new_reservation=reservation_e,
            current_policy_set_id=policy_set_v2["policy_set_id"],
        )
        assert migration["old_history_rewritten"] is False
        assert migration["new_reservation_is_continuation"] is False
        assert migration["ownership_transfer"] is False
        assert migration["reservation_authority"] == "none"
        assert migration["execution_authority"] == "none"

        # Customer owns the policy transition, but F and E own the reservation
        # actions. The identities are deliberately distinct.
        assert customer.particular() != guild_f.particular()
        assert customer.particular() != guild_e.particular()

        frozen_v1 = json.dumps(customer_v1, sort_keys=True)
        frozen_v2 = json.dumps(customer_v2, sort_keys=True)
        assert json.dumps(customer_v1, sort_keys=True) == frozen_v1
        assert json.dumps(customer_v2, sort_keys=True) == frozen_v2

        print(json.dumps({
            "simulation_passed": True,
            "modes": {
                "IMMEDIATE_REVALIDATION": immediate["action"],
                "GRACE_UNTIL_CUT": {
                    "cut7": grace7["action"],
                    "cut8": grace8["action"],
                    "cut9": grace9["action"],
                },
                "FINISH_IN_FLIGHT_ONLY": {
                    "started_before_v2": finish_started["action"],
                    "not_started": finish_not_started["action"],
                    "after_reservation_expiry": finish_expired["action"],
                },
                "NEW_WORK_ONLY": {
                    "preexisting_reservation": new_work_old["action"],
                    "new_reservation": new_work_new["action"],
                    "preexisting_after_expiry": new_work_expired["action"],
                },
                "MIGRATE_BEFORE_EXECUTION": migrate["action"],
            },
            "migration": {
                "before_owner_release_refused": (
                    migration_before_owner_release_refused
                ),
                "old_reservation_finalization": release_f["status"],
                "new_reservation_guild": treasury_e["guild_id"],
                "old_history_rewritten": False,
                "new_reservation_is_continuation": False,
                "ownership_transfer": False,
            },
            "authority": {
                "policy_issuer_is_f_owner": False,
                "policy_issuer_is_e_owner": False,
                "transition_resource_owner_authority": "none",
                "migration_reservation_authority": "none",
            },
            "laws": [
                "TRANSITION MODE != POLICY CONTENT",
                "GRACE != PERMANENT EXEMPTION",
                "IN-FLIGHT != UNBOUNDED GRANDFATHERING",
                "MIGRATION != HISTORY REWRITE",
                "POLICY ISSUER != RESOURCE OWNER",
                "DEFERRED ENFORCEMENT != ABSENT ENFORCEMENT",
            ],
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
