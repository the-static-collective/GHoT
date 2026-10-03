#!/usr/bin/env python3
"""Verify GHoT's Python identity profile against reLATTE fixed fixtures."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from relatte_identity import (
    derive_crossing_id,
    derive_receipt_id,
    verify_crossing,
    verify_receipt,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    crossing = json.loads(
        (ROOT / "fixtures" / "relatte-genesis-signed-crossing.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (ROOT / "fixtures" / "relatte-genesis-signed-receipt.json").read_text(
            encoding="utf-8"
        )
    )

    crossing_id_match = derive_crossing_id(crossing) == crossing["crossing_id"]
    receipt_id_match = derive_receipt_id(receipt) == receipt["receipt_id"]
    crossing_valid = verify_crossing(crossing)
    receipt_valid = verify_receipt(receipt)

    mutated = copy.deepcopy(crossing)
    mutated["source_world"] = "world:mutated"
    mutation_rejected = not verify_crossing(mutated)

    passed = (
        crossing_id_match
        and receipt_id_match
        and crossing_valid
        and receipt_valid
        and mutation_rejected
    )

    print(json.dumps({
        "simulation_passed": passed,
        "crossing_id_match": crossing_id_match,
        "receipt_id_match": receipt_id_match,
        "crossing_signature_valid": crossing_valid,
        "receipt_signature_valid": receipt_valid,
        "semantic_mutation_rejected": mutation_rejected,
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
