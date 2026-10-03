#!/usr/bin/env python3
"""Static-OS activation broker — Experiment 029.

The broker coordinates a human-visible ACT ceremony around 027/028 without
owning consent.

Flow:
    selected current local launch
      -> read-only destination preflight preview
      -> human sees exact proposal/effect
      -> explicit ACT + exact previewed proposal address
      -> 028 ticket issuance
      -> immediate 028 one-operation execution attempt
      -> display verified signed result

Laws:
    BROKER != CONSENT
    UI CLICK != ACT TICKET
    PREVIEW != AUTHORITY
    PREVIEWED PROPOSAL != CHANGED PROPOSAL
    RESULT DISPLAY != SUCCESS CLAIM
"""

from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from activation_ticket import (
    ActivationStore,
    CONSENT_PHRASE,
    DEFAULT_TTL_SECONDS,
    MAX_TTL_SECONDS,
    verify_execution_receipt,
)
from curious_doors import CuriousDoorsSurface
from launch_preflight import preflight_launch
from reference_node import ROOT
from relatte_identity import identity_safe
from state_migration import semantic_address


PREVIEW_KIND = "ghot.activation-broker.preview"
PREVIEW_VERSION = "0"
RESULT_KIND = "ghot.activation-broker.result"
RESULT_VERSION = "0"


def _proposal_address(preflight: dict[str, Any]) -> str | None:
    proposal = preflight.get("proposal")
    if not isinstance(proposal, dict):
        return None
    return semantic_address(identity_safe(proposal))


def _descriptor_address(descriptor: dict[str, Any]) -> str:
    return semantic_address(identity_safe(descriptor))


class ActivationBroker:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or ROOT
        self.surface = CuriousDoorsSurface(self.root)

    def preview(self, launch_id: str) -> dict[str, Any]:
        descriptor = self.surface.launch_descriptor(launch_id)
        preflight = preflight_launch(
            descriptor,
            root=self.root,
        )
        proposal_address = _proposal_address(preflight)
        return identity_safe({
            "kind": PREVIEW_KIND,
            "version": PREVIEW_VERSION,
            "launch_id": launch_id,
            "descriptor_address": _descriptor_address(descriptor),
            "label": descriptor.get("label"),
            "destination": descriptor.get("destination"),
            "context": descriptor.get("context"),
            "effect_if_executed": descriptor.get(
                "effect_if_executed"
            ),
            "preflight_status": preflight.get("status"),
            "preflight_checks": preflight.get("checks"),
            "proposal": preflight.get("proposal"),
            "proposal_address": proposal_address,
            "ready_to_act": (
                preflight.get("status") == "ready"
                and proposal_address is not None
            ),
            "required_phrase": CONSENT_PHRASE,
            "ticket_default_ttl_seconds": DEFAULT_TTL_SECONDS,
            "ticket_max_ttl_seconds": MAX_TTL_SECONDS,
            "preview_executes": False,
            "broker_executes_without_act": False,
            "broker_grants_consent": False,
            "ui_click_grants_consent": False,
            "act_binds_exact_proposal_address": True,
        })

    def act(
        self,
        *,
        launch_id: str,
        expected_proposal_address: str,
        confirm: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> dict[str, Any]:
        if confirm != CONSENT_PHRASE:
            raise ValueError(
                f"explicit consent phrase must be exactly {CONSENT_PHRASE}"
            )
        if not expected_proposal_address.startswith("sha256:"):
            raise ValueError("expected proposal address is required")

        preview = self.preview(launch_id)
        if preview.get("ready_to_act") is not True:
            raise ValueError(
                "launch is not currently READY for activation"
            )
        if (
            preview.get("proposal_address")
            != expected_proposal_address
        ):
            raise ValueError(
                "current proposal differs from the proposal the operator "
                "was shown"
            )

        descriptor = self.surface.launch_descriptor(launch_id)
        activation = ActivationStore(self.root)
        issued = activation.issue(
            descriptor,
            consent_phrase=confirm,
            ttl_seconds=ttl_seconds,
            expected_proposal_address=expected_proposal_address,
        )
        ticket = issued["ticket"]

        executed = activation.execute(ticket["ticket_id"])
        receipt = executed.get("receipt")
        verified = (
            verify_execution_receipt(receipt)
            if isinstance(receipt, dict)
            else False
        )
        signed_status = (
            receipt.get("status")
            if isinstance(receipt, dict)
            else None
        )
        signed_success = (
            receipt.get("success")
            if isinstance(receipt, dict)
            else None
        )
        verified_success = bool(
            verified
            and signed_status == "EXECUTED"
            and signed_success is True
        )

        return identity_safe({
            "kind": RESULT_KIND,
            "version": RESULT_VERSION,
            "launch_id": launch_id,
            "expected_proposal_address": expected_proposal_address,
            "ticket_id": ticket["ticket_id"],
            "ticket_issued": True,
            "ticket_spent": (
                receipt.get("ticket_spent")
                if isinstance(receipt, dict)
                else None
            ),
            "receipt_id": (
                receipt.get("receipt_id")
                if isinstance(receipt, dict)
                else None
            ),
            "receipt_verified": verified,
            "signed_status": signed_status,
            "signed_success": signed_success,
            "verified_success": verified_success,
            "result_address": (
                receipt.get("result_address")
                if isinstance(receipt, dict)
                else None
            ),
            "error": (
                receipt.get("error")
                if isinstance(receipt, dict)
                else None
            ),
            "success_claim_basis": (
                "verified-signed-execution-receipt"
                if verified_success
                else None
            ),
            "broker_inferred_success": False,
            "execution": executed,
        })


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def render_index(surface: CuriousDoorsSurface) -> str:
    snapshot = surface.snapshot()
    rows = []
    for door in snapshot.get("doors") or []:
        for descriptor in door.get("launches") or []:
            launch_id = descriptor.get("launch_id")
            destination = descriptor.get("destination") or {}
            if not isinstance(launch_id, str) or not launch_id:
                continue
            href = "/preview?launch_id=" + quote(launch_id, safe="")
            rows.append(
                '<li><a href="' + _esc(href) + '">'
                + _esc(descriptor.get("label"))
                + "</a><br><small><code>"
                + _esc(destination.get("app_id"))
                + " / "
                + _esc(destination.get("operation"))
                + "</code> · selection only · no consent</small></li>"
            )
    if not rows:
        rows.append("<li>No current typed launches.</li>")

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GHoT Activation Broker</title>
<style>
:root { color-scheme: dark; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
body { margin:0; background:#0d0f12; color:#e8eaed; }
main { max-width:920px; margin:0 auto; padding:2rem 1rem 4rem; }
li { margin:1.2rem 0; }
a { color:inherit; }
small { color:#aeb7c2; }
</style>
</head>
<body>
<main>
<h1>Activation Broker</h1>
<p>Selecting a launch opens a read-only destination preflight. Selection does not grant consent.</p>
<ul>""" + "".join(rows) + """</ul>
<p><small>BROKER != CONSENT · UI CLICK != ACT TICKET</small></p>
</main>
</body>
</html>
"""


def render_preview(preview: dict[str, Any]) -> str:
    ready = preview.get("ready_to_act") is True
    proposal = preview.get("proposal")
    checks = preview.get("preflight_checks") or []

    check_rows = "".join(
        "<li>"
        + ("PASS" if item.get("passed") else "FAIL")
        + " — "
        + _esc(item.get("name"))
        + "</li>"
        for item in checks
        if isinstance(item, dict)
    )
    if not check_rows:
        check_rows = "<li>No checks available.</li>"

    act_form = ""
    if ready:
        act_form = (
            '<form method="post" action="/act">'
            '<input type="hidden" name="launch_id" value="'
            + _esc(preview.get("launch_id"))
            + '">'
            '<input type="hidden" name="expected_proposal_address" value="'
            + _esc(preview.get("proposal_address"))
            + '">'
            '<label>Type <code>ACT</code> to authorize exactly this one '
            'attempt: <input name="confirm" autocomplete="off" '
            'required></label>'
            '<label>Ticket TTL seconds: <input name="ttl" type="number" '
            'min="1" max="600" value="120"></label>'
            '<button type="submit">Issue one ticket and attempt once</button>'
            "</form>"
        )
    else:
        act_form = (
            "<p><strong>Not ready:</strong> ACT is unavailable until the "
            "destination preflight is READY.</p>"
        )

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GHoT Activation Broker</title>
<style>
:root { color-scheme: dark; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
body { margin:0; background:#0d0f12; color:#e8eaed; }
main { max-width:920px; margin:0 auto; padding:2rem 1rem 4rem; }
section { border:1px solid #343941; border-radius:12px; padding:1rem; margin:1rem 0; background:#15191e; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; background:#0d0f12; padding:.8rem; border-radius:8px; }
label { display:block; margin:1rem 0; }
input { font:inherit; padding:.35rem; }
button { font:inherit; padding:.55rem .8rem; }
small { color:#aeb7c2; }
</style>
</head>
<body>
<main>
<h1>Activation Broker</h1>
<p>Preview is read-only. A click alone grants nothing. Type <code>ACT</code> to bind exactly the proposal shown below.</p>
<section>
<h2>Launch</h2>
<p><strong>Label:</strong> """ + _esc(preview.get("label")) + """</p>
<p><strong>Destination:</strong> <code>""" + _esc(json.dumps(preview.get("destination"), sort_keys=True)) + """</code></p>
<p><strong>Possible effect:</strong> """ + _esc(preview.get("effect_if_executed")) + """</p>
<p><strong>Preflight:</strong> """ + _esc(preview.get("preflight_status")) + """</p>
<p><strong>Proposal address:</strong> <code>""" + _esc(preview.get("proposal_address")) + """</code></p>
</section>
<section>
<h2>Destination checks</h2>
<ul>""" + check_rows + """</ul>
</section>
<section>
<h2>Exact proposed invocation</h2>
<pre>""" + _esc(json.dumps(proposal, indent=2, sort_keys=True)) + """</pre>
</section>
<section>
<h2>ACT boundary</h2>
""" + act_form + """
<small>BROKER != CONSENT · UI CLICK != ACT TICKET · PREVIEWED PROPOSAL != CHANGED PROPOSAL</small>
</section>
</main>
</body>
</html>
"""


def render_result(result: dict[str, Any]) -> str:
    verified = result.get("receipt_verified") is True
    status = result.get("signed_status")
    success = result.get("verified_success") is True

    if not verified:
        headline = "Execution receipt could not be verified."
    elif success:
        headline = "Verified signed receipt reports EXECUTED with success=true."
    elif status in {"REFUSED_STALE", "REFUSED_PROPOSAL_CHANGED"}:
        headline = "Verified signed receipt reports refusal."
    elif status == "FAILED":
        headline = "Verified signed receipt reports an attempted operation that failed."
    else:
        headline = "Verified signed receipt reports a non-success outcome."

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GHoT Activation Result</title>
<style>
:root { color-scheme: dark; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
body { margin:0; background:#0d0f12; color:#e8eaed; }
main { max-width:920px; margin:0 auto; padding:2rem 1rem 4rem; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; background:#15191e; padding:1rem; border-radius:10px; }
</style>
</head>
<body>
<main>
<h1>Activation Result</h1>
<p>""" + _esc(headline) + """</p>
<p><strong>Receipt verified:</strong> """ + _esc(verified) + """</p>
<p><strong>Signed status:</strong> """ + _esc(status) + """</p>
<p><strong>Signed success:</strong> """ + _esc(result.get("signed_success")) + """</p>
<pre>""" + _esc(json.dumps(result, indent=2, sort_keys=True)) + """</pre>
<p>RESULT DISPLAY != SUCCESS CLAIM. Success language above is used only when the signed receipt verifies and explicitly reports EXECUTED + success=true.</p>
</main>
</body>
</html>
"""


def broker_handler(
    root: Path,
) -> type[BaseHTTPRequestHandler]:
    broker = ActivationBroker(root)

    class Handler(BaseHTTPRequestHandler):
        server_version = "GHoTActivationBroker/0"

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

        def _browser_origin_allowed(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            host = self.headers.get("Host")
            if not host:
                return False
            return origin == "http://" + host

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                raw = render_index(broker.surface).encode("utf-8")
                self._send(200, raw, "text/html; charset=utf-8")
                return
            if parsed.path == "/health":
                raw = json.dumps({
                    "kind": "ghot.activation-broker.health",
                    "version": "0",
                    "status": "awake",
                    "preview_read_only": True,
                    "click_grants_consent": False,
                    "act_required": True,
                    "browser_post_same_origin_required": True,
                }).encode("utf-8")
                self._send(200, raw, "application/json")
                return

            if parsed.path in {"/preview", "/preview.json"}:
                params = parse_qs(parsed.query)
                launch_id = (params.get("launch_id") or [None])[0]
                if not isinstance(launch_id, str) or not launch_id:
                    self._send(
                        400,
                        b'{"error":"launch_id required"}',
                        "application/json",
                    )
                    return
                try:
                    preview = broker.preview(launch_id)
                except Exception as exc:
                    raw = json.dumps({
                        "error": f"{type(exc).__name__}: {exc}",
                    }).encode("utf-8")
                    self._send(404, raw, "application/json")
                    return
                if parsed.path == "/preview.json":
                    raw = json.dumps(preview, indent=2).encode("utf-8")
                    self._send(200, raw, "application/json")
                else:
                    raw = render_preview(preview).encode("utf-8")
                    self._send(200, raw, "text/html; charset=utf-8")
                return

            self._send(
                404,
                b'{"error":"not found"}',
                "application/json",
            )

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not self._browser_origin_allowed():
                self._send(
                    403,
                    b'{"error":"cross-origin browser activation refused"}',
                    "application/json",
                )
                return
            if parsed.path != "/act":
                self._send(
                    405,
                    b'{"error":"only POST /act is supported"}',
                    "application/json",
                )
                return

            length = int(self.headers.get("Content-Length") or "0")
            raw_body = self.rfile.read(length)
            content_type = self.headers.get("Content-Type") or ""
            wants_json = "application/json" in content_type

            try:
                if wants_json:
                    data = json.loads(raw_body.decode("utf-8"))
                    if not isinstance(data, dict):
                        raise ValueError("JSON object required")
                    launch_id = str(data.get("launch_id") or "")
                    expected = str(
                        data.get("expected_proposal_address") or ""
                    )
                    confirm = str(data.get("confirm") or "")
                    ttl = int(
                        data.get("ttl_seconds")
                        or DEFAULT_TTL_SECONDS
                    )
                else:
                    form = parse_qs(raw_body.decode("utf-8"))
                    launch_id = str(
                        (form.get("launch_id") or [""])[0]
                    )
                    expected = str(
                        (
                            form.get("expected_proposal_address")
                            or [""]
                        )[0]
                    )
                    confirm = str(
                        (form.get("confirm") or [""])[0]
                    )
                    ttl = int(
                        (form.get("ttl") or [DEFAULT_TTL_SECONDS])[0]
                    )

                result = broker.act(
                    launch_id=launch_id,
                    expected_proposal_address=expected,
                    confirm=confirm,
                    ttl_seconds=ttl,
                )
            except Exception as exc:
                payload = {
                    "error": f"{type(exc).__name__}: {exc}",
                    "ticket_issued": False,
                    "broker_granted_consent": False,
                }
                raw = json.dumps(payload, indent=2).encode("utf-8")
                self._send(409, raw, "application/json")
                return

            if wants_json:
                raw = json.dumps(result, indent=2).encode("utf-8")
                self._send(200, raw, "application/json")
            else:
                raw = render_result(result).encode("utf-8")
                self._send(200, raw, "text/html; charset=utf-8")

        def do_PUT(self) -> None:
            self._send(
                405,
                b'{"error":"method not allowed"}',
                "application/json",
            )

        def do_DELETE(self) -> None:
            self.do_PUT()

    return Handler


class ActivationBrokerHTTPService:
    def __init__(
        self,
        *,
        root: Path | None = None,
        host: str = "127.0.0.1",
        port: int = 7795,
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
            broker_handler(self.root),
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
        description=(
            "Preview and coordinate one explicit ACT activation."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    preview = sub.add_parser("preview")
    preview.add_argument("launch_id")

    act = sub.add_parser("act")
    act.add_argument("launch_id")
    act.add_argument("expected_proposal_address")
    act.add_argument("--confirm", required=True)
    act.add_argument("--ttl", type=int, default=DEFAULT_TTL_SECONDS)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7795)

    args = parser.parse_args()

    if args.command == "preview":
        broker = ActivationBroker()
        print(json.dumps(
            broker.preview(args.launch_id),
            indent=2,
        ))
        return 0

    if args.command == "act":
        broker = ActivationBroker()
        result = broker.act(
            launch_id=args.launch_id,
            expected_proposal_address=args.expected_proposal_address,
            confirm=args.confirm,
            ttl_seconds=args.ttl,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("verified_success") is True else 2

    service = ActivationBrokerHTTPService(
        host=args.host,
        port=args.port,
    )
    service.start()
    print(json.dumps({
        "event": "ghot.activation-broker.started",
        "host": args.host,
        "port": (
            service.server.server_port
            if service.server is not None
            else args.port
        ),
        "preview_read_only": True,
        "act_required": True,
        "click_grants_consent": False,
        "laws": [
            "BROKER != CONSENT",
            "UI CLICK != ACT TICKET",
            "PREVIEW != AUTHORITY",
            "PREVIEWED PROPOSAL != CHANGED PROPOSAL",
            "RESULT DISPLAY != SUCCESS CLAIM",
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
