#!/usr/bin/env python3
"""Read-only Curious Doors surface — Experiment 025.

025 projects durable 024 composition wants into a local human-readable surface.

It does not inspect the network, refresh wants, declare wants, request packages,
offer packages, validate packages, or install packages.

Laws:
    SURFACE != REQUEST
    ATTENTION != PRIORITY
    NEW CANDIDATE != NOTIFICATION AUTHORITY
    DISPLAY ORDER != RANK
"""

from __future__ import annotations

import argparse
import html
import json
import shlex
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from composition_want import CompositionWantStore
from reference_node import ROOT
from relatte_identity import identity_safe, timestamp_now


SURFACE_KIND = "ghot.curiosity.surface"
SURFACE_VERSION = "1"
DOOR_KIND = "ghot.curiosity.door"
DOOR_VERSION = "1"

STATE_OPEN = "open-gap"
STATE_CANDIDATE = "candidate-observed"
STATE_REQUESTED = "requested"
STATE_RESOLVED = "resolved-local"
STATE_BLOCKED = "blocked"

STATE_MESSAGES = {
    STATE_OPEN: "I don't know how to compose this yet.",
    STATE_CANDIDATE: "A structurally matching grammar has appeared in observed history.",
    STATE_REQUESTED: "A grammar has been requested; this gap is still locally unresolved.",
    STATE_RESOLVED: "This old gap is now locally satisfied.",
    STATE_BLOCKED: "This want cannot currently be projected from local evidence.",
}


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _evidence_destination(
    *,
    want_id: str,
    label: str = "Inspect door evidence",
) -> dict[str, Any]:
    return {
        "kind": "evidence-link",
        "label": label,
        "owner_contract": "ghot.curious-doors@1",
        "href": "/door?want_id=" + quote(want_id, safe=""),
        "method": "GET",
        "effect": "none",
        "executes": False,
        "permission_transfer": False,
    }


def _command_intent(
    *,
    label: str,
    owner_contract: str,
    argv: list[str],
    effect_if_run: str,
) -> dict[str, Any]:
    return {
        "kind": "command-intent",
        "label": label,
        "owner_contract": owner_contract,
        "argv": argv,
        "display_command": shlex.join(argv),
        "effect_if_run": effect_if_run,
        "executes": False,
        "permission_transfer": False,
    }


def _candidate_index(
    want: dict[str, Any],
    observations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    by_id: dict[str, dict[str, Any]] = {}
    first_seen: dict[str, str] = {}
    initial_at = str(want.get("created_at") or "")

    for item in want.get("candidates") or []:
        if not isinstance(item, dict):
            continue
        candidate_id = item.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        by_id[candidate_id] = item
        first_seen[candidate_id] = initial_at

    previously_seen = set(by_id)
    new_in_latest: list[str] = []

    for index, observation in enumerate(observations):
        observed_at = str(observation.get("observed_at") or "")
        current_ids: list[str] = []
        for item in observation.get("candidates") or []:
            if not isinstance(item, dict):
                continue
            candidate_id = item.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                continue
            current_ids.append(candidate_id)
            by_id[candidate_id] = item
            first_seen.setdefault(candidate_id, observed_at)

        if index == len(observations) - 1:
            new_in_latest = sorted(
                candidate_id
                for candidate_id in current_ids
                if candidate_id not in previously_seen
            )
        previously_seen.update(current_ids)

    rows = []
    for candidate_id in sorted(by_id):
        item = by_id[candidate_id]
        rows.append(identity_safe({
            "candidate_id": candidate_id,
            "first_seen_at": first_seen.get(candidate_id),
            "package_id": item.get("package_id"),
            "package_version": item.get("package_version"),
            "package_address": item.get("package_address"),
            "contract_id": item.get("contract_id"),
            "title": item.get("title"),
            "category": item.get("category"),
            "source_particular": item.get("source_particular"),
            "source_node_id": item.get("source_node_id"),
            "author_particular": item.get("author_particular"),
            "source": item.get("source"),
            "target": item.get("target"),
            "operation_kind": item.get("operation_kind"),
            "match": item.get("match"),
        }))

    return rows, new_in_latest


class CuriousDoorsSurface:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.store = CompositionWantStore(self.root)

    def _matching_plugin_parcels(
        self,
        *,
        package_addresses: set[str],
    ) -> list[dict[str, Any]]:
        rows = []
        inbox_dir = self.root / "merge-plugin-parcels" / "inbox"
        if not inbox_dir.is_dir():
            return rows
        for path in sorted(inbox_dir.glob("*.json")):
            try:
                item = _read_object(path)
            except Exception:
                continue
            address = item.get("package_address")
            if not isinstance(address, str) or address not in package_addresses:
                continue
            rows.append(identity_safe({
                "parcel_id": item.get("parcel_id"),
                "parcel_address": item.get("parcel_address"),
                "package_id": item.get("package_id"),
                "package_version": item.get("package_version"),
                "package_address": address,
                "author_particular": item.get("author_particular"),
                "author_signature_status": item.get("author_signature_status"),
                "status": item.get("status"),
                "received_at": item.get("received_at"),
                "updated_at": item.get("updated_at"),
                "validation_address": item.get("validation_address"),
                "install_receipt_id": item.get("install_receipt_id"),
            }))
        rows.sort(
            key=lambda item: (
                str(item.get("package_address") or ""),
                str(item.get("parcel_id") or ""),
            )
        )
        return rows

    def _navigation(
        self,
        *,
        want: dict[str, Any],
        state: str,
        candidates: list[dict[str, Any]],
        links: list[dict[str, Any]],
        plugin_parcels: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        want_id = str(want["want_id"])
        destinations: list[dict[str, Any]] = [
            _evidence_destination(want_id=want_id),
            _command_intent(
                label="Inspect this WANT in the owning subsystem",
                owner_contract="ghot.composition-wants@0",
                argv=[
                    "python3",
                    "ghot/composition_want.py",
                    "show",
                    want_id,
                ],
                effect_if_run="read-only",
            ),
        ]

        if state in {STATE_OPEN, STATE_CANDIDATE}:
            destinations.append(_command_intent(
                label="Refresh observed grammar candidates",
                owner_contract="ghot.composition-wants@0",
                argv=[
                    "python3",
                    "ghot/composition_want.py",
                    "refresh",
                    want_id,
                    "--scan",
                ],
                effect_if_run="network-read+local-observation-write",
            ))

        if state == STATE_CANDIDATE:
            for candidate in candidates:
                candidate_id = candidate.get("candidate_id")
                if not isinstance(candidate_id, str) or not candidate_id:
                    continue
                destinations.append(_command_intent(
                    label=(
                        "Request candidate "
                        + str(candidate.get("package_id") or candidate_id)
                    ),
                    owner_contract="ghot.composition-wants@0",
                    argv=[
                        "python3",
                        "ghot/composition_want.py",
                        "request",
                        want_id,
                        candidate_id,
                    ],
                    effect_if_run="signed-023-request",
                ))

        if state == STATE_REQUESTED:
            for parcel in plugin_parcels:
                parcel_id = parcel.get("parcel_id")
                status = parcel.get("status")
                if not isinstance(parcel_id, str) or not parcel_id:
                    continue
                destinations.append(_command_intent(
                    label="Inspect received plugin parcel",
                    owner_contract="ghot.merge-plugin-parcel-inbox@0",
                    argv=[
                        "python3",
                        "ghot/merge_plugin_parcel.py",
                        "show",
                        parcel_id,
                    ],
                    effect_if_run="read-only",
                ))
                if status == "HOLD":
                    destinations.append(_command_intent(
                        label="Validate held plugin parcel locally",
                        owner_contract="ghot.merge-plugin-parcel-inbox@0",
                        argv=[
                            "python3",
                            "ghot/merge_plugin_parcel.py",
                            "validate",
                            parcel_id,
                        ],
                        effect_if_run="local-validation-state-change",
                    ))
                elif status == "VALIDATED":
                    destinations.append(_command_intent(
                        label="Install validated plugin parcel locally",
                        owner_contract="ghot.merge-plugin-parcel-inbox@0",
                        argv=[
                            "python3",
                            "ghot/merge_plugin_parcel.py",
                            "install",
                            parcel_id,
                        ],
                        effect_if_run="local-plugin-install",
                    ))

        if state == STATE_RESOLVED:
            parcel_id = want.get("parcel_id")
            if isinstance(parcel_id, str) and parcel_id:
                destinations.append(_command_intent(
                    label="Inspect current local merge compatibility",
                    owner_contract="ghot.merge-contract-pantry@0",
                    argv=[
                        "python3",
                        "ghot/merge_contract_pantry.py",
                        "inspect",
                        parcel_id,
                    ],
                    effect_if_run="read-only",
                ))

        return destinations

    def evidence(self, want_id: str) -> dict[str, Any]:
        want = self.store.load_want(want_id)
        observations = self.store.observations(want_id=want_id)
        links = self.store.request_links(want_id=want_id)
        candidates, _new = _candidate_index(want, observations)
        package_addresses = {
            str(candidate.get("package_address"))
            for candidate in candidates
            if isinstance(candidate.get("package_address"), str)
        }
        plugin_parcels = self._matching_plugin_parcels(
            package_addresses=package_addresses,
        )
        try:
            current = self.store.pantry.inspect(str(want["parcel_id"]))
            current_error = None
        except Exception as exc:
            current = None
            current_error = f"{type(exc).__name__}: {exc}"
        return identity_safe({
            "kind": "ghot.curiosity.evidence",
            "version": "0",
            "want": want,
            "current_local_inspection": current,
            "current_local_inspection_error": current_error,
            "observations": observations,
            "request_links": links,
            "matching_plugin_parcels": plugin_parcels,
            "read_only": True,
        })

    def _door(self, want: dict[str, Any]) -> dict[str, Any]:
        want_id = str(want["want_id"])
        observations = self.store.observations(want_id=want_id)
        links = self.store.request_links(want_id=want_id)
        candidates, new_candidate_ids = _candidate_index(
            want,
            observations,
        )

        compatible: list[str] = []
        projection_error: str | None = None
        try:
            current = self.store.pantry.inspect(str(want["parcel_id"]))
            compatible = list(
                current.get("compatible_contract_ids") or []
            )
        except Exception as exc:
            current = None
            projection_error = f"{type(exc).__name__}: {exc}"

        if projection_error is not None:
            state = STATE_BLOCKED
        elif compatible:
            state = STATE_RESOLVED
        elif links:
            state = STATE_REQUESTED
        elif candidates:
            state = STATE_CANDIDATE
        else:
            state = STATE_OPEN

        requested_candidate_ids = sorted({
            str(link.get("candidate_id"))
            for link in links
            if isinstance(link.get("candidate_id"), str)
        })
        requested_package_addresses = {
            str(link.get("package_address"))
            for link in links
            if isinstance(link.get("package_address"), str)
        }
        plugin_parcels = self._matching_plugin_parcels(
            package_addresses=requested_package_addresses,
        )
        navigation = self._navigation(
            want=want,
            state=state,
            candidates=candidates,
            links=links,
            plugin_parcels=plugin_parcels,
        )

        return identity_safe({
            "kind": DOOR_KIND,
            "version": DOOR_VERSION,
            "door_id": f"curious-door:{want_id}",
            "want_id": want_id,
            "gap_id": want.get("gap_id"),
            "state": state,
            "message": STATE_MESSAGES[state],
            "created_at": want.get("created_at"),
            "note": want.get("note"),
            "parcel": {
                "parcel_id": want.get("parcel_id"),
                "parcel_address": want.get("parcel_address"),
                "payload_address": want.get("payload_address"),
                "admitted_ref": want.get("admitted_ref"),
            },
            "source": want.get("source"),
            "local_compatible_contract_ids": compatible,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "new_candidate_ids_in_latest_observation": new_candidate_ids,
            "new_candidate_count_in_latest_observation": len(
                new_candidate_ids
            ),
            "observation_count": len(observations),
            "request_count": len(links),
            "requested_candidate_ids": requested_candidate_ids,
            "matching_plugin_parcels": plugin_parcels,
            "navigation": navigation,
            "projection_error": projection_error,
            "read_only": True,
        })

    def snapshot(self) -> dict[str, Any]:
        doors = []
        if self.store.wants_dir.is_dir():
            for path in sorted(self.store.wants_dir.glob("*.json")):
                try:
                    want = self.store.load_want(
                        _read_object(path)["want_id"]
                    )
                    doors.append(self._door(want))
                except Exception as exc:
                    doors.append(identity_safe({
                        "kind": DOOR_KIND,
                        "version": DOOR_VERSION,
                        "door_id": f"curious-door:blocked:{path.name}",
                        "want_id": None,
                        "gap_id": None,
                        "state": STATE_BLOCKED,
                        "message": STATE_MESSAGES[STATE_BLOCKED],
                        "created_at": None,
                        "note": None,
                        "parcel": None,
                        "source": None,
                        "local_compatible_contract_ids": [],
                        "candidate_count": 0,
                        "candidates": [],
                        "new_candidate_ids_in_latest_observation": [],
                        "new_candidate_count_in_latest_observation": 0,
                        "observation_count": 0,
                        "request_count": 0,
                        "requested_candidate_ids": [],
                        "matching_plugin_parcels": [],
                        "navigation": [],
                        "projection_error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                        "read_only": True,
                    }))

        # Chronological presentation only. This is deliberately not a priority
        # sort and does not use candidate/request counts as weights.
        doors.sort(
            key=lambda item: (
                str(item.get("created_at") or ""),
                str(item.get("door_id") or ""),
            )
        )

        counts = {
            state: sum(
                1 for door in doors if door.get("state") == state
            )
            for state in (
                STATE_OPEN,
                STATE_CANDIDATE,
                STATE_REQUESTED,
                STATE_RESOLVED,
                STATE_BLOCKED,
            )
        }

        return identity_safe({
            "kind": SURFACE_KIND,
            "version": SURFACE_VERSION,
            "generated_at": timestamp_now(),
            "ordering": "chronological-created-at-then-door-id",
            "ordering_is_priority": False,
            "read_only": True,
            "network_refresh_performed": False,
            "automatic_want": False,
            "automatic_refresh": False,
            "automatic_request": False,
            "automatic_offer": False,
            "automatic_install": False,
            "navigation_executes": False,
            "navigation_transfers_permission": False,
            "counts": counts,
            "doors": doors,
        })


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _render_navigation(navigation: list[dict[str, Any]]) -> str:
    if not navigation:
        return "<p>No navigation destinations available.</p>"
    rows = []
    for item in navigation:
        kind = item.get("kind")
        label = _esc(item.get("label"))
        owner = _esc(item.get("owner_contract"))
        if kind == "evidence-link":
            href = _esc(item.get("href"))
            rows.append(
                "<li><a href=\"" + href + "\">" + label + "</a>"
                + " <small>owned by <code>" + owner + "</code></small></li>"
            )
        elif kind == "command-intent":
            command = _esc(item.get("display_command"))
            effect = _esc(item.get("effect_if_run"))
            rows.append(
                "<li><div>" + label
                + " <small>owned by <code>" + owner + "</code></small></div>"
                + "<pre>" + command + "</pre>"
                + "<small>Would have effect if separately run: "
                + effect + ". This surface does not execute it.</small></li>"
            )
    return "<ul class=\"navigation\">" + "".join(rows) + "</ul>"


def render_evidence_html(
    evidence: dict[str, Any],
    navigation: list[dict[str, Any]],
) -> str:
    want = evidence.get("want") or {}
    title = "Curious Door Evidence — " + str(want.get("want_id") or "")
    pretty = _esc(json.dumps(evidence, indent=2, sort_keys=True))
    nav = _render_navigation(navigation)
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>""" + _esc(title) + """</title>
<style>
:root { color-scheme: dark; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
body { margin: 0; background: #0d0f12; color: #e8eaed; }
main { max-width: 980px; margin: 0 auto; padding: 2rem 1rem 4rem; }
a { color: inherit; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #15191e; padding: .8rem; border-radius: 8px; }
.navigation li { margin: 1rem 0; }
small { color: #aeb7c2; }
</style>
</head>
<body>
<main>
<p><a href="/">← Curious Doors</a></p>
<h1>Evidence</h1>
<p>Read-only projection. Links navigate; command intents are inert text.</p>
<h2>Possible next places</h2>
""" + nav + """
<h2>Durable local evidence</h2>
<pre>""" + pretty + """</pre>
</main>
</body>
</html>
"""


def render_html(snapshot: dict[str, Any]) -> str:
    cards = []
    for door in snapshot.get("doors") or []:
        state = str(door.get("state") or STATE_BLOCKED)
        candidates = door.get("candidates") or []
        candidate_rows = "".join(
            (
                "<li><code>"
                + _esc(item.get("candidate_id"))
                + "</code> — "
                + _esc(item.get("package_id"))
                + " / "
                + _esc(item.get("contract_id"))
                + "</li>"
            )
            for item in candidates
        )
        if not candidate_rows:
            candidate_rows = "<li>None observed.</li>"

        new_count = int(
            door.get("new_candidate_count_in_latest_observation") or 0
        )
        new_note = (
            f"<p><strong>Observation delta:</strong> {new_count} newly "
            "observed candidate(s) in the latest stored refresh.</p>"
            if new_count
            else ""
        )

        cards.append(
            "<article class=\"door\">"
            f"<div class=\"state\">{_esc(state)}</div>"
            f"<h2>{_esc(door.get('message'))}</h2>"
            f"<p><strong>Want:</strong> <code>{_esc(door.get('want_id'))}</code></p>"
            f"<p><strong>Gap:</strong> <code>{_esc(door.get('gap_id'))}</code></p>"
            f"<p><strong>Source:</strong> <code>{_esc(json.dumps(door.get('source'), sort_keys=True))}</code></p>"
            f"<p><strong>Requests recorded:</strong> {_esc(door.get('request_count'))}</p>"
            + new_note
            + "<details><summary>Observed candidates</summary><ul>"
            + candidate_rows
            + "</ul></details>"
            + "<details><summary>Navigate without acting</summary>"
            + _render_navigation(door.get("navigation") or [])
            + "</details>"
            + (
                "<p class=\"error\"><strong>Projection error:</strong> "
                + _esc(door.get("projection_error"))
                + "</p>"
                if door.get("projection_error")
                else ""
            )
            + "</article>"
        )

    if not cards:
        cards = [
            "<article class=\"door empty\"><h2>No durable composition wants yet.</h2>"
            "<p>The surface does not create one automatically.</p></article>"
        ]

    counts = snapshot.get("counts") or {}
    count_text = " · ".join(
        f"{state}: {counts.get(state, 0)}"
        for state in (
            STATE_OPEN,
            STATE_CANDIDATE,
            STATE_REQUESTED,
            STATE_RESOLVED,
            STATE_BLOCKED,
        )
    )

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="10">
<title>GHoT — Curious Doors</title>
<style>
:root { color-scheme: dark; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
body { margin: 0; background: #0d0f12; color: #e8eaed; }
main { max-width: 980px; margin: 0 auto; padding: 2rem 1rem 4rem; }
header { border-bottom: 1px solid #343941; margin-bottom: 1.25rem; }
h1 { font-size: 1.8rem; margin-bottom: .35rem; }
.law { color: #aeb7c2; }
.summary { font-size: .9rem; color: #bdc5d0; }
.door { border: 1px solid #343941; border-radius: 12px; padding: 1rem; margin: 1rem 0; background: #15191e; }
.state { text-transform: uppercase; letter-spacing: .08em; font-size: .75rem; color: #aeb7c2; }
h2 { font-size: 1.15rem; line-height: 1.4; }
code { overflow-wrap: anywhere; }
details { margin-top: .75rem; }
.navigation li { margin: 1rem 0; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #0d0f12; padding: .6rem; border-radius: 8px; }
a { color: inherit; }
small { color: #aeb7c2; }
.error { border-left: 3px solid currentColor; padding-left: .7rem; }
footer { margin-top: 2rem; color: #8e98a5; font-size: .85rem; }
</style>
</head>
<body>
<main>
<header>
<h1>Curious Doors</h1>
<p class="law">Read-only projection. Surface ≠ request. Attention ≠ priority.</p>
<p class="summary">""" + _esc(count_text) + """</p>
</header>
""" + "\n".join(cards) + """
<footer>
<p>Chronological display only. No ranking, recommendation, network refresh, request, offer, validation, or installation occurs here.</p>
</footer>
</main>
</body>
</html>
"""


def surface_handler(
    root: Path,
) -> type[BaseHTTPRequestHandler]:
    surface = CuriousDoorsSurface(root)

    class Handler(BaseHTTPRequestHandler):
        server_version = "GHoTCuriousDoors/0"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send(
            self,
            status: int,
            raw: bytes,
            content_type: str,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/curious-doors.html"}:
                raw = render_html(surface.snapshot()).encode("utf-8")
                self._send(200, raw, "text/html; charset=utf-8")
                return
            if parsed.path == "/curious-doors":
                raw = json.dumps(
                    surface.snapshot(),
                    indent=2,
                ).encode("utf-8")
                self._send(200, raw, "application/json")
                return
            if parsed.path in {"/door", "/evidence"}:
                params = parse_qs(parsed.query)
                want_id = (params.get("want_id") or [None])[0]
                if not isinstance(want_id, str) or not want_id:
                    self._send(
                        400,
                        b'{"error":"want_id required"}',
                        "application/json",
                    )
                    return
                try:
                    snapshot = surface.snapshot()
                    door = next(
                        (
                            item
                            for item in snapshot.get("doors") or []
                            if item.get("want_id") == want_id
                        ),
                        None,
                    )
                    if not isinstance(door, dict):
                        raise ValueError("unknown curious door")
                    evidence = surface.evidence(want_id)
                except Exception as exc:
                    raw = json.dumps({
                        "error": f"{type(exc).__name__}: {exc}",
                    }).encode("utf-8")
                    self._send(404, raw, "application/json")
                    return
                if parsed.path == "/evidence":
                    raw = json.dumps(
                        evidence,
                        indent=2,
                    ).encode("utf-8")
                    self._send(200, raw, "application/json")
                else:
                    raw = render_evidence_html(
                        evidence,
                        door.get("navigation") or [],
                    ).encode("utf-8")
                    self._send(200, raw, "text/html; charset=utf-8")
                return
            if parsed.path == "/health":
                raw = json.dumps({
                    "kind": "ghot.curiosity.surface.health",
                    "version": "0",
                    "status": "awake",
                    "read_only": True,
                }).encode("utf-8")
                self._send(200, raw, "application/json")
                return
            self._send(
                404,
                b'{"error":"not found"}',
                "application/json",
            )

        def do_POST(self) -> None:
            self._send(
                405,
                b'{"error":"read-only surface"}',
                "application/json",
            )

        def do_PUT(self) -> None:
            self.do_POST()

        def do_DELETE(self) -> None:
            self.do_POST()

    return Handler


class CuriousDoorsHTTPService:
    def __init__(
        self,
        *,
        root: Path | None = None,
        host: str = "127.0.0.1",
        port: int = 7794,
    ) -> None:
        self.root = root or ROOT
        self.host = host
        self.port = port
        self.server: ThreadingHTTPServer | None = None
        self.thread = None

    def start(self) -> None:
        import threading

        self.server = ThreadingHTTPServer(
            (self.host, self.port),
            surface_handler(self.root),
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()

    def close(self) -> None:
        if self.server is not None:
            try:
                self.server.shutdown()
            except OSError:
                pass
            self.server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the read-only GHoT Curious Doors surface."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot")

    render = sub.add_parser("render")
    render.add_argument("--out", required=True)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7794)

    args = parser.parse_args()
    surface = CuriousDoorsSurface()

    if args.command == "snapshot":
        print(json.dumps(surface.snapshot(), indent=2))
        return 0

    if args.command == "render":
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            render_html(surface.snapshot()),
            encoding="utf-8",
        )
        print(json.dumps({
            "kind": "ghot.curiosity.surface.rendered",
            "version": "0",
            "path": str(out),
            "read_only_source_projection": True,
        }, indent=2))
        return 0

    service = CuriousDoorsHTTPService(
        host=args.host,
        port=args.port,
    )
    service.start()
    print(json.dumps({
        "event": "ghot.curiosity.surface.started",
        "host": args.host,
        "port": (
            service.server.server_port
            if service.server is not None
            else args.port
        ),
        "read_only": True,
        "laws": [
            "SURFACE != REQUEST",
            "ATTENTION != PRIORITY",
            "NEW CANDIDATE != NOTIFICATION AUTHORITY",
            "DISPLAY ORDER != RANK",
            "NAVIGATION != ACTION",
            "LINK != AUTHORITY",
        ],
    }, indent=2))
    try:
        import time
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        service.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
