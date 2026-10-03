#!/usr/bin/env python3
"""Local schema-specific state merge contracts — Experiment 019.

V0 first contract:
  admitted parcel from ghot.organ.state/v1 selector /body/offers
      -> GHOT_HOME/knowledge/foreign-offers.v0.json
      -> ghot.foreign-offer-catalog/v0

Only locally ADMITTED parcels are eligible.
No network merge endpoint exists.
A merge plan binds:
- exact admitted parcel and payload addresses;
- exact local before-state address;
- exact proposed after-state address;
- exact registered merge contract.

APPLY revalidates all of those before an atomic local write and BODY-signed
merge receipt. REJECT signs a terminal no-effect receipt.

The foreign-offer catalog is observational memory only. It grants no trust,
liveness, authority, scheduling eligibility, or execution permission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable

from reference_node import ROOT
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    identity_safe,
    jcs_bytes,
    particular_for_public_key,
    timestamp_now,
    unb64url,
    verify_p256,
)
from state_migration import semantic_address
from state_parcel import verify_bundle


PLAN_KIND = "ghot.state.merge.plan"
PLAN_VERSION = "0"
RECEIPT_KIND = "ghot.state.merge.receipt"
RECEIPT_VERSION = "0"

PLAN_ID_DOMAIN = b"GHoT-StateMergePlan-v0|"
RECEIPT_ID_DOMAIN = b"GHoT-StateMergeReceipt-v0|"
RECEIPT_SIGNATURE_DOMAIN = b"GHoT-StateMergeReceiptSignature-v0|"
RECEIPT_SIGNING_DOMAIN = "ghot.state-merge-receipt-signature/v0"

DISPOSITIONS = {"APPLY", "REJECT"}

MergeFn = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _safe_name(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def empty_foreign_offer_catalog() -> dict[str, Any]:
    return {
        "kind": "ghot.foreign-offer-catalog",
        "version": "0",
        "entries": [],
        "merged_parcels": [],
    }


def _normalized_offer(
    offer: dict[str, Any],
    *,
    parcel: dict[str, Any],
) -> dict[str, Any]:
    capability = offer.get("capability")
    if not isinstance(capability, str) or not capability:
        raise ValueError("foreign offer must name a capability")
    available = offer.get("available")
    if not isinstance(available, bool):
        raise ValueError("foreign offer available must be boolean")
    power_class = offer.get("power_class")
    if power_class is not None and not isinstance(power_class, str):
        raise ValueError("foreign offer power_class must be string or null")
    return {
        "source_particular": parcel["source"]["particular"],
        "source_node_id": parcel["source"]["node_id"],
        "capability": capability,
        "available": available,
        "power_class": power_class,
        "parcel_id": parcel["parcel_id"],
        "payload_address": parcel["payload"]["address"],
    }


def merge_foreign_offers(
    local_state: dict[str, Any],
    admitted_context: dict[str, Any],
) -> dict[str, Any]:
    if (
        local_state.get("kind") != "ghot.foreign-offer-catalog"
        or local_state.get("version") != "0"
    ):
        raise ValueError("local state must be ghot.foreign-offer-catalog/v0")

    parcel = admitted_context["parcel"]
    payload = parcel["payload"]["value"]
    if not isinstance(payload, list):
        raise ValueError("/body/offers parcel payload must be a list")

    entries_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in local_state.get("entries") or []:
        if not isinstance(raw, dict):
            raise ValueError("local catalog entry must be an object")
        particular = raw.get("source_particular")
        capability = raw.get("capability")
        if not isinstance(particular, str) or not isinstance(capability, str):
            raise ValueError("local catalog entry has invalid key")
        entries_by_key[(particular, capability)] = identity_safe(raw)

    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError("foreign offer payload entries must be objects")
        normalized = _normalized_offer(raw, parcel=parcel)
        key = (
            normalized["source_particular"],
            normalized["capability"],
        )
        entries_by_key[key] = normalized

    entries = [
        entries_by_key[key]
        for key in sorted(entries_by_key)
    ]
    merged_parcels = sorted(set(
        [
            str(item)
            for item in (local_state.get("merged_parcels") or [])
            if isinstance(item, str)
        ]
        + [parcel["parcel_id"]]
    ))

    return identity_safe({
        "kind": "ghot.foreign-offer-catalog",
        "version": "0",
        "entries": entries,
        "merged_parcels": merged_parcels,
    })


MERGE_CONTRACTS: dict[str, dict[str, Any]] = {
    "ghot.organ.offers->foreign-offer-catalog/v0": {
        "contract_id": "ghot.organ.offers->foreign-offer-catalog/v0",
        "parcel_state_kind": "ghot.organ.state",
        "parcel_state_version": "1",
        "parcel_selector": "/body/offers",
        "local_rel": "knowledge/foreign-offers.v0.json",
        "local_kind": "ghot.foreign-offer-catalog",
        "local_version": "0",
        "initial": empty_foreign_offer_catalog,
        "apply": merge_foreign_offers,
    },
}


def _plan_body(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": plan.get("kind"),
        "version": plan.get("version"),
        "contract_id": plan.get("contract_id"),
        "parcel_id": plan.get("parcel_id"),
        "parcel_address": plan.get("parcel_address"),
        "payload_address": plan.get("payload_address"),
        "admitted_ref": plan.get("admitted_ref"),
        "local_state_path": plan.get("local_state_path"),
        "local_state_kind": plan.get("local_state_kind"),
        "local_state_version": plan.get("local_state_version"),
        "local_before_address": plan.get("local_before_address"),
        "proposed_after_address": plan.get("proposed_after_address"),
        "mode": plan.get("mode"),
        "created_at": plan.get("created_at"),
    }


def derive_plan_id(plan: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        PLAN_ID_DOMAIN + jcs_bytes(identity_safe(_plan_body(plan)))
    ).hexdigest()
    return "ghot-state-merge-plan-v0:" + digest


def _receipt_body(receipt: dict[str, Any]) -> dict[str, Any]:
    signing = receipt.get("signing") or {}
    return {
        "kind": receipt.get("kind"),
        "version": receipt.get("version"),
        "receipt_id": None,
        "plan_id": receipt.get("plan_id"),
        "contract_id": receipt.get("contract_id"),
        "disposition": receipt.get("disposition"),
        "parcel_id": receipt.get("parcel_id"),
        "parcel_address": receipt.get("parcel_address"),
        "payload_address": receipt.get("payload_address"),
        "admitted_ref": receipt.get("admitted_ref"),
        "local_state_path": receipt.get("local_state_path"),
        "local_before_address": receipt.get("local_before_address"),
        "local_after_address": receipt.get("local_after_address"),
        "backup_path": receipt.get("backup_path"),
        "created_at": receipt.get("created_at"),
        "particular": receipt.get("particular"),
        "note": receipt.get("note"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    }


def derive_receipt_id(receipt: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        RECEIPT_ID_DOMAIN + jcs_bytes(identity_safe(_receipt_body(receipt)))
    ).hexdigest()
    return "ghot-state-merge-receipt-v0:" + digest


def receipt_signature_bytes(receipt: dict[str, Any]) -> bytes:
    body = identity_safe(_receipt_body(receipt))
    return RECEIPT_SIGNATURE_DOMAIN + jcs_bytes({
        "receipt_id": derive_receipt_id(receipt),
        **body,
    })


def sign_merge_receipt(
    *,
    plan: dict[str, Any],
    disposition: str,
    local_after_address: str,
    backup_path: str | None,
    signer: IdentityKey,
    note: str | None = None,
) -> dict[str, Any]:
    disposition = disposition.upper()
    if disposition not in DISPOSITIONS:
        raise ValueError("merge disposition must be APPLY or REJECT")
    receipt = {
        "kind": RECEIPT_KIND,
        "version": RECEIPT_VERSION,
        "receipt_id": "",
        "plan_id": plan["plan_id"],
        "contract_id": plan["contract_id"],
        "disposition": disposition,
        "parcel_id": plan["parcel_id"],
        "parcel_address": plan["parcel_address"],
        "payload_address": plan["payload_address"],
        "admitted_ref": plan["admitted_ref"],
        "local_state_path": plan["local_state_path"],
        "local_before_address": plan["local_before_address"],
        "local_after_address": local_after_address,
        "backup_path": backup_path,
        "created_at": timestamp_now(),
        "particular": signer.particular(),
        "note": note,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": RECEIPT_SIGNING_DOMAIN,
        },
    }
    receipt["receipt_id"] = derive_receipt_id(receipt)
    receipt["signing"]["signature"] = signer.sign(
        receipt_signature_bytes(receipt)
    )
    return receipt


def verify_merge_receipt(receipt: dict[str, Any]) -> bool:
    try:
        if (
            receipt.get("kind") != RECEIPT_KIND
            or receipt.get("version") != RECEIPT_VERSION
        ):
            return False
        if receipt.get("disposition") not in DISPOSITIONS:
            return False
        signing = receipt.get("signing") or {}
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != RECEIPT_SIGNING_DOMAIN:
            return False
        public_key = signing.get("public_key") or {}
        if receipt.get("particular") != particular_for_public_key(public_key):
            return False
        if receipt.get("receipt_id") != derive_receipt_id(receipt):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            receipt_signature_bytes(receipt),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


class StateMergeEngine:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.base = self.root / "state-merges"
        self.plans_dir = self.base / "plans"
        self.receipts_dir = self.base / "receipts"
        self.backups_dir = self.base / "backups"
        self.signer = IdentityKey.load_or_create(
            self.root / "identity" / "body-p256.pem"
        )

    def _parcel_paths(self, parcel_id: str) -> tuple[Path, Path, Path]:
        safe = _safe_name(parcel_id)
        return (
            self.root / "state-parcels" / "inbox" / f"{safe}.json",
            self.root / "state-parcels" / "raw" / f"{safe}.json",
            self.root / "state-parcels" / "admitted" / f"{safe}.json",
        )

    def _admitted_context(self, parcel_id: str) -> dict[str, Any]:
        inbox_path, raw_path, admitted_path = self._parcel_paths(parcel_id)
        for path in (inbox_path, raw_path, admitted_path):
            if not path.exists():
                raise ValueError("parcel is not locally ADMITTED")

        inbox = _read_object(inbox_path)
        if inbox.get("status") != "ADMIT":
            raise ValueError("parcel is not locally ADMITTED")
        bundle = _read_object(raw_path)
        if not verify_bundle(bundle):
            raise ValueError("stored parcel bundle no longer verifies")
        parcel = bundle.get("parcel") or {}
        if parcel.get("parcel_id") != parcel_id:
            raise ValueError("raw parcel id mismatch")
        admitted = _read_object(admitted_path)
        if admitted.get("parcel_id") != parcel_id:
            raise ValueError("admitted parcel id mismatch")

        expected_admitted = {
            "kind": admitted.get("kind"),
            "version": admitted.get("version"),
            "parcel_id": admitted.get("parcel_id"),
            "admitted_at": admitted.get("admitted_at"),
            "source": parcel.get("source"),
            "migration": parcel.get("migration"),
            "payload": parcel.get("payload"),
            "note": admitted.get("note"),
            "canonical_state_mutated": False,
        }
        if identity_safe(admitted) != identity_safe(expected_admitted):
            raise ValueError("admitted materialization no longer matches raw parcel")

        return {
            "inbox": inbox,
            "bundle": bundle,
            "parcel": parcel,
            "admitted": admitted,
            "admitted_ref": semantic_address(identity_safe(admitted)),
        }

    def eligible_contracts(self, parcel_id: str) -> list[str]:
        context = self._admitted_context(parcel_id)
        parcel = context["parcel"]
        source = parcel.get("source") or {}
        payload = parcel.get("payload") or {}
        eligible = []
        for contract_id, spec in sorted(MERGE_CONTRACTS.items()):
            if (
                source.get("state_kind") == spec["parcel_state_kind"]
                and source.get("state_version") == spec["parcel_state_version"]
                and payload.get("selector") == spec["parcel_selector"]
            ):
                eligible.append(contract_id)
        return eligible

    def _local_state(
        self,
        spec: dict[str, Any],
    ) -> tuple[Path, dict[str, Any], bool]:
        path = self.root / spec["local_rel"]
        if not path.exists():
            state = identity_safe(spec["initial"]())
            return path, state, False
        state = _read_object(path)
        if (
            state.get("kind") != spec["local_kind"]
            or state.get("version") != spec["local_version"]
        ):
            raise ValueError("local merge target has unsupported kind/version")
        return path, identity_safe(state), True

    def propose(
        self,
        parcel_id: str,
        contract_id: str | None = None,
    ) -> dict[str, Any]:
        context = self._admitted_context(parcel_id)
        eligible = self.eligible_contracts(parcel_id)
        if not eligible:
            raise ValueError("no merge contract accepts this admitted parcel")

        chosen = contract_id or eligible[0]
        if chosen not in eligible:
            raise ValueError("requested merge contract does not accept this parcel")
        spec = MERGE_CONTRACTS[chosen]

        local_path, local_before, existed = self._local_state(spec)
        if parcel_id in (local_before.get("merged_parcels") or []):
            raise ValueError("parcel is already merged into this local state")
        after = identity_safe(spec["apply"](local_before, context))
        if (
            after.get("kind") != spec["local_kind"]
            or after.get("version") != spec["local_version"]
        ):
            raise ValueError("merge function produced wrong local kind/version")

        plan = {
            "kind": PLAN_KIND,
            "version": PLAN_VERSION,
            "plan_id": "",
            "contract_id": chosen,
            "parcel_id": parcel_id,
            "parcel_address": context["parcel"]["parcel_address"],
            "payload_address": context["parcel"]["payload"]["address"],
            "admitted_ref": context["admitted_ref"],
            "local_state_path": str(local_path),
            "local_state_kind": spec["local_kind"],
            "local_state_version": spec["local_version"],
            "local_state_existed": existed,
            "local_before_address": semantic_address(local_before),
            "proposed_after_address": semantic_address(after),
            "mode": "apply",
            "created_at": timestamp_now(),
        }
        plan["plan_id"] = derive_plan_id(plan)
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(
            self.plans_dir / f"{_safe_name(plan['plan_id'])}.json",
            plan,
        )
        return plan

    def _plan_path(self, plan_id: str) -> Path:
        return self.plans_dir / f"{_safe_name(plan_id)}.json"

    def _receipt_path(self, receipt_id: str) -> Path:
        return self.receipts_dir / f"{_safe_name(receipt_id)}.json"

    def _load_plan(self, plan_id: str) -> dict[str, Any]:
        path = self._plan_path(plan_id)
        if not path.exists():
            raise ValueError("unknown merge plan")
        plan = _read_object(path)
        if plan.get("plan_id") != derive_plan_id(plan):
            raise ValueError("merge plan content address mismatch")
        return plan

    def receipts_for_plan(self, plan_id: str) -> list[dict[str, Any]]:
        if not self.receipts_dir.is_dir():
            return []
        found = []
        for path in sorted(self.receipts_dir.glob("*.json")):
            try:
                receipt = _read_object(path)
            except Exception:
                continue
            if receipt.get("plan_id") != plan_id:
                continue
            found.append(receipt)
        return found

    def _terminal_receipt(self, plan_id: str) -> dict[str, Any] | None:
        for receipt in self.receipts_for_plan(plan_id):
            if verify_merge_receipt(receipt):
                return receipt
        return None

    def reject(
        self,
        plan_id: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        plan = self._load_plan(plan_id)
        existing = self._terminal_receipt(plan_id)
        if existing is not None:
            if existing.get("disposition") == "REJECT":
                return existing
            raise ValueError("merge plan already applied")

        context = self._admitted_context(plan["parcel_id"])
        if context["admitted_ref"] != plan["admitted_ref"]:
            raise ValueError("admitted parcel changed after merge proposal")

        receipt = sign_merge_receipt(
            plan=plan,
            disposition="REJECT",
            local_after_address=plan["local_before_address"],
            backup_path=None,
            signer=self.signer,
            note=note,
        )
        if not verify_merge_receipt(receipt):
            raise RuntimeError("merge rejection receipt failed verification")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(self._receipt_path(receipt["receipt_id"]), receipt)
        return receipt

    def apply(
        self,
        plan_id: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        plan = self._load_plan(plan_id)
        existing = self._terminal_receipt(plan_id)
        if existing is not None:
            if existing.get("disposition") == "APPLY":
                return existing
            raise ValueError("merge plan was rejected")

        spec = MERGE_CONTRACTS.get(str(plan.get("contract_id") or ""))
        if spec is None:
            raise ValueError("merge contract is no longer registered")

        context = self._admitted_context(plan["parcel_id"])
        parcel = context["parcel"]
        if parcel["parcel_address"] != plan["parcel_address"]:
            raise ValueError("parcel address changed after merge proposal")
        if parcel["payload"]["address"] != plan["payload_address"]:
            raise ValueError("payload address changed after merge proposal")
        if context["admitted_ref"] != plan["admitted_ref"]:
            raise ValueError("admitted parcel changed after merge proposal")

        local_path, current, existed = self._local_state(spec)
        if str(local_path) != plan["local_state_path"]:
            raise ValueError("local merge target path changed")
        current_address = semantic_address(current)

        proposed = identity_safe(spec["apply"](current, context))
        proposed_address = semantic_address(proposed)

        # Normal apply: local current state must still equal the proposal's before.
        # Interrupted-write reconciliation: target already equals proposed after.
        mode = "apply"
        if current_address == plan["proposed_after_address"]:
            mode = "reconcile-receipt"
        elif current_address != plan["local_before_address"]:
            raise ValueError("local state changed after merge proposal")
        elif proposed_address != plan["proposed_after_address"]:
            raise ValueError("merge output changed after proposal")

        backup_path: Path | None = None
        if mode == "apply":
            if existed:
                digest = plan["local_before_address"].split(":", 1)[-1]
                backup_path = (
                    self.backups_dir
                    / _safe_name(plan["contract_id"])
                    / f"{digest}.json"
                )
                if not backup_path.exists():
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    temp = backup_path.with_suffix(f".tmp-{uuid.uuid4()}")
                    shutil.copyfile(local_path, temp)
                    temp.replace(backup_path)
            _write_atomic(local_path, proposed)
            persisted = _read_object(local_path)
            if semantic_address(identity_safe(persisted)) != plan["proposed_after_address"]:
                raise RuntimeError("persisted merged state failed after-address verification")
        else:
            # A previous process may have written the exact proposed state and
            # died before persisting the receipt. Never rewrite it merely to
            # recreate the witness.
            persisted = current

        receipt = sign_merge_receipt(
            plan=plan,
            disposition="APPLY",
            local_after_address=semantic_address(identity_safe(persisted)),
            backup_path=str(backup_path) if backup_path is not None else None,
            signer=self.signer,
            note=(
                note
                if mode == "apply"
                else (note or "reconciled receipt after exact target already existed")
            ),
        )
        if not verify_merge_receipt(receipt):
            raise RuntimeError("merge receipt failed local verification")
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(self._receipt_path(receipt["receipt_id"]), receipt)
        return receipt

    def list_plans(self) -> list[dict[str, Any]]:
        if not self.plans_dir.is_dir():
            return []
        result = []
        for path in sorted(self.plans_dir.glob("*.json")):
            try:
                plan = _read_object(path)
            except Exception:
                continue
            terminal = self._terminal_receipt(str(plan.get("plan_id") or ""))
            result.append({
                **plan,
                "terminal_disposition": (
                    terminal.get("disposition")
                    if isinstance(terminal, dict)
                    else None
                ),
            })
        return result

    def receipts(self) -> list[dict[str, Any]]:
        if not self.receipts_dir.is_dir():
            return []
        result = []
        for path in sorted(self.receipts_dir.glob("*.json")):
            try:
                receipt = _read_object(path)
            except Exception:
                continue
            result.append({
                **receipt,
                "verified": verify_merge_receipt(receipt),
            })
        return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Propose and apply owner-local merges from ADMITTED state parcels."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    eligible = sub.add_parser("eligible")
    eligible.add_argument("parcel_id")

    propose = sub.add_parser("propose")
    propose.add_argument("parcel_id")
    propose.add_argument("--contract", default=None)

    sub.add_parser("plans")

    apply = sub.add_parser("apply")
    apply.add_argument("plan_id")
    apply.add_argument("--note", default=None)

    reject = sub.add_parser("reject")
    reject.add_argument("plan_id")
    reject.add_argument("--note", default=None)

    sub.add_parser("receipts")

    args = parser.parse_args()
    engine = StateMergeEngine()

    if args.command == "eligible":
        print(json.dumps(engine.eligible_contracts(args.parcel_id), indent=2))
        return 0
    if args.command == "propose":
        print(json.dumps(
            engine.propose(args.parcel_id, contract_id=args.contract),
            indent=2,
        ))
        return 0
    if args.command == "plans":
        print(json.dumps(engine.list_plans(), indent=2))
        return 0
    if args.command == "apply":
        print(json.dumps(
            engine.apply(args.plan_id, note=args.note),
            indent=2,
        ))
        return 0
    if args.command == "reject":
        print(json.dumps(
            engine.reject(args.plan_id, note=args.note),
            indent=2,
        ))
        return 0
    if args.command == "receipts":
        print(json.dumps(engine.receipts(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
