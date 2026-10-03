#!/usr/bin/env python3
"""Shared epistemic-offer matching for GHoT capability composition."""

from __future__ import annotations

from typing import Any


CONTEXT_POSTURES = ("fresh", "bounded-window", "lineage-enabled", "owner-local")


def capability_offers(
    body_record: dict[str, Any],
    capability: str,
) -> list[dict[str, Any]]:
    return [
        offer
        for offer in body_record.get("offers", [])
        if offer.get("capability") == capability
    ]


def posture_matching_offers(
    body_record: dict[str, Any],
    capability: str,
    context_posture: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if context_posture is not None and context_posture not in CONTEXT_POSTURES:
        raise ValueError(f"unknown context posture: {context_posture}")

    all_capability_offers = capability_offers(body_record, capability)
    matching = [
        offer
        for offer in all_capability_offers
        if context_posture is None or offer.get("context_posture") == context_posture
    ]
    return all_capability_offers, matching
