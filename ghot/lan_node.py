#!/usr/bin/env python3
"""GHoT LAN node — Experiment 002.

Zero external dependencies.

Machine A:
    python3 ghot/lan_node.py serve --port 7788

Machine B:
    python3 ghot/lan_node.py scan
    python3 ghot/lan_node.py task http://192.168.1.10:7788 system.echo "hello other body"

Use only on a LAN you control. The V0 task endpoint exposes an intentionally
tiny allowlist inherited from reference_node.py.
"""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from reference_node import body, execute, node_id, now

DISCOVERY_PORT = 47888
DISCOVERY_MAGIC = "ghot.discover.v0"


def send_json(handler: BaseHTTPRequestHandler, status: int, value: Any) -> None:
    data = json.dumps(value, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    server_version = "GHoT/0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[http] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        if self.path == "/body":
            record = body()
            record["service"] = {
                "transport": "http",
                "port": self.server.server_port,
            }
            send_json(self, 200, record)
            return
        send_json(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/task":
            send_json(self, 404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            incoming = json.loads(raw.decode("utf-8"))
            capability = incoming["capability"]
            payload = incoming.get("input")
            task, receipt = execute(capability, payload)
            send_json(self, 200 if receipt["status"] == "ok" else 400, {
                "task": task,
                "receipt": receipt,
            })
        except Exception as exc:
            send_json(self, 400, {
                "error": f"{type(exc).__name__}: {exc}",
            })


def discovery_responder(http_port: int, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", DISCOVERY_PORT))
    sock.settimeout(1.0)

    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            message = json.loads(data.decode("utf-8"))
        except Exception:
            continue

        if message.get("kind") != DISCOVERY_MAGIC:
            continue

        response = {
            "kind": "ghot.here.v0",
            "version": "0",
            "node_id": node_id(),
            "observed_at": now(),
            "http_port": http_port,
            "body": body(),
        }
        sock.sendto(json.dumps(response).encode("utf-8"), addr)

    sock.close()


def serve(port: int) -> int:
    stop = threading.Event()
    responder = threading.Thread(
        target=discovery_responder,
        args=(port, stop),
        daemon=True,
    )
    responder.start()

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(json.dumps({
        "event": "ghot.node.started",
        "node_id": node_id(),
        "http_port": port,
        "discovery_port": DISCOVERY_PORT,
    }, indent=2))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.shutdown()
        server.server_close()

    return 0


def scan(timeout: float) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.25)
    sock.bind(("", 0))

    request = {
        "kind": DISCOVERY_MAGIC,
        "version": "0",
        "requester_node_id": node_id(),
        "observed_at": now(),
    }
    sock.sendto(
        json.dumps(request).encode("utf-8"),
        ("255.255.255.255", DISCOVERY_PORT),
    )

    deadline = time.monotonic() + timeout
    seen: dict[str, dict[str, Any]] = {}

    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue

        try:
            message = json.loads(data.decode("utf-8"))
        except Exception:
            continue

        if message.get("kind") != "ghot.here.v0":
            continue

        key = message.get("node_id") or f"{addr[0]}:{addr[1]}"
        message["address"] = addr[0]
        message["url"] = f"http://{addr[0]}:{message['http_port']}"
        seen[key] = message

    sock.close()
    print(json.dumps(list(seen.values()), indent=2))
    return 0


def cross_task(url: str, capability: str, payload: Any) -> int:
    envelope = {
        "kind": "ghot.task.request.v0",
        "version": "0",
        "requester_node_id": node_id(),
        "capability": capability,
        "input": payload,
    }
    data = json.dumps(envelope).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/task",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(json.dumps(result, indent=2))
            return 0
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"))
        return 1
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--port", type=int, default=7788)

    scan_parser = sub.add_parser("scan")
    scan_parser.add_argument("--timeout", type=float, default=2.0)

    task_parser = sub.add_parser("task")
    task_parser.add_argument("url")
    task_parser.add_argument("capability")
    task_parser.add_argument("payload", nargs="?", default="")

    args = parser.parse_args()

    if args.command == "serve":
        return serve(args.port)
    if args.command == "scan":
        return scan(args.timeout)
    if args.command == "task":
        return cross_task(args.url, args.capability, args.payload)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
