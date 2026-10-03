#!/usr/bin/env python3
"""One-operation activation tickets — Experiment 028.

Flow:
    typed launch descriptor
      -> destination preflight READY
      -> explicit local ACT
      -> short-lived BODY-signed one-operation ticket
      -> atomic claim
      -> destination preflight AGAIN
      -> exactly one owning-subsystem operation attempt
      -> BODY-signed execution receipt

The BODY signature witnesses the local activation artifact. It does not prove a
human identity.

Laws:
    READINESS != CONSENT
    CONSENT TICKET != BLANKET AUTHORITY
    ONE ACTION != SESSION AUTHORITY
    EXECUTION != SUCCESS
    BODY SIGNATURE != HUMAN IDENTITY
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from composition_want import CompositionWantStore, collect_observations
from curious_doors import ReadOnlyCuriosityStore
from launch_descriptor import (
    APP_COMPOSITION_WANTS,
    APP_MERGE_PANTRY,
    APP_PLUGIN_PARCEL,
    verify_launch_descriptor,
)
from launch_preflight import preflight_launch
from merge_plugin_parcel import MergePluginParcelInbox
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


TICKET_KIND = "ghot.activation.ticket"
TICKET_VERSION = "0"
TICKET_DOMAIN = "ghot.activation-ticket-signature/v0"
TICKET_BYTES_DOMAIN = b"GHoT-ActivationTicket-v0|"
TICKET_ID_DOMAIN = b"GHoT-ActivationTicketId-v0|"

RECEIPT_KIND = "ghot.activation.execution-receipt"
RECEIPT_VERSION = "0"
RECEIPT_DOMAIN = "ghot.activation-execution-receipt-signature/v0"
RECEIPT_BYTES_DOMAIN = b"GHoT-ActivationExecutionReceipt-v0|"
RECEIPT_ID_DOMAIN = b"GHoT-ActivationExecutionReceiptId-v0|"

DEFAULT_TTL_SECONDS = 120
MAX_TTL_SECONDS = 600
CONSENT_PHRASE = "ACT"

FINAL_STATUSES = {
    "EXECUTED",
    "FAILED",
    "REFUSED_STALE",
    "REFUSED_PROPOSAL_CHANGED",
}


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


def _epoch(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc).timestamp()


def _proposal_address(proposal: dict[str, Any]) -> str:
    return semantic_address(identity_safe(proposal))


def _descriptor_address(descriptor: dict[str, Any]) -> str:
    return semantic_address(identity_safe(descriptor))


def _ticket_body(ticket: dict[str, Any]) -> dict[str, Any]:
    signing = ticket.get("signing") or {}
    return identity_safe({
        "kind": ticket.get("kind"),
        "version": ticket.get("version"),
        "nonce": ticket.get("nonce"),
        "launch_id": ticket.get("launch_id"),
        "descriptor": ticket.get("descriptor"),
        "descriptor_address": ticket.get("descriptor_address"),
        "proposal_address": ticket.get("proposal_address"),
        "destination": ticket.get("destination"),
        "issued_at": ticket.get("issued_at"),
        "ttl_seconds": ticket.get("ttl_seconds"),
        "one_operation": ticket.get("one_operation"),
        "consent_mode": ticket.get("consent_mode"),
        "human_identity_proven": ticket.get("human_identity_proven"),
        "issuer_particular": ticket.get("issuer_particular"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    })


def derive_ticket_id(ticket: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        TICKET_ID_DOMAIN + jcs_bytes(_ticket_body(ticket))
    ).hexdigest()
    return "ghot-activation-ticket-v0:" + digest


def ticket_signature_bytes(ticket: dict[str, Any]) -> bytes:
    return TICKET_BYTES_DOMAIN + jcs_bytes({
        "ticket_id": derive_ticket_id(ticket),
        **_ticket_body(ticket),
    })


def verify_activation_ticket(ticket: dict[str, Any]) -> bool:
    try:
        if ticket.get("kind") != TICKET_KIND:
            return False
        if ticket.get("version") != TICKET_VERSION:
            return False
        if ticket.get("ticket_id") != derive_ticket_id(ticket):
            return False
        if ticket.get("one_operation") is not True:
            return False
        if ticket.get("consent_mode") != "explicit-local-ACT":
            return False
        if ticket.get("human_identity_proven") is not False:
            return False

        ttl = int(ticket.get("ttl_seconds") or 0)
        if ttl <= 0 or ttl > MAX_TTL_SECONDS:
            return False

        descriptor = ticket.get("descriptor")
        if not isinstance(descriptor, dict):
            return False
        if not verify_launch_descriptor(descriptor):
            return False
        if ticket.get("launch_id") != descriptor.get("launch_id"):
            return False
        if ticket.get("descriptor_address") != _descriptor_address(descriptor):
            return False
        if ticket.get("destination") != descriptor.get("destination"):
            return False

        proposal_address = ticket.get("proposal_address")
        if (
            not isinstance(proposal_address, str)
            or not proposal_address.startswith("sha256:")
        ):
            return False

        signing = ticket.get("signing") or {}
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != TICKET_DOMAIN:
            return False
        public_key = signing.get("public_key") or {}
        if (
            ticket.get("issuer_particular")
            != particular_for_public_key(public_key)
        ):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            ticket_signature_bytes(ticket),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


def ticket_is_fresh(
    ticket: dict[str, Any],
    *,
    at: float | None = None,
) -> bool:
    try:
        if not verify_activation_ticket(ticket):
            return False
        issued = _epoch(str(ticket["issued_at"]))
        now = time.time() if at is None else float(at)
        ttl = int(ticket["ttl_seconds"])
        return issued - 5.0 <= now <= issued + ttl
    except Exception:
        return False


def _receipt_body(receipt: dict[str, Any]) -> dict[str, Any]:
    signing = receipt.get("signing") or {}
    return identity_safe({
        "kind": receipt.get("kind"),
        "version": receipt.get("version"),
        "ticket_id": receipt.get("ticket_id"),
        "launch_id": receipt.get("launch_id"),
        "destination": receipt.get("destination"),
        "status": receipt.get("status"),
        "started_at": receipt.get("started_at"),
        "completed_at": receipt.get("completed_at"),
        "proposal_address": receipt.get("proposal_address"),
        "execution_preflight_status": receipt.get(
            "execution_preflight_status"
        ),
        "execution_preflight_proposal_address": receipt.get(
            "execution_preflight_proposal_address"
        ),
        "result_address": receipt.get("result_address"),
        "error": receipt.get("error"),
        "ticket_spent": receipt.get("ticket_spent"),
        "operation_attempted": receipt.get("operation_attempted"),
        "success": receipt.get("success"),
        "issuer_particular": receipt.get("issuer_particular"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": signing.get("public_key"),
            "domain": signing.get("domain"),
        },
    })


def derive_execution_receipt_id(receipt: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        RECEIPT_ID_DOMAIN + jcs_bytes(_receipt_body(receipt))
    ).hexdigest()
    return "ghot-activation-execution-receipt-v0:" + digest


def execution_receipt_signature_bytes(
    receipt: dict[str, Any],
) -> bytes:
    return RECEIPT_BYTES_DOMAIN + jcs_bytes({
        "receipt_id": derive_execution_receipt_id(receipt),
        **_receipt_body(receipt),
    })


def verify_execution_receipt(receipt: dict[str, Any]) -> bool:
    try:
        if receipt.get("kind") != RECEIPT_KIND:
            return False
        if receipt.get("version") != RECEIPT_VERSION:
            return False
        if (
            receipt.get("receipt_id")
            != derive_execution_receipt_id(receipt)
        ):
            return False
        if receipt.get("status") not in FINAL_STATUSES:
            return False
        if receipt.get("ticket_spent") is not True:
            return False

        signing = receipt.get("signing") or {}
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != RECEIPT_DOMAIN:
            return False
        public_key = signing.get("public_key") or {}
        if (
            receipt.get("issuer_particular")
            != particular_for_public_key(public_key)
        ):
            return False
        raw = unb64url(str(signing.get("signature") or ""))
        if len(raw) != 64:
            return False
        return verify_p256(
            public_key,
            execution_receipt_signature_bytes(receipt),
            str(signing.get("signature") or ""),
        )
    except Exception:
        return False


class ActivationStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.base = self.root / "activation-tickets"
        self.tickets_dir = self.base / "tickets"
        self.claims_dir = self.base / "claims"
        self.receipts_dir = self.base / "receipts"
        self.results_dir = self.base / "results"
        self.signer = IdentityKey.load_or_create(
            self.root / "identity" / "body-p256.pem"
        )

    def _ticket_path(self, ticket_id: str) -> Path:
        return self.tickets_dir / f"{_safe_name(ticket_id)}.json"

    def _claim_path(self, ticket_id: str) -> Path:
        return self.claims_dir / f"{_safe_name(ticket_id)}.json"

    def _receipt_path(self, ticket_id: str) -> Path:
        return self.receipts_dir / f"{_safe_name(ticket_id)}.json"

    def _result_path(self, ticket_id: str) -> Path:
        return self.results_dir / f"{_safe_name(ticket_id)}.json"

    def issue(
        self,
        descriptor: dict[str, Any],
        *,
        consent_phrase: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> dict[str, Any]:
        if consent_phrase != CONSENT_PHRASE:
            raise ValueError(
                f"explicit consent phrase must be exactly {CONSENT_PHRASE}"
            )
        if not verify_launch_descriptor(descriptor):
            raise ValueError("launch descriptor failed verification")
        ttl = int(ttl_seconds)
        if ttl <= 0 or ttl > MAX_TTL_SECONDS:
            raise ValueError(
                f"ttl_seconds must be between 1 and {MAX_TTL_SECONDS}"
            )

        preflight = preflight_launch(descriptor, root=self.root)
        if preflight.get("status") != "ready":
            raise ValueError(
                "launch must preflight READY before ACT: "
                + str(preflight.get("status"))
            )
        proposal = preflight.get("proposal")
        if not isinstance(proposal, dict):
            raise ValueError("ready preflight did not produce a proposal")

        ticket = {
            "kind": TICKET_KIND,
            "version": TICKET_VERSION,
            "ticket_id": "",
            "nonce": f"activation-{uuid.uuid4()}",
            "launch_id": descriptor["launch_id"],
            "descriptor": descriptor,
            "descriptor_address": _descriptor_address(descriptor),
            "proposal_address": _proposal_address(proposal),
            "destination": descriptor["destination"],
            "issued_at": timestamp_now(),
            "ttl_seconds": ttl,
            "one_operation": True,
            "consent_mode": "explicit-local-ACT",
            "human_identity_proven": False,
            "issuer_particular": self.signer.particular(),
            "signing": {
                "algorithm": ALGORITHM,
                "public_key": self.signer.public_jwk(),
                "signature": "",
                "domain": TICKET_DOMAIN,
            },
        }
        ticket["ticket_id"] = derive_ticket_id(ticket)
        ticket["signing"]["signature"] = self.signer.sign(
            ticket_signature_bytes(ticket)
        )
        if not verify_activation_ticket(ticket):
            raise RuntimeError("new activation ticket failed verification")
        _write_atomic(self._ticket_path(ticket["ticket_id"]), ticket)
        return {
            "ticket": ticket,
            "preflight": preflight,
        }

    def load_ticket(self, ticket_id: str) -> dict[str, Any]:
        path = self._ticket_path(ticket_id)
        if not path.exists():
            raise ValueError("unknown activation ticket")
        ticket = _read_object(path)
        if not verify_activation_ticket(ticket):
            raise ValueError("stored activation ticket failed verification")
        return ticket

    def _claim(
        self,
        ticket: dict[str, Any],
    ) -> dict[str, Any]:
        ticket_id = str(ticket["ticket_id"])
        path = self._claim_path(ticket_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        claim = identity_safe({
            "kind": "ghot.activation.claim",
            "version": "0",
            "ticket_id": ticket_id,
            "launch_id": ticket["launch_id"],
            "claimed_at": timestamp_now(),
            "one_operation": True,
        })
        raw = (
            json.dumps(claim, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError as exc:
            raise ValueError("activation ticket already spent") from exc
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        return claim

    def _sign_receipt(
        self,
        *,
        ticket: dict[str, Any],
        status: str,
        started_at: str,
        proposal_address: str,
        execution_preflight_status: str | None,
        execution_preflight_proposal_address: str | None,
        result_address: str | None,
        error: dict[str, Any] | None,
        operation_attempted: bool,
        success: bool,
    ) -> dict[str, Any]:
        receipt = {
            "kind": RECEIPT_KIND,
            "version": RECEIPT_VERSION,
            "receipt_id": "",
            "ticket_id": ticket["ticket_id"],
            "launch_id": ticket["launch_id"],
            "destination": ticket["destination"],
            "status": status,
            "started_at": started_at,
            "completed_at": timestamp_now(),
            "proposal_address": proposal_address,
            "execution_preflight_status": execution_preflight_status,
            "execution_preflight_proposal_address": (
                execution_preflight_proposal_address
            ),
            "result_address": result_address,
            "error": error,
            "ticket_spent": True,
            "operation_attempted": operation_attempted,
            "success": success,
            "issuer_particular": self.signer.particular(),
            "signing": {
                "algorithm": ALGORITHM,
                "public_key": self.signer.public_jwk(),
                "signature": "",
                "domain": RECEIPT_DOMAIN,
            },
        }
        receipt["receipt_id"] = derive_execution_receipt_id(receipt)
        receipt["signing"]["signature"] = self.signer.sign(
            execution_receipt_signature_bytes(receipt)
        )
        if not verify_execution_receipt(receipt):
            raise RuntimeError("execution receipt failed verification")
        _write_atomic(self._receipt_path(ticket["ticket_id"]), receipt)
        return receipt

    def _dispatch(
        self,
        descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        destination = descriptor["destination"]
        context = descriptor["context"]
        app_id = str(destination["app_id"])
        operation = str(destination["operation"])

        if app_id == APP_COMPOSITION_WANTS:
            want_id = str(context.get("want_id") or "")
            if operation == "show-want":
                store = ReadOnlyCuriosityStore(self.root)
                want = store.load_want(want_id)
                return {
                    "want": want,
                    "observations": store.observations(want_id=want_id),
                    "request_links": store.request_links(want_id=want_id),
                    "current_local_inspection": store.inspect(
                        str(want["parcel_id"])
                    ),
                }

            store = CompositionWantStore(self.root)
            if operation == "refresh-candidates":
                observations = collect_observations(scan=True)
                return store.refresh(
                    want_id,
                    observations=observations,
                )
            if operation == "request-candidate":
                candidate_id = str(context.get("candidate_id") or "")
                return store.request_candidate(
                    want_id,
                    candidate_id,
                )
            raise ValueError("unsupported Composition Wants activation")

        if app_id == APP_PLUGIN_PARCEL:
            parcel_id = str(context.get("plugin_parcel_id") or "")
            inbox = MergePluginParcelInbox(self.root)
            if operation == "show-parcel":
                return inbox.show(parcel_id)
            if operation == "validate-parcel":
                return inbox.validate_local(parcel_id)
            if operation == "install-parcel":
                return inbox.install_local(
                    parcel_id,
                    note=(
                        "installed via one-operation 028 activation ticket"
                    ),
                )
            raise ValueError("unsupported plugin parcel activation")

        if app_id == APP_MERGE_PANTRY:
            if operation != "inspect-parcel":
                raise ValueError("unsupported merge pantry activation")
            parcel_id = str(context.get("parcel_id") or "")
            return ReadOnlyCuriosityStore(self.root).inspect(parcel_id)

        raise ValueError("unknown activation destination app")

    def execute(self, ticket_id: str) -> dict[str, Any]:
        ticket = self.load_ticket(ticket_id)
        if not ticket_is_fresh(ticket):
            raise ValueError("activation ticket expired")

        started_at = timestamp_now()
        self._claim(ticket)

        descriptor = ticket["descriptor"]
        preflight = preflight_launch(descriptor, root=self.root)
        status = str(preflight.get("status") or "blocked")
        proposal = preflight.get("proposal")
        current_proposal_address = (
            _proposal_address(proposal)
            if isinstance(proposal, dict)
            else None
        )

        if status != "ready":
            receipt = self._sign_receipt(
                ticket=ticket,
                status="REFUSED_STALE",
                started_at=started_at,
                proposal_address=ticket["proposal_address"],
                execution_preflight_status=status,
                execution_preflight_proposal_address=(
                    current_proposal_address
                ),
                result_address=None,
                error={
                    "type": "StaleActivationContext",
                    "message": str(preflight.get("note") or status),
                },
                operation_attempted=False,
                success=False,
            )
            return {
                "ticket": ticket,
                "execution_preflight": preflight,
                "receipt": receipt,
                "result": None,
            }

        if current_proposal_address != ticket["proposal_address"]:
            receipt = self._sign_receipt(
                ticket=ticket,
                status="REFUSED_PROPOSAL_CHANGED",
                started_at=started_at,
                proposal_address=ticket["proposal_address"],
                execution_preflight_status=status,
                execution_preflight_proposal_address=(
                    current_proposal_address
                ),
                result_address=None,
                error={
                    "type": "ProposalChanged",
                    "message": (
                        "fresh destination proposal differs from consented "
                        "proposal"
                    ),
                },
                operation_attempted=False,
                success=False,
            )
            return {
                "ticket": ticket,
                "execution_preflight": preflight,
                "receipt": receipt,
                "result": None,
            }

        try:
            result = identity_safe(self._dispatch(descriptor))
            result_address = semantic_address(result)
            _write_atomic(self._result_path(ticket_id), result)
            receipt = self._sign_receipt(
                ticket=ticket,
                status="EXECUTED",
                started_at=started_at,
                proposal_address=ticket["proposal_address"],
                execution_preflight_status=status,
                execution_preflight_proposal_address=(
                    current_proposal_address
                ),
                result_address=result_address,
                error=None,
                operation_attempted=True,
                success=True,
            )
            return {
                "ticket": ticket,
                "execution_preflight": preflight,
                "receipt": receipt,
                "result": result,
            }
        except Exception as exc:
            receipt = self._sign_receipt(
                ticket=ticket,
                status="FAILED",
                started_at=started_at,
                proposal_address=ticket["proposal_address"],
                execution_preflight_status=status,
                execution_preflight_proposal_address=(
                    current_proposal_address
                ),
                result_address=None,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
                operation_attempted=True,
                success=False,
            )
            return {
                "ticket": ticket,
                "execution_preflight": preflight,
                "receipt": receipt,
                "result": None,
            }

    def show(self, ticket_id: str) -> dict[str, Any]:
        ticket = self.load_ticket(ticket_id)
        claim = (
            _read_object(self._claim_path(ticket_id))
            if self._claim_path(ticket_id).exists()
            else None
        )
        receipt = (
            _read_object(self._receipt_path(ticket_id))
            if self._receipt_path(ticket_id).exists()
            else None
        )
        result = (
            _read_object(self._result_path(ticket_id))
            if self._result_path(ticket_id).exists()
            else None
        )
        return {
            "ticket": ticket,
            "fresh": ticket_is_fresh(ticket),
            "spent": claim is not None,
            "claim": claim,
            "receipt": receipt,
            "receipt_verified": (
                verify_execution_receipt(receipt)
                if isinstance(receipt, dict)
                else None
            ),
            "result": result,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Issue and spend one-operation destination activation tickets."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("issue")
    issue.add_argument("descriptor_file")
    issue.add_argument("--confirm", required=True)
    issue.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)

    execute = sub.add_parser("execute")
    execute.add_argument("ticket_id")

    show = sub.add_parser("show")
    show.add_argument("ticket_id")

    verify = sub.add_parser("verify")
    verify.add_argument("ticket_file")

    args = parser.parse_args()
    store = ActivationStore()

    if args.command == "issue":
        descriptor = _read_object(
            Path(args.descriptor_file).expanduser()
        )
        result = store.issue(
            descriptor,
            consent_phrase=args.confirm,
            ttl_seconds=args.ttl,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "execute":
        result = store.execute(args.ticket_id)
        print(json.dumps(result, indent=2))
        status = (result.get("receipt") or {}).get("status")
        return 0 if status == "EXECUTED" else 2

    if args.command == "show":
        print(json.dumps(store.show(args.ticket_id), indent=2))
        return 0

    ticket = _read_object(
        Path(args.ticket_file).expanduser()
    )
    valid = verify_activation_ticket(ticket)
    print(json.dumps({
        "valid": valid,
        "fresh": ticket_is_fresh(ticket) if valid else False,
    }, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
