#!/usr/bin/env python3
"""Experiment 037 — Guild Treasury as heterogeneous resource inventory."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_guild_treasury import (
    collapse_to_universal_total,
    make_resource_view,
    make_snapshot_crossing,
    make_treasury_entry,
    make_treasury_snapshot,
    next_treasury_snapshot,
    verify_treasury_snapshot,
)
from lightwalker_heterogeneous_exchange import (
    accept_exchange_offer,
    make_exchange_offer,
    make_obligation,
    settle_exchange,
    sign_obligation_performance,
    verify_exchange_settlement,
)
from lightwalker_labor_writ import (
    LaborWritStore,
    issue_labor_writ,
    make_redemption_request,
    verify_performance_receipt,
)
from relatte_identity import IdentityKey, verify_crossing
from state_parcel import StateParcelExporter, StateParcelInbox


def refused(fn) -> bool:
    try:
        fn()
    except LightwalkerEconomyError:
        return True
    return False


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        guild = IdentityKey.load_or_create(root / "guild" / "body-p256.pem")
        worker = IdentityKey.load_or_create(root / "worker" / "body-p256.pem")
        partner = IdentityKey.load_or_create(root / "partner" / "body-p256.pem")
        outsider = IdentityKey.load_or_create(root / "outsider" / "body-p256.pem")

        guild_id = "guild:lantern-forge"

        incoming_writ = issue_labor_writ(
            issuer=worker,
            holder_particular=guild.particular(),
            scope={
                "work_type": "documentation-pass",
                "target_ref": "ghot:experiment-037",
                "bounded_actions": ["produce-one-resource-map"],
                "acceptance_test": "guild-local-review",
            },
            issued_at_cut=0,
            expires_after_cut=6,
            delegation_policy={"mode": "nondelegable", "max_delegations": 0},
            redemption_policy={
                "one_redemption": True,
                "performance_evidence_policy": "signed-completion-reference",
            },
        )

        outgoing_writ = issue_labor_writ(
            issuer=guild,
            holder_particular=partner.particular(),
            scope={
                "work_type": "integration-pass",
                "target_ref": "ghot:guild-treasury",
                "bounded_actions": ["one-integration-pass"],
                "acceptance_test": "guild-local-review",
            },
            issued_at_cut=0,
            expires_after_cut=8,
            delegation_policy={"mode": "bounded", "max_delegations": 1},
            redemption_policy={
                "one_redemption": True,
                "performance_evidence_policy": "signed-completion-reference",
            },
        )

        # Build one genuine heterogeneous settlement receipt from 035 grammar.
        guild_hosting = make_obligation(
            obligation_type="hosting-service",
            resource_ref="host:guild-bundle",
            terms={
                "availability_window": "declared-72h-window",
                "integrity_check": "sha256",
            },
            evidence_policy="uptime-log-plus-integrity-receipt",
        )
        partner_right = make_obligation(
            obligation_type="artifact-access",
            resource_ref="artifact:right-demo-001",
            terms={
                "scope": "read-and-derive",
                "revocation": "none-for-frozen-specimen",
            },
            evidence_policy="signed-license-grant-reference",
        )
        offer = make_exchange_offer(
            offeror_particular=guild.particular(),
            offeror_obligation=guild_hosting,
            acceptor_obligation=partner_right,
            orientation_refs=[],
            valid_through_cut=5,
        )
        acceptance = accept_exchange_offer(
            offer,
            acceptor_particular=partner.particular(),
            accepted_at_cut=1,
        )
        guild_perf = sign_obligation_performance(
            offer,
            acceptance,
            role="OFFEROR",
            signer=guild,
            evidence_ref=content_address(
                {"kind": "hosting-proof", "offer_id": offer["offer_id"]}
            ),
        )
        partner_perf = sign_obligation_performance(
            offer,
            acceptance,
            role="ACCEPTOR",
            signer=partner,
            evidence_ref=content_address(
                {"kind": "artifact-grant-proof", "offer_id": offer["offer_id"]}
            ),
        )
        settlement = settle_exchange(
            offer,
            acceptance,
            [guild_perf, partner_perf],
        )
        assert verify_exchange_settlement(
            offer,
            acceptance,
            [guild_perf, partner_perf],
            settlement,
        )

        entries = [
            make_treasury_entry(
                category="capability",
                position="available",
                subject_ref="capability:compute-pool-a",
                source_ref="ghot-node:guild-compute-a",
                evidence_refs=["receipt:compute-probe-001"],
                native_measure={"unit": "compute-minute", "quantity": 120},
                metadata={"capability": "render.verified"},
            ),
            make_treasury_entry(
                category="capability",
                position="available",
                subject_ref="capability:storage-pool-a",
                source_ref="ghot-node:guild-storage-a",
                evidence_refs=["receipt:storage-integrity-001"],
                native_measure={"unit": "gb-hour", "quantity": 720},
                metadata={"integrity": "sha256"},
            ),
            make_treasury_entry(
                category="claim",
                position="available",
                subject_ref="labor-writ:" + incoming_writ["writ_id"],
                source_ref=incoming_writ["writ_id"],
                evidence_refs=[incoming_writ["writ_id"]],
                metadata={
                    "scope_digest": incoming_writ["scope_digest"],
                    "expires_after_cut": incoming_writ["expires_after_cut"],
                    "issuer_particular": incoming_writ["issuer_particular"],
                },
            ),
            make_treasury_entry(
                category="obligation",
                position="outstanding",
                subject_ref="labor-writ:" + outgoing_writ["writ_id"],
                source_ref=outgoing_writ["writ_id"],
                evidence_refs=[outgoing_writ["writ_id"]],
                metadata={
                    "scope_digest": outgoing_writ["scope_digest"],
                    "expires_after_cut": outgoing_writ["expires_after_cut"],
                    "holder_particular": outgoing_writ["initial_holder_particular"],
                },
            ),
            make_treasury_entry(
                category="right",
                position="available",
                subject_ref="artifact:right-demo-001",
                source_ref=settlement["settlement_id"],
                evidence_refs=[partner_perf["attestation_id"]],
                metadata={"scope": "read-and-derive"},
            ),
            make_treasury_entry(
                category="receipt",
                position="evidence",
                subject_ref="settlement:" + settlement["settlement_id"],
                source_ref=settlement["settlement_id"],
                evidence_refs=[
                    guild_perf["attestation_id"],
                    partner_perf["attestation_id"],
                ],
                metadata={"status": settlement["status"]},
            ),
            make_treasury_entry(
                category="credit",
                position="available",
                subject_ref="realm-credit:lantern-demo",
                source_ref="realm:lantern",
                evidence_refs=["projection:demo-lumen-001"],
                native_measure={"unit": "lumen", "quantity": 13},
                metadata={"authority": "realm-local"},
            ),
            make_treasury_entry(
                category="money-reference",
                position="external-reference",
                subject_ref="external-money-reference:demo-usd",
                source_ref="external-ledger:demo-only",
                evidence_refs=["statement-ref:demo-001"],
                native_measure={"unit": "USD", "quantity": 250},
                metadata={
                    "reference_only": True,
                    "custody_inferred": False,
                },
            ),
            make_treasury_entry(
                category="obligation",
                position="encumbered",
                subject_ref="storage-commitment:client-a",
                source_ref="agreement:storage-commitment-a",
                evidence_refs=["receipt:commitment-a"],
                native_measure={"unit": "gb-hour", "quantity": 96},
                metadata={"release_condition": "declared-window-complete"},
            ),
        ]

        snapshot0 = make_treasury_snapshot(
            guild_id=guild_id,
            steward=guild,
            entries=entries,
            sequence=0,
        )
        assert verify_treasury_snapshot(snapshot0)
        frozen_snapshot0 = json.dumps(snapshot0, sort_keys=True)

        view0 = make_resource_view(snapshot0)
        assert view0["universal_total"] is None
        assert view0["collapse_status"] == "REFUSED_BY_PROTOCOL"
        units0 = {item["unit"] for item in view0["native_buckets"]}
        assert units0 == {"USD", "compute-minute", "gb-hour", "lumen"}

        collapse_refused = refused(
            lambda: collapse_to_universal_total(snapshot0)
        )
        assert collapse_refused

        duplicate_entry_refused = refused(
            lambda: make_treasury_snapshot(
                guild_id=guild_id,
                steward=guild,
                entries=entries + [entries[0]],
                sequence=0,
            )
        )
        assert duplicate_entry_refused

        outsider_transition_refused = refused(
            lambda: next_treasury_snapshot(
                snapshot0,
                steward=outsider,
                add_entries=[],
                retire_entry_ids=[],
            )
        )
        assert outsider_transition_refused

        unknown_retirement_refused = refused(
            lambda: next_treasury_snapshot(
                snapshot0,
                steward=guild,
                retire_entry_ids=["sha256:" + "0" * 64],
            )
        )
        assert unknown_retirement_refused

        # Redeem and fulfill the incoming claim. The old snapshot remains frozen;
        # the new one retires only the live claim and adds evidence.
        redemption_request = make_redemption_request(
            incoming_writ,
            signer=guild,
            requested_at_cut=2,
        )
        worker_store = LaborWritStore(root / "worker-state", issuer=worker)
        redemption = worker_store.redeem(
            incoming_writ,
            redemption_request,
            observed_cut=2,
        )
        performance = worker_store.complete(
            incoming_writ,
            redemption,
            evidence_ref=content_address(
                {
                    "kind": "resource-map-output",
                    "guild_id": guild_id,
                    "writ_id": incoming_writ["writ_id"],
                }
            ),
            outcome="FULFILLED",
        )
        assert verify_performance_receipt(
            incoming_writ,
            redemption,
            performance,
        )

        live_claim_entry = next(
            item
            for item in snapshot0["entries"]
            if item["subject_ref"] == "labor-writ:" + incoming_writ["writ_id"]
        )
        performance_entry = make_treasury_entry(
            category="receipt",
            position="evidence",
            subject_ref="labor-writ-performance:" + performance["performance_receipt_id"],
            source_ref=performance["performance_receipt_id"],
            evidence_refs=[
                redemption["redemption_receipt_id"],
                performance["performance_receipt_id"],
            ],
            metadata={
                "writ_id": incoming_writ["writ_id"],
                "outcome": performance["outcome"],
                "claim_retired": True,
            },
        )

        snapshot1 = next_treasury_snapshot(
            snapshot0,
            steward=guild,
            add_entries=[performance_entry],
            retire_entry_ids=[live_claim_entry["entry_id"]],
        )
        assert verify_treasury_snapshot(snapshot1)
        assert snapshot1["prior_snapshot_id"] == snapshot0["snapshot_id"]
        assert snapshot1["sequence"] == 1
        assert json.dumps(snapshot0, sort_keys=True) == frozen_snapshot0

        view1 = make_resource_view(snapshot1)
        assert view1["universal_total"] is None
        assert live_claim_entry["entry_id"] not in {
            item["entry_id"] for item in snapshot1["entries"]
        }
        assert performance_entry["entry_id"] in {
            item["entry_id"] for item in snapshot1["entries"]
        }

        crossing = make_snapshot_crossing(
            snapshot1,
            signer=guild,
            node_id="lightwalker-guild-treasury-037",
        )
        assert verify_crossing(crossing)
        effect = crossing["requested_effect"]
        assert effect["automatic_balance_mutation_requested"] is False
        assert effect["automatic_ownership_inference_requested"] is False
        assert effect["universal_valuation_requested"] is False

        packet_root = root / "treasury-source"
        packet_path = packet_root / "guild" / "treasury-037.v0.json"
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps(
                {
                    "snapshot": snapshot1,
                    "resource_view": view1,
                    "crossing": crossing,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        inbox = StateParcelInbox(root / "treasury-receiver")
        bundle = StateParcelExporter(packet_root).export(
            str(packet_path.relative_to(packet_root)),
            selector="$",
            target_particular=inbox.signer.particular(),
        )
        held = inbox.receive(bundle)
        assert held["kind"] == "HELD"
        assert held["semantic_effect"] == "none"
        admitted = inbox.decide(
            bundle["parcel"]["parcel_id"],
            "ADMIT",
            note=(
                "037 admit Guild Treasury snapshot as inventory evidence; "
                "do not infer custody, ownership, balance mutation, or valuation"
            ),
        )
        assert admitted["kind"] == "ADMITTED"

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "snapshot0": {
                        "snapshot_id": snapshot0["snapshot_id"],
                        "entry_count": len(snapshot0["entries"]),
                        "universal_total": view0["universal_total"],
                        "native_units": sorted(units0),
                    },
                    "transition": {
                        "prior_snapshot_preserved": True,
                        "incoming_claim_retired": True,
                        "performance_evidence_added": True,
                        "unrelated_positions_preserved": True,
                    },
                    "snapshot1": {
                        "snapshot_id": snapshot1["snapshot_id"],
                        "prior_snapshot_id": snapshot1["prior_snapshot_id"],
                        "sequence": snapshot1["sequence"],
                        "entry_count": len(snapshot1["entries"]),
                        "universal_total": view1["universal_total"],
                    },
                    "hostile_controls": {
                        "universal_collapse_refused": collapse_refused,
                        "duplicate_entry_refused": duplicate_entry_refused,
                        "outsider_transition_refused": outsider_transition_refused,
                        "unknown_retirement_refused": unknown_retirement_refused,
                    },
                    "crossing": {
                        "verified": True,
                        "held_first": held["kind"],
                        "owner_disposition": admitted["kind"],
                        "balance_mutation_requested": False,
                        "ownership_inference_requested": False,
                        "universal_valuation_requested": False,
                    },
                    "laws": [
                        "TREASURY != BALANCE",
                        "INVENTORY != OWNERSHIP",
                        "REFERENCE != CUSTODY",
                        "NATIVE UNIT != UNIVERSAL UNIT",
                        "RESOURCE VIEW != PRICE",
                        "SNAPSHOT != SETTLEMENT",
                        "WHAT CAN WE MOBILIZE? PRECEDES HOW RICH ARE WE?",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
