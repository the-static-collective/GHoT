#!/usr/bin/env python3
"""UNFINISHED BUSINESS 001: bounded, read-only opportunity discovery.

All metadata is caller-declared. Git refs and assertions are NOT fetched or
verified here; matching is not authority, compatibility, or execution.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "ghot.unfinished-inventory/v0"
RESULT_SCHEMA = "ghot.unfinished-cases/v0"
DECISION_SCHEMA = "ghot.unfinished-decision/v0"
CAP = re.compile(r"^[a-z][a-z0-9._-]{0,119}$")
KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
STATES = {"OPEN", "HELD", "RELEASED"}
DECISIONS = {"HOLD", "RELEASED", "ACCEPT_FOR_REVIEW"}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label)
    return value.strip()


def capabilities(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError(label)
    if any(not isinstance(x, str) or not CAP.fullmatch(x) for x in value):
        raise ValueError(label)
    if len(value) != len(set(value)):
        raise ValueError(label + "_DUPLICATE")
    return sorted(value)


def source(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("SOURCE_REQUIRED")
    repo = nonempty(value.get("repo"), "SOURCE_REPO")
    commit = nonempty(value.get("commit"), "SOURCE_COMMIT")
    path = nonempty(value.get("path"), "SOURCE_PATH")
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
            or not SHA.fullmatch(commit) or path.startswith("/")
            or "\\" in path or any(p in ("", ".", "..") for p in path.split("/"))):
        raise ValueError("INVALID_SOURCE_ADDRESS")
    return {"repo": repo, "commit": commit, "path": path}


def validate(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        raise ValueError("INVALID_INVENTORY_SCHEMA")
    items = raw.get("items")
    relations = raw.get("relations", [])
    if not isinstance(items, list) or not 1 <= len(items) <= 500:
        raise ValueError("INVALID_ITEMS")
    if not isinstance(relations, list) or len(relations) > 500:
        raise ValueError("INVALID_RELATIONS")
    out_items = []
    ids = set()
    for x in items:
        if not isinstance(x, dict):
            raise ValueError("INVALID_ITEM")
        item_id = nonempty(x.get("id"), "ITEM_ID")
        if not KEY.fullmatch(item_id) or item_id in ids:
            raise ValueError("DUPLICATE_OR_INVALID_ITEM_ID")
        ids.add(item_id)
        state = x.get("state")
        if state not in STATES:
            raise ValueError("INVALID_ITEM_STATE")
        out_items.append({
            "id": item_id,
            "title": nonempty(x.get("title"), "ITEM_TITLE"),
            "source": source(x.get("source")),
            "state": state,
            "needs": capabilities(x.get("needs"), "INVALID_NEEDS"),
            "offers": capabilities(x.get("offers"), "INVALID_OFFERS"),
            "annotation": nonempty(x.get("annotation"), "ANNOTATION_REQUIRED"),
        })
    out_relations = []
    relation_ids = set()
    for r in relations:
        if not isinstance(r, dict):
            raise ValueError("INVALID_RELATION")
        rid = nonempty(r.get("id"), "RELATION_ID")
        a, b = r.get("from"), r.get("to")
        if not KEY.fullmatch(rid) or rid in relation_ids:
            raise ValueError("INVALID_OR_DUPLICATE_RELATION_ID")
        if any(not isinstance(c, str) or not CAP.fullmatch(c) for c in (a, b)):
            raise ValueError("INVALID_RELATION_ENDPOINT")
        relation_ids.add(rid)
        out_relations.append({
            "id": rid, "from": a, "to": b,
            "proposed_by": nonempty(r.get("proposed_by"), "RELATION_AUTHOR_REQUIRED"),
            "basis": nonempty(r.get("basis"), "RELATION_BASIS_REQUIRED"),
        })
    return {
        "schema": SCHEMA,
        "items": sorted(out_items, key=lambda x: x["id"]),
        "relations": sorted(out_relations, key=lambda x: x["id"]),
    }


def route(offered: str, needed: str, edges: list[dict], dial: int) -> list[str] | None:
    """Exact capability identity uses 0 links. All other links are declared proposals."""
    if offered == needed:
        return []
    seen = {offered}
    queue = deque([(offered, [])])
    while queue:
        current, hops = queue.popleft()
        if len(hops) >= dial - 1:
            continue
        for edge in edges:
            if edge["from"] != current or edge["to"] in seen:
                continue
            following = hops + [edge["id"]]
            if edge["to"] == needed:
                return following
            seen.add(edge["to"])
            queue.append((edge["to"], following))
    return None


def discover(raw: Any, dial: int = 1) -> dict[str, Any]:
    if type(dial) is not int or not 1 <= dial <= 11:
        raise ValueError("DIAL_OUT_OF_RANGE")
    inventory = validate(raw)
    cases = []
    for item in inventory["items"]:
        witnesses = []
        missing = []
        for need in item["needs"]:
            possibilities = []
            if item["state"] == "OPEN":
                for provider in inventory["items"]:
                    if provider["id"] == item["id"] or provider["state"] != "OPEN":
                        continue
                    for offered in provider["offers"]:
                        hops = route(offered, need, inventory["relations"], dial)
                        if hops is not None:
                            possibilities.append({
                                "provider_id": provider["id"],
                                "provider_source": provider["source"],
                                "offered": offered,
                                "required": need,
                                "declared_relation_ids": hops,
                                "source_verification": "NOT_PERFORMED",
                            })
            if possibilities:
                witnesses.append({
                    "need": need,
                    "candidates": sorted(
                        possibilities,
                        key=lambda x: (len(x["declared_relation_ids"]), x["provider_id"], x["offered"]),
                    ),
                })
            else:
                missing.append(need)
        status = ("RELEASED" if item["state"] == "RELEASED" else
                  "HOLD" if item["state"] == "HELD" else
                  "OBSTACLE" if missing else
                  "CANDIDATE")
        case = {
            "subject_id": item["id"],
            "subject_source": item["source"],
            "status": status,
            "matched": witnesses,
            "unmet": missing,
            "semantic_effect": "none",
            "execution_authorized": False,
        }
        case["case_id"] = "ghot-ub-case-v0:" + digest(case)
        cases.append(case)
    body = {
        "schema": RESULT_SCHEMA,
        "inventory_sha256": digest(inventory),
        "dial": dial,
        "cases": cases,
        "source_verification": "NOT_PERFORMED",
        "laws": [
            "UNFINISHED != FAILED",
            "SOURCE ADDRESS != VERIFIED CONTENT",
            "MATCH != COMPATIBILITY",
            "DISCOVERY != AUTHORITY",
            "PROPOSAL != EXECUTION",
            "RELEASED != DELETED",
        ],
    }
    return {**body, "result_id": "ghot-ub-result-v0:" + digest(body)}


def decide(result: dict, case_id: str, decision: str, selection_source: str) -> dict:
    if decision not in DECISIONS:
        raise ValueError("INVALID_DECISION")
    actor = nonempty(selection_source, "SELECTION_SOURCE_REQUIRED")
    if not isinstance(result, dict) or result.get("schema") != RESULT_SCHEMA:
        raise ValueError("INVALID_RESULT")
    body = {k: v for k, v in result.items() if k != "result_id"}
    if result.get("result_id") != "ghot-ub-result-v0:" + digest(body):
        raise ValueError("RESULT_IDENTITY_MISMATCH")
    cases = result.get("cases", [])
    target = next((c for c in cases if c.get("case_id") == case_id), None)
    if target is None or case_id != "ghot-ub-case-v0:" + digest({k:v for k,v in target.items() if k != "case_id"}):
        raise ValueError("CASE_NOT_IN_RESULT")
    if target["status"] == "RELEASED" and decision != "RELEASED":
        raise ValueError("RELEASED_CASE_CANNOT_BE_REOPENED")
    if decision == "ACCEPT_FOR_REVIEW" and target["status"] != "CANDIDATE":
        raise ValueError("ONLY_CANDIDATE_CAN_BE_REVIEWED")
    receipt = {
        "schema": DECISION_SCHEMA,
        "result_id": result["result_id"],
        "case_id": case_id,
        "decision": decision,
        "selection_source": actor,
        "semantic_effect": "decision-receipt-only",
        "executed": False,
        "signed": False,
        "laws": ["DECISION != EXECUTION", "RECEIPT != SIGNATURE", "RELEASE != ERASURE"],
    }
    return {**receipt, "receipt_id": "ghot-ub-decision-v0:" + digest(receipt)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("discover")
    d.add_argument("inventory", type=Path)
    d.add_argument("--dial", type=int, default=1)
    s = sub.add_parser("decide")
    s.add_argument("inventory", type=Path)
    s.add_argument("--dial", type=int, default=1)
    s.add_argument("--case-id", required=True)
    s.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    s.add_argument("--selection-source", required=True)
    s.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raw = json.loads(args.inventory.read_text(encoding="utf-8"))
    result = discover(raw, args.dial)
    if args.command == "discover":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        receipt = decide(result, args.case_id, args.decision, args.selection_source)
        # Exclusive write; a decision does not overwrite earlier testimony.
        with args.out.open("x", encoding="utf-8") as f:
            f.write(canonical(receipt) + "\n")
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
