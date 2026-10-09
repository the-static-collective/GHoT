"""THE RIFF-RAFT 001 — topology overlay for GHoT ECOLOGY-ROUTER-001.

Routes synthetic resource proposals through explicitly offered land/shore/river/
floating links. Never upgrades a HOLD, energizes a cable, pilots a vessel,
claims structural safety, or dispatches a task. Topology is scenario evidence,
not survey, permission, engineering certification, or realtime observation.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from ecology_router import (
    Hold, PRIORITIES, RESOURCES, digest, integer,
    plan as ecology_plan, require, validate as validate_ecology,
)

SCHEMA = "ghot.riff-raft-topology/v0"
PLAN_SCHEMA = "ghot.riff-raft-plan/v0"
KINDS = {"land", "shore", "river", "floating"}
LINK_RESOURCES = {
    "radio": {"information"},
    "cable": {"electricity", "information"},
    "thermal-exchanger": {"heat"},
    "cargo": {"materials"},
    "clean-water-line": {"freshwater"},
    "nutrient-line": {"nutrients"},
}
MAX_NODES = 64
MAX_LINKS = 256
MAX_HOPS = 8


def validate_topology(topology: Any, world: dict[str, Any]) -> dict[str, Any]:
    validate_ecology(world)
    require(isinstance(topology, dict) and set(topology) == {
        "schema", "mode", "ecology_world_sha256", "places", "links",
    }, "topology fields changed")
    require(topology["schema"] == SCHEMA and topology["mode"] == "simulation-only",
            "unsupported or physically claimed topology")
    require(topology["ecology_world_sha256"] == digest(world),
            "ecology world changed; topology pin stale")
    places = topology["places"]
    links = topology["links"]
    require(isinstance(places, list) and 1 <= len(places) <= MAX_NODES,
            "invalid place count")
    require(isinstance(links, list) and len(links) <= MAX_LINKS,
            "invalid link count")

    nodes: dict[str, dict[str, Any]] = {}
    for place in places:
        require(isinstance(place, dict) and set(place) == {
            "id", "kind", "owner_id", "status", "scenario_integrity_ok",
        }, "place fields changed")
        ident = place["id"]
        require(isinstance(ident, str) and ident and ident not in nodes,
                "duplicate or invalid place")
        require(place["kind"] in KINDS, "unknown place kind")
        require(isinstance(place["owner_id"], str) and place["owner_id"],
                "place owner required")
        require(place["status"] in {"modeled-active", "withdrawn"} and
                type(place["scenario_integrity_ok"]) is bool,
                "place status or integrity invalid")
        nodes[ident] = place
    for source in world["sources"]:
        require(source["node"] in nodes, "source references unmodeled place")
    for load in world["loads"]:
        require(load["node"] in nodes, "load references unmodeled place")

    seen = set()
    for link in links:
        require(isinstance(link, dict) and set(link) == {
            "id", "from", "to", "carrier", "resource", "unit",
            "limit_units", "permit_ok", "weather_ok", "isolation_ok",
            "owner_grants", "status", "scenario_only",
        }, "link fields changed")
        ident = link["id"]
        require(isinstance(ident, str) and ident and ident not in seen,
                "duplicate or invalid link")
        seen.add(ident)
        require(link["from"] in nodes and link["to"] in nodes and
                link["from"] != link["to"], "unknown or self-linked places")
        require(link["carrier"] in LINK_RESOURCES, "unsupported carrier")
        require(link["resource"] in LINK_RESOURCES[link["carrier"]] and
                link["unit"] == RESOURCES[link["resource"]],
                "resource unsupported by carrier")
        integer(link["limit_units"], "link units", minimum=1)
        require(all(type(link[key]) is bool for key in (
            "permit_ok", "weather_ok", "isolation_ok", "scenario_only",
        )) and link["scenario_only"] is True,
                "link cannot claim physical readiness")
        require(link["status"] in {"offered", "withdrawn"}, "invalid link status")
        owners = link["owner_grants"]
        require(isinstance(owners, list) and
                all(isinstance(o, str) and o for o in owners) and
                owners == sorted(set(owners)), "owner grants malformed")
    return topology


def _link_allowed(link: dict[str, Any], nodes: dict[str, Any],
                  available: dict[str, int], units: int) -> bool:
    start = nodes[link["from"]]
    end = nodes[link["to"]]
    needed = {start["owner_id"], end["owner_id"]}
    return (
        link["status"] == "offered"
        and link["permit_ok"] is True
        and link["weather_ok"] is True
        and link["isolation_ok"] is True
        and start["status"] == end["status"] == "modeled-active"
        and start["scenario_integrity_ok"] is True
        and end["scenario_integrity_ok"] is True
        and needed.issubset(set(link["owner_grants"]))
        and available[link["id"]] >= units
    )


def _find_path(source_place: str, load_place: str, resource: str, unit: str,
               units: int, nodes: dict[str, Any], links: list[dict[str, Any]],
               available: dict[str, int]) -> list[str] | None:
    if source_place == load_place:
        local = nodes[source_place]
        return [] if (local["status"] == "modeled-active" and
                      local["scenario_integrity_ok"] is True) else None
    # Deterministic minimal-hop search, no cycle visits; the graph is
    # a *route proposal* graph, not a proven physical/cable network.
    q = deque([(source_place, [], frozenset({source_place}))])
    while q:
        where, hops, visited = q.popleft()
        if len(hops) >= MAX_HOPS:
            continue
        for link in sorted(links, key=lambda item: item["id"]):
            if (link["from"] != where or link["to"] in visited or
                    link["resource"] != resource or link["unit"] != unit):
                continue
            if not _link_allowed(link, nodes, available, units):
                continue
            onward = hops + [link["id"]]
            if link["to"] == load_place:
                return onward
            q.append((link["to"], onward, visited | {link["to"]}))
    return None


def compose(world: dict[str, Any], topology: dict[str, Any]) -> dict[str, Any]:
    """Narrow ECOLOGY PROPOSE to reachable scenario paths. NEVER promote HOLD."""
    validate_topology(topology, world)
    base = ecology_plan(world)
    nodes = {x["id"]: x for x in topology["places"]}
    links = topology["links"]
    budgets = {x["id"]: x["limit_units"] for x in links}
    by_load = {x["id"]: x for x in world["loads"]}
    by_source = {x["id"]: x for x in world["sources"]}
    base_rows = {x["load_id"]: x for x in base["proposals"]}
    decisions = []
    unavailable_life_resources = set()

    loads = sorted(world["loads"], key=lambda load: (
        PRIORITIES[load["priority"]], load["resource"], load["id"]))
    for load in loads:
        row = base_rows[load["id"]]
        if row["decision"] != "PROPOSE":
            reasons = ["UPSTREAM_HOLD"] + row["reasons"]
            route = None
        elif load["priority"] != "life-support" and load["resource"] in unavailable_life_resources:
            reasons = ["LIFE_SUPPORT_PATH_NOT_READY"]
            route = None
        else:
            source = by_source[row["source_id"]]
            route = _find_path(source["node"], load["node"], row["resource"],
                               row["unit"], row["proposed_units"],
                               nodes, links, budgets)
            reasons = [] if route is not None else ["NO_ELIGIBLE_PHYSICAL_ROUTE"]

        if route is None:
            if load["priority"] == "life-support" and load["status"] == "requested":
                unavailable_life_resources.add(load["resource"])
            decisions.append({
                "load_id": load["id"], "decision": "HOLD",
                "source_id": None, "route_link_ids": [],
                "resource": load["resource"], "unit": load["unit"],
                "proposed_units": 0, "reasons": sorted(set(reasons)),
            })
        else:
            for link_id in route:
                budgets[link_id] -= row["proposed_units"]
                require(budgets[link_id] >= 0, "link double-budgeted")
            decisions.append({
                "load_id": load["id"], "decision": "PROPOSE",
                "source_id": row["source_id"],
                "route_link_ids": route, "resource": row["resource"],
                "unit": row["unit"], "proposed_units": row["proposed_units"],
                "reasons": ["UPSTREAM_PROPOSED", "TOPOLOGY_SIMULATED_ELIGIBLE",
                            "NO_PHYSICAL_CROSSING"],
            })
    return {
        "schema": PLAN_SCHEMA, "name": "The Riff-Raft",
        "mode": "simulation-only",
        "ecology_world_sha256": digest(world),
        "topology_sha256": digest(topology),
        "ecology_plan_sha256": digest(base),
        "routes": decisions,
        "remaining_link_units": budgets,
        "physical_transfer_performed": False,
        "physical_safety_certified": False,
        "habitation_permitted": False,
        "source_or_destination_admission": False,
        "automatic_dispatch": False,
        "signed_relatte_crossing": False,
    }
