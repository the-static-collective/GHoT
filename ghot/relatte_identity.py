#!/usr/bin/env python3
"""Bounded Python witness of reLATTE Identity + Signature Profile v0.

Implements the exact v0 crossing/receipt identity equations for the protocol
surface GHoT emits:
- ECDSA P-256 + SHA-256
- canonical unpadded base64url JWK coordinates
- raw 64-byte r||s portable signatures
- reLATTE domain-separated IDs and signature bytes
- strict timestamp / root-field / signing-field guards

Curve operations are delegated to the system OpenSSL executable so the Python
runtime remains package-free.

The JCS encoder here intentionally accepts only the value family used by GHoT's
signed protocol objects: null, booleans, safe integers, strings, arrays and
plain string-keyed objects. Floats are rejected before signing. GHoT converts
runtime measurement numbers in signed extensions to strings.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


CROSSING_ID_DOMAIN = b"reLATTE-CrossingEnvelope-v0|"
CROSSING_SIGNATURE_DOMAIN = b"reLATTE-CrossingSignature-v0|"
RECEIPT_ID_DOMAIN = b"reLATTE-Receipt-v0|"
RECEIPT_SIGNATURE_DOMAIN = b"reLATTE-ReceiptSignature-v0|"

CROSSING_SIGNING_DOMAIN = "relatte.crossing-signature/v0"
RECEIPT_SIGNING_DOMAIN = "relatte.receipt-signature/v0"
ALGORITHM = "ECDSA-P256-SHA256"

SAFE_INT_MAX = 9007199254740991
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$"
)

CROSSING_REQUIRED_FIELDS = {
    "schema",
    "crossing_id",
    "protocol_version",
    "source_particular",
    "source_world",
    "declared_kind",
    "payload_refs",
    "created_at",
    "signing",
}

CROSSING_ROOT_FIELDS = {
    "schema",
    "crossing_id",
    "protocol_version",
    "source_particular",
    "source_world",
    "source_history_head",
    "parents",
    "declared_kind",
    "payload_refs",
    "requested_effect",
    "capability_ref",
    "privacy_policy",
    "audience_policy",
    "return_address",
    "created_at",
    "signing",
    "extensions",
}

RECEIPT_REQUIRED_FIELDS = {
    "schema",
    "receipt_id",
    "crossing_id",
    "world_id",
    "receiver_particular",
    "kind",
    "semantic_effect",
    "created_at",
    "signing",
}

RECEIPT_ROOT_FIELDS = {
    "schema",
    "receipt_id",
    "crossing_id",
    "world_id",
    "receiver_particular",
    "kind",
    "semantic_effect",
    "contract_ref",
    "pre_state_ref",
    "post_state_ref",
    "descendant_refs",
    "residual_refs",
    "note",
    "created_at",
    "signing",
    "extensions",
}

SIGNING_FIELDS = {"algorithm", "public_key", "signature", "domain"}
PUBLIC_JWK_FIELDS = {"kty", "crv", "x", "y"}

SPKI_P256_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)


class IdentityProfileError(ValueError):
    pass


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def unb64url(value: str) -> bytes:
    if not isinstance(value, str) or "=" in value:
        raise IdentityProfileError("base64url must be canonical and unpadded")
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise IdentityProfileError("invalid base64url") from exc
    if b64url(decoded) != value:
        raise IdentityProfileError("non-canonical base64url")
    return decoded


def timestamp_ms(epoch: float) -> str:
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(float(epoch), timezone.utc)
    milliseconds = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{milliseconds:03d}Z"


def timestamp_now() -> str:
    import time

    return timestamp_ms(time.time())


def normalize_timestamp(value: str) -> str:
    from datetime import datetime, timezone

    if TIMESTAMP_RE.fullmatch(value):
        return value
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IdentityProfileError("invalid timestamp") from exc
    if dt.tzinfo is None:
        raise IdentityProfileError("timestamp must include timezone")
    dt = dt.astimezone(timezone.utc)
    milliseconds = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{milliseconds:03d}Z"


def _validate_jcs_value(value: Any, depth: int = 0) -> None:
    if depth > 100:
        raise IdentityProfileError("maximum canonicalization depth exceeded")
    if value is None or isinstance(value, (bool, str)):
        if isinstance(value, str):
            for char in value:
                code = ord(char)
                if 0xD800 <= code <= 0xDFFF:
                    raise IdentityProfileError("lone Unicode surrogate rejected")
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > SAFE_INT_MAX:
            raise IdentityProfileError("unsafe integer rejected")
        return
    if isinstance(value, float):
        raise IdentityProfileError("floating-point value rejected by bounded GHoT JCS surface")
    if isinstance(value, list):
        for item in value:
            _validate_jcs_value(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise IdentityProfileError("object keys must be strings")
            _validate_jcs_value(key, depth + 1)
            _validate_jcs_value(item, depth + 1)
        return
    raise IdentityProfileError(f"unsupported canonical JSON type: {type(value).__name__}")


def jcs_bytes(value: Any) -> bytes:
    _validate_jcs_value(value)
    # GHoT's signed protocol keys are ASCII. For this bounded surface, Python's
    # sorted key order therefore matches JCS UTF-16 lexical ordering.
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def identity_safe(value: Any) -> Any:
    """Convert runtime values to the bounded signed JSON family.

    Integral floats become integers. Non-integral floats become decimal strings
    so measurements can be carried without pretending the bounded JCS witness
    implements ECMAScript number serialization.
    """
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if value.is_integer() and abs(value) <= SAFE_INT_MAX:
            return int(value)
        return format(value, ".17g")
    if isinstance(value, list):
        return [identity_safe(item) for item in value]
    if isinstance(value, tuple):
        return [identity_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): identity_safe(item) for key, item in value.items()}
    return str(value)


def normalize_public_jwk(jwk: dict[str, Any]) -> dict[str, str]:
    if not isinstance(jwk, dict):
        raise IdentityProfileError("public key must be an object")
    if set(jwk) != PUBLIC_JWK_FIELDS:
        raise IdentityProfileError("P-256 public key has unknown/missing fields")
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise IdentityProfileError("public key must be EC P-256")
    x = unb64url(str(jwk.get("x") or ""))
    y = unb64url(str(jwk.get("y") or ""))
    if len(x) != 32 or len(y) != 32:
        raise IdentityProfileError("P-256 coordinates must be exactly 32 bytes")
    return {"kty": "EC", "crv": "P-256", "x": b64url(x), "y": b64url(y)}


def particular_for_public_key(jwk: dict[str, Any]) -> str:
    normalized = normalize_public_jwk(jwk)
    digest = hashlib.sha256(jcs_bytes(normalized)).hexdigest()
    return f"ghot-p256:{digest}"


def _der_length(data: bytes, index: int) -> tuple[int, int]:
    first = data[index]
    index += 1
    if first < 0x80:
        return first, index
    count = first & 0x7F
    if count == 0 or count > 4:
        raise IdentityProfileError("unsupported DER length")
    end = index + count
    if end > len(data):
        raise IdentityProfileError("truncated DER length")
    return int.from_bytes(data[index:end], "big"), end


def der_signature_to_raw(der: bytes) -> bytes:
    index = 0
    if not der or der[index] != 0x30:
        raise IdentityProfileError("ECDSA signature is not a DER sequence")
    index += 1
    sequence_length, index = _der_length(der, index)
    if index + sequence_length != len(der):
        raise IdentityProfileError("invalid DER sequence length")

    values: list[bytes] = []
    for _ in range(2):
        if index >= len(der) or der[index] != 0x02:
            raise IdentityProfileError("ECDSA signature integer missing")
        index += 1
        length, index = _der_length(der, index)
        raw = der[index:index + length]
        index += length
        if not raw:
            raise IdentityProfileError("empty ECDSA integer")
        if raw[0] == 0:
            raw = raw[1:]
        if len(raw) > 32:
            raise IdentityProfileError("ECDSA integer wider than P-256")
        values.append(raw.rjust(32, b"\x00"))

    if index != len(der):
        raise IdentityProfileError("trailing DER signature bytes")
    return values[0] + values[1]


def _der_integer(raw: bytes) -> bytes:
    raw = raw.lstrip(b"\x00") or b"\x00"
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return b"\x02" + bytes([len(raw)]) + raw


def raw_signature_to_der(raw: bytes) -> bytes:
    if len(raw) != 64:
        raise IdentityProfileError("P-256 raw signature must be 64 bytes")
    body = _der_integer(raw[:32]) + _der_integer(raw[32:])
    if len(body) >= 128:
        raise IdentityProfileError("unexpected P-256 DER signature length")
    return b"\x30" + bytes([len(body)]) + body


def public_jwk_to_pem(jwk: dict[str, Any]) -> bytes:
    normalized = normalize_public_jwk(jwk)
    point = b"\x04" + unb64url(normalized["x"]) + unb64url(normalized["y"])
    der = SPKI_P256_PREFIX + point[1:]
    encoded = base64.b64encode(der).decode("ascii")
    lines = [encoded[i:i + 64] for i in range(0, len(encoded), 64)]
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        + "\n".join(lines)
        + "\n-----END PUBLIC KEY-----\n"
    ).encode("ascii")


class IdentityKey:
    def __init__(self, private_key_path: Path) -> None:
        self.private_key_path = private_key_path

    @classmethod
    def load_or_create(cls, private_key_path: Path) -> "IdentityKey":
        private_key_path.parent.mkdir(parents=True, exist_ok=True)
        if not private_key_path.exists():
            if shutil.which("openssl") is None:
                raise RuntimeError("openssl is required for the reLATTE P-256 profile")
            subprocess.run(
                [
                    "openssl",
                    "genpkey",
                    "-algorithm",
                    "EC",
                    "-pkeyopt",
                    "ec_paramgen_curve:P-256",
                    "-out",
                    str(private_key_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                private_key_path.chmod(0o600)
            except OSError:
                pass
        return cls(private_key_path)

    def public_jwk(self) -> dict[str, str]:
        result = subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(self.private_key_path),
                "-pubout",
                "-outform",
                "DER",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        der = result.stdout
        if not der.startswith(SPKI_P256_PREFIX) or len(der) != len(SPKI_P256_PREFIX) + 64:
            raise IdentityProfileError("unexpected OpenSSL P-256 public key encoding")
        point_xy = der[len(SPKI_P256_PREFIX):]
        return {
            "kty": "EC",
            "crv": "P-256",
            "x": b64url(point_xy[:32]),
            "y": b64url(point_xy[32:]),
        }

    def particular(self) -> str:
        return particular_for_public_key(self.public_jwk())

    def sign(self, data: bytes) -> str:
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                str(self.private_key_path),
            ],
            input=data,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return b64url(der_signature_to_raw(result.stdout))


def verify_p256(public_jwk: dict[str, Any], data: bytes, signature_text: str) -> bool:
    try:
        raw = unb64url(signature_text)
        der_signature = raw_signature_to_der(raw)
        public_pem = public_jwk_to_pem(public_jwk)
    except IdentityProfileError:
        return False

    with tempfile.TemporaryDirectory() as tmp:
        public_path = Path(tmp) / "public.pem"
        signature_path = Path(tmp) / "signature.der"
        public_path.write_bytes(public_pem)
        signature_path.write_bytes(der_signature)
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_path),
                "-signature",
                str(signature_path),
            ],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0


def _crossing_identity_body(envelope: dict[str, Any]) -> dict[str, Any]:
    signing = envelope.get("signing") or {}
    return {
        "schema": envelope.get("schema"),
        "protocol_version": envelope.get("protocol_version"),
        "source_particular": envelope.get("source_particular"),
        "source_world": envelope.get("source_world"),
        "source_history_head": envelope.get("source_history_head"),
        "parents": envelope.get("parents") or [],
        "declared_kind": envelope.get("declared_kind"),
        "payload_refs": envelope.get("payload_refs") or [],
        "requested_effect": envelope.get("requested_effect"),
        "capability_ref": envelope.get("capability_ref"),
        "privacy_policy": envelope.get("privacy_policy"),
        "audience_policy": envelope.get("audience_policy"),
        "return_address": envelope.get("return_address"),
        "created_at": envelope.get("created_at"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": normalize_public_jwk(signing.get("public_key") or {}),
            "domain": signing.get("domain"),
        },
        "extensions": envelope.get("extensions") or {},
    }


def derive_crossing_id(envelope: dict[str, Any]) -> str:
    body = _crossing_identity_body(envelope)
    digest = hashlib.sha256(CROSSING_ID_DOMAIN + jcs_bytes(body)).hexdigest()
    return "relatte-crossing-v0:" + digest


def crossing_signature_bytes(envelope: dict[str, Any]) -> bytes:
    body = _crossing_identity_body(envelope)
    signature_body = {"crossing_id": derive_crossing_id(envelope), **body}
    return CROSSING_SIGNATURE_DOMAIN + jcs_bytes(signature_body)


def sign_crossing(envelope: dict[str, Any], key: IdentityKey) -> dict[str, Any]:
    signed = dict(envelope)
    signed["created_at"] = normalize_timestamp(str(signed["created_at"]))
    signed["signing"] = {
        "algorithm": ALGORITHM,
        "public_key": key.public_jwk(),
        "signature": "",
        "domain": CROSSING_SIGNING_DOMAIN,
    }
    signed["crossing_id"] = derive_crossing_id(signed)
    signed["signing"]["signature"] = key.sign(crossing_signature_bytes(signed))
    return signed


def verify_crossing(envelope: dict[str, Any]) -> bool:
    try:
        fields = set(envelope)
        if not CROSSING_REQUIRED_FIELDS.issubset(fields):
            return False
        if not fields.issubset(CROSSING_ROOT_FIELDS):
            return False
        signing = envelope.get("signing")
        if not isinstance(signing, dict) or set(signing) != SIGNING_FIELDS:
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != CROSSING_SIGNING_DOMAIN:
            return False
        created_at = str(envelope.get("created_at") or "")
        if not TIMESTAMP_RE.fullmatch(created_at):
            return False
        public_key = normalize_public_jwk(signing.get("public_key") or {})
        if envelope.get("crossing_id") != derive_crossing_id(envelope):
            return False
        signature_text = str(signing.get("signature") or "")
        raw = unb64url(signature_text)
        if len(raw) != 64:
            return False
        return verify_p256(public_key, crossing_signature_bytes(envelope), signature_text)
    except (IdentityProfileError, TypeError, ValueError):
        return False


def _receipt_identity_body(receipt: dict[str, Any]) -> dict[str, Any]:
    signing = receipt.get("signing") or {}
    return {
        "schema": receipt.get("schema"),
        "crossing_id": receipt.get("crossing_id"),
        "world_id": receipt.get("world_id"),
        "receiver_particular": receipt.get("receiver_particular"),
        "kind": receipt.get("kind"),
        "semantic_effect": receipt.get("semantic_effect"),
        "contract_ref": receipt.get("contract_ref"),
        "pre_state_ref": receipt.get("pre_state_ref"),
        "post_state_ref": receipt.get("post_state_ref"),
        "descendant_refs": receipt.get("descendant_refs") or [],
        "residual_refs": receipt.get("residual_refs") or [],
        "note": receipt.get("note"),
        "created_at": receipt.get("created_at"),
        "signing": {
            "algorithm": signing.get("algorithm"),
            "public_key": normalize_public_jwk(signing.get("public_key") or {}),
            "domain": signing.get("domain"),
        },
        "extensions": receipt.get("extensions") or {},
    }


def derive_receipt_id(receipt: dict[str, Any]) -> str:
    body = _receipt_identity_body(receipt)
    digest = hashlib.sha256(RECEIPT_ID_DOMAIN + jcs_bytes(body)).hexdigest()
    return "relatte-receipt-v0:" + digest


def receipt_signature_bytes(receipt: dict[str, Any]) -> bytes:
    body = _receipt_identity_body(receipt)
    signature_body = {"receipt_id": derive_receipt_id(receipt), **body}
    return RECEIPT_SIGNATURE_DOMAIN + jcs_bytes(signature_body)


def sign_receipt(receipt: dict[str, Any], key: IdentityKey) -> dict[str, Any]:
    signed = dict(receipt)
    signed["created_at"] = normalize_timestamp(str(signed["created_at"]))
    signed["signing"] = {
        "algorithm": ALGORITHM,
        "public_key": key.public_jwk(),
        "signature": "",
        "domain": RECEIPT_SIGNING_DOMAIN,
    }
    signed["receipt_id"] = derive_receipt_id(signed)
    signed["signing"]["signature"] = key.sign(receipt_signature_bytes(signed))
    return signed


def verify_receipt(
    receipt: dict[str, Any],
    *,
    expected_public_key: dict[str, Any] | None = None,
    expected_receiver_particular: str | None = None,
) -> bool:
    try:
        fields = set(receipt)
        if not RECEIPT_REQUIRED_FIELDS.issubset(fields):
            return False
        if not fields.issubset(RECEIPT_ROOT_FIELDS):
            return False
        signing = receipt.get("signing")
        if not isinstance(signing, dict) or set(signing) != SIGNING_FIELDS:
            return False
        if signing.get("algorithm") != ALGORITHM:
            return False
        if signing.get("domain") != RECEIPT_SIGNING_DOMAIN:
            return False
        created_at = str(receipt.get("created_at") or "")
        if not TIMESTAMP_RE.fullmatch(created_at):
            return False
        public_key = normalize_public_jwk(signing.get("public_key") or {})
        if expected_public_key is not None:
            if public_key != normalize_public_jwk(expected_public_key):
                return False
        if expected_receiver_particular is not None:
            if receipt.get("receiver_particular") != expected_receiver_particular:
                return False
        if receipt.get("receipt_id") != derive_receipt_id(receipt):
            return False
        signature_text = str(signing.get("signature") or "")
        raw = unb64url(signature_text)
        if len(raw) != 64:
            return False
        return verify_p256(public_key, receipt_signature_bytes(receipt), signature_text)
    except (IdentityProfileError, TypeError, ValueError):
        return False
