#!/usr/bin/env python3
"""Lightwalker Labor Writ 001.

A Labor Writ is a bounded issuer-signed promise of future work. It is not
currency, blanket authority, or proof that work already occurred.

Lifecycle:
    issue -> optional bounded delegation -> redemption -> performance receipt
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from lightwalker_economy import LightwalkerEconomyError, canonical_bytes, content_address
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    identity_safe,
    particular_for_public_key,
    sign_crossing,
    timestamp_now,
    verify_crossing,
    verify_p256,
)

WRIT_KIND = "ghot.lightwalker.labor-writ"
WRIT_VERSION = "0"
DELEGATION_KIND = "ghot.lightwalker.labor-writ-delegation"
DELEGATION_VERSION = "0"
REDEMPTION_KIND = "ghot.lightwalker.labor-writ-redemption-request"
REDEMPTION_VERSION = "0"
REDEMPTION_RECEIPT_KIND = "ghot.lightwalker.labor-writ-redemption-receipt"
REDEMPTION_RECEIPT_VERSION = "0"
PERFORMANCE_RECEIPT_KIND = "ghot.lightwalker.labor-writ-performance-receipt"
PERFORMANCE_RECEIPT_VERSION = "0"

WRIT_SIGNING_DOMAIN = "ghot.lightwalker-labor-writ-signature/v0"
DELEGATION_SIGNING_DOMAIN = "ghot.lightwalker-labor-writ-delegation-signature/v0"
REDEMPTION_SIGNING_DOMAIN = "ghot.lightwalker-labor-writ-redemption-signature/v0"
REDEMPTION_RECEIPT_SIGNING_DOMAIN = "ghot.lightwalker-labor-writ-redemption-receipt-signature/v0"
PERFORMANCE_RECEIPT_SIGNING_DOMAIN = "ghot.lightwalker-labor-writ-performance-receipt-signature/v0"

WRIT_BYTES_DOMAIN = b"GHOT-LightwalkerLaborWrit-v0|"
DELEGATION_BYTES_DOMAIN = b"GHOT-LightwalkerLaborWritDelegation-v0|"
REDEMPTION_BYTES_DOMAIN = b"GHOT-LightwalkerLaborWritRedemption-v0|"
REDEMPTION_RECEIPT_BYTES_DOMAIN = b"GHOT-LightwalkerLaborWritRedemptionReceipt-v0|"
PERFORMANCE_RECEIPT_BYTES_DOMAIN = b"GHOT-LightwalkerLaborWritPerformanceReceipt-v0|"

WRIT_CAPABILITY = "ghot.lightwalker-labor-writ/v0"
REDEMPTION_CAPABILITY = "ghot.lightwalker-labor-writ-redemption/v0"


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return value


def _signed_payload(
    body: dict[str, Any],
    *,
    item_id_field: str,
    signing_domain: str,
    bytes_domain: bytes,
    signer: IdentityKey,
) -> dict[str, Any]:
    item_id = content_address(body)
    value = {
        **body,
        item_id_field: item_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": signing_domain,
        },
    }
    value["signing"]["signature"] = signer.sign(
        bytes_domain + canonical_bytes({item_id_field: item_id, **body})
    )
    return value


def _verify_signed_payload(
    value: dict[str, Any],
    *,
    item_id_field: str,
    signing_domain: str,
    bytes_domain: bytes,
    expected_particular_field: str,
) -> bool:
    try:
        signing = value.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM or signing.get("domain") != signing_domain:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != value.get(expected_particular_field):
            return False
        body = {
            key: item
            for key, item in value.items()
            if key not in {item_id_field, "signing"}
        }
        item_id = value.get(item_id_field)
        if not isinstance(item_id, str) or content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            bytes_domain + canonical_bytes({item_id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def issue_labor_writ(
    *,
    issuer: IdentityKey,
    holder_particular: str,
    scope: dict[str, Any],
    issued_at_cut: int,
    expires_after_cut: int,
    delegation_policy: dict[str, Any],
    redemption_policy: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(scope, dict) or not scope:
        raise LightwalkerEconomyError("scope must be a non-empty object")
    issued = _nonnegative_int(issued_at_cut, "issued_at_cut")
    expiry = _nonnegative_int(expires_after_cut, "expires_after_cut")
    if expiry < issued:
        raise LightwalkerEconomyError("expiry cannot precede issue")

    mode = delegation_policy.get("mode")
    maximum = _nonnegative_int(
        delegation_policy.get("max_delegations"),
        "delegation_policy.max_delegations",
    )
    if mode not in {"nondelegable", "bounded"}:
        raise LightwalkerEconomyError("unsupported delegation mode")
    if mode == "nondelegable" and maximum != 0:
        raise LightwalkerEconomyError("nondelegable writ must allow zero delegations")
    if mode == "bounded" and maximum < 1:
        raise LightwalkerEconomyError("bounded delegation needs at least one hop")
    if redemption_policy.get("one_redemption") is not True:
        raise LightwalkerEconomyError("v0 requires one_redemption = true")

    scope_safe = identity_safe(scope)
    body = {
        "kind": WRIT_KIND,
        "version": WRIT_VERSION,
        "authority": "issuer-promise-only",
        "issuer_particular": issuer.particular(),
        "initial_holder_particular": _nonempty(holder_particular, "holder_particular"),
        "scope": scope_safe,
        "scope_digest": content_address(scope_safe),
        "issued_at_cut": issued,
        "expires_after_cut": expiry,
        "delegation_policy": {"mode": mode, "max_delegations": maximum},
        "redemption_policy": {
            "one_redemption": True,
            "performance_evidence_policy": _nonempty(
                redemption_policy.get("performance_evidence_policy"),
                "performance_evidence_policy",
            ),
        },
        "laws": [
            "WRIT != MONEY",
            "WRIT != PERFORMANCE",
            "PORTABILITY != AUTHORITY",
            "REDEMPTION != PERFORMANCE",
            "ONE WRIT -> AT MOST ONE REDEMPTION",
        ],
    }
    return _signed_payload(
        body,
        item_id_field="writ_id",
        signing_domain=WRIT_SIGNING_DOMAIN,
        bytes_domain=WRIT_BYTES_DOMAIN,
        signer=issuer,
    )


def verify_labor_writ(writ: dict[str, Any]) -> bool:
    try:
        if writ.get("kind") != WRIT_KIND or writ.get("version") != WRIT_VERSION:
            return False
        if writ.get("authority") != "issuer-promise-only":
            return False
        if writ.get("scope_digest") != content_address(writ.get("scope")):
            return False
        return _verify_signed_payload(
            writ,
            item_id_field="writ_id",
            signing_domain=WRIT_SIGNING_DOMAIN,
            bytes_domain=WRIT_BYTES_DOMAIN,
            expected_particular_field="issuer_particular",
        )
    except Exception:
        return False


def verify_delegation(writ: dict[str, Any], delegation: dict[str, Any]) -> bool:
    try:
        if not verify_labor_writ(writ):
            return False
        if delegation.get("kind") != DELEGATION_KIND or delegation.get("version") != DELEGATION_VERSION:
            return False
        if delegation.get("writ_id") != writ["writ_id"]:
            return False
        if delegation.get("scope_digest") != writ["scope_digest"]:
            return False
        index = int(delegation.get("delegation_index", -1))
        if index < 1 or index > int(writ["delegation_policy"]["max_delegations"]):
            return False
        if int(delegation.get("delegated_at_cut", -1)) > int(writ["expires_after_cut"]):
            return False
        return _verify_signed_payload(
            delegation,
            item_id_field="delegation_id",
            signing_domain=DELEGATION_SIGNING_DOMAIN,
            bytes_domain=DELEGATION_BYTES_DOMAIN,
            expected_particular_field="from_holder_particular",
        )
    except Exception:
        return False


def _resolve_holder(
    writ: dict[str, Any],
    delegation: dict[str, Any] | None = None,
) -> tuple[str, int]:
    if not verify_labor_writ(writ):
        raise LightwalkerEconomyError("invalid Labor Writ")
    if delegation is None:
        return str(writ["initial_holder_particular"]), 0
    if not verify_delegation(writ, delegation):
        raise LightwalkerEconomyError("invalid Labor Writ delegation")
    return str(delegation["to_holder_particular"]), int(delegation["delegation_index"])


def delegate_labor_writ(
    writ: dict[str, Any],
    *,
    signer: IdentityKey,
    to_holder_particular: str,
    delegated_at_cut: int,
    prior_delegation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_holder, prior_count = _resolve_holder(writ, prior_delegation)
    if signer.particular() != current_holder:
        raise LightwalkerEconomyError("delegation signer is not current holder")
    policy = writ["delegation_policy"]
    if policy["mode"] != "bounded":
        raise LightwalkerEconomyError("writ is nondelegable")
    new_index = prior_count + 1
    if new_index > int(policy["max_delegations"]):
        raise LightwalkerEconomyError("delegation limit exhausted")
    cut = _nonnegative_int(delegated_at_cut, "delegated_at_cut")
    if cut > int(writ["expires_after_cut"]):
        raise LightwalkerEconomyError("cannot delegate expired writ")

    body = {
        "kind": DELEGATION_KIND,
        "version": DELEGATION_VERSION,
        "writ_id": writ["writ_id"],
        "from_holder_particular": current_holder,
        "to_holder_particular": _nonempty(to_holder_particular, "to_holder_particular"),
        "delegated_at_cut": cut,
        "delegation_index": new_index,
        "prior_delegation_id": delegation_id if (delegation_id := (prior_delegation or {}).get("delegation_id")) else None,
        "scope_digest": writ["scope_digest"],
        "laws": [
            "DELEGATION != REWRITING",
            "DELEGATION MAY NOT EXPAND SCOPE",
            "DELEGATION MAY NOT EXTEND EXPIRY",
        ],
    }
    return _signed_payload(
        body,
        item_id_field="delegation_id",
        signing_domain=DELEGATION_SIGNING_DOMAIN,
        bytes_domain=DELEGATION_BYTES_DOMAIN,
        signer=signer,
    )


def make_redemption_request(
    writ: dict[str, Any],
    *,
    signer: IdentityKey,
    requested_at_cut: int,
    delegation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holder, _ = _resolve_holder(writ, delegation)
    if signer.particular() != holder:
        raise LightwalkerEconomyError("redeemer is not current holder")
    cut = _nonnegative_int(requested_at_cut, "requested_at_cut")
    if cut > int(writ["expires_after_cut"]):
        raise LightwalkerEconomyError("Labor Writ expired before redemption")

    body = {
        "kind": REDEMPTION_KIND,
        "version": REDEMPTION_VERSION,
        "writ_id": writ["writ_id"],
        "redeemer_particular": holder,
        "requested_at_cut": cut,
        "delegation_id": (delegation or {}).get("delegation_id"),
        "scope_digest": writ["scope_digest"],
        "nonce": f"redemption-{uuid.uuid4()}",
        "laws": [
            "REDEMPTION != PERFORMANCE",
            "REDEEMER MUST HOLD THE WRIT",
            "REDEMPTION MAY NOT CHANGE SCOPE",
        ],
    }
    return _signed_payload(
        body,
        item_id_field="redemption_request_id",
        signing_domain=REDEMPTION_SIGNING_DOMAIN,
        bytes_domain=REDEMPTION_BYTES_DOMAIN,
        signer=signer,
    )


def verify_redemption_request(
    writ: dict[str, Any],
    request: dict[str, Any],
    *,
    delegation: dict[str, Any] | None = None,
) -> bool:
    try:
        holder, _ = _resolve_holder(writ, delegation)
        if request.get("kind") != REDEMPTION_KIND or request.get("version") != REDEMPTION_VERSION:
            return False
        if request.get("writ_id") != writ["writ_id"]:
            return False
        if request.get("redeemer_particular") != holder:
            return False
        if request.get("scope_digest") != writ["scope_digest"]:
            return False
        if request.get("delegation_id") != (delegation or {}).get("delegation_id"):
            return False
        if int(request.get("requested_at_cut", -1)) > int(writ["expires_after_cut"]):
            return False
        return _verify_signed_payload(
            request,
            item_id_field="redemption_request_id",
            signing_domain=REDEMPTION_SIGNING_DOMAIN,
            bytes_domain=REDEMPTION_BYTES_DOMAIN,
            expected_particular_field="redeemer_particular",
        )
    except Exception:
        return False


def make_writ_crossing(
    writ: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
) -> dict[str, Any]:
    if not verify_labor_writ(writ):
        raise LightwalkerEconomyError("invalid Labor Writ")
    if signer.particular() != writ["issuer_particular"]:
        raise LightwalkerEconomyError("writ crossing signer must be issuer")
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": "LIGHTWALKER_LABOR_WRIT",
        "payload_refs": [writ["writ_id"], writ["scope_digest"]],
        "requested_effect": identity_safe(
            {
                "operation": "consider-labor-writ",
                "writ_id": writ["writ_id"],
                "automatic_redemption_requested": False,
                "execution_authority_requested": False,
            }
        ),
        "capability_ref": WRIT_CAPABILITY,
        "privacy_policy": {"transport": "replaceable", "payload_encryption": False},
        "audience_policy": {"holder_particular": writ["initial_holder_particular"]},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-labor-writ/v0",
            "portability_is_not_authority": True,
            "writ_is_not_performance": True,
        },
        "signing": {"algorithm": "", "public_key": {}, "signature": "", "domain": ""},
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("Labor Writ crossing failed verification")
    return signed


def make_redemption_crossing(
    writ: dict[str, Any],
    request: dict[str, Any],
    *,
    signer: IdentityKey,
    node_id: str,
    delegation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not verify_redemption_request(writ, request, delegation=delegation):
        raise LightwalkerEconomyError("invalid redemption request")
    if signer.particular() != request["redeemer_particular"]:
        raise LightwalkerEconomyError("redemption crossing signer mismatch")
    envelope = {
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": signer.particular(),
        "source_world": f"ghot-node:{node_id}",
        "source_history_head": None,
        "parents": [],
        "declared_kind": "LIGHTWALKER_LABOR_WRIT_REDEMPTION",
        "payload_refs": [writ["writ_id"], request["redemption_request_id"]],
        "requested_effect": identity_safe(
            {
                "operation": "consider-labor-writ-redemption",
                "writ_id": writ["writ_id"],
                "redemption_request_id": request["redemption_request_id"],
                "automatic_execution_requested": False,
                "automatic_settlement_requested": False,
            }
        ),
        "capability_ref": REDEMPTION_CAPABILITY,
        "privacy_policy": {"transport": "replaceable", "payload_encryption": False},
        "audience_policy": {"issuer_particular": writ["issuer_particular"]},
        "return_address": None,
        "created_at": timestamp_now(),
        "extensions": {
            "ghot_profile": "lightwalker-labor-writ-redemption/v0",
            "redemption_is_not_performance": True,
        },
        "signing": {"algorithm": "", "public_key": {}, "signature": "", "domain": ""},
    }
    signed = sign_crossing(envelope, signer)
    if not verify_crossing(signed):
        raise LightwalkerEconomyError("redemption crossing failed verification")
    return signed


def verify_redemption_receipt(writ: dict[str, Any], receipt: dict[str, Any]) -> bool:
    if not verify_labor_writ(writ):
        return False
    if receipt.get("kind") != REDEMPTION_RECEIPT_KIND or receipt.get("version") != REDEMPTION_RECEIPT_VERSION:
        return False
    if receipt.get("writ_id") != writ["writ_id"] or receipt.get("scope_digest") != writ["scope_digest"]:
        return False
    if receipt.get("writ_exhausted") is not True:
        return False
    return _verify_signed_payload(
        receipt,
        item_id_field="redemption_receipt_id",
        signing_domain=REDEMPTION_RECEIPT_SIGNING_DOMAIN,
        bytes_domain=REDEMPTION_RECEIPT_BYTES_DOMAIN,
        expected_particular_field="issuer_particular",
    )


def verify_performance_receipt(
    writ: dict[str, Any],
    redemption_receipt: dict[str, Any],
    receipt: dict[str, Any],
) -> bool:
    if not verify_redemption_receipt(writ, redemption_receipt):
        return False
    if receipt.get("kind") != PERFORMANCE_RECEIPT_KIND or receipt.get("version") != PERFORMANCE_RECEIPT_VERSION:
        return False
    if receipt.get("writ_id") != writ["writ_id"]:
        return False
    if receipt.get("redemption_receipt_id") != redemption_receipt["redemption_receipt_id"]:
        return False
    if receipt.get("scope_digest") != writ["scope_digest"] or receipt.get("writ_exhausted") is not True:
        return False
    return _verify_signed_payload(
        receipt,
        item_id_field="performance_receipt_id",
        signing_domain=PERFORMANCE_RECEIPT_SIGNING_DOMAIN,
        bytes_domain=PERFORMANCE_RECEIPT_BYTES_DOMAIN,
        expected_particular_field="issuer_particular",
    )


class LaborWritStore:
    """Issuer-local atomic redemption and terminal performance witness."""

    def __init__(self, root: Path, *, issuer: IdentityKey) -> None:
        self.root = root
        self.issuer = issuer
        self.claims_dir = root / "labor-writs" / "claims"
        self.redemptions_dir = root / "labor-writs" / "redemptions"
        self.performance_dir = root / "labor-writs" / "performance"

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _path(self, directory: Path, writ_id: str) -> Path:
        return directory / f"{self._safe(writ_id)}.json"

    def _exclusive_write(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        finally:
            os.close(fd)

    def redeem(
        self,
        writ: dict[str, Any],
        request: dict[str, Any],
        *,
        delegation: dict[str, Any] | None = None,
        observed_cut: int,
    ) -> dict[str, Any]:
        if not verify_labor_writ(writ):
            raise LightwalkerEconomyError("invalid Labor Writ")
        if self.issuer.particular() != writ["issuer_particular"]:
            raise LightwalkerEconomyError("local issuer does not own this writ")
        if not verify_redemption_request(writ, request, delegation=delegation):
            raise LightwalkerEconomyError("invalid redemption request")
        cut = _nonnegative_int(observed_cut, "observed_cut")
        if cut > int(writ["expires_after_cut"]):
            raise LightwalkerEconomyError("Labor Writ expired")

        claim = {
            "kind": "ghot.lightwalker.labor-writ-claim",
            "version": "0",
            "writ_id": writ["writ_id"],
            "redemption_request_id": request["redemption_request_id"],
            "redeemer_particular": request["redeemer_particular"],
            "observed_cut": cut,
            "scope_digest": writ["scope_digest"],
        }
        claim_path = self._path(self.claims_dir, writ["writ_id"])
        try:
            self._exclusive_write(claim_path, claim)
        except FileExistsError as exc:
            raise LightwalkerEconomyError("Labor Writ already redeemed/exhausted") from exc

        body = {
            "kind": REDEMPTION_RECEIPT_KIND,
            "version": REDEMPTION_RECEIPT_VERSION,
            "issuer_particular": self.issuer.particular(),
            "writ_id": writ["writ_id"],
            "redemption_request_id": request["redemption_request_id"],
            "redeemer_particular": request["redeemer_particular"],
            "scope_digest": writ["scope_digest"],
            "observed_cut": cut,
            "status": "REDEEMED",
            "writ_exhausted": True,
            "performance_completed": False,
            "laws": [
                "REDEMPTION != PERFORMANCE",
                "REDEEMED WRIT MAY NOT BE REDEEMED AGAIN",
                "EXHAUSTION DOES NOT PROVE SUCCESSFUL PERFORMANCE",
            ],
        }
        receipt = _signed_payload(
            body,
            item_id_field="redemption_receipt_id",
            signing_domain=REDEMPTION_RECEIPT_SIGNING_DOMAIN,
            bytes_domain=REDEMPTION_RECEIPT_BYTES_DOMAIN,
            signer=self.issuer,
        )
        self.redemptions_dir.mkdir(parents=True, exist_ok=True)
        self._path(self.redemptions_dir, writ["writ_id"]).write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return receipt

    def complete(
        self,
        writ: dict[str, Any],
        redemption_receipt: dict[str, Any],
        *,
        evidence_ref: str,
        outcome: str = "FULFILLED",
    ) -> dict[str, Any]:
        if not verify_redemption_receipt(writ, redemption_receipt):
            raise LightwalkerEconomyError("invalid redemption receipt")
        if outcome not in {"FULFILLED", "FAILED"}:
            raise LightwalkerEconomyError("unsupported performance outcome")
        claim_path = self._path(self.claims_dir, writ["writ_id"])
        if not claim_path.exists():
            raise LightwalkerEconomyError("no redemption claim exists")

        body = {
            "kind": PERFORMANCE_RECEIPT_KIND,
            "version": PERFORMANCE_RECEIPT_VERSION,
            "issuer_particular": self.issuer.particular(),
            "writ_id": writ["writ_id"],
            "redemption_receipt_id": redemption_receipt["redemption_receipt_id"],
            "redeemer_particular": redemption_receipt["redeemer_particular"],
            "scope_digest": writ["scope_digest"],
            "evidence_ref": _nonempty(evidence_ref, "evidence_ref"),
            "outcome": outcome,
            "writ_exhausted": True,
            "laws": [
                "PERFORMANCE RECEIPT != WRIT",
                "FAILURE DOES NOT UNSPEND A REDEEMED WRIT",
                "TERMINAL PERFORMANCE RECEIPT MAY NOT BE REPLAYED",
            ],
        }
        receipt = _signed_payload(
            body,
            item_id_field="performance_receipt_id",
            signing_domain=PERFORMANCE_RECEIPT_SIGNING_DOMAIN,
            bytes_domain=PERFORMANCE_RECEIPT_BYTES_DOMAIN,
            signer=self.issuer,
        )
        try:
            self._exclusive_write(
                self._path(self.performance_dir, writ["writ_id"]),
                receipt,
            )
        except FileExistsError as exc:
            raise LightwalkerEconomyError(
                "Labor Writ already has a terminal performance receipt"
            ) from exc
        return receipt


__all__ = [
    "LaborWritStore",
    "delegate_labor_writ",
    "issue_labor_writ",
    "make_redemption_crossing",
    "make_redemption_request",
    "make_writ_crossing",
    "verify_delegation",
    "verify_labor_writ",
    "verify_performance_receipt",
    "verify_redemption_receipt",
    "verify_redemption_request",
]
