#!/usr/bin/env python3
"""Lightwalker Reservation / Concurrency 001.

This layer closes the first double-spend-shaped aperture in Guild economics.

A visible treasury capacity can support multiple proposals, but active
reservations reduce what remains authorizable.

Core laws:
    VISIBLE CAPACITY != UNENCUMBERED CAPACITY
    AUTHORIZATION != RESERVATION
    RESERVATION != CONSUMPTION
    RELEASE != EXECUTION
    RELEASED RESERVATION INVALIDATES RESERVED EXECUTION
    ACTIVE RESERVATIONS MAY NOT EXCEED VISIBLE CAPACITY
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from lightwalker_economy import (
    LightwalkerEconomyError,
    canonical_bytes,
    content_address,
)
from lightwalker_guild_authorization import (
    GuildAuthorizationStore,
    authorize_resource_proposal,
    verify_execution_receipt,
    verify_resource_authorization,
    verify_resource_proposal,
)
from lightwalker_guild_treasury import verify_treasury_snapshot
from relatte_identity import (
    ALGORITHM,
    IdentityKey,
    particular_for_public_key,
    verify_p256,
)


RESERVATION_KIND = "ghot.lightwalker.guild-resource-reservation"
RESERVATION_VERSION = "0"
FINALIZATION_KIND = "ghot.lightwalker.guild-resource-reservation-finalization"
FINALIZATION_VERSION = "0"

RESERVATION_DOMAIN = "ghot.lightwalker-guild-resource-reservation-signature/v0"
FINALIZATION_DOMAIN = "ghot.lightwalker-guild-resource-reservation-finalization-signature/v0"
RESERVATION_BYTES = b"GHOT-LightwalkerGuildResourceReservation-v0|"
FINALIZATION_BYTES = b"GHOT-LightwalkerGuildResourceReservationFinalization-v0|"

FINAL_STATUSES = {"CONSUMED", "RELEASED"}


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LightwalkerEconomyError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LightwalkerEconomyError(f"{name} must be a non-negative integer")
    return value


def _signed(
    body: dict[str, Any],
    *,
    id_field: str,
    signer: IdentityKey,
    domain: str,
    byte_domain: bytes,
) -> dict[str, Any]:
    item_id = content_address(body)
    value = {
        **body,
        id_field: item_id,
        "signing": {
            "algorithm": ALGORITHM,
            "public_key": signer.public_jwk(),
            "signature": "",
            "domain": domain,
        },
    }
    value["signing"]["signature"] = signer.sign(
        byte_domain + canonical_bytes({id_field: item_id, **body})
    )
    return value


def _verify_signed(
    value: dict[str, Any],
    *,
    id_field: str,
    particular_field: str,
    domain: str,
    byte_domain: bytes,
) -> bool:
    try:
        signing = value.get("signing")
        if not isinstance(signing, dict):
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != domain:
            return False
        public_key = signing.get("public_key")
        if particular_for_public_key(public_key) != value.get(particular_field):
            return False
        body = {
            key: item
            for key, item in value.items()
            if key not in {id_field, "signing"}
        }
        item_id = value.get(id_field)
        if not isinstance(item_id, str) or content_address(body) != item_id:
            return False
        return verify_p256(
            public_key,
            byte_domain + canonical_bytes({id_field: item_id, **body}),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def _resource_entry(snapshot: dict[str, Any], entry_id: str) -> dict[str, Any]:
    if not verify_treasury_snapshot(snapshot):
        raise LightwalkerEconomyError("invalid treasury snapshot")
    for entry in snapshot["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise LightwalkerEconomyError("resource entry not found")


def verify_reservation(
    snapshot: dict[str, Any],
    proposal: dict[str, Any],
    authorization: dict[str, Any],
    reservation: dict[str, Any],
) -> bool:
    try:
        if not verify_resource_authorization(snapshot, proposal, authorization):
            return False
        if reservation.get("kind") != RESERVATION_KIND:
            return False
        if reservation.get("version") != RESERVATION_VERSION:
            return False
        if reservation.get("authority") != "guild-local-capacity-reservation":
            return False
        if reservation.get("guild_id") != snapshot["guild_id"]:
            return False
        if reservation.get("snapshot_id") != snapshot["snapshot_id"]:
            return False
        if reservation.get("proposal_id") != proposal["proposal_id"]:
            return False
        if reservation.get("authorization_id") != authorization["authorization_id"]:
            return False
        if reservation.get("resource_entry_id") != proposal["resource_entry_id"]:
            return False
        if reservation.get("reserved_measure") != authorization["authorized_measure"]:
            return False
        if reservation.get("steward_particular") != snapshot["steward_particular"]:
            return False
        if reservation.get("status") != "ACTIVE":
            return False
        return _verify_signed(
            reservation,
            id_field="reservation_id",
            particular_field="steward_particular",
            domain=RESERVATION_DOMAIN,
            byte_domain=RESERVATION_BYTES,
        )
    except Exception:
        return False


def verify_finalization(
    reservation: dict[str, Any],
    finalization: dict[str, Any],
) -> bool:
    try:
        if not isinstance(finalization, dict):
            return False
        if finalization.get("kind") != FINALIZATION_KIND:
            return False
        if finalization.get("version") != FINALIZATION_VERSION:
            return False
        if finalization.get("reservation_id") != reservation["reservation_id"]:
            return False
        if finalization.get("authorization_id") != reservation["authorization_id"]:
            return False
        if finalization.get("snapshot_id") != reservation["snapshot_id"]:
            return False
        if finalization.get("resource_entry_id") != reservation["resource_entry_id"]:
            return False
        if finalization.get("steward_particular") != reservation["steward_particular"]:
            return False
        if finalization.get("status") not in FINAL_STATUSES:
            return False
        if finalization.get("status") == "CONSUMED":
            if finalization.get("released_measure") is not None:
                return False
            if finalization.get("consumed_measure") != reservation["reserved_measure"]:
                return False
        if finalization.get("status") == "RELEASED":
            if finalization.get("consumed_measure") is not None:
                return False
            if finalization.get("released_measure") != reservation["reserved_measure"]:
                return False
        return _verify_signed(
            finalization,
            id_field="finalization_id",
            particular_field="steward_particular",
            domain=FINALIZATION_DOMAIN,
            byte_domain=FINALIZATION_BYTES,
        )
    except Exception:
        return False


class GuildReservationStore:
    """Steward-local atomic reservation ledger.

    Reservation creation is serialized under one file lock so two proposals
    against the same visible snapshot cannot both reserve overlapping capacity.
    """

    def __init__(self, root: Path, *, steward: IdentityKey) -> None:
        self.root = root
        self.steward = steward
        self.reservations_dir = root / "guild-reservations" / "active"
        self.finalizations_dir = root / "guild-reservations" / "finalizations"
        self.lock_path = root / "guild-reservations" / "ledger.lock"
        self.execution_store = GuildAuthorizationStore(
            root / "guild-reservations" / "executions"
        )

    def _safe(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _reservation_path(self, reservation_id: str) -> Path:
        return self.reservations_dir / f"{self._safe(reservation_id)}.json"

    def _finalization_path(self, reservation_id: str) -> Path:
        return self.finalizations_dir / f"{self._safe(reservation_id)}.json"

    def _write_exclusive(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(
                fd,
                (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            )
        finally:
            os.close(fd)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load_finalization(self, reservation_id: str) -> dict[str, Any] | None:
        path = self._finalization_path(reservation_id)
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError("invalid reservation finalization file")
        return value

    def _load_reservation(self, path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise LightwalkerEconomyError("invalid reservation file")
        return value

    def _active_reservations(
        self,
        snapshot_id: str,
        resource_entry_id: str,
    ) -> list[dict[str, Any]]:
        if not self.reservations_dir.exists():
            return []
        active: list[dict[str, Any]] = []
        for path in self.reservations_dir.glob("*.json"):
            reservation = self._load_reservation(path)
            if reservation.get("snapshot_id") != snapshot_id:
                continue
            if reservation.get("resource_entry_id") != resource_entry_id:
                continue
            if self._load_finalization(str(reservation["reservation_id"])) is None:
                active.append(reservation)
        return active

    def capacity_state(
        self,
        snapshot: dict[str, Any],
        resource_entry_id: str,
    ) -> dict[str, Any]:
        entry = _resource_entry(snapshot, resource_entry_id)
        measure = entry.get("native_measure")
        if not isinstance(measure, dict):
            raise LightwalkerEconomyError("resource has no native measure")
        with self._locked():
            active = self._active_reservations(
                snapshot["snapshot_id"],
                resource_entry_id,
            )
            reserved = sum(
                int(item["reserved_measure"]["quantity"])
                for item in active
            )
            visible = int(measure["quantity"])
            return {
                "snapshot_id": snapshot["snapshot_id"],
                "resource_entry_id": resource_entry_id,
                "unit": measure["unit"],
                "visible_quantity": visible,
                "reserved_quantity": reserved,
                "unencumbered_quantity": visible - reserved,
                "active_reservation_ids": sorted(
                    item["reservation_id"] for item in active
                ),
            }

    def reserve_and_authorize(
        self,
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        *,
        executor_particular: str,
        authorized_at_cut: int,
        expires_after_cut: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not verify_resource_proposal(snapshot, proposal):
            raise LightwalkerEconomyError("invalid resource proposal")
        if self.steward.particular() != snapshot["steward_particular"]:
            raise LightwalkerEconomyError("local steward does not own treasury")

        entry = _resource_entry(snapshot, proposal["resource_entry_id"])
        measure = entry.get("native_measure")
        if not isinstance(measure, dict):
            raise LightwalkerEconomyError("resource has no native measure")
        requested = proposal["requested_measure"]
        if requested["unit"] != measure["unit"]:
            raise LightwalkerEconomyError("reservation unit mismatch")

        with self._locked():
            active = self._active_reservations(
                snapshot["snapshot_id"],
                proposal["resource_entry_id"],
            )
            reserved = sum(
                int(item["reserved_measure"]["quantity"])
                for item in active
            )
            visible = int(measure["quantity"])
            unencumbered = visible - reserved
            quantity = int(requested["quantity"])
            if quantity > unencumbered:
                raise LightwalkerEconomyError(
                    "proposal exceeds unencumbered treasury capacity"
                )

            authorization = authorize_resource_proposal(
                snapshot,
                proposal,
                steward=self.steward,
                executor_particular=executor_particular,
                authorized_at_cut=authorized_at_cut,
                expires_after_cut=expires_after_cut,
            )
            body = {
                "kind": RESERVATION_KIND,
                "version": RESERVATION_VERSION,
                "authority": "guild-local-capacity-reservation",
                "guild_id": snapshot["guild_id"],
                "snapshot_id": snapshot["snapshot_id"],
                "proposal_id": proposal["proposal_id"],
                "authorization_id": authorization["authorization_id"],
                "resource_entry_id": proposal["resource_entry_id"],
                "resource_subject_ref": proposal["resource_subject_ref"],
                "steward_particular": self.steward.particular(),
                "reserved_measure": authorization["authorized_measure"],
                "authorized_at_cut": authorization["authorized_at_cut"],
                "expires_after_cut": authorization["expires_after_cut"],
                "status": "ACTIVE",
                "laws": [
                    "VISIBLE CAPACITY != UNENCUMBERED CAPACITY",
                    "AUTHORIZATION != RESERVATION",
                    "RESERVATION != CONSUMPTION",
                ],
            }
            reservation = _signed(
                body,
                id_field="reservation_id",
                signer=self.steward,
                domain=RESERVATION_DOMAIN,
                byte_domain=RESERVATION_BYTES,
            )
            self._write_exclusive(
                self._reservation_path(reservation["reservation_id"]),
                reservation,
            )
            return authorization, reservation

    def _finalize(
        self,
        reservation: dict[str, Any],
        *,
        status: str,
        reason: str,
        observed_cut: int,
        execution_receipt_id: str | None = None,
    ) -> dict[str, Any]:
        if status not in FINAL_STATUSES:
            raise LightwalkerEconomyError("unsupported reservation final status")
        cut = _nonnegative_int(observed_cut, "observed_cut")
        body = {
            "kind": FINALIZATION_KIND,
            "version": FINALIZATION_VERSION,
            "reservation_id": reservation["reservation_id"],
            "authorization_id": reservation["authorization_id"],
            "snapshot_id": reservation["snapshot_id"],
            "resource_entry_id": reservation["resource_entry_id"],
            "steward_particular": self.steward.particular(),
            "status": status,
            "reason": _nonempty(reason, "reason"),
            "observed_cut": cut,
            "execution_receipt_id": execution_receipt_id,
            "consumed_measure": (
                reservation["reserved_measure"]
                if status == "CONSUMED"
                else None
            ),
            "released_measure": (
                reservation["reserved_measure"]
                if status == "RELEASED"
                else None
            ),
            "laws": [
                "RESERVATION != CONSUMPTION",
                "RELEASE != EXECUTION",
                "FINALIZATION DOES NOT REWRITE RESERVATION",
            ],
        }
        value = _signed(
            body,
            id_field="finalization_id",
            signer=self.steward,
            domain=FINALIZATION_DOMAIN,
            byte_domain=FINALIZATION_BYTES,
        )
        self._write_exclusive(
            self._finalization_path(reservation["reservation_id"]),
            value,
        )
        return value

    def release(
        self,
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        reservation: dict[str, Any],
        *,
        observed_cut: int,
        reason: str,
    ) -> dict[str, Any]:
        if not verify_reservation(
            snapshot, proposal, authorization, reservation
        ):
            raise LightwalkerEconomyError("invalid reservation")
        if self.steward.particular() != reservation["steward_particular"]:
            raise LightwalkerEconomyError("local steward does not own reservation")
        with self._locked():
            if self._load_finalization(reservation["reservation_id"]) is not None:
                raise LightwalkerEconomyError("reservation already finalized")
            return self._finalize(
                reservation,
                status="RELEASED",
                reason=reason,
                observed_cut=observed_cut,
            )

    def release_expired(
        self,
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        reservation: dict[str, Any],
        *,
        observed_cut: int,
    ) -> dict[str, Any]:
        cut = _nonnegative_int(observed_cut, "observed_cut")
        if cut <= int(authorization["expires_after_cut"]):
            raise LightwalkerEconomyError("authorization has not expired")
        return self.release(
            snapshot,
            proposal,
            authorization,
            reservation,
            observed_cut=cut,
            reason="AUTHORIZATION_EXPIRED",
        )

    def execute_reserved(
        self,
        snapshot: dict[str, Any],
        proposal: dict[str, Any],
        authorization: dict[str, Any],
        reservation: dict[str, Any],
        *,
        executor: IdentityKey,
        observed_cut: int,
        simulate_success: bool,
        result_ref: str | None = None,
        error: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not verify_reservation(
            snapshot, proposal, authorization, reservation
        ):
            raise LightwalkerEconomyError("invalid reservation")

        with self._locked():
            existing = self._load_finalization(reservation["reservation_id"])
            if existing is not None:
                raise LightwalkerEconomyError(
                    "reservation is finalized and cannot authorize execution"
                )

            receipt = self.execution_store.execute(
                snapshot,
                proposal,
                authorization,
                executor=executor,
                observed_cut=observed_cut,
                simulate_success=simulate_success,
                result_ref=result_ref,
                error=error,
            )
            if not verify_execution_receipt(
                snapshot, proposal, authorization, receipt
            ):
                raise LightwalkerEconomyError("invalid execution receipt")

            if receipt["success"]:
                finalization = self._finalize(
                    reservation,
                    status="CONSUMED",
                    reason="EXECUTION_SUCCEEDED",
                    observed_cut=observed_cut,
                    execution_receipt_id=receipt["execution_receipt_id"],
                )
            else:
                finalization = self._finalize(
                    reservation,
                    status="RELEASED",
                    reason="EXECUTION_FAILED",
                    observed_cut=observed_cut,
                    execution_receipt_id=receipt["execution_receipt_id"],
                )
            return receipt, finalization


__all__ = [
    "GuildReservationStore",
    "verify_finalization",
    "verify_reservation",
]
