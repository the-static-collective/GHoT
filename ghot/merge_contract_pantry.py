#!/usr/bin/env python3
"""Discover and explicitly select local state merge contracts — Experiment 020.

The pantry separates:
  discovery -> compatibility -> selection -> proposal -> apply/reject

Contract discovery is descriptive only.
Selection is owner-local and persisted, but still does not mutate state.
A selected contract must be revalidated before a 019 merge proposal is created.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from reference_node import ROOT
from relatte_identity import identity_safe, jcs_bytes, timestamp_now
from state_merge import StateMergeEngine, merge_payload_type
from state_migration import semantic_address


INSPECTION_KIND = "ghot.merge-contract.inspection"
INSPECTION_VERSION = "0"
SELECTION_KIND = "ghot.merge-contract.selection"
SELECTION_VERSION = "0"
SELECTION_ID_DOMAIN = b"GHoT-MergeContractSelection-v0|"
PROPOSAL_LINK_KIND = "ghot.merge-contract.proposal-link"
PROPOSAL_LINK_VERSION = "0"
PROPOSAL_LINK_ID_DOMAIN = b"GHoT-MergeContractProposalLink-v0|"


def _safe_name(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def contract_descriptor(contract_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    return identity_safe({
        "kind": "ghot.merge-contract",
        "version": "0",
        "contract_id": contract_id,
        "title": spec.get("title"),
        "description": spec.get("description"),
        "category": spec.get("category"),
        "source": {
            "state_kind": spec.get("parcel_state_kind"),
            "state_version": spec.get("parcel_state_version"),
            "selector": spec.get("parcel_selector"),
            "payload_type": spec.get("payload_type"),
        },
        "target": {
            "relative_path": spec.get("local_rel"),
            "state_kind": spec.get("local_kind"),
            "state_version": spec.get("local_version"),
        },
        "authority_effect": spec.get("authority_effect", "none"),
        "freshness_effect": spec.get("freshness_effect", "none"),
        "selection_required": bool(spec.get("selection_required", True)),
        "origin": (
            {
                "kind": "plugin",
                "package_id": spec.get("plugin_package_id"),
                "package_version": spec.get("plugin_package_version"),
                "package_address": spec.get("plugin_package_address"),
                "operation_kind": spec.get("operation_kind"),
            }
            if spec.get("plugin_package_id")
            else {
                "kind": "builtin",
                "package_id": None,
                "package_version": None,
                "package_address": None,
                "operation_kind": "python-builtin",
            }
        ),
    })


def contract_address(contract_id: str, spec: dict[str, Any]) -> str:
    return semantic_address(contract_descriptor(contract_id, spec))


def _selection_body(selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": selection.get("kind"),
        "version": selection.get("version"),
        "parcel_id": selection.get("parcel_id"),
        "parcel_address": selection.get("parcel_address"),
        "payload_address": selection.get("payload_address"),
        "admitted_ref": selection.get("admitted_ref"),
        "contract_id": selection.get("contract_id"),
        "contract_address": selection.get("contract_address"),
        "selected_at": selection.get("selected_at"),
        "selection_source": selection.get("selection_source"),
    }


def derive_selection_id(selection: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        SELECTION_ID_DOMAIN + jcs_bytes(identity_safe(_selection_body(selection)))
    ).hexdigest()
    return "ghot-merge-contract-selection-v0:" + digest


def _proposal_link_body(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": link.get("kind"),
        "version": link.get("version"),
        "selection_id": link.get("selection_id"),
        "plan_id": link.get("plan_id"),
        "contract_id": link.get("contract_id"),
        "parcel_id": link.get("parcel_id"),
        "linked_at": link.get("linked_at"),
    }


def derive_proposal_link_id(link: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        PROPOSAL_LINK_ID_DOMAIN
        + jcs_bytes(identity_safe(_proposal_link_body(link)))
    ).hexdigest()
    return "ghot-merge-contract-proposal-link-v0:" + digest


class MergeContractPantry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.engine = StateMergeEngine(self.root)
        self.base = self.root / "state-merges"
        self.selections_dir = self.base / "selections"
        self.proposal_links_dir = self.base / "proposal-links"

    def contracts(self) -> list[dict[str, Any]]:
        result = []
        for contract_id, spec in sorted(self.engine.contract_registry().items()):
            descriptor = contract_descriptor(contract_id, spec)
            result.append({
                **descriptor,
                "contract_address": contract_address(contract_id, spec),
            })
        return result

    def inspect(self, parcel_id: str) -> dict[str, Any]:
        context = self.engine._admitted_context(parcel_id)
        parcel = context["parcel"]
        source = parcel.get("source") or {}
        payload = parcel.get("payload") or {}
        value_type = merge_payload_type(payload.get("value"))

        rows = []
        for contract_id, spec in sorted(self.engine.contract_registry().items()):
            reasons = []
            if source.get("state_kind") != spec.get("parcel_state_kind"):
                reasons.append("state-kind-mismatch")
            if source.get("state_version") != spec.get("parcel_state_version"):
                reasons.append("state-version-mismatch")
            if payload.get("selector") != spec.get("parcel_selector"):
                reasons.append("selector-mismatch")
            if value_type != spec.get("payload_type"):
                reasons.append("payload-type-mismatch")

            target_status = "not-checked"
            local_address = None
            if not reasons:
                try:
                    _path, local_state, existed = self.engine._local_state(spec)
                    target_status = "merge" if existed else "create"
                    local_address = semantic_address(local_state)
                    if parcel_id in (local_state.get("merged_parcels") or []):
                        reasons.append("already-merged")
                except Exception as exc:
                    target_status = "blocked"
                    reasons.append(f"local-target-blocked:{type(exc).__name__}")

            compatible = len(reasons) == 0
            descriptor = contract_descriptor(contract_id, spec)
            rows.append({
                "contract_id": contract_id,
                "contract_address": contract_address(contract_id, spec),
                "title": descriptor.get("title"),
                "category": descriptor.get("category"),
                "compatible": compatible,
                "reasons": reasons,
                "target_status": target_status,
                "local_before_address": local_address,
                "authority_effect": descriptor.get("authority_effect"),
                "freshness_effect": descriptor.get("freshness_effect"),
            })

        return {
            "kind": INSPECTION_KIND,
            "version": INSPECTION_VERSION,
            "parcel_id": parcel_id,
            "parcel_address": parcel.get("parcel_address"),
            "payload_address": payload.get("address"),
            "admitted_ref": context["admitted_ref"],
            "source": {
                "state_kind": source.get("state_kind"),
                "state_version": source.get("state_version"),
                "selector": payload.get("selector"),
                "payload_type": value_type,
            },
            "contracts": rows,
            "compatible_contract_ids": [
                row["contract_id"]
                for row in rows
                if row["compatible"] is True
            ],
        }

    def select(
        self,
        parcel_id: str,
        contract_id: str,
    ) -> dict[str, Any]:
        inspection = self.inspect(parcel_id)
        row = next(
            (
                item for item in inspection["contracts"]
                if item["contract_id"] == contract_id
            ),
            None,
        )
        if row is None:
            raise ValueError("unknown merge contract")
        if row["compatible"] is not True:
            raise ValueError(
                "merge contract is not compatible: "
                + ",".join(row["reasons"])
            )

        selection = {
            "kind": SELECTION_KIND,
            "version": SELECTION_VERSION,
            "selection_id": "",
            "parcel_id": parcel_id,
            "parcel_address": inspection["parcel_address"],
            "payload_address": inspection["payload_address"],
            "admitted_ref": inspection["admitted_ref"],
            "contract_id": contract_id,
            "contract_address": row["contract_address"],
            "selected_at": timestamp_now(),
            "selection_source": "owner-local-cli",
        }
        selection["selection_id"] = derive_selection_id(selection)
        self.selections_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(
            self.selections_dir / f"{_safe_name(selection['selection_id'])}.json",
            selection,
        )
        return selection

    def _selection_path(self, selection_id: str) -> Path:
        return self.selections_dir / f"{_safe_name(selection_id)}.json"

    def _load_selection(self, selection_id: str) -> dict[str, Any]:
        path = self._selection_path(selection_id)
        if not path.exists():
            raise ValueError("unknown merge-contract selection")
        selection = _read_object(path)
        if selection.get("selection_id") != derive_selection_id(selection):
            raise ValueError("merge-contract selection id mismatch")
        return selection

    def selections(self) -> list[dict[str, Any]]:
        if not self.selections_dir.is_dir():
            return []
        result = []
        for path in sorted(self.selections_dir.glob("*.json")):
            try:
                selection = _read_object(path)
            except Exception:
                continue
            result.append(selection)
        return result

    def propose(self, selection_id: str) -> dict[str, Any]:
        selection = self._load_selection(selection_id)
        contract_id = str(selection.get("contract_id") or "")
        spec = self.engine.contract_registry().get(contract_id)
        if spec is None:
            raise ValueError("selected merge contract is no longer installed")
        if selection.get("contract_address") != contract_address(contract_id, spec):
            raise ValueError("selected merge contract changed after selection")

        inspection = self.inspect(str(selection["parcel_id"]))
        if inspection["parcel_address"] != selection.get("parcel_address"):
            raise ValueError("parcel address changed after selection")
        if inspection["payload_address"] != selection.get("payload_address"):
            raise ValueError("payload address changed after selection")
        if inspection["admitted_ref"] != selection.get("admitted_ref"):
            raise ValueError("admitted materialization changed after selection")
        if contract_id not in inspection["compatible_contract_ids"]:
            raise ValueError("selected merge contract is no longer compatible")

        plan = self.engine.propose(
            str(selection["parcel_id"]),
            contract_id=contract_id,
        )
        link = {
            "kind": PROPOSAL_LINK_KIND,
            "version": PROPOSAL_LINK_VERSION,
            "link_id": "",
            "selection_id": selection["selection_id"],
            "plan_id": plan["plan_id"],
            "contract_id": contract_id,
            "parcel_id": selection["parcel_id"],
            "linked_at": timestamp_now(),
        }
        link["link_id"] = derive_proposal_link_id(link)
        self.proposal_links_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(
            self.proposal_links_dir / f"{_safe_name(link['link_id'])}.json",
            link,
        )
        return {
            "kind": "ghot.merge-contract.proposal",
            "version": "0",
            "selection": selection,
            "plan": plan,
            "link": link,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover and explicitly select compatible local merge contracts."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")

    inspect = sub.add_parser("inspect")
    inspect.add_argument("parcel_id")

    select = sub.add_parser("select")
    select.add_argument("parcel_id")
    select.add_argument("contract_id")

    sub.add_parser("selections")

    propose = sub.add_parser("propose")
    propose.add_argument("selection_id")

    args = parser.parse_args()
    pantry = MergeContractPantry()

    if args.command == "list":
        print(json.dumps(pantry.contracts(), indent=2))
        return 0
    if args.command == "inspect":
        print(json.dumps(pantry.inspect(args.parcel_id), indent=2))
        return 0
    if args.command == "select":
        print(json.dumps(
            pantry.select(args.parcel_id, args.contract_id),
            indent=2,
        ))
        return 0
    if args.command == "selections":
        print(json.dumps(pantry.selections(), indent=2))
        return 0
    if args.command == "propose":
        print(json.dumps(pantry.propose(args.selection_id), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
