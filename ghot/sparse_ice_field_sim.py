#!/usr/bin/env python3
"""Closed-loop SPARSE ICE FIELD 001 integration proof."""

from __future__ import annotations

import base64
import copy
import json
import math
import tempfile
from pathlib import Path

from field_commons import (
    FieldCommonsStore,
    _validate_commons_contract,
    accept_commons_offer,
    make_artifact_access_grant,
    make_artifact_for_compute_offer,
    verify_artifact_access_grant,
)
from ice_cube import (
    FAMILY,
    challenge_coordinates,
    content_address,
    fibonacci_matrix_power,
    make_execution_receipt,
    make_halley_witnesses,
    make_work_crossing,
    render_pgm,
    verify_with_dogram,
    work_address,
)
from ice_cube_return import IceCubeReturnInbox, make_return_bundle
from ice_field import IceFieldStore
from lightwalker_economy import LightwalkerEconomyError
from lightwalker_guild_authorization import (
    GuildAuthorizationStore,
    apply_execution_to_treasury,
    authorize_resource_proposal,
    make_resource_proposal,
    verify_execution_receipt,
    verify_resource_authorization,
)
from lightwalker_guild_reservation import GuildReservationStore
from lightwalker_guild_treasury import (
    make_treasury_entry,
    make_treasury_snapshot,
    verify_treasury_snapshot,
)
from lightwalker_heterogeneous_exchange import (
    settle_exchange,
    sign_obligation_performance,
    verify_exchange_acceptance,
    verify_exchange_offer,
    verify_exchange_settlement,
)
from lightwalker_sparse_region_lease import (
    SparseRegionLeaseBudget,
    SparseRegionLeaseIssuer,
    derive_sparse_region_execution_evidence,
    verify_sparse_region_close,
    verify_sparse_region_lease,
    verify_sparse_region_release,
    verify_sparse_region_use,
)
from lightwalker_work_region_salvage import region_claim_set
from merge_contract_pantry import MergeContractPantry
from merge_plugin import MergePluginStore, verify_install_receipt
from relatte_identity import IdentityKey
from sparse_ice_field import (
    dogram_sparse_receipt_for,
    make_genesis_missing_set,
    reconstruct_pgm_from_region_claims,
)
from state_merge import MERGE_CONTRACTS, StateMergeEngine, verify_merge_receipt


PACKAGE_ID = "ghot.plugin.verified-ice-cube"
CONTRACT_ID = "ghot.ice-cube-result->verified-ice-cube-catalog/v0"


def refused(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def install_and_merge(root: Path, parcel_id: str, package: dict) -> None:
    install = MergePluginStore(root).install(
        package,
        builtin_contract_ids=set(MERGE_CONTRACTS),
    )
    assert verify_install_receipt(install)
    pantry = MergeContractPantry(root)
    inspection = pantry.inspect(parcel_id)
    assert CONTRACT_ID in inspection["compatible_contract_ids"]
    selection = pantry.select(parcel_id, CONTRACT_ID)
    proposal = pantry.propose(selection["selection_id"])
    receipt = StateMergeEngine(root).apply(
        proposal["plan"]["plan_id"],
        note="Sparse Ice Field verified cube enters local pantry",
    )
    assert verify_merge_receipt(receipt)


def seed_field(
    receiver_root: Path,
    dogram_repo: Path,
    package: dict,
) -> tuple[IceFieldStore, IceCubeReturnInbox, dict]:
    from ice_cube import build_work, mine_ice_cube

    seed_worker = receiver_root.parent / "seed-worker"
    inbox = IceCubeReturnInbox(receiver_root)
    seed = mine_ice_cube(
        worker_root=seed_worker,
        dogram_repo=dogram_repo,
        work=build_work(
            lucas_index=2,
            width=6,
            height=6,
            max_halley_iter=8,
        ),
    )
    bundle = make_return_bundle(
        seed_worker,
        seed["result_path"],
        target_particular=inbox.signer.particular(),
        chunk_size=97,
    )
    held = inbox.receive(bundle)
    assert held["kind"] == "HELD"
    parcel_id = bundle["state_parcel_bundle"]["parcel"]["parcel_id"]
    verified = inbox.verify_local(parcel_id, dogram_repo=dogram_repo)
    assert verified["status"] == "VERIFIED"
    admitted = inbox.admit_verified(parcel_id)
    assert admitted["admission_receipt"]["kind"] == "ADMITTED"
    install_and_merge(receiver_root, parcel_id, package)
    field = IceFieldStore(receiver_root)
    field.refresh()
    return field, inbox, seed


def provider(
    base: Path,
    name: str,
    *,
    quantity: int,
    evidence_ref: str,
) -> dict:
    guild = IdentityKey.load_or_create(base / name / "guild.pem")
    worker = IdentityKey.load_or_create(base / name / "worker.pem")
    entry = make_treasury_entry(
        category="capability",
        position="available",
        subject_ref="ghot-capability:ghot.ice-cube-region/v0",
        source_ref=f"provider:{name}",
        evidence_refs=[evidence_ref],
        native_measure={
            "unit": "compute-minute",
            "quantity": quantity,
        },
        metadata={
            "scope": "exact sparse Ice Cube regions",
        },
    )
    snapshot = make_treasury_snapshot(
        guild_id=f"guild:sparse:{name}",
        steward=guild,
        entries=[entry],
        sequence=0,
    )
    return {
        "guild": guild,
        "worker": worker,
        "entry": entry,
        "snapshot": snapshot,
        "store": GuildReservationStore(
            base / name / "reservations",
            steward=guild,
        ),
    }


def execute_regions(
    provider_record: dict,
    *,
    work: dict,
    plan: dict,
    missing_set: dict,
    lease: dict,
    region_ids: list[str],
    root: Path,
    cut: int,
) -> dict:
    worker = provider_record["worker"]
    proposal = make_resource_proposal(
        provider_record["snapshot"],
        proposer=worker,
        resource_entry_id=provider_record["entry"]["entry_id"],
        requested_quantity=len(region_ids),
        requested_unit="compute-minute",
        purpose_ref=lease["sparse_region_lease_id"],
        proposed_at_cut=cut,
    )
    authorization, reservation = provider_record["store"].reserve_and_authorize(
        provider_record["snapshot"],
        proposal,
        executor_particular=worker.particular(),
        authorized_at_cut=cut,
        expires_after_cut=cut + 20,
    )
    claims = region_claim_set(
        work,
        plan,
        region_ids=region_ids,
        executor_particular=worker.particular(),
    )
    execution, finalization = provider_record["store"].execute_reserved(
        provider_record["snapshot"],
        proposal,
        authorization,
        reservation,
        executor=worker,
        observed_cut=cut,
        simulate_success=True,
        result_ref=claims["region_claim_set_id"],
    )
    budget = SparseRegionLeaseBudget(
        root / ("budget-" + worker.particular()[-12:]),
        node=worker,
    )
    use = budget.record_execution(
        work,
        plan,
        missing_set,
        lease,
        region_ids=region_ids,
        snapshot=provider_record["snapshot"],
        proposal=proposal,
        authorization=authorization,
        reservation=reservation,
        execution=execution,
        finalization=finalization,
        observed_cut=cut,
    )
    assert verify_sparse_region_use(
        work,
        plan,
        missing_set,
        lease,
        use,
    )
    return {
        "budget": budget,
        "use": use,
        "proposal": proposal,
        "authorization": authorization,
        "reservation": reservation,
        "execution": execution,
        "finalization": finalization,
    }


def build_sparse_result(
    *,
    worker_root: Path,
    signer: IdentityKey,
    node_id: str,
    work: dict,
    render_bytes: bytes,
    claims: list[dict],
    dogram_repo: Path,
) -> tuple[dict, Path, dict]:
    render_address = content_address(render_bytes)
    index = int(work["lucas_index"])
    matrix_power = 2 * index
    matrix = fibonacci_matrix_power(matrix_power)
    trace = matrix[0][0] + matrix[1][1]
    determinant = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    fiber_count = int(work["mapping_torus"]["fiber_count"])
    shift = trace % fiber_count
    components = math.gcd(fiber_count, shift)

    by_xy = {
        (int(row["x"]), int(row["y"])): int(row["value"])
        for row in claims
    }
    coords = challenge_coordinates(
        work,
        int(work["render"]["challenge_count"]),
    )
    pixel_challenges = [
        {"x": x, "y": y, "value": by_xy[(x, y)]}
        for x, y in coords
    ]

    specimen_core = {
        "family": FAMILY,
        "work_address": work_address(work),
        "render_address": render_address,
        "monodromy_trace": trace,
    }
    specimen_id = "ice-cube-v0:" + __import__("hashlib").sha256(
        json.dumps(
            specimen_core,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    specimen = {
        "schema": "static.ice-cube-specimen/v0",
        "specimen_id": specimen_id,
        "family": FAMILY,
        "work": work,
        "work_address": work_address(work),
        "lucas_value": int(work["period"]),
        "monodromy": {
            "power": matrix_power,
            "matrix": [list(matrix[0]), list(matrix[1])],
            "trace": trace,
            "determinant": determinant,
        },
        "mapping_torus": {
            "fiber_count": fiber_count,
            "shift": shift,
            "normalized_shift": shift % fiber_count,
            "components": components,
            "orbit_length": fiber_count // components,
        },
        "halley_witnesses": make_halley_witnesses(work),
        "render": {
            "address": render_address,
            "challenge_count": len(pixel_challenges),
            "pixel_challenges": pixel_challenges,
        },
    }
    specimen_address = content_address(specimen)
    dogram_receipt = verify_with_dogram(
        dogram_repo,
        specimen,
        render_bytes,
    )
    assert dogram_receipt["status"] == "OK"
    dogram_receipt_address = content_address(dogram_receipt)

    crossing = make_work_crossing(
        work,
        signer=signer,
        node_id=node_id,
    )
    execution_receipt = make_execution_receipt(
        crossing,
        signer=signer,
        node_id=node_id,
        specimen_address=specimen_address,
        render_address=render_address,
        dogram_receipt_address=dogram_receipt_address,
    )

    result = {
        "kind": "ghot.ice-cube-result",
        "version": "0",
        "specimen_id": specimen_id,
        "family": FAMILY,
        "work_address": work_address(work),
        "specimen_address": specimen_address,
        "render_address": render_address,
        "dogram_receipt_address": dogram_receipt_address,
        "dogram_status": dogram_receipt["status"],
        "execution_receipt_id": execution_receipt["receipt_id"],
        "work_crossing_id": crossing["crossing_id"],
        "work_crossing": crossing,
        "execution_receipt": execution_receipt,
        "render_encoding": "base64",
        "render_base64": base64.b64encode(render_bytes).decode("ascii"),
        "specimen": specimen,
        "dogram_receipt": dogram_receipt,
    }
    base = worker_root / "ice-cubes" / "outgoing" / specimen_id.replace(":", "_")
    base.mkdir(parents=True, exist_ok=True)
    path = base / "result.v0.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result, path, dogram_receipt


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dogram-repo", type=Path, required=True)
    args = parser.parse_args()
    dogram_repo = args.dogram_repo.resolve()

    repo_root = Path(__file__).resolve().parents[1]
    package = json.loads(
        (
            repo_root
            / "examples"
            / "merge-plugins"
            / "verified-ice-cube.package.json"
        ).read_text(encoding="utf-8")
    )

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        receiver_root = base / "receiver"
        sparse_worker_root = base / "sparse-coordinator"

        field, inbox, seed = seed_field(
            receiver_root,
            dogram_repo,
            package,
        )
        want = next(
            item for item in field.wants()
            if item["relation"] == "lucas-next"
        )
        work = copy.deepcopy(want["work"])
        # Freeze a small but nontrivial child for the integration proof.
        work["render"]["width"] = 6
        work["render"]["height"] = 6
        work["render"]["max_halley_iter"] = 8
        work["render"]["challenge_count"] = 8
        want["work"] = work
        want["work_address"] = work_address(work)

        artifact_owner = IdentityKey.load_or_create(base / "keys" / "artifact-owner.pem")
        guild = IdentityKey.load_or_create(base / "keys" / "commons-guild.pem")
        service_executor = IdentityKey.load_or_create(base / "keys" / "service-executor.pem")

        offer = make_artifact_for_compute_offer(
            artifact_owner=artifact_owner,
            guild_particular=guild.particular(),
            artifact_ref=seed["specimen"]["render"]["address"],
            want=want,
            valid_through_cut=50,
        )
        acceptance = accept_commons_offer(
            offer,
            guild=guild,
            accepted_at_cut=2,
        )
        assert verify_exchange_offer(offer)
        assert verify_exchange_acceptance(offer, acceptance)

        service_entry = make_treasury_entry(
            category="capability",
            position="available",
            subject_ref=f"ghot-capability:{FAMILY}",
            source_ref="field-commons:sparse-service",
            evidence_refs=[offer["offer_id"]],
            native_measure={"unit": "ice-cube-job", "quantity": 1},
            metadata={"backing": "exact sparse region workers"},
        )
        service_treasury = make_treasury_snapshot(
            guild_id="guild:sparse-field-commons",
            steward=guild,
            entries=[service_entry],
            sequence=0,
        )
        service_proposal = make_resource_proposal(
            service_treasury,
            proposer=artifact_owner,
            resource_entry_id=service_entry["entry_id"],
            requested_quantity=1,
            requested_unit="ice-cube-job",
            purpose_ref=want["want_id"],
            proposed_at_cut=3,
        )
        service_authorization = authorize_resource_proposal(
            service_treasury,
            service_proposal,
            steward=guild,
            executor_particular=service_executor.particular(),
            authorized_at_cut=4,
            expires_after_cut=40,
        )
        assert verify_resource_authorization(
            service_treasury,
            service_proposal,
            service_authorization,
        )

        invalid_authority_refused = refused(
            lambda: _validate_commons_contract(
                want=want,
                offer=offer,
                acceptance=acceptance,
                treasury_snapshot=service_treasury,
                proposal=service_proposal,
                authorization={},
                guild=guild,
                executor=service_executor,
            )
        )
        assert invalid_authority_refused
        _validate_commons_contract(
            want=want,
            offer=offer,
            acceptance=acceptance,
            treasury_snapshot=service_treasury,
            proposal=service_proposal,
            authorization=service_authorization,
            guild=guild,
            executor=service_executor,
        )
        commons_claims = FieldCommonsStore(receiver_root)
        commons_claims._claim(
            service_authorization["authorization_id"],
            want["want_id"],
        )
        service_replay_refused = refused(
            lambda: commons_claims._claim(
                service_authorization["authorization_id"],
                want["want_id"],
            )
        )
        assert service_replay_refused

        plan, missing_set = make_genesis_missing_set(
            work,
            assignment_owner_particular=guild.particular(),
            continuation_lineage_id=f"sparse-ice:{want['want_id']}",
        )
        all_regions = list(missing_set["missing_region_ids"])
        assert len(all_regions) == 36

        issuer = SparseRegionLeaseIssuer(
            base / "sparse-assignment-ledger",
            assigner=guild,
        )
        r = provider(
            base / "providers",
            "r",
            quantity=22,
            evidence_ref=want["want_id"],
        )
        s = provider(
            base / "providers",
            "s",
            quantity=14,
            evidence_ref=want["want_id"],
        )

        lease_r = issuer.issue(
            missing_set,
            pixel_region_plan_id=plan["pixel_region_plan_id"],
            node_id="node:r",
            node_particular=r["worker"].particular(),
            region_ids=all_regions,
            issued_at_cut=5,
            expires_after_cut=30,
        )
        assert verify_sparse_region_lease(missing_set, lease_r)
        overlap_refused = refused(
            lambda: issuer.issue(
                missing_set,
                pixel_region_plan_id=plan["pixel_region_plan_id"],
                node_id="node:s-overlap",
                node_particular=s["worker"].particular(),
                region_ids=[all_regions[0]],
                issued_at_cut=5,
                expires_after_cut=30,
            )
        )
        assert overlap_refused

        r_ids = all_regions[:22]
        r_exec = execute_regions(
            r,
            work=work,
            plan=plan,
            missing_set=missing_set,
            lease=lease_r,
            region_ids=r_ids,
            root=base,
            cut=6,
        )
        release_r = r_exec["budget"].release(
            missing_set,
            lease_r,
            observed_cut=7,
        )
        assert verify_sparse_region_release(lease_r, release_r)
        assert release_r["consumed_region_ids"] == r_ids
        returned = list(release_r["returned_region_ids"])
        assert returned == all_regions[22:]
        close_r = issuer.close(
            missing_set,
            lease_r,
            release_r,
            observed_cut=7,
        )
        assert verify_sparse_region_close(missing_set, lease_r, close_r)

        consumed_reassignment_refused = refused(
            lambda: issuer.issue(
                missing_set,
                pixel_region_plan_id=plan["pixel_region_plan_id"],
                node_id="node:s-bad",
                node_particular=s["worker"].particular(),
                region_ids=[r_ids[0]],
                issued_at_cut=8,
                expires_after_cut=30,
            )
        )
        assert consumed_reassignment_refused

        lease_s = issuer.issue(
            missing_set,
            pixel_region_plan_id=plan["pixel_region_plan_id"],
            node_id="node:s",
            node_particular=s["worker"].particular(),
            region_ids=returned,
            issued_at_cut=8,
            expires_after_cut=30,
        )
        s_exec = execute_regions(
            s,
            work=work,
            plan=plan,
            missing_set=missing_set,
            lease=lease_s,
            region_ids=returned,
            root=base,
            cut=9,
        )
        release_s = s_exec["budget"].release(
            missing_set,
            lease_s,
            observed_cut=10,
        )
        assert release_s["returned_region_ids"] == []
        close_s = issuer.close(
            missing_set,
            lease_s,
            release_s,
            observed_cut=10,
        )

        bundles = [
            {
                "lease": lease_r,
                "use": r_exec["use"],
                "release": release_r,
                "close": close_r,
                "snapshot": r["snapshot"],
                "proposal": r_exec["proposal"],
                "authorization": r_exec["authorization"],
                "reservation": r_exec["reservation"],
                "execution": r_exec["execution"],
                "finalization": r_exec["finalization"],
            },
            {
                "lease": lease_s,
                "use": s_exec["use"],
                "release": release_s,
                "close": close_s,
                "snapshot": s["snapshot"],
                "proposal": s_exec["proposal"],
                "authorization": s_exec["authorization"],
                "reservation": s_exec["reservation"],
                "execution": s_exec["execution"],
                "finalization": s_exec["finalization"],
            },
        ]
        sparse_evidence = derive_sparse_region_execution_evidence(
            work,
            plan,
            missing_set,
            bundles,
        )
        assert sparse_evidence["all_missing_regions_satisfied"] is True
        assert sparse_evidence["region_authority_duplicated"] is False
        assert sparse_evidence["region_count"] == 36

        claims = sparse_evidence["region_claims"]
        render_bytes = reconstruct_pgm_from_region_claims(
            work,
            plan,
            claims,
        )

        # CI oracle only: prove the sparse reconstruction is byte-identical to
        # the ordinary renderer. Production artifact creation above does not use
        # render_pgm.
        oracle_render, _ = render_pgm(work)
        assert render_bytes == oracle_render

        sparse_dogram = dogram_sparse_receipt_for(
            dogram_repo,
            work,
            plan,
            claims,
            root_probe_count=4,
            prior={"clean": "3/4", "dirty": "1/4"},
        )
        assert sparse_dogram["status"] == "OK"
        assert sparse_dogram["branch_triggered"] is False
        assert sparse_dogram["probed_region_count"] == 4

        # Cost prior changes interpretation, never evidence/probe selection.
        sparse_dogram_uniform = dogram_sparse_receipt_for(
            dogram_repo,
            work,
            plan,
            claims,
            root_probe_count=4,
            prior={"clean": "1/2", "dirty": "1/2"},
        )
        assert sparse_dogram_uniform["status"] == sparse_dogram["status"]
        assert sparse_dogram_uniform["probed_region_indices"] == sparse_dogram[
            "probed_region_indices"
        ]
        assert sparse_dogram_uniform["cost_analysis"][
            "adaptive_expected_cost_if_prior_declared"
        ] != sparse_dogram["cost_analysis"][
            "adaptive_expected_cost_if_prior_declared"
        ]

        damaged = copy.deepcopy(claims)
        bad_index = sparse_dogram["root_probe_indices"][0]
        damaged[bad_index]["value"] ^= 0x01
        refused_probe = dogram_sparse_receipt_for(
            dogram_repo,
            work,
            plan,
            damaged,
            root_probe_count=4,
        )
        assert refused_probe["status"] == "REFUSED"
        assert refused_probe["branch_triggered"] is True
        assert refused_probe["probed_region_count"] == 36

        result, result_path, standard_dogram = build_sparse_result(
            worker_root=sparse_worker_root,
            signer=service_executor,
            node_id="node:sparse-commons",
            work=work,
            render_bytes=render_bytes,
            claims=claims,
            dogram_repo=dogram_repo,
        )
        assert standard_dogram["status"] == "OK"

        return_bundle = make_return_bundle(
            sparse_worker_root,
            result_path,
            target_particular=inbox.signer.particular(),
            chunk_size=113,
        )
        held = inbox.receive(return_bundle)
        assert held["kind"] == "HELD"
        child_parcel_id = return_bundle["state_parcel_bundle"]["parcel"]["parcel_id"]
        assert inbox.show(child_parcel_id)["status"]["verification_status"] == "UNVERIFIED"

        service_evidence = {
            "kind": "ghot.sparse-ice-field.service-evidence",
            "version": "0",
            "want_id": want["want_id"],
            "work_address": want["work_address"],
            "sparse_region_execution_evidence_id": sparse_evidence[
                "sparse_region_execution_evidence_id"
            ],
            "sparse_dogram_receipt_id": sparse_dogram["receipt_id"],
            "standard_dogram_receipt_address": content_address(standard_dogram),
            "returned_parcel_id": child_parcel_id,
            "return_disposition": held["kind"],
            "return_semantic_effect": held["semantic_effect"],
        }
        service_evidence_id = content_address(service_evidence)

        service_store = GuildAuthorizationStore(
            base / "service-authorization-execution"
        )
        service_execution = service_store.execute(
            service_treasury,
            service_proposal,
            service_authorization,
            executor=service_executor,
            observed_cut=11,
            simulate_success=True,
            result_ref=service_evidence_id,
        )
        assert verify_execution_receipt(
            service_treasury,
            service_proposal,
            service_authorization,
            service_execution,
        )
        service_treasury_after = apply_execution_to_treasury(
            service_treasury,
            service_proposal,
            service_authorization,
            service_execution,
            steward=guild,
        )
        assert verify_treasury_snapshot(service_treasury_after)

        grant = make_artifact_access_grant(
            owner=artifact_owner,
            grantee_particular=guild.particular(),
            artifact_ref=seed["specimen"]["render"]["address"],
            offer_id=offer["offer_id"],
        )
        assert verify_artifact_access_grant(grant)
        offeror_perf = sign_obligation_performance(
            offer,
            acceptance,
            role="OFFEROR",
            signer=artifact_owner,
            evidence_ref=grant["grant_id"],
        )
        acceptor_perf = sign_obligation_performance(
            offer,
            acceptance,
            role="ACCEPTOR",
            signer=guild,
            evidence_ref=service_execution["execution_receipt_id"],
        )
        settlement = settle_exchange(
            offer,
            acceptance,
            [offeror_perf, acceptor_perf],
        )
        assert verify_exchange_settlement(
            offer,
            acceptance,
            [offeror_perf, acceptor_perf],
            settlement,
        )

        # Settlement still cannot admit the artifact.
        before_verify = inbox.show(child_parcel_id)
        assert before_verify["state_parcel"]["queue"]["status"] == "HOLD"
        assert before_verify["status"]["verification_status"] == "UNVERIFIED"

        local = inbox.verify_local(
            child_parcel_id,
            dogram_repo=dogram_repo,
        )
        assert local["status"] == "VERIFIED"
        admitted = inbox.admit_verified(child_parcel_id)
        assert admitted["admission_receipt"]["kind"] == "ADMITTED"
        install_and_merge(receiver_root, child_parcel_id, package)

        refreshed = field.refresh()
        completed = field.load(next(
            row["want_id"] for row in field.wants()
            if row["work_address"] == work_address(work)
        ))
        assert completed["status"] == "satisfied"
        catalog = json.loads(field.catalog_path.read_text(encoding="utf-8"))
        assert len(catalog["entries"]) == 2

        print(json.dumps({
            "simulation_passed": True,
            "commons": {
                "settlement_status": settlement["status"],
                "common_unit": None,
                "service_authorization_required": invalid_authority_refused,
                "service_authorization_replay_refused": service_replay_refused,
                "settled_while_artifact_hold": True,
            },
            "sparse_regions": {
                "root_regions": len(all_regions),
                "r_consumed": len(r_ids),
                "r_returned": len(returned),
                "s_consumed": len(returned),
                "live_overlap_refused": overlap_refused,
                "consumed_reassignment_refused": consumed_reassignment_refused,
                "region_authority_duplicated": sparse_evidence[
                    "region_authority_duplicated"
                ],
            },
            "workers": {
                "service_authority_distinct_from_worker_capacity": True,
                "region_assignment_distinct_from_worker_capacity": True,
                "worker_r_capacity_consumed": len(r_ids),
                "worker_s_capacity_consumed": len(returned),
            },
            "dogram": {
                "sparse_status": sparse_dogram["status"],
                "adaptive_root_probes": sparse_dogram["probed_region_count"],
                "prior_changed_cost_not_evidence": True,
                "damaged_root_triggered_full_probe": refused_probe[
                    "probed_region_count"
                ] == 36,
                "damaged_claim_refused": refused_probe["status"] == "REFUSED",
                "standard_ice_receipt": standard_dogram["status"],
            },
            "artifact": {
                "reconstructed_from_sparse_claims": True,
                "oracle_byte_identical": render_bytes == oracle_render,
                "render_address": result["render_address"],
                "return_disposition": held["kind"],
                "receiver_reverified": local["status"],
                "owner_admitted": admitted["admission_receipt"]["kind"],
            },
            "field": {
                "completed_want": completed["status"],
                "verified_pantry_entries": len(catalog["entries"]),
                "new_wants_after_growth": refreshed["want_count"],
            },
        }, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
