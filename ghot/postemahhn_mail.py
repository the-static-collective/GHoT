#!/usr/bin/env python3
"""PostEmahh'n MAIL-001: addressed PDF parcels with recipient-only print release.

This is a local/offline transport-independent prototype. It does NOT operate
public e-mail, encrypt documents, print to hardware, or prove human identity.
All paths are for a trusted local machine or transferred bundles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from relatte_identity import (
    IdentityKey, jcs_bytes, normalize_public_jwk, particular_for_public_key,
    sign_crossing, sign_receipt, timestamp_now, verify_crossing, verify_receipt,
)

PROFILE = "postemahhn.mail-print/v0"
MAX_BYTES = 5 * 1024 * 1024
MAX_ITEMS_PER_ADDRESS = 32


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def address(public_key: dict[str, Any]) -> str:
    key = normalize_public_jwk(public_key)
    return "pm1-" + digest(jcs_bytes(key))[:40]


def contact_for_key(key: IdentityKey) -> dict[str, Any]:
    pub = key.public_jwk()
    return {"schema": "postemahhn.address/v0", "address": address(pub), "public_key": pub}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def canonical_contact(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {"schema", "address", "public_key"}:
        raise ValueError("invalid contact card fields")
    if value["schema"] != "postemahhn.address/v0":
        raise ValueError("unsupported contact card")
    pub = normalize_public_jwk(value["public_key"])
    if value["address"] != address(pub):
        raise ValueError("contact card address/public-key mismatch")
    return {"schema": value["schema"], "address": value["address"], "public_key": pub}


def pdf_ok(data: bytes) -> None:
    if len(data) < 16 or len(data) > MAX_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("only PDFs up to 5 MiB are accepted")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def register(mail_root: Path, owner: IdentityKey) -> dict[str, Any]:
    contact = contact_for_key(owner)
    directory = mail_root / "addresses"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (contact["address"] + ".json")
    if path.exists() and canonical_contact(load_json(path)) != contact:
        raise ValueError("existing address binding differs")
    if not path.exists():
        write_json(path, contact)
    return contact


def compose(pdf: bytes, recipient: dict[str, Any], sender: IdentityKey,
            output: Path) -> Path:
    pdf_ok(pdf)
    recipient = canonical_contact(recipient)
    crossing = sign_crossing({
        "schema": "relatte.crossing-envelope/v0",
        "crossing_id": "",
        "protocol_version": "0",
        "source_particular": sender.particular(),
        "source_world": "postemahhn-mail-sender",
        "declared_kind": "POSTEMAHHN_MAIL_PDF_V0",
        "payload_refs": [{"sha256": digest(pdf), "media_type": "application/pdf"}],
        "requested_effect": {
            "action": "DELIVER_TO_HOLD",
            "recipient_address": recipient["address"],
            "nonce": str(uuid.uuid4()),
        },
        "created_at": timestamp_now(),
        "extensions": {"postemahhn_profile": PROFILE},
        "signing": {},
    }, sender)
    if output.exists():
        raise ValueError("parcel directory already exists")
    output.mkdir(parents=True, mode=0o700)
    (output / "document.pdf").write_bytes(pdf)
    write_json(output / "crossing.json", crossing)
    write_json(output / "recipient.json", recipient)
    return output


def verify_parcel(parcel: Path) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    for name in ("document.pdf", "crossing.json", "recipient.json"):
        if not (parcel / name).is_file() or (parcel / name).is_symlink():
            raise ValueError("parcel member missing or symlinked: " + name)
    pdf = (parcel / "document.pdf").read_bytes()
    pdf_ok(pdf)
    crossing = load_json(parcel / "crossing.json")
    recipient = canonical_contact(load_json(parcel / "recipient.json"))
    if not verify_crossing(crossing):
        raise ValueError("invalid reLATTE source crossing")
    if crossing.get("source_particular") != particular_for_public_key(
        crossing["signing"]["public_key"]
    ):
        raise ValueError("source identity does not match signing key")
    if crossing.get("declared_kind") != "POSTEMAHHN_MAIL_PDF_V0":
        raise ValueError("wrong mail crossing kind")
    if crossing.get("extensions") != {"postemahhn_profile": PROFILE}:
        raise ValueError("unsupported mail extension")
    if crossing.get("payload_refs") != [{"sha256": digest(pdf), "media_type": "application/pdf"}]:
        raise ValueError("PDF does not match source-signed content")
    effect = crossing.get("requested_effect")
    if not isinstance(effect, dict) or effect.get("action") != "DELIVER_TO_HOLD":
        raise ValueError("unsupported requested effect")
    if effect.get("recipient_address") != recipient["address"]:
        raise ValueError("crossing recipient mismatch")
    return crossing, recipient, pdf


def received_path(mail_root: Path, recipient_address: str, crossing_id: str) -> Path:
    return mail_root / "inbox" / recipient_address / digest(crossing_id.encode("utf-8"))


def receive(mail_root: Path, parcel: Path) -> Path:
    crossing, recipient, pdf = verify_parcel(parcel)
    addr = recipient["address"]
    registered = mail_root / "addresses" / (addr + ".json")
    if not registered.is_file() or registered.is_symlink():
        raise ValueError("recipient address is not registered at this station")
    if canonical_contact(load_json(registered)) != recipient:
        raise ValueError("recipient key not recognized by the station")
    mailbox = mail_root / "inbox" / addr
    mailbox.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = received_path(mail_root, addr, crossing["crossing_id"])
    if target.exists():
        existing_crossing, existing_recipient, existing_pdf = verify_parcel(target)
        if (existing_crossing != crossing or existing_recipient != recipient
                or existing_pdf != pdf):
            raise ValueError("existing receipt material differs")
        return target
    if sum(1 for x in mailbox.iterdir() if x.is_dir()) >= MAX_ITEMS_PER_ADDRESS:
        raise ValueError("mailbox quota exceeded")
    temp = Path(tempfile.mkdtemp(prefix=".mail-", dir=mailbox))
    try:
        (temp / "document.pdf").write_bytes(pdf)
        write_json(temp / "crossing.json", crossing)
        write_json(temp / "recipient.json", recipient)
        try:
            temp.rename(target)
        except OSError:
            if not target.is_dir() or target.is_symlink():
                raise
            existing_crossing, existing_recipient, existing_pdf = verify_parcel(target)
            if (existing_crossing != crossing or existing_recipient != recipient
                    or existing_pdf != pdf):
                raise ValueError("concurrent delivery differs")
        return target
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def inbox(mail_root: Path, owner: IdentityKey) -> list[dict[str, str]]:
    contact = contact_for_key(owner)
    registered = mail_root / "addresses" / (contact["address"] + ".json")
    if not registered.is_file() or canonical_contact(load_json(registered)) != contact:
        raise ValueError("owner key not registered")
    directory = mail_root / "inbox" / contact["address"]
    if not directory.exists():
        return []
    items = []
    for member in sorted(directory.iterdir()):
        if not member.is_dir() or member.is_symlink():
            continue
        crossing, recipient, pdf = verify_parcel(member)
        if recipient != contact:
            raise ValueError("cross-address mailbox corruption")
        items.append({
            "crossing_id": crossing["crossing_id"], "sha256": digest(pdf),
            "state": "HELD", "sender_particular": crossing["source_particular"],
        })
    return items


def release(mail_root: Path, owner: IdentityKey, crossing_id: str,
            station_id: str, valid_for_seconds: int = 900) -> dict[str, Any]:
    if not station_id or len(station_id) > 128 or any(ch in station_id for ch in "/\\\n"):
        raise ValueError("station id must be a bounded label")
    if not 1 <= valid_for_seconds <= 3600:
        raise ValueError("release duration must be 1..3600 seconds")
    contact = contact_for_key(owner)
    item = received_path(mail_root, contact["address"], crossing_id)
    if not item.is_dir() or item.is_symlink():
        raise ValueError("owner/address/crossing mismatch")
    crossing, recipient, pdf = verify_parcel(item)
    if crossing["crossing_id"] != crossing_id or recipient != contact:
        raise ValueError("owner/address/crossing mismatch")
    registered = canonical_contact(load_json(
        mail_root / "addresses" / (contact["address"] + ".json")))
    if registered != contact:
        raise ValueError("owner key differs from registered receiver")
    expires = datetime.now(timezone.utc) + timedelta(seconds=valid_for_seconds)
    receipt = sign_receipt({
        "schema": "relatte.receipt/v0", "receipt_id": "",
        "crossing_id": crossing["crossing_id"],
        "world_id": "postemahhn-mailbox:" + contact["address"],
        "receiver_particular": owner.particular(),
        "kind": "VERIFIED", "semantic_effect": "none",
        "created_at": timestamp_now(),
        "note": "Recipient authorizes one local PDF export, not a hardware print",
        "extensions": {"postemahhn_release": {
            "profile": PROFILE, "recipient_address": contact["address"],
            "artifact_sha256": digest(pdf), "station_id": station_id,
            "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "action": "LOCAL_PDF_EXPORT", "physical_print_claimed": False,
        }},
        "signing": {},
    }, owner)
    return receipt


def authorize_export(mail_root: Path, receipt: dict[str, Any], station_id: str,
                     now: datetime | None = None) -> tuple[bytes, str]:
    ext = receipt.get("extensions") or {}
    release_obj = ext.get("postemahhn_release") if isinstance(ext, dict) else None
    if not isinstance(release_obj, dict):
        raise ValueError("missing signed release body")
    addr = release_obj.get("recipient_address")
    if not isinstance(addr, str) or not addr.startswith("pm1-"):
        raise ValueError("invalid release address")
    contact_path = mail_root / "addresses" / (addr + ".json")
    if not contact_path.is_file() or contact_path.is_symlink():
        raise ValueError("recipient address not trusted here")
    contact = canonical_contact(load_json(contact_path))
    if not verify_receipt(
        receipt, expected_public_key=contact["public_key"],
        expected_receiver_particular=particular_for_public_key(contact["public_key"])
    ):
        raise ValueError("invalid recipient release signature")
    if receipt.get("kind") != "VERIFIED" or receipt.get("semantic_effect") != "none":
        raise ValueError("print authorization cannot assert external effect")
    if release_obj.get("profile") != PROFILE or release_obj.get("action") != "LOCAL_PDF_EXPORT":
        raise ValueError("unsupported release action")
    if release_obj.get("physical_print_claimed") is not False:
        raise ValueError("cannot claim physical printing")
    if release_obj.get("station_id") != station_id:
        raise ValueError("wrong release station")
    try:
        expires = datetime.strptime(release_obj["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError("invalid release expiry") from e
    current = now or datetime.now(timezone.utc)
    created = datetime.fromisoformat(receipt["created_at"].replace("Z", "+00:00"))
    if current > expires or expires <= created or (expires-created).total_seconds() > 3601:
        raise ValueError("expired or invalid release window")
    crossing_id = receipt.get("crossing_id")
    if not isinstance(crossing_id, str):
        raise ValueError("invalid crossing reference")
    item = received_path(mail_root, addr, crossing_id)
    crossing, recipient, pdf = verify_parcel(item)
    if crossing["crossing_id"] != crossing_id or recipient != contact:
        raise ValueError("held mail no longer matches signed release")
    if release_obj.get("artifact_sha256") != digest(pdf):
        raise ValueError("signed release no longer matches PDF bytes")
    return pdf, digest(pdf)


def export_pdf(mail_root: Path, receipt: dict[str, Any], station_id: str,
               out_dir: Path, now: datetime | None = None) -> Path:
    pdf, pdf_hash = authorize_export(mail_root, receipt, station_id, now)
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = out_dir / ("postemahhn-" + pdf_hash[:24] + ".pdf")
    if destination.exists():
        if destination.is_symlink() or destination.read_bytes() != pdf:
            raise ValueError("existing print-ready file differs")
        return destination
    # Exclusive creation: no silent overwrite of a previously released file.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pdf)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="PostEmahh'n addressed MAIL -> HOLD -> local PDF export")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("register")
    r.add_argument("--owner-key", type=Path, required=True)
    r.add_argument("--mail-root", type=Path, required=True)
    r.add_argument("--contact-out", type=Path)
    c = sub.add_parser("compose")
    c.add_argument("--sender-key", type=Path, required=True)
    c.add_argument("--to", type=Path, required=True)
    c.add_argument("--pdf", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    recv = sub.add_parser("receive")
    recv.add_argument("--mail-root", type=Path, required=True)
    recv.add_argument("--parcel", type=Path, required=True)
    listing = sub.add_parser("inbox")
    listing.add_argument("--mail-root", type=Path, required=True)
    listing.add_argument("--owner-key", type=Path, required=True)
    rel = sub.add_parser("release")
    rel.add_argument("--mail-root", type=Path, required=True)
    rel.add_argument("--owner-key", type=Path, required=True)
    rel.add_argument("--crossing-id", required=True)
    rel.add_argument("--station-id", required=True)
    rel.add_argument("--out", type=Path, required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--mail-root", type=Path, required=True)
    exp.add_argument("--release", type=Path, required=True)
    exp.add_argument("--station-id", required=True)
    exp.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        owner = IdentityKey.load_or_create(args.owner_key)
        result = register(args.mail_root, owner)
        if args.contact_out:
            write_json(args.contact_out, result)
        print(json.dumps(result, indent=2))
    elif args.command == "compose":
        sender = IdentityKey.load_or_create(args.sender_key)
        output = compose(args.pdf.read_bytes(), load_json(args.to), sender, args.out)
        print(json.dumps({"parcel": str(output), "status": "SEALED"}, indent=2))
    elif args.command == "receive":
        result = receive(args.mail_root, args.parcel)
        print(json.dumps({"held": str(result), "status": "HELD"}, indent=2))
    elif args.command == "inbox":
        owner = IdentityKey.load_or_create(args.owner_key)
        print(json.dumps(inbox(args.mail_root, owner), indent=2))
    elif args.command == "release":
        owner = IdentityKey.load_or_create(args.owner_key)
        receipt = release(args.mail_root, owner, args.crossing_id, args.station_id)
        if args.out.exists():
            raise ValueError("release path already exists")
        write_json(args.out, receipt)
        print(json.dumps({"release": str(args.out), "receipt_id": receipt["receipt_id"]}, indent=2))
    elif args.command == "export":
        output = export_pdf(args.mail_root, load_json(args.release), args.station_id, args.out_dir)
        print(json.dumps({"print_ready_pdf": str(output), "printed": False}, indent=2))


if __name__ == "__main__":
    main()
