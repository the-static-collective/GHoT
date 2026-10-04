#!/usr/bin/env python3
"""FIELD COMMONS 001.

Compose a bounded Ice Field WANT with a voluntary heterogeneous exchange and a
Guild-local compute authorization.

No universal price is invented. The first exchange is:

    read-only artifact access <-> one Ice Cube compute job

The Guild's visible compute capacity does not schedule anything by itself.
A valid accepted exchange and a one-shot Guild authorization are both required
before the Commons may dispatch the WANT.

    WANT != OFFER
    OFFER != ACCEPTANCE
    ACCEPTANCE != TREASURY AUTHORITY
    CAPACITY != AUTHORIZATION
    AUTHORIZATION != EXECUTION
    EXECUTION != VERIFIED RETURN
    SETTLEMENT != ADMISSION
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from ice_cube import ICE_CUBE_CAPABILITY
from ice_field import IceFieldStore
from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_authorization import (
    GuildAuthorizationStore,
    apply_execution_to_treasury,
    verify_resource_authorization,
)
from lightwalker_guild_treasury import verify_treasury_snapshot
from lightwalker_heterogeneous_exchange import (
    accept_exchange_offer,
    make_exchange_offer,
    make_obligation,
    settle_exchange,
    sign_obligation_performance,
    verify_exchange_acceptance,
    verify_exchange_offer,
)
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


COMMONS_KIND = "ghot.field-commons.exchange"
COMMONS_VERSION = "0"
GRANT_KIND = "ghot.field-commons.artifact-access-grant"
GRANT_VERSION = "0"
GRANT_DOMAIN = "ghot.field-commons-artifact-grant-signature/v0"
GRANT_BYTES = b"GHoT-FieldCommonsArtifactGrant-v0|"


def _safe(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(
            fd,
            (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
    finally:
        os.close(fd)


def _signed_grant_body(grant: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in grant.items()
        if key not in {"grant_id", "signing"}
    }


def _grant_signature_bytes(grant: dict[str, Any]) -> bytes:
    body = _signed_grant_body(grant)
    return GRANT_BYTES + canonical_bytes(
        {"grant_id": content_address(body), **body}
    )


def make_artifact_access_grant(
    *,
    owner: IdentityKey,
    grantee_particular: str,
    artifact_ref: str,
    offer_id: str,
    scope: str = "read-only",
) -> dict[str, Any]:
    if not artifact_ref or not grantee_particular or not offer_id:
        raise ValueError("artifact grant fields must be non-empty")
    body = {
        "kind": GRANT_KIND,
        "version": GRANT_VERSION,
        "authority": "owner-local-access-grant",
        "owner_particular": owner.particular(),
        "grantee_particular": grantee_particular,
        "artifact_ref": artifact_ref,
        "offer_id": offer_id,
        "scope": scope,
        "revocation": "outside-v0",
        "laws": [
            "ACCESS GRANT != OWNERSHIP",
            "ACCESS != ADMISSION",
            "GRANT != UNIVERSAL LICENSE",
        ],
    }
    grant_id = content_address(body)
    grant = {
        **body,
        "grant_id": grant_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": owner.public_jwk(),
            "signature": "",
            "domain": GRANT_DOMAIN,
        },
    }
    grant["signing"]["signature"] = owner.sign(_grant_signature_bytes(grant))
    return grant


def verify_artifact_access_grant(grant: dict[str, Any]) -> bool:
    try:
        if grant.get("kind") != GRANT_KIND or grant.get("version") != GRANT_VERSION:
            return False
        body = _signed_grant_body(grant)
        if grant.get("grant_id") != content_address(body):
            return False
        signing = grant.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM or signing.get("domain") != GRANT_DOMAIN:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != grant.get("owner_particular"):
            return False
        return verify_p256(
            public_key,
            _grant_signature_bytes(grant),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def make_artifact_for_compute_offer(
    *,
    artifact_owner: IdentityKey,
    guild_particular: str,
    artifact_ref: str,
    want: dict[str, Any],
    valid_through_cut: int,
) -> dict[str, Any]:
    if want.get("kind") != "ghot.ice-field.want":
        raise ValueError("Field Commons requires an Ice Field want")
    work = want.get("work")
    if not isinstance(work, dict):
        raise ValueError("Ice Field want has no work spec")
    render = work.get("render") or {}

    artifact_access = make_obligation(
        obligation_type="artifact-access",
        resource_ref=f"artifact:{artifact_ref}",
        terms={
            "scope": "read-only",
            "artifact_ref": artifact_ref,
            "revocation": "outside-v0",
        },
        evidence_policy="owner-signed-access-grant/v0",
    )
    compute_service = make_obligation(
        obligation_type="compute-service",
        resource_ref=f"ghot-capability:{ICE_CUBE_CAPABILITY}",
        terms={
            "want_id": want["want_id"],
            "work_address": want["work_address"],
            "work_family": work["family"],
            "requested_width": int(render.get("width", 96)),
            "requested_height": int(render.get("height", 96)),
            "verification": "Dogram OK on worker",
            "delivery": "receiver HOLD receipt",
        },
        evidence_policy="guild-execution-receipt+ghot-return-hold/v0",
    )
    return make_exchange_offer(
        offeror_particular=artifact_owner.particular(),
        offeror_obligation=artifact_access,
        acceptor_obligation=compute_service,
        orientation_refs=[
            want["want_id"],
            want["work_address"],
            artifact_ref,
        ],
        valid_through_cut=valid_through_cut,
    )


def accept_commons_offer(
    offer: dict[str, Any],
    *,
    guild: IdentityKey,
    accepted_at_cut: int,
) -> dict[str, Any]:
    return accept_exchange_offer(
        offer,
        acceptor_particular=guild.particular(),
        accepted_at_cut=accepted_at_cut,
    )


def _validate_commons_contract(
    *,
    want: dict[str, Any],
    offer: dict[str, Any],
    acceptance: dict[str, Any],
    treasury_snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    guild: IdentityKey,
    executor: IdentityKey,
) -> None:
    if want.get("kind") != "ghot.ice-field.want":
        raise LightwalkerEconomyError("invalid Ice Field want")
    if not verify_exchange_offer(offer):
        raise LightwalkerEconomyError("invalid heterogeneous Commons offer")
    if not verify_exchange_acceptance(offer, acceptance):
        raise LightwalkerEconomyError("invalid Commons acceptance")
    if acceptance["acceptor_particular"] != guild.particular():
        raise LightwalkerEconomyError("accepted compute provider is not this Guild")
    if not verify_treasury_snapshot(treasury_snapshot):
        raise LightwalkerEconomyError("invalid Guild treasury snapshot")
    if treasury_snapshot["steward_particular"] != guild.particular():
        raise LightwalkerEconomyError("Guild actor does not steward treasury")
    if not verify_resource_authorization(
        treasury_snapshot,
        proposal,
        authorization,
    ):
        raise LightwalkerEconomyError("invalid Guild compute authorization")
    if authorization["executor_particular"] != executor.particular():
        raise LightwalkerEconomyError("Commons executor is not Guild-authorized")
    if proposal["purpose_ref"] != want["want_id"]:
        raise LightwalkerEconomyError("Guild authorization purpose is not this WANT")
    if proposal["requested_measure"] != {
        "unit": "ice-cube-job",
        "quantity": 1,
    }:
        raise LightwalkerEconomyError(
            "Field Commons 001 requires exactly one ice-cube-job authorization"
        )

    offeror = offer["offeror_obligation"]
    acceptor = offer["acceptor_obligation"]
    if offeror["obligation_type"] != "artifact-access":
        raise LightwalkerEconomyError("Commons offeror obligation must be artifact-access")
    if acceptor["obligation_type"] != "compute-service":
        raise LightwalkerEconomyError("Commons acceptor obligation must be compute-service")
    terms = acceptor["terms"]
    if terms.get("want_id") != want["want_id"]:
        raise LightwalkerEconomyError("compute obligation WANT mismatch")
    if terms.get("work_address") != want["work_address"]:
        raise LightwalkerEconomyError("compute obligation work-address mismatch")
    if acceptor["resource_ref"] != f"ghot-capability:{ICE_CUBE_CAPABILITY}":
        raise LightwalkerEconomyError("compute obligation names wrong capability")


class FieldCommonsStore:
    """One-shot Commons execution gate keyed by Guild authorization."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.claims_dir = self.root / "field-commons" / "claims"
        self.records_dir = self.root / "field-commons" / "records"

    def _claim(self, authorization_id: str, want_id: str) -> None:
        claim = {
            "kind": "ghot.field-commons.execution-claim",
            "version": "0",
            "authorization_id": authorization_id,
            "want_id": want_id,
        }
        try:
            _atomic_json(
                self.claims_dir / f"{_safe(authorization_id)}.json",
                claim,
            )
        except FileExistsError as exc:
            raise LightwalkerEconomyError(
                "Commons authorization already claimed for an execution attempt"
            ) from exc

    def execute(
        self,
        *,
        field: IceFieldStore,
        want_id: str,
        offer: dict[str, Any],
        acceptance: dict[str, Any],
        artifact_owner: IdentityKey,
        guild: IdentityKey,
        treasury_snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        executor: IdentityKey,
        return_url: str,
        return_particular: str,
        observed_cut: int,
        timeout: float = 2.0,
        return_chunk_size: int | None = None,
    ) -> dict[str, Any]:
        want = field.load(want_id)
        _validate_commons_contract(
            want=want,
            offer=offer,
            acceptance=acceptance,
            treasury_snapshot=treasury_snapshot,
            proposal=proposal,
            authorization=authorization,
            guild=guild,
            executor=executor,
        )

        # Claim before scheduling so the same authorization cannot launch two
        # compute attempts even if callers race.
        self._claim(authorization["authorization_id"], want_id)

        dispatch = field.dispatch(
            want_id,
            return_url=return_url,
            return_particular=return_particular,
            timeout=timeout,
            return_chunk_size=return_chunk_size,
        )
        ok = dispatch.get("status") == "ok"
        output = (
            ((dispatch.get("execution") or {}).get("receipt") or {}).get("output")
            if ok
            else None
        )
        if ok and not isinstance(output, dict):
            ok = False

        compute_evidence = {
            "kind": "ghot.field-commons.compute-evidence",
            "version": "0",
            "want_id": want_id,
            "work_address": want["work_address"],
            "dispatch_status": dispatch.get("status"),
            "energy_plan_id": (dispatch.get("energy_plan") or {}).get("energy_plan_id"),
            "selected_node_id": (
                ((dispatch.get("energy_plan") or {}).get("selected") or {}).get("node_id")
            ),
            "worker_execution_receipt_id": (
                output.get("execution_receipt_id") if isinstance(output, dict) else None
            ),
            "worker_dogram_status": (
                output.get("dogram_status") if isinstance(output, dict) else None
            ),
            "return_receipt_id": (
                ((output.get("verified_return") or {}).get("receiver_receipt_id"))
                if isinstance(output, dict)
                else None
            ),
            "return_disposition": (
                ((output.get("verified_return") or {}).get("receiver_disposition"))
                if isinstance(output, dict)
                else None
            ),
        }
        compute_evidence_id = content_address(compute_evidence)

        guild_store = GuildAuthorizationStore(self.root)
        guild_execution = guild_store.execute(
            treasury_snapshot,
            proposal,
            authorization,
            executor=executor,
            observed_cut=observed_cut,
            simulate_success=ok,
            result_ref=compute_evidence_id if ok else None,
            error=None if ok else f"dispatch status: {dispatch.get('status')}",
        )
        next_treasury = apply_execution_to_treasury(
            treasury_snapshot,
            proposal,
            authorization,
            guild_execution,
            steward=guild,
        )

        if not ok:
            record = {
                "kind": COMMONS_KIND,
                "version": COMMONS_VERSION,
                "status": "FAILED",
                "want_id": want_id,
                "offer_id": offer["offer_id"],
                "acceptance_id": acceptance["acceptance_id"],
                "authorization_id": authorization["authorization_id"],
                "dispatch": dispatch,
                "compute_evidence": compute_evidence,
                "guild_execution": guild_execution,
                "treasury_snapshot_after": next_treasury,
                "settlement": None,
            }
            record["commons_id"] = content_address(record)
            _atomic_json(
                self.records_dir / f"{_safe(record['commons_id'])}.json",
                record,
            )
            return record

        if output.get("dogram_status") != "OK":
            raise RuntimeError("successful dispatch lacked worker Dogram OK")
        returned = output.get("verified_return") or {}
        if returned.get("receiver_disposition") != "HELD":
            raise RuntimeError("successful Commons compute did not return as HOLD")
        if returned.get("receiver_semantic_effect") != "none":
            raise RuntimeError("returned Commons compute gained semantic effect in transport")

        artifact_ref = str(offer["offeror_obligation"]["terms"]["artifact_ref"])
        grant = make_artifact_access_grant(
            owner=artifact_owner,
            grantee_particular=guild.particular(),
            artifact_ref=artifact_ref,
            offer_id=offer["offer_id"],
        )
        if not verify_artifact_access_grant(grant):
            raise RuntimeError("new artifact access grant failed verification")

        offeror_performance = sign_obligation_performance(
            offer,
            acceptance,
            role="OFFEROR",
            signer=artifact_owner,
            evidence_ref=grant["grant_id"],
        )
        acceptor_performance = sign_obligation_performance(
            offer,
            acceptance,
            role="ACCEPTOR",
            signer=guild,
            evidence_ref=guild_execution["execution_receipt_id"],
        )
        settlement = settle_exchange(
            offer,
            acceptance,
            [offeror_performance, acceptor_performance],
        )

        record = {
            "kind": COMMONS_KIND,
            "version": COMMONS_VERSION,
            "status": "SETTLED",
            "authority": "bilateral-evidence-only",
            "want_id": want_id,
            "work_address": want["work_address"],
            "offer": offer,
            "acceptance": acceptance,
            "artifact_access_grant": grant,
            "compute_evidence": compute_evidence,
            "guild_authorization_id": authorization["authorization_id"],
            "guild_execution": guild_execution,
            "treasury_snapshot_before": treasury_snapshot,
            "treasury_snapshot_after": next_treasury,
            "offeror_performance": offeror_performance,
            "acceptor_performance": acceptor_performance,
            "settlement": settlement,
            "dispatch": dispatch,
            "laws": [
                "COMMONS != CURRENCY",
                "SETTLEMENT != ADMISSION",
                "GUILD AUTHORIZATION != DOGRAM VERIFICATION",
                "WORKER VERIFICATION != RECEIVER VERIFICATION",
            ],
        }
        record["commons_id"] = content_address(record)
        _atomic_json(
            self.records_dir / f"{_safe(record['commons_id'])}.json",
            record,
        )
        return record


__all__ = [
    "FieldCommonsStore",
    "accept_commons_offer",
    "make_artifact_access_grant",
    "make_artifact_for_compute_offer",
    "verify_artifact_access_grant",
]
