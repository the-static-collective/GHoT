#!/usr/bin/env python3
"""GHoT Organ Daemon — Experiment 014.

One process can now inhabit a body:

    python3 ghot/organ.py

The daemon composes existing GHoT subsystems rather than replacing them:
- BODY HTTP service
- BODY LAN discovery responder
- fresh BODY/power/offer probe
- liveness field refresh
- trusted authority porch discovery
- portable lease worker

Subsystem failures are recorded and retried on later cycles. One failed loop
does not erase body identity or the rest of the organ's state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from authority_discovery import resolve_trusted_authorities
from boot_presence import PresenceStore
from lan_node import (
    DISCOVERY_MAGIC,
    DISCOVERY_PORT,
    Handler,
    discover_peers,
    send_json,
)
from lease_remote import work_available
from liveness_field import LivenessField
from reference_node import ROOT, body, node_id
from relatte_identity import IdentityKey
from state_migration import StateMigrator
from state_parcel import parcel_handler
from grammar_exchange import GrammarExchangeService
from curious_doors import CuriousDoorsHTTPService


BodyProbe = Callable[[], dict[str, Any]]
PeerDiscoverer = Callable[[float], list[dict[str, Any]]]
AuthorityResolver = Callable[[float], list[dict[str, Any]]]
WorkRunner = Callable[..., dict[str, Any]]


def iso_now(epoch: float | None = None) -> str:
    when = time.time() if epoch is None else float(epoch)
    return datetime.fromtimestamp(when, timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


class OrganDaemon:
    def __init__(
        self,
        *,
        root: Path | None = None,
        body_probe: BodyProbe = body,
        peer_discoverer: PeerDiscoverer = discover_peers,
        authority_resolver: AuthorityResolver = resolve_trusted_authorities,
        work_runner: WorkRunner = work_available,
        discovery_timeout: float = 2.0,
        authority_timeout: float = 2.0,
        lease_seconds: float = 60.0,
        presence_context: dict[str, Any] | None = None,
    ) -> None:
        self.root = root or ROOT
        self.body_probe = body_probe
        self.peer_discoverer = peer_discoverer
        self.authority_resolver = authority_resolver
        self.work_runner = work_runner
        self.discovery_timeout = discovery_timeout
        self.authority_timeout = authority_timeout
        self.lease_seconds = lease_seconds
        self.presence_context = presence_context or {
            "boot_id": None,
            "manifest_address": None,
            "startup_receipt_id": None,
        }
        self.state_path = self.root / "organ" / "state.v1.json"
        self.records_dir = self.root / "records"
        self.field = LivenessField(
            state_path=self.root / "field.v0.json",
            event_sink=self._field_event,
        )
        self.started_at = iso_now()
        self.cycle_count = 0
        self.last_event_fingerprint: str | None = None
        self.service_state: dict[str, Any] = {
            "body_http": {"state": "not-started"},
            "body_discovery": {"state": "not-started"},
            "presence_http": {"state": "not-started"},
            "state_parcel_http": {"state": "not-started"},
            "grammar_exchange": {"state": "not-started"},
            "curious_doors": {"state": "not-started"},
        }

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(f".tmp-{uuid.uuid4()}")
        temp.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.state_path)

    def _event(self, event_type: str, detail: dict[str, Any]) -> dict[str, Any]:
        self.records_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "kind": "ghot.organ.event",
            "version": "0",
            "event_id": f"organ-event-{uuid.uuid4()}",
            "event_type": event_type,
            "node_id": detail.get("node_id"),
            "observed_at": iso_now(),
            "detail": detail,
        }
        path = self.records_dir / (
            f"{int(time.time() * 1000)}-organ-event-{event['event_id']}.json"
        )
        path.write_text(
            json.dumps(event, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return event

    def _field_event(self, event: dict[str, Any]) -> None:
        self._event(
            str(event.get("event_type") or "field.event"),
            {
                "node_id": event.get("node_id"),
                "field_event": event,
            },
        )

    @staticmethod
    def _body_summary(record: dict[str, Any]) -> dict[str, Any]:
        identity = record.get("identity") or {}
        power = record.get("power") or {}
        offers = []
        for offer in record.get("offers") or []:
            if not isinstance(offer, dict):
                continue
            offers.append({
                "capability": offer.get("capability"),
                "available": offer.get("available"),
                "power_class": (offer.get("power") or {}).get("class"),
            })
        offers.sort(key=lambda item: str(item.get("capability")))
        return {
            "node_id": record.get("node_id"),
            "identity": {
                "available": identity.get("available"),
                "particular": identity.get("particular"),
                "profile": identity.get("profile"),
            },
            "power": {
                "source": power.get("source"),
                "battery_percent": power.get("battery_percent"),
                "charging": power.get("charging"),
                "renewable_surplus": power.get("renewable_surplus"),
                "willingness": power.get("willingness"),
            },
            "offers": offers,
        }

    @staticmethod
    def _authority_summary(
        observations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for observation in observations:
            advert = observation.get("advert") or {}
            result.append({
                "authority_id": advert.get("authority_id"),
                "particular": advert.get("particular"),
                "authority_url": observation.get("authority_url"),
                "trust": observation.get("trust"),
            })
        result.sort(
            key=lambda item: (
                str(item.get("particular")),
                str(item.get("authority_url")),
            )
        )
        return result

    def cycle(self, *, at: float | None = None) -> dict[str, Any]:
        when = time.time() if at is None else float(at)
        self.cycle_count += 1
        errors: list[dict[str, str]] = []

        try:
            local = self.body_probe()
        except Exception as exc:
            local = {
                "kind": "ghot.body",
                "version": "0",
                "node_id": node_id(),
                "offers": [],
            }
            errors.append({
                "subsystem": "body",
                "error": f"{type(exc).__name__}: {exc}",
            })

        local_id = str(local.get("node_id") or node_id())

        try:
            peers = self.peer_discoverer(self.discovery_timeout)
        except Exception as exc:
            peers = []
            errors.append({
                "subsystem": "body-discovery",
                "error": f"{type(exc).__name__}: {exc}",
            })

        observations = [{
            "node_id": local_id,
            "body": local,
            "url": None,
            "address": None,
        }]
        observations.extend(peers)

        try:
            field_snapshot = self.field.refresh_observations(
                observations,
                at=when,
            )
        except Exception as exc:
            field_snapshot = self.field.snapshot(
                at=when,
                sweep_first=False,
            )
            errors.append({
                "subsystem": "liveness",
                "error": f"{type(exc).__name__}: {exc}",
            })

        try:
            authorities = self.authority_resolver(self.authority_timeout)
        except Exception as exc:
            authorities = []
            errors.append({
                "subsystem": "authority-discovery",
                "error": f"{type(exc).__name__}: {exc}",
            })

        urls = [
            item["authority_url"]
            for item in authorities
            if item.get("authority_url")
        ]
        try:
            work = self.work_runner(
                urls,
                worker_id=local_id,
                lease_seconds=self.lease_seconds,
            )
        except Exception as exc:
            work = {
                "status": "worker-error",
                "worker_id": local_id,
                "error": f"{type(exc).__name__}: {exc}",
            }
            errors.append({
                "subsystem": "lease-worker",
                "error": work["error"],
            })

        state = {
            "kind": "ghot.organ.state",
            "version": "1",
            "node_id": local_id,
            "started_at": self.started_at,
            "updated_at": iso_now(when),
            "cycle": self.cycle_count,
            "body": self._body_summary(local),
            "field": field_snapshot,
            "authorities": self._authority_summary(authorities),
            "work": work,
            "services": self.service_state,
            "errors": errors,
            "presence": dict(self.presence_context),
        }
        self._write_state(state)

        event_projection = {
            "node_id": local_id,
            "body": state["body"],
            "field_states": [
                {
                    "node_id": entry.get("node_id"),
                    "state": entry.get("state"),
                }
                for entry in field_snapshot.get("bodies", [])
            ],
            "authorities": state["authorities"],
            "work_status": work.get("status"),
            "work_authority": work.get("authority_particular"),
            "work_receipt": (
                (work.get("authority_receipt") or {}).get("receipt_id")
                if isinstance(work.get("authority_receipt"), dict)
                else None
            ),
            "errors": errors,
        }
        event_fingerprint = _fingerprint(event_projection)
        if (
            event_fingerprint != self.last_event_fingerprint
            or errors
            or work.get("status") not in {
                "no-dispatch",
                "no-trusted-authority",
            }
        ):
            self._event("organ.state_changed", event_projection)
            self.last_event_fingerprint = event_fingerprint

        return state


class BodyDiscoveryService:
    """BODY discovery responder with bind failure visible to the supervisor."""

    def __init__(
        self,
        *,
        http_port: int,
        discovery_port: int,
        state_parcel_port: int | None,
        stop: threading.Event,
    ) -> None:
        self.http_port = http_port
        self.discovery_port = discovery_port
        self.state_parcel_port = state_parcel_port
        self.stop = stop
        self.socket: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.error: str | None = None

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.discovery_port))
        sock.settimeout(1.0)
        self.socket = sock
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        assert self.socket is not None
        sock = self.socket
        try:
            while not self.stop.is_set():
                try:
                    data, address = sock.recvfrom(65535)
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
                    "observed_at": iso_now(),
                    "http_port": self.http_port,
                    "state_parcel_port": self.state_parcel_port,
                    "body": body(),
                }
                sock.sendto(json.dumps(response).encode("utf-8"), address)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def close(self) -> None:
        if self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass


class OrganServices:
    def __init__(
        self,
        daemon: OrganDaemon,
        *,
        http_host: str,
        http_port: int,
        discovery_port: int,
        state_parcel_port: int | None = None,
    ) -> None:
        self.daemon = daemon
        self.http_host = http_host
        self.http_port = http_port
        self.discovery_port = discovery_port
        self.state_parcel_port = state_parcel_port
        self.stop = threading.Event()
        self.http_server: ThreadingHTTPServer | None = None
        self.http_thread: threading.Thread | None = None
        self.discovery: BodyDiscoveryService | None = None

    def _start_http(self) -> None:
        server = ThreadingHTTPServer(
            (self.http_host, self.http_port),
            Handler,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()
        self.http_server = server
        self.http_thread = thread
        self.daemon.service_state["body_http"] = {
            "state": "awake",
            "port": server.server_port,
        }

    def _start_discovery(self) -> None:
        discovery = BodyDiscoveryService(
            http_port=self.http_port,
            discovery_port=self.discovery_port,
            state_parcel_port=self.state_parcel_port,
            stop=self.stop,
        )
        discovery.start()
        self.discovery = discovery
        self.daemon.service_state["body_discovery"] = {
            "state": "awake",
            "port": self.discovery_port,
        }

    def start(self) -> None:
        try:
            self._start_http()
        except Exception as exc:
            self.daemon.service_state["body_http"] = {
                "state": "failed",
                "port": self.http_port,
                "error": f"{type(exc).__name__}: {exc}",
            }

        try:
            self._start_discovery()
        except Exception as exc:
            self.daemon.service_state["body_discovery"] = {
                "state": "failed",
                "port": self.discovery_port,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def supervise(self) -> None:
        if self.stop.is_set():
            return

        if self.http_thread is None or not self.http_thread.is_alive():
            if self.http_server is not None:
                try:
                    self.http_server.server_close()
                except OSError:
                    pass
            try:
                self._start_http()
                self.daemon._event("organ.service_restarted", {
                    "node_id": node_id(),
                    "service": "body_http",
                    "port": self.http_port,
                })
            except Exception as exc:
                self.daemon.service_state["body_http"] = {
                    "state": "failed",
                    "port": self.http_port,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        discovery_alive = (
            self.discovery is not None
            and self.discovery.thread is not None
            and self.discovery.thread.is_alive()
        )
        if not discovery_alive:
            if self.discovery is not None:
                self.discovery.close()
            try:
                self._start_discovery()
                self.daemon._event("organ.service_restarted", {
                    "node_id": node_id(),
                    "service": "body_discovery",
                    "port": self.discovery_port,
                })
            except Exception as exc:
                self.daemon.service_state["body_discovery"] = {
                    "state": "failed",
                    "port": self.discovery_port,
                    "error": f"{type(exc).__name__}: {exc}",
                }

    def close(self) -> None:
        self.stop.set()
        if self.discovery is not None:
            self.discovery.close()
        if self.http_server is not None:
            try:
                self.http_server.shutdown()
            except OSError:
                pass
            self.http_server.server_close()
        self.daemon.service_state["body_http"] = {
            **self.daemon.service_state.get("body_http", {}),
            "state": "stopped",
        }
        self.daemon.service_state["body_discovery"] = {
            **self.daemon.service_state.get("body_discovery", {}),
            "state": "stopped",
        }


class PresenceHTTPService:
    """Loopback-first health/presence endpoint for the local machine."""

    def __init__(
        self,
        daemon: OrganDaemon,
        store: PresenceStore,
        *,
        host: str,
        port: int,
    ) -> None:
        self.daemon = daemon
        self.store = store
        self.host = host
        self.port = port
        service = self

        class PresenceHandler(BaseHTTPRequestHandler):
            server_version = "GHoTPresence/0"

            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                if self.path == "/health":
                    send_json(self, 200, service.store.health())
                    return
                if self.path == "/presence":
                    send_json(self, 200, service.store.presence())
                    return
                send_json(self, 404, {"error": "not found"})

        self.handler = PresenceHandler
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.server = ThreadingHTTPServer(
            (self.host, self.port),
            self.handler,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.daemon.service_state["presence_http"] = {
            "state": "awake",
            "host": self.host,
            "port": self.server.server_port,
        }

    def supervise(self) -> None:
        alive = self.thread is not None and self.thread.is_alive()
        if alive:
            return
        if self.server is not None:
            try:
                self.server.server_close()
            except OSError:
                pass
        try:
            self.start()
            self.daemon._event("organ.service_restarted", {
                "node_id": node_id(),
                "service": "presence_http",
                "host": self.host,
                "port": self.port,
            })
        except Exception as exc:
            self.daemon.service_state["presence_http"] = {
                "state": "failed",
                "host": self.host,
                "port": self.port,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def close(self) -> None:
        if self.server is not None:
            try:
                self.server.shutdown()
            except OSError:
                pass
            self.server.server_close()
        self.daemon.service_state["presence_http"] = {
            **self.daemon.service_state.get("presence_http", {}),
            "state": "stopped",
        }


class StateParcelHTTPService:
    """Supervised HOLD-only state parcel porch."""

    def __init__(
        self,
        daemon: OrganDaemon,
        *,
        root: Path,
        host: str,
        port: int,
    ) -> None:
        self.daemon = daemon
        self.root = root
        self.host = host
        self.port = port
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.server = ThreadingHTTPServer(
            (self.host, self.port),
            parcel_handler(self.root),
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.daemon.service_state["state_parcel_http"] = {
            "state": "awake",
            "host": self.host,
            "port": self.server.server_port,
            "automatic_disposition": "HOLD",
        }

    def supervise(self) -> None:
        alive = self.thread is not None and self.thread.is_alive()
        if alive:
            return
        if self.server is not None:
            try:
                self.server.server_close()
            except OSError:
                pass
        try:
            self.start()
            self.daemon._event("organ.service_restarted", {
                "node_id": node_id(),
                "service": "state_parcel_http",
                "host": self.host,
                "port": self.port,
            })
        except Exception as exc:
            self.daemon.service_state["state_parcel_http"] = {
                "state": "failed",
                "host": self.host,
                "port": self.port,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def close(self) -> None:
        if self.server is not None:
            try:
                self.server.shutdown()
            except OSError:
                pass
            self.server.server_close()
        self.daemon.service_state["state_parcel_http"] = {
            **self.daemon.service_state.get("state_parcel_http", {}),
            "state": "stopped",
        }


class OrganGrammarExchangeService:
    """Supervise the non-authoritative grammar exchange table."""

    def __init__(
        self,
        daemon: OrganDaemon,
        *,
        root: Path,
        host: str,
        port: int,
        discovery_port: int,
        parcel_port: int,
    ) -> None:
        self.daemon = daemon
        self.root = root
        self.host = host
        self.port = port
        self.discovery_port = discovery_port
        self.parcel_port = parcel_port
        self.service: GrammarExchangeService | None = None

    def start(self) -> None:
        self.service = GrammarExchangeService(
            root=self.root,
            host=self.host,
            port=self.port,
            discovery_port=self.discovery_port,
            parcel_port=self.parcel_port,
        )
        self.service.start()
        self.daemon.service_state["grammar_exchange"] = {
            "state": "awake",
            "host": self.host,
            "port": (
                self.service.server.server_port
                if self.service.server is not None
                else self.port
            ),
            "discovery_port": self.discovery_port,
            "auto_share": False,
            "auto_request": False,
            "auto_offer": False,
            "auto_install": False,
        }

    def supervise(self) -> None:
        alive = (
            self.service is not None
            and self.service.http_thread is not None
            and self.service.http_thread.is_alive()
            and self.service.discovery_thread is not None
            and self.service.discovery_thread.is_alive()
        )
        if alive:
            return
        if self.service is not None:
            self.service.close()
        try:
            self.start()
            self.daemon._event("organ.service_restarted", {
                "node_id": node_id(),
                "service": "grammar_exchange",
                "host": self.host,
                "port": self.port,
                "discovery_port": self.discovery_port,
            })
        except Exception as exc:
            self.daemon.service_state["grammar_exchange"] = {
                "state": "failed",
                "host": self.host,
                "port": self.port,
                "discovery_port": self.discovery_port,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def close(self) -> None:
        if self.service is not None:
            self.service.close()
        self.daemon.service_state["grammar_exchange"] = {
            **self.daemon.service_state.get("grammar_exchange", {}),
            "state": "stopped",
        }


class OrganCuriousDoorsService:
    """Supervise the loopback-only read-only curiosity surface."""

    def __init__(
        self,
        daemon: OrganDaemon,
        *,
        root: Path,
        host: str,
        port: int,
    ) -> None:
        self.daemon = daemon
        self.root = root
        self.host = host
        self.port = port
        self.service: CuriousDoorsHTTPService | None = None

    def start(self) -> None:
        self.service = CuriousDoorsHTTPService(
            root=self.root,
            host=self.host,
            port=self.port,
        )
        self.service.start()
        live_port = (
            self.service.server.server_port
            if self.service.server is not None
            else self.port
        )
        self.daemon.service_state["curious_doors"] = {
            "state": "awake",
            "host": self.host,
            "port": live_port,
            "read_only": True,
            "auto_want": False,
            "auto_refresh": False,
            "auto_request": False,
            "auto_offer": False,
            "auto_install": False,
        }

    def supervise(self) -> None:
        alive = (
            self.service is not None
            and self.service.thread is not None
            and self.service.thread.is_alive()
        )
        if alive:
            return
        if self.service is not None:
            self.service.close()
        try:
            self.start()
            self.daemon._event("organ.service_restarted", {
                "node_id": node_id(),
                "service": "curious_doors",
                "host": self.host,
                "port": self.port,
            })
        except Exception as exc:
            self.daemon.service_state["curious_doors"] = {
                "state": "failed",
                "host": self.host,
                "port": self.port,
                "read_only": True,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def close(self) -> None:
        if self.service is not None:
            self.service.close()
        self.daemon.service_state["curious_doors"] = {
            **self.daemon.service_state.get("curious_doors", {}),
            "state": "stopped",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one GHoT organ process.")
    parser.add_argument("--http-host", default="0.0.0.0")
    parser.add_argument("--http-port", type=int, default=7788)
    parser.add_argument("--discovery-port", type=int, default=DISCOVERY_PORT)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--discovery-timeout", type=float, default=2.0)
    parser.add_argument("--authority-timeout", type=float, default=2.0)
    parser.add_argument("--lease-seconds", type=float, default=60.0)
    parser.add_argument("--health-host", default="127.0.0.1")
    parser.add_argument("--health-port", type=int, default=7791)
    parser.add_argument("--state-host", default="0.0.0.0")
    parser.add_argument("--state-port", type=int, default=7792)
    parser.add_argument("--grammar-exchange-host", default="0.0.0.0")
    parser.add_argument("--grammar-exchange-port", type=int, default=7793)
    parser.add_argument("--grammar-discovery-port", type=int, default=47890)
    parser.add_argument("--curious-doors-host", default="127.0.0.1")
    parser.add_argument("--curious-doors-port", type=int, default=7794)
    parser.add_argument(
        "--no-health",
        action="store_true",
        help="disable the loopback health/presence HTTP endpoint",
    )
    parser.add_argument(
        "--no-state-porch",
        action="store_true",
        help="disable the HOLD-only state parcel receiving porch",
    )
    parser.add_argument(
        "--no-grammar-exchange",
        action="store_true",
        help="disable the signed grammar exchange table service",
    )
    parser.add_argument(
        "--no-curious-doors",
        action="store_true",
        help="disable the loopback-only read-only Curious Doors surface",
    )
    parser.add_argument(
        "--no-auto-migrate",
        action="store_true",
        help="inspect state but do not apply registered startup migrations",
    )
    parser.add_argument(
        "--no-serve",
        action="store_true",
        help="run supervisory cycles without BODY HTTP/discovery services",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one cycle and exit",
    )
    args = parser.parse_args()

    if args.interval <= 0:
        raise SystemExit("--interval must be > 0")

    body_record = body()
    migrator = StateMigrator(ROOT)
    migration_run: dict[str, Any] = {
        "kind": "ghot.state.migration.run",
        "version": "0",
        "applied": [],
        "state": migrator.inspect(),
    }
    if not args.no_auto_migrate:
        try:
            migration_signer = IdentityKey.load_or_create(
                ROOT / "identity" / "body-p256.pem"
            )
            migration_run = migrator.apply_available(
                signer=migration_signer,
            )
        except Exception as exc:
            migration_run = {
                "kind": "ghot.state.migration.run",
                "version": "0",
                "applied": [],
                "state": migrator.inspect(),
                "error": f"{type(exc).__name__}: {exc}",
            }

    presence_store = PresenceStore(ROOT)
    boot_manifest, startup_receipt = presence_store.wake(
        repo_root=Path(__file__).resolve().parents[1],
        body_record=body_record,
        migration_run=migration_run,
    )
    presence_context = {
        "boot_id": boot_manifest.get("boot_id"),
        "manifest_address": boot_manifest.get("manifest_address"),
        "startup_receipt_id": (
            startup_receipt.get("receipt_id")
            if isinstance(startup_receipt, dict)
            else None
        ),
    }
    daemon = OrganDaemon(
        discovery_timeout=args.discovery_timeout,
        authority_timeout=args.authority_timeout,
        lease_seconds=args.lease_seconds,
        presence_context=presence_context,
    )

    services: OrganServices | None = None
    presence_service: PresenceHTTPService | None = None
    state_parcel_service: StateParcelHTTPService | None = None
    grammar_exchange_service: OrganGrammarExchangeService | None = None
    curious_doors_service: OrganCuriousDoorsService | None = None

    if not args.no_serve:
        services = OrganServices(
            daemon,
            http_host=args.http_host,
            http_port=args.http_port,
            discovery_port=args.discovery_port,
            state_parcel_port=(
                None if args.no_state_porch else args.state_port
            ),
        )
        services.start()
        if not args.no_state_porch:
            state_parcel_service = StateParcelHTTPService(
                daemon,
                root=ROOT,
                host=args.state_host,
                port=args.state_port,
            )
            try:
                state_parcel_service.start()
            except Exception as exc:
                daemon.service_state["state_parcel_http"] = {
                    "state": "failed",
                    "host": args.state_host,
                    "port": args.state_port,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        if not args.no_grammar_exchange:
            grammar_exchange_service = OrganGrammarExchangeService(
                daemon,
                root=ROOT,
                host=args.grammar_exchange_host,
                port=args.grammar_exchange_port,
                discovery_port=args.grammar_discovery_port,
                parcel_port=args.state_port,
            )
            try:
                grammar_exchange_service.start()
            except Exception as exc:
                daemon.service_state["grammar_exchange"] = {
                    "state": "failed",
                    "host": args.grammar_exchange_host,
                    "port": args.grammar_exchange_port,
                    "discovery_port": args.grammar_discovery_port,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        if not args.no_curious_doors:
            curious_doors_service = OrganCuriousDoorsService(
                daemon,
                root=ROOT,
                host=args.curious_doors_host,
                port=args.curious_doors_port,
            )
            try:
                curious_doors_service.start()
            except Exception as exc:
                daemon.service_state["curious_doors"] = {
                    "state": "failed",
                    "host": args.curious_doors_host,
                    "port": args.curious_doors_port,
                    "read_only": True,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        if not args.no_health:
            presence_service = PresenceHTTPService(
                daemon,
                presence_store,
                host=args.health_host,
                port=args.health_port,
            )
            try:
                presence_service.start()
            except Exception as exc:
                daemon.service_state["presence_http"] = {
                    "state": "failed",
                    "host": args.health_host,
                    "port": args.health_port,
                    "error": f"{type(exc).__name__}: {exc}",
                }

    initial_health = presence_store.health()
    print(json.dumps({
        "event": "ghot.organ.started",
        "node_id": node_id(),
        "boot_id": boot_manifest.get("boot_id"),
        "manifest_address": boot_manifest.get("manifest_address"),
        "startup_receipt_id": (
            startup_receipt.get("receipt_id")
            if isinstance(startup_receipt, dict)
            else None
        ),
        "boot_surface": boot_manifest.get("boot_surface"),
        "initial_health": initial_health.get("status"),
        "migrations_applied": (
            boot_manifest.get("state", {})
            .get("automatic_migrations_applied", [])
        ),
        "migration_error": migration_run.get("error"),
        "body_http_port": None if args.no_serve else args.http_port,
        "body_discovery_port": None if args.no_serve else args.discovery_port,
        "health_endpoint": (
            None
            if args.no_serve or args.no_health
            else f"http://{args.health_host}:{args.health_port}/health"
        ),
        "presence_endpoint": (
            None
            if args.no_serve or args.no_health
            else f"http://{args.health_host}:{args.health_port}/presence"
        ),
        "state_parcel_endpoint": (
            None
            if args.no_serve or args.no_state_porch
            else f"http://{args.state_host}:{args.state_port}/state-parcel"
        ),
        "curious_doors_endpoint": (
            None
            if args.no_serve or args.no_curious_doors
            else f"http://{args.curious_doors_host}:{args.curious_doors_port}/"
        ),
        "cycle_interval": args.interval,
        "authority_discovery": True,
    }, indent=2))

    try:
        while True:
            if services is not None:
                services.supervise()
            if presence_service is not None:
                presence_service.supervise()
            if state_parcel_service is not None:
                state_parcel_service.supervise()
            if grammar_exchange_service is not None:
                grammar_exchange_service.supervise()
            if curious_doors_service is not None:
                curious_doors_service.supervise()
            state = daemon.cycle()
            work_status = (state.get("work") or {}).get("status")
            if (
                args.once
                or state.get("errors")
                or work_status not in {"no-dispatch", "no-trusted-authority"}
            ):
                print(json.dumps(state, indent=2))
            if args.once:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        if curious_doors_service is not None:
            curious_doors_service.close()
        if grammar_exchange_service is not None:
            grammar_exchange_service.close()
        if state_parcel_service is not None:
            state_parcel_service.close()
        if presence_service is not None:
            presence_service.close()
        if services is not None:
            services.close()


if __name__ == "__main__":
    raise SystemExit(main())
