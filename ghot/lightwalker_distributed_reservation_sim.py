#!/usr/bin/env python3
"""Experiment 040 — distributed reservation conflict without global ordering."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_distributed_reservation import (
    execution_gate,
    make_claim_crossing,
    make_conflict_resolution,
    make_local_reservation_claim,
    materialize_resolved_claim,
    reconcile_claims,
    verify_conflict_resolution,
    verify_local_reservation_claim,
)
from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_guild_authorization import (
    apply_execution_to_treasury,
    make_resource_proposal,
)
from lightwalker_guild_reservation import GuildReservationStore
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    verify_treasury_snapshot,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def resource_quantity(snapshot: dict, subject_ref: str) -> int:
    entry = next(
        item
        for item in snapshot["entries"]
        if item["subject_ref"] == subject_ref
        and item["category"] == "capability"
        and item["position"] == "available"
    )
    return int(entry["native_measure"]["quantity"])


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild = IdentityKey.load_or_create(root / "guild" / "body-p256.pem")
        worker_a = IdentityKey.load_or_create(root / "worker-a" / "body-p256.pem")
        worker_b = IdentityKey.load_or_create(root / "worker-b" / "body-p256.pem")

        node_a = StateParcelInbox(root / "node-a")
        node_b = StateParcelInbox(root / "node-b")

        compute_ref = "capability:compute-pool-040"
        compute = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref=compute_ref,
            source_ref="ghot-node:guild-compute-040",
            evidence_refs=["receipt:compute-probe-040"],
            native_measure={"unit": "compute-minute", "quantity": 120},
            metadata={"capability": "render.verified"},
        )
        snapshot0 = make_treasury_snapshot(
            guild_id="guild:lantern-forge",
            steward=guild,
            entries=[compute],
            sequence=0,
        )
        assert verify_treasury_snapshot(snapshot0)
        frozen_snapshot0 = json.dumps(snapshot0, sort_keys=True)

        proposal_a = make_resource_proposal(
            snapshot0,
            proposer=worker_a,
            resource_entry_id=compute["entry_id"],
            requested_quantity=80,
            requested_unit="compute-minute",
            purpose_ref="purpose:distributed-a",
            proposed_at_cut=1,
        )
        proposal_b = make_resource_proposal(
            snapshot0,
            proposer=worker_b,
            resource_entry_id=compute["entry_id"],
            requested_quantity=80,
            requested_unit="compute-minute",
            purpose_ref="purpose:distributed-b",
            proposed_at_cut=1,
        )
        proposals = {
            proposal_a["proposal_id"]: proposal_a,
            proposal_b["proposal_id"]: proposal_b,
        }

        # Split-brain moment: each node knows only its own locally signed claim.
        claim_a = make_local_reservation_claim(
            snapshot0,
            proposal_a,
            node=node_a.signer,
            node_id="guild-node-a",
            executor_particular=worker_a.particular(),
            claimed_at_cut=1,
            expires_after_cut=5,
            known_claim_ids=[],
        )
        claim_b = make_local_reservation_claim(
            snapshot0,
            proposal_b,
            node=node_b.signer,
            node_id="guild-node-b",
            executor_particular=worker_b.particular(),
            claimed_at_cut=1,
            expires_after_cut=5,
            known_claim_ids=[],
        )
        assert verify_local_reservation_claim(snapshot0, proposal_a, claim_a)
        assert verify_local_reservation_claim(snapshot0, proposal_b, claim_b)

        frozen_claim_a = json.dumps(claim_a, sort_keys=True)
        frozen_claim_b = json.dumps(claim_b, sort_keys=True)

        local_a = reconcile_claims(snapshot0, [claim_a], proposals)
        local_b = reconcile_claims(snapshot0, [claim_b], proposals)
        assert local_a["status"] == "NO_CONFLICT"
        assert local_b["status"] == "NO_CONFLICT"
        assert local_a["total_claimed_quantity"] == 80
        assert local_b["total_claimed_quantity"] == 80

        crossing_a = make_claim_crossing(claim_a, signer=node_a.signer)
        crossing_b = make_claim_crossing(claim_b, signer=node_b.signer)
        assert verify_crossing(crossing_a)
        assert verify_crossing(crossing_b)
        assert crossing_a["requested_effect"]["automatic_consensus_requested"] is False
        assert crossing_b["requested_effect"]["automatic_execution_requested"] is False

        # Exchange claims via replaceable parcel transport. Arrival is HOLD-first.
        source_a = root / "source-a"
        source_b = root / "source-b"
        file_a = source_a / "distributed" / "claim-a.json"
        file_b = source_b / "distributed" / "claim-b.json"
        file_a.parent.mkdir(parents=True, exist_ok=True)
        file_b.parent.mkdir(parents=True, exist_ok=True)
        file_a.write_text(
            json.dumps(
                {"claim": claim_a, "crossing": crossing_a},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        file_b.write_text(
            json.dumps(
                {"claim": claim_b, "crossing": crossing_b},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        bundle_a_to_b = StateParcelExporter(source_a).export(
            str(file_a.relative_to(source_a)),
            selector="$",
            target_particular=node_b.signer.particular(),
        )
        bundle_b_to_a = StateParcelExporter(source_b).export(
            str(file_b.relative_to(source_b)),
            selector="$",
            target_particular=node_a.signer.particular(),
        )

        held_at_b = node_b.receive(bundle_a_to_b)
        held_at_a = node_a.receive(bundle_b_to_a)
        assert held_at_b["kind"] == "HELD"
        assert held_at_a["kind"] == "HELD"
        assert held_at_b["semantic_effect"] == "none"
        assert held_at_a["semantic_effect"] == "none"

        admitted_at_b = node_b.decide(
            bundle_a_to_b["parcel"]["parcel_id"],
            "ADMIT",
            note="040 admit foreign reservation claim as history, not consensus",
        )
        admitted_at_a = node_a.decide(
            bundle_b_to_a["parcel"]["parcel_id"],
            "ADMIT",
            note="040 admit foreign reservation claim as history, not consensus",
        )
        assert admitted_at_b["kind"] == "ADMITTED"
        assert admitted_at_a["kind"] == "ADMITTED"

        # Both nodes now know both histories. Order does not matter.
        reconciliation_a = reconcile_claims(
            snapshot0, [claim_a, claim_b], proposals
        )
        reconciliation_b = reconcile_claims(
            snapshot0, [claim_b, claim_a], proposals
        )
        assert reconciliation_a == reconciliation_b
        assert reconciliation_a["status"] == "CONFLICT"
        assert reconciliation_a["visible_quantity"] == 120
        assert reconciliation_a["total_claimed_quantity"] == 160
        assert reconciliation_a["overcommit_quantity"] == 40

        assert execution_gate(
            snapshot0,
            claim_a,
            [claim_a, claim_b],
            proposals,
        ) == "BLOCKED_CONFLICT"
        assert execution_gate(
            snapshot0,
            claim_b,
            [claim_a, claim_b],
            proposals,
        ) == "BLOCKED_CONFLICT"

        outsider = IdentityKey.load_or_create(root / "outsider" / "body-p256.pem")
        outsider_resolution_refused = refused(
            lambda: make_conflict_resolution(
                snapshot0,
                reconciliation_a,
                [claim_a, claim_b],
                steward=outsider,
            )
        )
        assert outsider_resolution_refused

        resolution = make_conflict_resolution(
            snapshot0,
            reconciliation_a,
            [claim_a, claim_b],
            steward=guild,
        )
        assert verify_conflict_resolution(
            snapshot0,
            reconciliation_a,
            [claim_a, claim_b],
            resolution,
        )

        selected_id = resolution["selected_claim_ids"][0]
        winner = claim_a if claim_a["claim_id"] == selected_id else claim_b
        loser = claim_b if winner is claim_a else claim_a
        winner_worker = worker_a if winner is claim_a else worker_b

        assert execution_gate(
            snapshot0,
            winner,
            [claim_a, claim_b],
            proposals,
            resolution=resolution,
        ) == "ELIGIBLE_RESOLVED"
        assert execution_gate(
            snapshot0,
            loser,
            [claim_a, claim_b],
            proposals,
            resolution=resolution,
        ) == "SUPERSEDED"

        tampered_resolution = json.loads(json.dumps(resolution))
        tampered_resolution["selected_claim_ids"] = [
            claim_a["claim_id"],
            claim_b["claim_id"],
        ]
        tampered_resolution_refused = not verify_conflict_resolution(
            snapshot0,
            reconciliation_a,
            [claim_a, claim_b],
            tampered_resolution,
        )
        assert tampered_resolution_refused

        authoritative_store = GuildReservationStore(
            root / "authoritative-reservation",
            steward=guild,
        )

        loser_materialization_refused = refused(
            lambda: materialize_resolved_claim(
                snapshot0,
                loser,
                [claim_a, claim_b],
                proposals,
                resolution,
                reservation_store=authoritative_store,
            )
        )
        assert loser_materialization_refused

        authorization, reservation = materialize_resolved_claim(
            snapshot0,
            winner,
            [claim_a, claim_b],
            proposals,
            resolution,
            reservation_store=authoritative_store,
        )

        success_receipt, finalization = authoritative_store.execute_reserved(
            snapshot0,
            proposals[winner["proposal_id"]],
            authorization,
            reservation,
            executor=winner_worker,
            observed_cut=3,
            simulate_success=True,
            result_ref=content_address(
                {
                    "kind": "distributed-reservation-result",
                    "resolution_id": resolution["resolution_id"],
                    "claim_id": winner["claim_id"],
                }
            ),
        )
        assert success_receipt["success"] is True
        assert finalization["status"] == "CONSUMED"

        snapshot1 = apply_execution_to_treasury(
            snapshot0,
            proposals[winner["proposal_id"]],
            authorization,
            success_receipt,
            steward=guild,
        )
        assert verify_treasury_snapshot(snapshot1)
        assert resource_quantity(snapshot1, compute_ref) == 40
        assert snapshot1["prior_snapshot_id"] == snapshot0["snapshot_id"]

        # Reconciliation and resolution added history; they did not rewrite
        # either node's stale local claim or the original Treasury snapshot.
        assert json.dumps(snapshot0, sort_keys=True) == frozen_snapshot0
        assert json.dumps(claim_a, sort_keys=True) == frozen_claim_a
        assert json.dumps(claim_b, sort_keys=True) == frozen_claim_b
        assert claim_a["claim_id"] in reconciliation_a["claim_ids"]
        assert claim_b["claim_id"] in reconciliation_a["claim_ids"]
        assert loser["claim_id"] in resolution["superseded_claim_ids"]

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "split_brain": {
                        "node_a_local_status": local_a["status"],
                        "node_b_local_status": local_b["status"],
                        "each_locally_claimed": 80,
                        "visible_capacity": 120,
                    },
                    "crossing": {
                        "node_a_received_foreign_as": held_at_a["kind"],
                        "node_b_received_foreign_as": held_at_b["kind"],
                        "admission_is_consensus": False,
                    },
                    "reconciliation": {
                        "same_reconciliation_on_both_nodes": True,
                        "status": reconciliation_a["status"],
                        "total_claimed": reconciliation_a["total_claimed_quantity"],
                        "overcommit": reconciliation_a["overcommit_quantity"],
                        "both_execution_gates_blocked_before_resolution": True,
                    },
                    "resolution": {
                        "rule": resolution["rule"],
                        "selected_claim_id": selected_id,
                        "losing_claim_preserved": True,
                        "outsider_resolution_refused": outsider_resolution_refused,
                        "tampered_resolution_refused": tampered_resolution_refused,
                        "loser_materialization_refused": loser_materialization_refused,
                    },
                    "materialization": {
                        "winner_becomes_039_reservation": True,
                        "execution_success": success_receipt["success"],
                        "reservation_finalization": finalization["status"],
                        "treasury_capacity_after_success": 40,
                    },
                    "history": {
                        "snapshot0_unchanged": True,
                        "claim_a_unchanged": True,
                        "claim_b_unchanged": True,
                        "conflict_preserved_both_claims": True,
                    },
                    "laws": [
                        "LOCAL KNOWLEDGE != GLOBAL KNOWLEDGE",
                        "RESERVATION CLAIM != CONSENSUS",
                        "CONFLICT != SILENT OVERCOMMIT",
                        "RECONCILIATION != HISTORY REWRITE",
                        "RESOLUTION != CLAIM DELETION",
                        "LOCAL CLAIM != EXECUTION AUTHORITY",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
