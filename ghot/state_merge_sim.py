#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 019."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from relatte_identity import IdentityKey
from state_merge import (
    MERGE_CONTRACTS,
    StateMergeEngine,
    merge_foreign_offers,
    semantic_address,
    verify_merge_receipt,
)
from state_parcel import (
    StateParcelExporter,
    StateParcelInbox,
    verify_bundle,
)


CONTRACT = "ghot.organ.offers->foreign-offer-catalog/v0"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def organ_state(node: str, offers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind": "ghot.organ.state",
        "version": "1",
        "node_id": node,
        "started_at": "2026-10-03T00:00:00Z",
        "updated_at": "2026-10-03T00:01:00Z",
        "cycle": 1,
        "body": {
            "node_id": node,
            "offers": offers,
        },
        "field": {"bodies": []},
        "authorities": [],
        "work": {"status": "no-dispatch"},
        "services": {},
        "errors": [],
        "presence": {
            "boot_id": "boot-source",
            "manifest_address": "sha256:" + "a" * 64,
            "startup_receipt_id": "startup-source",
        },
    }


def admit(
    source_root: Path,
    receiver_root: Path,
    *,
    selector: str,
    offers: list[dict[str, Any]],
) -> dict[str, Any]:
    source_state = organ_state("node-source", offers)
    write_json(source_root / "organ" / "state.v1.json", source_state)

    receiver_signer = IdentityKey.load_or_create(
        receiver_root / "identity" / "body-p256.pem"
    )
    bundle = StateParcelExporter(source_root).export(
        "organ/state.v1.json",
        selector=selector,
        target_particular=receiver_signer.particular(),
    )
    assert verify_bundle(bundle)

    inbox = StateParcelInbox(receiver_root)
    held = inbox.receive(bundle)
    assert held["kind"] == "HELD"
    admitted = inbox.decide(
        bundle["parcel"]["parcel_id"],
        "ADMIT",
        note="019 merge simulation admission",
    )
    assert admitted["kind"] == "ADMITTED"
    return bundle


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        source_root = base / "source"
        receiver_root = base / "receiver"

        # A — first real merge from an ADMITTED /body/offers parcel.
        first = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            offers=[
                {
                    "capability": "media.probe",
                    "available": True,
                    "power_class": "light",
                },
                {
                    "capability": "llm.infer.local",
                    "available": False,
                    "power_class": "heavy",
                },
            ],
        )
        first_id = first["parcel"]["parcel_id"]

        engine = StateMergeEngine(receiver_root)
        assert engine.eligible_contracts(first_id) == [CONTRACT]
        plan1 = engine.propose(first_id)
        assert plan1["contract_id"] == CONTRACT
        assert plan1["local_state_existed"] is False
        assert plan1["local_before_address"] != plan1["proposed_after_address"]

        receipt1 = engine.apply(plan1["plan_id"], note="owner approved first merge")
        assert verify_merge_receipt(receipt1)
        assert receipt1["disposition"] == "APPLY"
        assert receipt1["backup_path"] is None

        catalog_path = receiver_root / "knowledge" / "foreign-offers.v0.json"
        catalog1 = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert catalog1["kind"] == "ghot.foreign-offer-catalog"
        assert catalog1["version"] == "0"
        assert catalog1["merged_parcels"] == [first_id]
        assert [item["capability"] for item in catalog1["entries"]] == [
            "llm.infer.local",
            "media.probe",
        ]
        assert all(
            item["source_particular"] == first["parcel"]["source"]["particular"]
            for item in catalog1["entries"]
        )

        # Applying the same plan is idempotent, and proposing the already-merged
        # parcel is refused.
        assert engine.apply(plan1["plan_id"])["receipt_id"] == receipt1["receipt_id"]
        duplicate_proposal_refused = False
        try:
            engine.propose(first_id)
        except ValueError:
            duplicate_proposal_refused = True
        assert duplicate_proposal_refused

        # B — second admitted snapshot updates the same source/capability keys
        # and must preserve an exact backup of the existing local catalog.
        catalog1_bytes = catalog_path.read_bytes()
        second = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            offers=[
                {
                    "capability": "media.probe",
                    "available": False,
                    "power_class": "light",
                },
                {
                    "capability": "speech.transcribe.local",
                    "available": True,
                    "power_class": "heavy",
                },
            ],
        )
        second_id = second["parcel"]["parcel_id"]
        plan2 = engine.propose(second_id)
        receipt2 = engine.apply(plan2["plan_id"], note="update remembered offers")
        assert verify_merge_receipt(receipt2)
        assert receipt2["backup_path"] is not None
        backup2 = Path(receipt2["backup_path"])
        assert backup2.read_bytes() == catalog1_bytes

        catalog2 = json.loads(catalog_path.read_text(encoding="utf-8"))
        by_cap = {item["capability"]: item for item in catalog2["entries"]}
        assert by_cap["media.probe"]["available"] is False
        assert by_cap["llm.infer.local"]["available"] is False
        assert by_cap["speech.transcribe.local"]["available"] is True
        assert set(catalog2["merged_parcels"]) == {first_id, second_id}

        # C — stale local-state plan is refused.
        third = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            offers=[
                {
                    "capability": "runtime.git.version",
                    "available": True,
                    "power_class": "light",
                }
            ],
        )
        plan3 = engine.propose(third["parcel"]["parcel_id"])
        raced = json.loads(catalog_path.read_text(encoding="utf-8"))
        raced["entries"].append({
            "source_particular": "local-race",
            "source_node_id": "local-race",
            "capability": "race.marker",
            "available": True,
            "power_class": None,
            "parcel_id": "local-race",
            "payload_address": "sha256:" + "b" * 64,
        })
        raced["entries"] = sorted(
            raced["entries"],
            key=lambda item: (
                item["source_particular"],
                item["capability"],
            ),
        )
        write_json(catalog_path, raced)

        stale_refused = False
        try:
            engine.apply(plan3["plan_id"])
        except ValueError:
            stale_refused = True
        assert stale_refused
        assert engine.receipts_for_plan(plan3["plan_id"]) == []

        # Restore pre-race catalog for subsequent trials.
        write_json(catalog_path, catalog2)

        # D — explicit REJECT is signed and terminal.
        fourth = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            offers=[
                {
                    "capability": "image.inspect.local",
                    "available": True,
                    "power_class": "heavy",
                }
            ],
        )
        plan4 = engine.propose(fourth["parcel"]["parcel_id"])
        rejected = engine.reject(
            plan4["plan_id"],
            note="owner does not want this snapshot merged",
        )
        assert verify_merge_receipt(rejected)
        assert rejected["disposition"] == "REJECT"
        assert rejected["local_after_address"] == rejected["local_before_address"]
        apply_after_reject_refused = False
        try:
            engine.apply(plan4["plan_id"])
        except ValueError:
            apply_after_reject_refused = True
        assert apply_after_reject_refused
        assert json.loads(catalog_path.read_text(encoding="utf-8")) == catalog2

        # E — HOLD is not enough. Non-admitted parcels are merge-ineligible.
        hold_bundle = StateParcelExporter(source_root).export(
            "organ/state.v1.json",
            selector="/body/offers",
            target_particular=IdentityKey.load_or_create(
                receiver_root / "identity" / "body-p256.pem"
            ).particular(),
        )
        StateParcelInbox(receiver_root).receive(hold_bundle)
        hold_refused = False
        try:
            engine.eligible_contracts(hold_bundle["parcel"]["parcel_id"])
        except ValueError:
            hold_refused = True
        assert hold_refused

        # F — ADMITTED but schema/selector-incompatible parcel gets no contract.
        incompatible = admit(
            source_root,
            receiver_root,
            selector="/work",
            offers=[
                {
                    "capability": "system.echo",
                    "available": True,
                    "power_class": "essential",
                }
            ],
        )
        incompatible_id = incompatible["parcel"]["parcel_id"]
        assert engine.eligible_contracts(incompatible_id) == []
        incompatible_refused = False
        try:
            engine.propose(incompatible_id)
        except ValueError:
            incompatible_refused = True
        assert incompatible_refused

        # G — interrupted write: exact proposed state exists but merge receipt
        # is absent. APPLY reconciles the receipt without rewriting the target.
        fifth = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            offers=[
                {
                    "capability": "runtime.python.version",
                    "available": True,
                    "power_class": "light",
                }
            ],
        )
        fifth_id = fifth["parcel"]["parcel_id"]
        plan5 = engine.propose(fifth_id)
        context5 = engine._admitted_context(fifth_id)
        spec = MERGE_CONTRACTS[CONTRACT]
        current5 = json.loads(catalog_path.read_text(encoding="utf-8"))
        proposed5 = merge_foreign_offers(current5, context5)
        assert semantic_address(proposed5) == plan5["proposed_after_address"]
        write_json(catalog_path, proposed5)
        target_before_reconcile = catalog_path.read_bytes()

        reconciled = engine.apply(
            plan5["plan_id"],
            note="recover receipt after simulated crash",
        )
        assert verify_merge_receipt(reconciled)
        assert reconciled["disposition"] == "APPLY"
        assert catalog_path.read_bytes() == target_before_reconcile

        # H — tampering with admitted materialization after planning invalidates
        # the merge proposal before local state is touched.
        sixth = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            offers=[
                {
                    "capability": "runtime.ffmpeg.version",
                    "available": True,
                    "power_class": "light",
                }
            ],
        )
        sixth_id = sixth["parcel"]["parcel_id"]
        plan6 = engine.propose(sixth_id)
        safe = sixth_id.replace(":", "_").replace("/", "_")
        admitted_path = (
            receiver_root / "state-parcels" / "admitted" / f"{safe}.json"
        )
        admitted_value = json.loads(admitted_path.read_text(encoding="utf-8"))
        admitted_value["note"] = "tampered after plan"
        write_json(admitted_path, admitted_value)
        admitted_tamper_refused = False
        before_tamper_apply = catalog_path.read_bytes()
        try:
            engine.apply(plan6["plan_id"])
        except ValueError:
            admitted_tamper_refused = True
        assert admitted_tamper_refused
        assert catalog_path.read_bytes() == before_tamper_apply

        all_receipts = engine.receipts()
        assert all(item["verified"] is True for item in all_receipts)

        passed = all([
            duplicate_proposal_refused,
            stale_refused,
            apply_after_reject_refused,
            hold_refused,
            incompatible_refused,
            admitted_tamper_refused,
            verify_merge_receipt(receipt1),
            verify_merge_receipt(receipt2),
            verify_merge_receipt(rejected),
            verify_merge_receipt(reconciled),
        ])

        print(json.dumps({
            "simulation_passed": passed,
            "first_merge": {
                "contract": plan1["contract_id"],
                "receipt_verified": verify_merge_receipt(receipt1),
                "catalog_entries": len(catalog1["entries"]),
                "duplicate_proposal_refused": duplicate_proposal_refused,
            },
            "second_merge": {
                "backup_exact_bytes": backup2.read_bytes() == catalog1_bytes,
                "updated_media_probe": by_cap["media.probe"]["available"] is False,
                "preserved_prior_capability": "llm.infer.local" in by_cap,
            },
            "race": {
                "stale_local_plan_refused": stale_refused,
            },
            "decision": {
                "reject_receipt_verified": verify_merge_receipt(rejected),
                "apply_after_reject_refused": apply_after_reject_refused,
            },
            "eligibility": {
                "hold_is_not_mergeable": hold_refused,
                "wrong_selector_has_no_contract": incompatible_refused,
            },
            "crash_recovery": {
                "receipt_reconciled": verify_merge_receipt(reconciled),
                "target_not_rewritten": catalog_path.read_bytes() != b"",
            },
            "tamper": {
                "admitted_materialization_change_refused": admitted_tamper_refused,
            },
            "receipts_verified": all(
                item["verified"] is True for item in all_receipts
            ),
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
