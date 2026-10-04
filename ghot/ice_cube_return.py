#!/usr/bin/env python3
"""Chunked Ice Cube return crossing — Experiment 032.

The worker's signed State Parcel commits to a compact Ice Cube result manifest.
Large render bytes travel as content-addressed chunks named by that manifest.

Network arrival may only HOLD. The receiver independently runs Dogram before
the helper permits owner-local ADMIT.

    WORKER VERIFIED != RECEIVER VERIFIED
    RETURNED != ADMITTED
    ADMITTED != MERGED
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import uuid
import urllib.request
from pathlib import Path
from typing import Any

from ice_cube import (
    RESULT_KIND,
    RESULT_VERSION,
    content_address,
    dogram_receipt_for,
)
from relatte_identity import (
    identity_safe,
    sign_receipt,
    timestamp_now,
    verify_crossing,
    verify_receipt,
)
from state_parcel import (
    StateParcelExporter,
    StateParcelInbox,
    verify_bundle as verify_state_bundle,
)


RETURN_KIND = "ghot.ice-cube.return-bundle"
RETURN_VERSION = "0"
RETURN_INBOX_KIND = "ghot.ice-cube-return.inbox"
RETURN_INBOX_VERSION = "0"
VERIFY_CONTRACT = "ghot.ice-cube-return-verification@0"
CHUNK_ENCODING = "base64"
DEFAULT_CHUNK_BYTES = 128 * 1024
MAX_CHUNKS = 4096
MAX_RETURN_BYTES = 256 * 1024 * 1024


def _safe_name(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".tmp-{uuid.uuid4()}")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _decode_b64(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError("invalid base64 chunk") from exc


def _chunk_address(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _result_without_inline_render(
    result: dict[str, Any],
    render_bytes: bytes,
    *,
    chunk_size: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    chunks: list[dict[str, Any]] = []
    descriptors: list[dict[str, Any]] = []
    for index, start in enumerate(range(0, len(render_bytes), chunk_size)):
        data = render_bytes[start:start + chunk_size]
        address = _chunk_address(data)
        descriptors.append({
            "index": index,
            "address": address,
            "size_bytes": len(data),
        })
        chunks.append({
            "index": index,
            "address": address,
            "size_bytes": len(data),
            "encoding": CHUNK_ENCODING,
            "data": base64.b64encode(data).decode("ascii"),
        })
    if len(chunks) > MAX_CHUNKS:
        raise ValueError(f"return requires more than {MAX_CHUNKS} chunks")

    portable = copy.deepcopy(result)
    portable.pop("render_base64", None)
    portable["render_encoding"] = "chunked-base64/v0"
    portable["render_transport"] = {
        "kind": "ghot.chunk-manifest",
        "version": "0",
        "total_size_bytes": len(render_bytes),
        "chunk_size_bytes": chunk_size,
        "chunk_count": len(descriptors),
        "chunks": descriptors,
    }
    return portable, chunks


def reconstruct_render(
    portable_result: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> bytes:
    transport = portable_result.get("render_transport")
    if not isinstance(transport, dict):
        raise ValueError("Ice Cube return lacks render_transport")
    descriptors = transport.get("chunks")
    if not isinstance(descriptors, list):
        raise ValueError("render_transport.chunks must be an array")
    if int(transport.get("chunk_count", -1)) != len(descriptors):
        raise ValueError("chunk_count mismatch")
    if len(descriptors) > MAX_CHUNKS:
        raise ValueError("too many return chunks")
    if len(chunks) != len(descriptors):
        raise ValueError("return chunk payload count mismatch")

    by_index: dict[int, dict[str, Any]] = {}
    for chunk in chunks:
        index = int(chunk.get("index", -1))
        if index in by_index:
            raise ValueError("duplicate return chunk index")
        by_index[index] = chunk

    pieces: list[bytes] = []
    total = 0
    for expected_index, descriptor in enumerate(descriptors):
        if int(descriptor.get("index", -1)) != expected_index:
            raise ValueError("chunk manifest indices must be contiguous")
        chunk = by_index.get(expected_index)
        if chunk is None:
            raise ValueError("missing return chunk")
        if chunk.get("encoding") != CHUNK_ENCODING:
            raise ValueError("unsupported return chunk encoding")
        data = _decode_b64(str(chunk.get("data") or ""))
        address = _chunk_address(data)
        if address != descriptor.get("address"):
            raise ValueError("chunk content address mismatch")
        if address != chunk.get("address"):
            raise ValueError("chunk wrapper address mismatch")
        if len(data) != int(descriptor.get("size_bytes", -1)):
            raise ValueError("chunk manifest size mismatch")
        if len(data) != int(chunk.get("size_bytes", -1)):
            raise ValueError("chunk wrapper size mismatch")
        total += len(data)
        if total > MAX_RETURN_BYTES:
            raise ValueError("returned artifact exceeds bounded v0 size")
        pieces.append(data)

    combined = b"".join(pieces)
    if len(combined) != int(transport.get("total_size_bytes", -1)):
        raise ValueError("returned render total size mismatch")
    if _chunk_address(combined) != portable_result.get("render_address"):
        raise ValueError("returned render address mismatch")
    return combined


def verify_return_bundle(bundle: dict[str, Any]) -> bool:
    try:
        if bundle.get("kind") != RETURN_KIND:
            return False
        if bundle.get("version") != RETURN_VERSION:
            return False
        state_bundle = bundle.get("state_parcel_bundle")
        chunks = bundle.get("chunks")
        if not isinstance(state_bundle, dict) or not isinstance(chunks, list):
            return False
        if not verify_state_bundle(state_bundle):
            return False

        parcel = state_bundle["parcel"]
        payload = parcel["payload"]
        result = payload.get("value")
        if not isinstance(result, dict):
            return False
        if result.get("kind") != RESULT_KIND or result.get("version") != RESULT_VERSION:
            return False

        render_bytes = reconstruct_render(result, chunks)
        specimen = result.get("specimen")
        dogram_receipt = result.get("dogram_receipt")
        work_crossing = result.get("work_crossing")
        execution_receipt = result.get("execution_receipt")
        if not all(isinstance(item, dict) for item in (
            specimen,
            dogram_receipt,
            work_crossing,
            execution_receipt,
        )):
            return False

        if content_address(specimen) != result.get("specimen_address"):
            return False
        if content_address(dogram_receipt) != result.get("dogram_receipt_address"):
            return False
        if content_address(render_bytes) != result.get("render_address"):
            return False

        if not verify_crossing(work_crossing):
            return False
        if work_crossing.get("crossing_id") != result.get("work_crossing_id"):
            return False
        if not verify_receipt(execution_receipt):
            return False
        if execution_receipt.get("receipt_id") != result.get("execution_receipt_id"):
            return False
        if execution_receipt.get("crossing_id") != work_crossing.get("crossing_id"):
            return False

        descendants = set(execution_receipt.get("descendant_refs") or [])
        required_descendants = {
            result.get("specimen_address"),
            result.get("render_address"),
            result.get("dogram_receipt_address"),
        }
        if not required_descendants.issubset(descendants):
            return False

        # The signed State Parcel commits to the chunk manifest and all worker
        # lineage. Chunk bytes are independently bound by those manifest hashes.
        crossing = state_bundle["crossing"]
        if crossing.get("payload_refs") != [parcel["parcel_address"]]:
            return False
        target = (parcel.get("target") or {}).get("particular")
        if (crossing.get("audience_policy") or {}).get("target_particular") != target:
            # Current StateParcel profile does not use target_particular in the
            # audience policy, so only enforce if present.
            audience = crossing.get("audience_policy") or {}
            if "target_particular" in audience:
                return False
        return True
    except Exception:
        return False


def make_return_bundle(
    worker_root: Path,
    result_path: Path,
    *,
    target_particular: str,
    chunk_size: int = DEFAULT_CHUNK_BYTES,
) -> dict[str, Any]:
    worker_root = worker_root.resolve()
    result_path = result_path.resolve()
    try:
        result_path.relative_to(worker_root)
    except ValueError as exc:
        raise ValueError("result_path must be inside worker_root") from exc

    result = _read_json(result_path)
    if not isinstance(result, dict):
        raise ValueError("Ice Cube result must be an object")
    if result.get("kind") != RESULT_KIND or result.get("version") != RESULT_VERSION:
        raise ValueError("not a supported Ice Cube result")
    raw_render = result.get("render_base64")
    if not isinstance(raw_render, str):
        raise ValueError("worker result does not contain inline render bytes")
    render_bytes = _decode_b64(raw_render)
    if content_address(render_bytes) != result.get("render_address"):
        raise ValueError("worker result render address mismatch")

    portable_result, chunks = _result_without_inline_render(
        result,
        render_bytes,
        chunk_size=chunk_size,
    )
    return_dir = result_path.parent / "return"
    return_result_path = return_dir / "result.return.v0.json"
    _write_json(return_result_path, portable_result)

    exporter = StateParcelExporter(worker_root)
    state_bundle = exporter.export(
        str(return_result_path.relative_to(worker_root)),
        selector="$",
        target_particular=target_particular,
    )
    bundle = {
        "kind": RETURN_KIND,
        "version": RETURN_VERSION,
        "state_parcel_bundle": state_bundle,
        "chunks": chunks,
    }
    if not verify_return_bundle(bundle):
        raise RuntimeError("new Ice Cube return bundle failed local verification")
    return bundle


def _verification_receipt(
    *,
    state_bundle: dict[str, Any],
    local_dogram_receipt: dict[str, Any],
    signer: Any,
    node_id: str,
) -> dict[str, Any]:
    parcel = state_bundle["parcel"]
    result = parcel["payload"]["value"]
    local_address = content_address(local_dogram_receipt)
    ok = local_dogram_receipt.get("status") == "OK"
    receipt = {
        "schema": "relatte.receipt/v0",
        "receipt_id": "",
        "crossing_id": state_bundle["crossing"]["crossing_id"],
        "world_id": f"ghot-node:{node_id}",
        "receiver_particular": signer.particular(),
        "kind": "VERIFIED" if ok else "REFUSED",
        "semantic_effect": "none",
        "contract_ref": VERIFY_CONTRACT,
        "pre_state_ref": parcel["payload"]["address"],
        "post_state_ref": local_address,
        "descendant_refs": [local_address],
        "residual_refs": [],
        "note": (
            "receiver independently re-verified Ice Cube with local Dogram"
            if ok
            else "receiver-local Dogram refused Ice Cube claim"
        ),
        "created_at": timestamp_now(),
        "extensions": identity_safe({
            "parcel_id": parcel["parcel_id"],
            "specimen_id": result.get("specimen_id"),
            "render_address": result.get("render_address"),
            "worker_dogram_receipt_address": result.get("dogram_receipt_address"),
            "local_dogram_receipt_address": local_address,
            "local_dogram_status": local_dogram_receipt.get("status"),
            "claim_scope": (
                (local_dogram_receipt.get("result") or {}).get("claim_scope")
            ),
            "independent_reverification": True,
            "worker_verification_is_not_authority": True,
            "verification_is_not_admission": True,
        }),
        "signing": {
            "algorithm": "",
            "public_key": {},
            "signature": "",
            "domain": "",
        },
    }
    signed = sign_receipt(receipt, signer)
    if not verify_receipt(signed):
        raise RuntimeError("local Ice Cube verification receipt failed verification")
    return signed


class IceCubeReturnInbox:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.state_inbox = StateParcelInbox(root)
        self.signer = self.state_inbox.signer
        self.node_id = self.state_inbox.node_id
        self.base = root / "ice-cube-returns"
        self.raw_dir = self.base / "raw"
        self.status_dir = self.base / "status"
        self.dogram_dir = self.base / "dogram"
        self.receipts_dir = self.base / "receipts"

    def _raw_path(self, parcel_id: str) -> Path:
        return self.raw_dir / f"{_safe_name(parcel_id)}.json"

    def _status_path(self, parcel_id: str) -> Path:
        return self.status_dir / f"{_safe_name(parcel_id)}.json"

    def _read_status(self, parcel_id: str) -> dict[str, Any]:
        path = self._status_path(parcel_id)
        if not path.exists():
            raise ValueError("unknown Ice Cube return parcel")
        value = _read_json(path)
        if not isinstance(value, dict):
            raise ValueError("invalid Ice Cube return status")
        return value

    def receive(self, bundle: dict[str, Any]) -> dict[str, Any]:
        if not verify_return_bundle(bundle):
            raise ValueError("invalid Ice Cube return bundle")
        state_bundle = bundle["state_parcel_bundle"]
        receipt = self.state_inbox.receive(state_bundle)
        if receipt.get("kind") != "HELD":
            return receipt

        parcel = state_bundle["parcel"]
        parcel_id = parcel["parcel_id"]
        raw_path = self._raw_path(parcel_id)
        if raw_path.exists():
            prior = _read_json(raw_path)
            if prior != bundle:
                raise ValueError("same parcel_id arrived with different return wrapper")
        else:
            _write_json(raw_path, bundle)

        result = parcel["payload"]["value"]
        status = {
            "kind": RETURN_INBOX_KIND,
            "version": RETURN_INBOX_VERSION,
            "parcel_id": parcel_id,
            "state_crossing_id": state_bundle["crossing"]["crossing_id"],
            "specimen_id": result.get("specimen_id"),
            "render_address": result.get("render_address"),
            "network_disposition": "HOLD",
            "verification_status": "UNVERIFIED",
            "local_dogram_receipt_address": None,
            "local_verification_receipt_id": None,
            "admission_receipt_id": None,
        }
        if not self._status_path(parcel_id).exists():
            _write_json(self._status_path(parcel_id), status)
        return receipt

    def list(self) -> list[dict[str, Any]]:
        if not self.status_dir.is_dir():
            return []
        rows = []
        for path in sorted(self.status_dir.glob("*.json")):
            try:
                value = _read_json(path)
            except Exception:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def show(self, parcel_id: str) -> dict[str, Any]:
        return {
            "status": self._read_status(parcel_id),
            "return_bundle": _read_json(self._raw_path(parcel_id)),
            "state_parcel": self.state_inbox.show(parcel_id),
        }

    def verify_local(
        self,
        parcel_id: str,
        *,
        dogram_repo: Path,
    ) -> dict[str, Any]:
        status = self._read_status(parcel_id)
        state = self.state_inbox.show(parcel_id)
        if state["queue"]["status"] != "HOLD":
            raise ValueError("Ice Cube must remain HOLD during receiver verification")
        bundle = _read_json(self._raw_path(parcel_id))
        if not verify_return_bundle(bundle):
            raise ValueError("stored Ice Cube return bundle no longer verifies")

        state_bundle = bundle["state_parcel_bundle"]
        result = state_bundle["parcel"]["payload"]["value"]
        render_bytes = reconstruct_render(result, bundle["chunks"])
        local_dogram = dogram_receipt_for(
            dogram_repo,
            result["specimen"],
            render_bytes,
        )
        local_address = content_address(local_dogram)

        dogram_path = self.dogram_dir / f"{_safe_name(parcel_id)}.json"
        _write_json(dogram_path, local_dogram)
        signed = _verification_receipt(
            state_bundle=state_bundle,
            local_dogram_receipt=local_dogram,
            signer=self.signer,
            node_id=self.node_id,
        )
        _write_json(
            self.receipts_dir / f"{_safe_name(signed['receipt_id'])}.json",
            signed,
        )

        status["verification_status"] = (
            "VERIFIED" if local_dogram.get("status") == "OK" else "REFUSED"
        )
        status["local_dogram_receipt_address"] = local_address
        status["local_verification_receipt_id"] = signed["receipt_id"]
        _write_json(self._status_path(parcel_id), status)
        return {
            "status": status["verification_status"],
            "dogram_receipt": local_dogram,
            "verification_receipt": signed,
        }

    def admit_verified(
        self,
        parcel_id: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        status = self._read_status(parcel_id)
        if status.get("verification_status") != "VERIFIED":
            raise ValueError("Ice Cube cannot ADMIT before receiver-local verification")
        verification_path = self.receipts_dir / (
            f"{_safe_name(str(status['local_verification_receipt_id']))}.json"
        )
        verification_receipt = _read_json(verification_path)
        if not verify_receipt(verification_receipt):
            raise ValueError("stored local verification receipt no longer verifies")

        bundle = _read_json(self._raw_path(parcel_id))
        if not verify_return_bundle(bundle):
            raise ValueError("stored Ice Cube return bundle no longer verifies")
        result = bundle["state_parcel_bundle"]["parcel"]["payload"]["value"]
        render_bytes = reconstruct_render(result, bundle["chunks"])

        receipt = self.state_inbox.decide(
            parcel_id,
            "ADMIT",
            note=note or "owner-local ADMIT after independent Dogram verification",
        )
        if receipt.get("kind") != "ADMITTED":
            return {"admission_receipt": receipt}

        specimen_id = str(result["specimen_id"])
        base = self.root / "ice-cubes" / "returned" / _safe_name(specimen_id)
        render_path = base / "render.pgm"
        result_path = base / "result.return.v0.json"
        base.mkdir(parents=True, exist_ok=True)
        render_path.write_bytes(render_bytes)
        _write_json(result_path, result)

        if content_address(render_path.read_bytes()) != result["render_address"]:
            raise RuntimeError("persisted returned render failed address verification")
        if content_address(_read_json(result_path)["specimen"]) != result["specimen_address"]:
            raise RuntimeError("persisted returned specimen failed address verification")

        status["network_disposition"] = "ADMIT"
        status["admission_receipt_id"] = receipt["receipt_id"]
        status["materialized_render_path"] = str(render_path)
        status["materialized_result_path"] = str(result_path)
        _write_json(self._status_path(parcel_id), status)
        return {
            "admission_receipt": receipt,
            "render_path": str(render_path),
            "result_path": str(result_path),
        }

    def reject(
        self,
        parcel_id: str,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        receipt = self.state_inbox.decide(
            parcel_id,
            "REJECT",
            note=note or "owner-local rejection of returned Ice Cube",
        )
        status = self._read_status(parcel_id)
        status["network_disposition"] = "REJECT"
        status["admission_receipt_id"] = receipt.get("receipt_id")
        _write_json(self._status_path(parcel_id), status)
        return receipt


def send_return_bundle(
    bundle: dict[str, Any],
    base_url: str,
) -> dict[str, Any]:
    if not verify_return_bundle(bundle):
        raise ValueError("refusing to send invalid Ice Cube return bundle")
    data = json.dumps(bundle, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_RETURN_BYTES * 2:
        raise ValueError("encoded Ice Cube return exceeds bounded v0 transport size")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/ice-cube-return",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        receipt = json.loads(response.read().decode("utf-8"))
    if not isinstance(receipt, dict):
        raise RuntimeError("Ice Cube return receiver did not return a receipt")
    state_bundle = bundle["state_parcel_bundle"]
    if receipt.get("crossing_id") != state_bundle["crossing"]["crossing_id"]:
        raise RuntimeError("Ice Cube HOLD receipt crossing mismatch")
    if not verify_receipt(receipt):
        raise RuntimeError("Ice Cube HOLD receipt failed signature verification")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack, send, and verify Ice Cube returns.")
    sub = parser.add_subparsers(dest="command", required=True)

    pack = sub.add_parser("pack")
    pack.add_argument("worker_root", type=Path)
    pack.add_argument("result_path", type=Path)
    pack.add_argument("target_particular")
    pack.add_argument("--out", type=Path, required=True)
    pack.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_BYTES)

    send = sub.add_parser("send")
    send.add_argument("bundle_file", type=Path)
    send.add_argument("base_url")

    verify = sub.add_parser("verify")
    verify.add_argument("parcel_id")
    verify.add_argument("--root", type=Path, default=Path(".ghot"))
    verify.add_argument("--dogram-repo", type=Path, required=True)

    admit = sub.add_parser("admit")
    admit.add_argument("parcel_id")
    admit.add_argument("--root", type=Path, default=Path(".ghot"))

    reject = sub.add_parser("reject")
    reject.add_argument("parcel_id")
    reject.add_argument("--root", type=Path, default=Path(".ghot"))

    args = parser.parse_args()

    if args.command == "pack":
        bundle = make_return_bundle(
            args.worker_root,
            args.result_path,
            target_particular=args.target_particular,
            chunk_size=args.chunk_size,
        )
        _write_json(args.out, bundle)
        parcel = bundle["state_parcel_bundle"]["parcel"]
        print(json.dumps({
            "bundle_file": str(args.out),
            "parcel_id": parcel["parcel_id"],
            "crossing_id": bundle["state_parcel_bundle"]["crossing"]["crossing_id"],
            "chunk_count": len(bundle["chunks"]),
        }, indent=2))
        return 0

    if args.command == "send":
        bundle = _read_json(args.bundle_file)
        print(json.dumps(send_return_bundle(bundle, args.base_url), indent=2))
        return 0

    inbox = IceCubeReturnInbox(args.root)
    if args.command == "verify":
        print(json.dumps(
            inbox.verify_local(args.parcel_id, dogram_repo=args.dogram_repo),
            indent=2,
        ))
        return 0
    if args.command == "admit":
        print(json.dumps(inbox.admit_verified(args.parcel_id), indent=2))
        return 0
    if args.command == "reject":
        print(json.dumps(inbox.reject(args.parcel_id), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
