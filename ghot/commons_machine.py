#!/usr/bin/env python3
"""Commons Machine 001: proposal-only consequences of synthetic physical events.

No devices, networking, GHoT tasks, or relays are executed. This is a bounded
scenario evaluator, NOT a sensor, scheduler, or source of physical authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "ghot.commons.scenario/v0"
ALLOWED_KINDS = {"event", "physical-effect", "sensor", "inference", "proposal", "actuator"}
ALLOWED_RELATIONS = {
    "mechanical", "observation", "inference", "candidate-action", "fluid-transfer"
}
DANGEROUS_MEDIA = {"potable", "wastewater", "coolant", "greywater", "process-water"}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def address(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def validate(scenario: dict[str, Any]) -> tuple[dict[str, dict], list[dict]]:
    if not isinstance(scenario, dict) or scenario.get("kind") != VERSION:
        raise ValueError("Expected ghot.commons.scenario/v0")
    source = scenario.get("source_event")
    if not isinstance(source, dict) or source.get("synthetic") is not True:
        raise ValueError("V0 requires an explicitly synthetic source event")
    nodes = scenario.get("nodes")
    edges = scenario.get("edges")
    if not isinstance(nodes, list) or not nodes or not isinstance(edges, list):
        raise ValueError("Nonempty nodes and an edges list are required")
    indexed: dict[str, dict] = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            raise ValueError("Every node needs a nonempty string id")
        if node["id"] in indexed:
            raise ValueError("Duplicate node id: " + node["id"])
        if node.get("kind") not in ALLOWED_KINDS:
            raise ValueError("Invalid node kind")
        if not isinstance(node.get("domain"), str) or not node["domain"]:
            raise ValueError("Every node needs a physical/informational domain")
        if node.get("medium") is not None and node["medium"] not in DANGEROUS_MEDIA:
            raise ValueError("Unknown fluid quality category")
        indexed[node["id"]] = node
    if source.get("node_id") not in indexed or indexed[source["node_id"]]["kind"] != "event":
        raise ValueError("Source must refer to an event node")
    edge_ids: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Edge must be an object")
        ident = edge.get("id")
        if not isinstance(ident, str) or not ident or ident in edge_ids:
            raise ValueError("Missing or duplicate edge id")
        edge_ids.add(ident)
        if edge.get("from") not in indexed or edge.get("to") not in indexed:
            raise ValueError("Unknown edge endpoint")
        if edge.get("from") == edge.get("to"):
            raise ValueError("Self-loop not permitted")
        if edge.get("relation") not in ALLOWED_RELATIONS:
            raise ValueError("Unknown edge relation")
        if edge.get("relation") == "candidate-action" and indexed[edge["to"]]["kind"] not in {"proposal", "actuator"}:
            raise ValueError("Candidate-action must target proposal or actuator")
        if edge.get("relation") == "fluid-transfer":
            if "medium" not in indexed[edge["from"]] or "medium" not in indexed[edge["to"]]:
                raise ValueError("Fluid transfer needs declared medium on both endpoints")
    # Avoid self-propagating Rube Goldberg loops in the first model.
    children = {ident: [] for ident in indexed}
    for edge in edges:
        children[edge["from"]].append(edge["to"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError("Cycles require a separately bounded execution model")
        if key in visited:
            return
        visiting.add(key)
        for child in children[key]:
            visit(child)
        visiting.remove(key)
        visited.add(key)

    for key in indexed:
        visit(key)
    return indexed, edges


def evaluate_edge(edge: dict, nodes: dict[str, dict]) -> tuple[str, str]:
    src = nodes[edge["from"]]
    dst = nodes[edge["to"]]
    if edge["relation"] == "fluid-transfer" and src.get("medium") != dst.get("medium"):
        return "REFUSE", "cross-quality physical fluid transfer is not admitted"
    if edge["relation"] == "candidate-action" or dst["kind"] == "actuator":
        return "HOLD", "requires live instrument evidence, local selection and explicit authority"
    return "YES", "admissible as a synthetic candidate relation; not a measurement"


def simulate(scenario: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = validate(scenario)
    source = scenario["source_event"]["node_id"]
    reachable = {source}
    pending = list(edges)
    steps = []
    # Repeated passes allow arbitrary input edge order without requiring sort order.
    while True:
        progress = False
        waiting = []
        for edge in pending:
            if edge["from"] not in reachable:
                waiting.append(edge)
                continue
            status, reason = evaluate_edge(edge, nodes)
            steps.append({
                "edge_id": edge["id"],
                "from": edge["from"],
                "to": edge["to"],
                "relation": edge["relation"],
                "decision": status,
                "reason": reason,
                "requested_capability": nodes[edge["to"]].get("capability"),
                "observed_physical_result": None,
                "executed": False,
            })
            if status == "YES":
                reachable.add(edge["to"])
            progress = True
        pending = waiting
        if not progress:
            break
    result: dict[str, Any] = {
        "kind": "ghot.commons.simulation/v0",
        "scenario_id": scenario.get("scenario_id"),
        "source_event": scenario["source_event"],
        "scenario_sha256": address(scenario),
        "decisions": steps,
        "unvisited_edges": sorted(edge["id"] for edge in pending),
        "reachable_nodes": sorted(reachable),
        "authority": "none",
        "no_physical_observations_made": True,
        "no_tasks_executed": True,
        "no_dispatch": True,
    }
    result["simulation_sha256"] = address(result)
    return result


def persist_simulation(result: dict[str, Any], home: Path) -> Path:
    records = home / "records"
    records.mkdir(parents=True, exist_ok=True)
    receipt = {
        "kind": "ghot.commons.simulation-receipt/v0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "simulation_sha256": result["simulation_sha256"],
        "simulation": result,
        "authority": "none",
        "signature": None,
    }
    dest = records / f"commons-{uuid.uuid4()}.json"
    with dest.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--write-receipt", action="store_true", help="Append an unsigned local simulation receipt under GHOT_HOME")
    args = parser.parse_args()
    try:
        scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
        result = simulate(scenario)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.write_receipt:
        home = Path(os.environ.get("GHOT_HOME", ".ghot"))
        result["local_receipt_path"] = str(persist_simulation(result, home))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
