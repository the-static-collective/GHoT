#!/usr/bin/env python3
"""Experiment 036 — Labor Writs."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lightwalker_economy import LightwalkerEconomyError, content_address
from lightwalker_heterogeneous_exchange import (
    make_exchange_offer,
    make_obligation,
    verify_exchange_offer,
)
from lightwalker_labor_writ import (
    LaborWritStore,
    delegate_labor_writ,
    issue_labor_writ,
    make_redemption_crossing,
    make_redemption_request,
    make_writ_crossing,
    verify_delegation,
    verify_labor_writ,
    verify_performance_receipt,
    verify_redemption_receipt,
    verify_redemption_request,
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
        issuer = IdentityKey.load_or_create(root / "issuer" / "body-p256.pem")
        holder_a = IdentityKey.load_or_create(root / "holder-a" / "body-p256.pem")
        holder_b = IdentityKey.load_or_create(root / "holder-b" / "body-p256.pem")
        holder_c = IdentityKey.load_or_create(root / "holder-c" / "body-p256.pem")

        writ = issue_labor_writ(
            issuer=issuer,
            holder_particular=holder_a.particular(),
            scope={
                "work_type": "documentation-pass",
                "target_ref": "ghot:experiment-035",
                "bounded_actions": [
                    "read-current-experiment",
                    "produce-one-documentation-pass",
                ],
                "acceptance_test": "issuer-local-review",
            },
            issued_at_cut=0,
            expires_after_cut=5,
            delegation_policy={"mode": "bounded", "max_delegations": 1},
            redemption_policy={
                "one_redemption": True,
                "performance_evidence_policy": "signed-completion-reference",
            },
        )
        assert verify_labor_writ(writ)
        frozen_writ = json.dumps(writ, sort_keys=True)

        crossing = make_writ_crossing(
            writ,
            signer=issuer,
            node_id="lightwalker-labor-writ-036-issuer",
        )
        assert verify_crossing(crossing)
        assert crossing["requested_effect"]["automatic_redemption_requested"] is False
        assert crossing["requested_effect"]["execution_authority_requested"] is False

        packet_root = root / "transport-source"
        packet_path = packet_root / "labor-writ" / "writ.v0.json"
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps({"writ": writ, "crossing": crossing}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        inbox = StateParcelInbox(root / "holder-receiver")
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
            note="036 admit Labor Writ information; do not redeem automatically",
        )
        assert admitted["kind"] == "ADMITTED"

        delegation = delegate_labor_writ(
            writ,
            signer=holder_a,
            to_holder_particular=holder_b.particular(),
            delegated_at_cut=1,
        )
        assert verify_delegation(writ, delegation)

        second_delegation_refused = refused(
            lambda: delegate_labor_writ(
                writ,
                signer=holder_b,
                to_holder_particular=holder_c.particular(),
                delegated_at_cut=2,
                prior_delegation=delegation,
            )
        )
        assert second_delegation_refused

        wrong_holder_redemption_refused = refused(
            lambda: make_redemption_request(
                writ,
                signer=holder_a,
                requested_at_cut=2,
                delegation=delegation,
            )
        )
        assert wrong_holder_redemption_refused

        request = make_redemption_request(
            writ,
            signer=holder_b,
            requested_at_cut=2,
            delegation=delegation,
        )
        assert verify_redemption_request(writ, request, delegation=delegation)

        redemption_crossing = make_redemption_crossing(
            writ,
            request,
            signer=holder_b,
            node_id="lightwalker-labor-writ-036-holder",
            delegation=delegation,
        )
        assert verify_crossing(redemption_crossing)
        assert redemption_crossing["requested_effect"]["automatic_execution_requested"] is False

        store = LaborWritStore(root / "issuer-state", issuer=issuer)
        redemption_receipt = store.redeem(
            writ,
            request,
            delegation=delegation,
            observed_cut=2,
        )
        assert verify_redemption_receipt(writ, redemption_receipt)
        assert redemption_receipt["writ_exhausted"] is True
        assert redemption_receipt["performance_completed"] is False

        exact_replay_refused = refused(
            lambda: store.redeem(
                writ,
                request,
                delegation=delegation,
                observed_cut=2,
            )
        )
        assert exact_replay_refused

        second_request = make_redemption_request(
            writ,
            signer=holder_b,
            requested_at_cut=3,
            delegation=delegation,
        )
        distinct_second_redemption_refused = refused(
            lambda: store.redeem(
                writ,
                second_request,
                delegation=delegation,
                observed_cut=3,
            )
        )
        assert distinct_second_redemption_refused

        performance_evidence = content_address(
            {
                "kind": "simulation.documentation-pass",
                "writ_id": writ["writ_id"],
                "target_ref": "ghot:experiment-035",
                "result": "one bounded documentation pass completed",
            }
        )
        performance = store.complete(
            writ,
            redemption_receipt,
            evidence_ref=performance_evidence,
            outcome="FULFILLED",
        )
        assert verify_performance_receipt(writ, redemption_receipt, performance)

        second_completion_refused = refused(
            lambda: store.complete(
                writ,
                redemption_receipt,
                evidence_ref=performance_evidence,
                outcome="FULFILLED",
            )
        )
        assert second_completion_refused

        expired_writ = issue_labor_writ(
            issuer=issuer,
            holder_particular=holder_a.particular(),
            scope={
                "work_type": "repair-pass",
                "target_ref": "ghot:fixture",
                "bounded_actions": ["one-repair-pass"],
                "acceptance_test": "issuer-local-review",
            },
            issued_at_cut=0,
            expires_after_cut=1,
            delegation_policy={"mode": "nondelegable", "max_delegations": 0},
            redemption_policy={
                "one_redemption": True,
                "performance_evidence_policy": "signed-completion-reference",
            },
        )
        expired_redemption_refused = refused(
            lambda: make_redemption_request(
                expired_writ,
                signer=holder_a,
                requested_at_cut=2,
            )
        )
        assert expired_redemption_refused

        hosting = make_obligation(
            obligation_type="hosting-service",
            resource_ref="host:bounded-bundle",
            terms={
                "availability_window": "declared-72h-window",
                "integrity_check": "sha256",
            },
            evidence_policy="uptime-log-plus-integrity-receipt",
        )
        writ_obligation = make_obligation(
            obligation_type="future-labor-writ",
            resource_ref="labor-writ:" + writ["writ_id"],
            terms={
                "writ_id": writ["writ_id"],
                "scope_digest": writ["scope_digest"],
                "expires_after_cut": writ["expires_after_cut"],
                "delegation_mode": writ["delegation_policy"]["mode"],
            },
            evidence_policy="labor-writ-performance-receipt",
        )
        exchange_offer = make_exchange_offer(
            offeror_particular=holder_a.particular(),
            offeror_obligation=hosting,
            acceptor_obligation=writ_obligation,
            orientation_refs=[],
            valid_through_cut=4,
        )
        assert verify_exchange_offer(exchange_offer)

        assert json.dumps(writ, sort_keys=True) == frozen_writ
        assert "price" not in writ
        assert "currency" not in writ
        assert "balance" not in writ

        print(
            json.dumps(
                {
                    "simulation_passed": True,
                    "writ": {
                        "writ_id": writ["writ_id"],
                        "expiry_cut": writ["expires_after_cut"],
                        "scope_digest": writ["scope_digest"],
                        "immutable_after_lifecycle": True,
                    },
                    "portability": {
                        "crossing_verified": True,
                        "receiver_first_disposition": held["kind"],
                        "receiver_local_disposition": admitted["kind"],
                        "automatic_redemption": False,
                    },
                    "delegation": {
                        "valid_first_delegation": True,
                        "second_delegation_refused": second_delegation_refused,
                        "wrong_holder_redemption_refused": wrong_holder_redemption_refused,
                    },
                    "redemption": {
                        "status": redemption_receipt["status"],
                        "writ_exhausted": redemption_receipt["writ_exhausted"],
                        "performance_completed_at_redemption": False,
                        "exact_replay_refused": exact_replay_refused,
                        "distinct_second_redemption_refused": distinct_second_redemption_refused,
                        "expired_redemption_refused": expired_redemption_refused,
                    },
                    "performance": {
                        "outcome": performance["outcome"],
                        "receipt_verified": True,
                        "second_completion_refused": second_completion_refused,
                    },
                    "heterogeneous_exchange": {
                        "labor_writ_can_be_typed_obligation": True,
                        "offer_id": exchange_offer["offer_id"],
                        "currency_required": False,
                    },
                    "laws": [
                        "WRIT != MONEY",
                        "WRIT != PERFORMANCE",
                        "PORTABILITY != AUTHORITY",
                        "DELEGATION != REWRITING",
                        "REDEMPTION != PERFORMANCE",
                        "ONE WRIT -> AT MOST ONE REDEMPTION",
                        "EXHAUSTION SURVIVES PERFORMANCE FAILURE OR SUCCESS",
                    ],
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
