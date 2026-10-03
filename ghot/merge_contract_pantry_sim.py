#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 020."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from merge_contract_pantry import (
    MergeContractPantry,
    derive_selection_id,
)
from relatte_identity import IdentityKey
from state_merge import (
    MERGE_CONTRACTS,
    StateMergeEngine,
    verify_merge_receipt,
)
from state_parcel import StateParcelExporter, StateParcelInbox


OFFERS_CONTRACT = "ghot.organ.offers->foreign-offer-catalog/v0"
PRESENCE_CONTRACT = "ghot.organ.presence->foreign-presence-catalog/v0"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source_state(
    *,
    offers: Any,
    boot_id: str,
) -> dict[str, Any]:
    return {
        "kind": "ghot.organ.state",
        "version": "1",
        "node_id": "node-source",
        "started_at": "2026-10-03T01:00:00Z",
        "updated_at": "2026-10-03T01:01:00Z",
        "cycle": 3,
        "body": {
            "node_id": "node-source",
            "offers": offers,
        },
        "field": {"bodies": []},
        "authorities": [],
        "work": {"status": "no-dispatch"},
        "services": {},
        "errors": [],
        "presence": {
            "boot_id": boot_id,
            "manifest_address": "sha256:" + "a" * 64,
            "startup_receipt_id": f"startup-{boot_id}",
        },
    }


def admit(
    source_root: Path,
    receiver_root: Path,
    *,
    selector: str,
    state_value: dict[str, Any],
) -> dict[str, Any]:
    write_json(source_root / "organ" / "state.v1.json", state_value)
    receiver = IdentityKey.load_or_create(
        receiver_root / "identity" / "body-p256.pem"
    )
    bundle = StateParcelExporter(source_root).export(
        "organ/state.v1.json",
        selector=selector,
        target_particular=receiver.particular(),
    )
    inbox = StateParcelInbox(receiver_root)
    held = inbox.receive(bundle)
    assert held["kind"] == "HELD"
    admitted = inbox.decide(
        bundle["parcel"]["parcel_id"],
        "ADMIT",
        note="020 pantry simulation admission",
    )
    assert admitted["kind"] == "ADMITTED"
    return bundle


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        source_root = base / "source"
        receiver_root = base / "receiver"

        pantry = MergeContractPantry(receiver_root)
        engine = StateMergeEngine(receiver_root)

        # A — pantry contains multiple installed bounded grammars.
        contracts = pantry.contracts()
        ids = [item["contract_id"] for item in contracts]
        assert ids == [OFFERS_CONTRACT, PRESENCE_CONTRACT]
        assert len({item["contract_address"] for item in contracts}) == 2
        assert all(item["authority_effect"] == "none" for item in contracts)
        assert all(item["freshness_effect"] == "none" for item in contracts)
        assert all(item["selection_required"] is True for item in contracts)

        # B — offers parcel matches exactly the offers grammar.
        offers_bundle = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            state_value=source_state(
                offers=[
                    {
                        "capability": "media.probe",
                        "available": True,
                        "power_class": "light",
                    }
                ],
                boot_id="boot-offers",
            ),
        )
        offers_id = offers_bundle["parcel"]["parcel_id"]
        offers_inspection = pantry.inspect(offers_id)
        assert offers_inspection["compatible_contract_ids"] == [OFFERS_CONTRACT]
        presence_row = next(
            row for row in offers_inspection["contracts"]
            if row["contract_id"] == PRESENCE_CONTRACT
        )
        assert "selector-mismatch" in presence_row["reasons"]
        assert "payload-type-mismatch" in presence_row["reasons"]

        wrong_selection_refused = False
        try:
            pantry.select(offers_id, PRESENCE_CONTRACT)
        except ValueError:
            wrong_selection_refused = True
        assert wrong_selection_refused

        offers_target = receiver_root / "knowledge" / "foreign-offers.v0.json"
        assert not offers_target.exists()
        assert engine.list_plans() == []

        selection = pantry.select(offers_id, OFFERS_CONTRACT)
        assert selection["selection_id"] == derive_selection_id(selection)
        assert selection["contract_id"] == OFFERS_CONTRACT
        assert not offers_target.exists()
        assert engine.list_plans() == []

        plan = pantry.propose(selection["selection_id"])
        assert plan["contract_id"] == OFFERS_CONTRACT
        assert not offers_target.exists()

        applied = engine.apply(plan["plan_id"], note="020 selected offers grammar")
        assert verify_merge_receipt(applied)
        assert offers_target.exists()

        catalog = json.loads(offers_target.read_text(encoding="utf-8"))
        assert catalog["kind"] == "ghot.foreign-offer-catalog"
        assert catalog["entries"][0]["capability"] == "media.probe"

        after_merge = pantry.inspect(offers_id)
        offers_after_row = next(
            row for row in after_merge["contracts"]
            if row["contract_id"] == OFFERS_CONTRACT
        )
        assert offers_after_row["compatible"] is False
        assert "already-merged" in offers_after_row["reasons"]

        # C — presence parcel discovers the second grammar, and its result stays
        # historical/observational rather than becoming liveness.
        presence_bundle = admit(
            source_root,
            receiver_root,
            selector="/presence",
            state_value=source_state(
                offers=[],
                boot_id="boot-presence",
            ),
        )
        presence_id = presence_bundle["parcel"]["parcel_id"]
        presence_inspection = pantry.inspect(presence_id)
        assert presence_inspection["compatible_contract_ids"] == [PRESENCE_CONTRACT]

        presence_target = receiver_root / "knowledge" / "foreign-presence.v0.json"
        presence_selection = pantry.select(presence_id, PRESENCE_CONTRACT)
        assert not presence_target.exists()
        presence_plan = pantry.propose(presence_selection["selection_id"])
        assert not presence_target.exists()
        presence_receipt = engine.apply(
            presence_plan["plan_id"],
            note="020 selected presence grammar",
        )
        assert verify_merge_receipt(presence_receipt)

        presence_catalog = json.loads(
            presence_target.read_text(encoding="utf-8")
        )
        assert presence_catalog["kind"] == "ghot.foreign-presence-catalog"
        assert presence_catalog["entries"][0]["boot_id"] == "boot-presence"
        assert "liveness" not in presence_catalog
        assert "trust" not in presence_catalog
        assert "authority" not in presence_catalog

        # D — incompatible selector gets explanation, not a generic fallback.
        work_bundle = admit(
            source_root,
            receiver_root,
            selector="/work",
            state_value=source_state(
                offers=[],
                boot_id="boot-work",
            ),
        )
        work_id = work_bundle["parcel"]["parcel_id"]
        work_inspection = pantry.inspect(work_id)
        assert work_inspection["compatible_contract_ids"] == []
        generic_fallback_absent = False
        try:
            pantry.select(work_id, OFFERS_CONTRACT)
        except ValueError:
            generic_fallback_absent = True
        assert generic_fallback_absent

        # E — selection binds admitted materialization. Change that local
        # materialization after SELECT and PROPOSE must refuse.
        drift_bundle = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            state_value=source_state(
                offers=[
                    {
                        "capability": "runtime.git.version",
                        "available": True,
                        "power_class": "light",
                    }
                ],
                boot_id="boot-drift",
            ),
        )
        drift_id = drift_bundle["parcel"]["parcel_id"]
        drift_selection = pantry.select(drift_id, OFFERS_CONTRACT)
        safe = drift_id.replace(":", "_").replace("/", "_")
        admitted_path = (
            receiver_root / "state-parcels" / "admitted" / f"{safe}.json"
        )
        admitted = json.loads(admitted_path.read_text(encoding="utf-8"))
        admitted["note"] = "changed after pantry selection"
        write_json(admitted_path, admitted)

        admitted_drift_refused = False
        try:
            pantry.propose(drift_selection["selection_id"])
        except ValueError:
            admitted_drift_refused = True
        assert admitted_drift_refused

        # F — selection also binds the installed contract descriptor itself.
        contract_bundle = admit(
            source_root,
            receiver_root,
            selector="/presence",
            state_value=source_state(
                offers=[],
                boot_id="boot-contract-drift",
            ),
        )
        contract_id = contract_bundle["parcel"]["parcel_id"]
        contract_selection = pantry.select(contract_id, PRESENCE_CONTRACT)

        original_title = MERGE_CONTRACTS[PRESENCE_CONTRACT]["title"]
        MERGE_CONTRACTS[PRESENCE_CONTRACT]["title"] = "Changed after selection"
        contract_drift_refused = False
        try:
            pantry.propose(contract_selection["selection_id"])
        except ValueError:
            contract_drift_refused = True
        finally:
            MERGE_CONTRACTS[PRESENCE_CONTRACT]["title"] = original_title
        assert contract_drift_refused

        # G — payload shape participates in the same compatibility primitive
        # used by the lower-level engine.
        shape_bundle = admit(
            source_root,
            receiver_root,
            selector="/body/offers",
            state_value=source_state(
                offers={"not": "an array"},
                boot_id="boot-shape",
            ),
        )
        shape_id = shape_bundle["parcel"]["parcel_id"]
        shape_inspection = pantry.inspect(shape_id)
        assert shape_inspection["compatible_contract_ids"] == []
        assert engine.eligible_contracts(shape_id) == []
        offers_shape_row = next(
            row for row in shape_inspection["contracts"]
            if row["contract_id"] == OFFERS_CONTRACT
        )
        assert "payload-type-mismatch" in offers_shape_row["reasons"]

        selections = pantry.selections()
        assert len(selections) >= 4

        passed = all([
            wrong_selection_refused,
            generic_fallback_absent,
            admitted_drift_refused,
            contract_drift_refused,
            verify_merge_receipt(applied),
            verify_merge_receipt(presence_receipt),
            engine.eligible_contracts(shape_id) == [],
        ])

        print(json.dumps({
            "simulation_passed": passed,
            "pantry": {
                "installed_contract_ids": ids,
                "contract_addresses_unique": (
                    len({item["contract_address"] for item in contracts}) == 2
                ),
            },
            "offers": {
                "compatible": offers_inspection["compatible_contract_ids"],
                "wrong_selection_refused": wrong_selection_refused,
                "selection_created_no_plan": True,
                "apply_receipt_verified": verify_merge_receipt(applied),
                "already_merged_removed_from_compatibility": (
                    "already-merged" in offers_after_row["reasons"]
                ),
            },
            "presence": {
                "compatible": presence_inspection["compatible_contract_ids"],
                "apply_receipt_verified": verify_merge_receipt(presence_receipt),
                "historical_not_liveness": "liveness" not in presence_catalog,
            },
            "no_fallback": {
                "work_compatible_contracts": work_inspection["compatible_contract_ids"],
                "selection_refused": generic_fallback_absent,
            },
            "selection_revalidation": {
                "admitted_drift_refused": admitted_drift_refused,
                "contract_descriptor_drift_refused": contract_drift_refused,
            },
            "shared_compatibility": {
                "shape_pantry": shape_inspection["compatible_contract_ids"],
                "shape_engine": engine.eligible_contracts(shape_id),
            },
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
