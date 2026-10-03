#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 013."""

from __future__ import annotations

import copy
import json
import tempfile
import time
from pathlib import Path

from authority_discovery import (
    AuthorityTrustStore,
    advert_is_fresh,
    make_authority_advert,
    trusted_observations,
    verify_authority_advert,
)
from relatte_identity import IdentityKey, timestamp_ms


def base(authority_id: str, signer: IdentityKey) -> dict:
    return {
        "kind": "ghot.lease.authority",
        "version": "1",
        "authority_id": authority_id,
        "owner_node_id": "node-owner",
        "world_id": f"ghot-authority-world:{authority_id}",
        "particular": signer.particular(),
        "public_key": signer.public_jwk(),
        "capability_ref": "ghot.work-lease/v0",
        "crossing_schema": "relatte.crossing-envelope/v0",
        "receipt_schema": "relatte.receipt/v0",
        "signing_profile": "relatte.identity-signature/v0",
        "algorithm": "ECDSA-P256-SHA256",
        "public_key_identity_claimed": True,
    }


def observation(advert: dict, address: str) -> dict:
    return {
        "advert": advert,
        "address": address,
        "authority_url": f"http://{address}:{advert['lease_port']}",
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = AuthorityTrustStore(root)

        good_key = IdentityKey.load_or_create(root / "good.pem")
        other_key = IdentityKey.load_or_create(root / "other.pem")

        good = make_authority_advert(
            base("authority-good", good_key),
            signer=good_key,
            lease_port=7790,
            ttl_seconds=30,
        )
        other = make_authority_advert(
            base("authority-other", other_key),
            signer=other_key,
            lease_port=7790,
            ttl_seconds=30,
        )

        assert verify_authority_advert(good)
        assert verify_authority_advert(other)

        tampered = copy.deepcopy(good)
        tampered["lease_port"] = 9999
        assert not verify_authority_advert(tampered)

        before = trusted_observations(
            [observation(good, "10.0.0.5"), observation(other, "10.0.0.6")],
            store=store,
        )
        assert before == []

        admitted = store.trust(good, route="http://10.0.0.5:7790")
        assert admitted["particular"] == good["particular"]

        after = trusted_observations(
            [observation(good, "10.0.0.5"), observation(other, "10.0.0.6")],
            store=store,
        )
        assert len(after) == 1
        assert after[0]["advert"]["particular"] == good["particular"]
        assert after[0]["trust"] == "remembered"

        moved_road = trusted_observations(
            [observation(good, "10.0.0.77")],
            store=store,
        )
        assert len(moved_road) == 1
        assert moved_road[0]["authority_url"] == "http://10.0.0.77:7790"

        wrong_authority_id = make_authority_advert(
            {
                **base("authority-impostor-name", good_key),
                "world_id": "ghot-authority-world:authority-impostor-name",
            },
            signer=good_key,
            lease_port=7790,
            ttl_seconds=30,
        )
        assert verify_authority_advert(wrong_authority_id)
        mismatch = trusted_observations(
            [observation(wrong_authority_id, "10.0.0.88")],
            store=store,
        )
        assert mismatch == []

        pinned = trusted_observations(
            [observation(other, "10.0.0.6")],
            store=AuthorityTrustStore(root / "empty"),
            pinned_particular=other["particular"],
        )
        assert len(pinned) == 1
        assert pinned[0]["trust"] == "pinned"

        now = time.time()
        stale = make_authority_advert(
            base("authority-good", good_key),
            signer=good_key,
            lease_port=7790,
            ttl_seconds=5,
            issued_at=timestamp_ms(now - 60),
        )
        assert verify_authority_advert(stale)
        assert not advert_is_fresh(stale, at=now)

        removed = store.forget(good["particular"])
        assert removed
        forgotten = trusted_observations(
            [observation(good, "10.0.0.5")],
            store=store,
        )
        assert forgotten == []

        passed = (
            before == []
            and len(after) == 1
            and moved_road[0]["authority_url"] == "http://10.0.0.77:7790"
            and mismatch == []
            and len(pinned) == 1
            and not advert_is_fresh(stale, at=now)
            and forgotten == []
        )

        print(json.dumps({
            "simulation_passed": passed,
            "signed_advert": verify_authority_advert(good),
            "tamper_rejected": not verify_authority_advert(tampered),
            "discovery_before_trust": len(before),
            "remembered_authority_count": len(after),
            "road_change_preserved_identity": moved_road[0]["authority_url"],
            "same_key_wrong_authority_id_rejected": mismatch == [],
            "pin_accepts_without_store": len(pinned) == 1,
            "stale_advert_rejected": not advert_is_fresh(stale, at=now),
            "forget_removes_admission": forgotten == [],
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
