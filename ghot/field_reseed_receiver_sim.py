#!/usr/bin/env python3
"""Deterministic proof for FIELD-RESEED-RECEIVER-001."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from field_reseed_receiver import admit, receive, status


def reseed() -> dict:
    body = {
        "schema": "workbench.field-reseed/v0",
        "source_return_id": "field-return-v0:" + "1" * 64,
        "field_state_id": "field-station-v0:" + "2" * 64,
        "door": {
            "schema": "workbench.field-station-door/v0",
            "door_id": "field-door-v0:" + "3" * 64,
            "kind": "hold-silence",
            "label": "Hold silence",
            "why": "Nothing is obligated to cross.",
            "lane": "silence",
            "adapter": "House / HOLD",
            "evidence": [],
            "target": None,
            "effect": "none",
            "laws": [],
        },
        "human_note": "carry the exact possibility",
        "status": "proposal-only",
        "effect": "none",
        "laws": [
            "RESEED != ADMISSION",
            "TRANSPORT != AUTHORITY",
            "DOWNSTREAM INTERPRETATION != SOURCE FACT",
        ],
    }
    from field_reseed_receiver import _digest
    return {
        **body,
        "reseed_id": "field-reseed-v0:" + _digest(body),
    }


def relatte(seed: dict) -> dict:
    from field_reseed_receiver import _digest
    crossing_id = "relatte-crossing-v0:" + "4" * 64
    return {
        "schema": "relatte.opaque-roundtrip-result/v0",
        "request_id": "relatte-opaque-roundtrip-v0:" + "5" * 64,
        "crossing": {
            "crossing_id": crossing_id,
            "payload_refs": [{
                "address": "sha256:" + _digest(seed),
                "role": "field-reseed",
                "media_type": "application/json",
            }],
            "extensions": {
                "organ_adapter": {
                    "family_ref": "organ:static-workbench/field-return",
                    "donor_claims": {
                        "reseed_id": seed["reseed_id"],
                    },
                },
            },
        },
        "receive_receipt": {
            "crossing_id": crossing_id,
            "receipt_id": "relatte-receipt-v0:" + "6" * 64,
            "kind": "RECEIVED",
            "semantic_effect": "none",
            "world_id": "world:ghot:field-reseed-inbox",
        },
        "disposition_receipt": {
            "crossing_id": crossing_id,
            "receipt_id": "relatte-receipt-v0:" + "7" * 64,
            "kind": "R3_HOLD",
            "semantic_effect": "none",
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ghot-field-reseed-") as raw:
        os.environ["GHOT_HOME"] = str(Path(raw) / "ghot")
        seed = reseed()
        crossing = relatte(seed)

        held = receive(seed, crossing)
        assert held["status"] == "HOLD"
        assert held["semantic_effect"] == "none"
        assert held["donor_reseed"] == seed

        repeated = receive(seed, crossing)
        assert repeated["hold_id"] == held["hold_id"]
        assert status()["held"] == 1
        assert status()["admitted"] == 0

        admitted = admit(held["hold_id"], "human-explicit")
        assert admitted["status"] == "ADMITTED"
        assert admitted["semantic_effect"] == "local-inbox-only"
        assert admitted["intent"]["status"] == "admitted-not-assigned"
        assert admitted["intent"]["effect"] == "local-inbox-only"

        repeated_admission = admit(held["hold_id"], "human-explicit")
        assert repeated_admission["admission_id"] == admitted["admission_id"]

        final = status()
        assert final["held"] == 0
        assert final["admitted"] == 1
        assert final["items"][0]["intent_id"] == admitted["intent"]["intent_id"]

        # Admission is deliberately not execution.
        assert not (Path(os.environ["GHOT_HOME"]) / "executions").exists()

    print(json.dumps({
        "status": "ok",
        "law": "ADMISSION != EXECUTION",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
