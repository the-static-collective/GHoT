#!/usr/bin/env python3
"""Remote GHoT organ for owner-issued P-256 work leases — Experiments 012/013.

013 adds zero-hand-wired authority resolution:
- discover signed authority porch adverts on the LAN;
- accept only pinned or previously admitted authority particulars;
- derive the current HTTP road from discovery;
- keep authority identity separate from network address.

Legacy explicit-URL invocation remains supported.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.request
from typing import Any

from authority_discovery import (
    fetch_authority_advert,
    resolve_trusted_authorities,
    verify_authority_advert,
)
from portable_lease import IdentityKey, make_crossing, verify_receipt
from reference_node import ROOT, execute, node_id


def body_signer() -> IdentityKey:
    return IdentityKey.load_or_create(ROOT / "identity" / "body-p256.pem")


def get_authority(base_url: str) -> dict[str, Any]:
    value = fetch_authority_advert(base_url)
    if not verify_authority_advert(value):
        raise RuntimeError("authority advert signature verification failed")

    pinned = os.environ.get("GHOT_AUTHORITY_PARTICULAR")
    if pinned and pinned != value.get("particular"):
        raise RuntimeError("authority particular does not match GHOT_AUTHORITY_PARTICULAR")
    return value


def post_crossing(
    base_url: str,
    crossing: dict[str, Any],
    *,
    authority: dict[str, Any],
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/crossing"
    data = json.dumps(crossing).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        receipt = json.loads(response.read().decode("utf-8"))
    if not isinstance(receipt, dict):
        raise RuntimeError("authority receipt is not an object")
    if receipt.get("crossing_id") != crossing.get("crossing_id"):
        raise RuntimeError("authority receipt crossing_id mismatch")
    if not verify_receipt(
        receipt,
        expected_public_key=authority["public_key"],
        expected_receiver_particular=authority["particular"],
    ):
        raise RuntimeError("authority receipt P-256 verification failed")
    return receipt


def extension(receipt: dict[str, Any]) -> dict[str, Any]:
    return ((receipt.get("extensions") or {}).get("ghot_lease") or {})


def crossing_for(
    action: str,
    *,
    authority: dict[str, Any],
    signer: IdentityKey,
    worker_id: str,
    hold_id: str | None = None,
    dispatch_id: str | None = None,
    lease_id: str | None = None,
    lease_seconds: float | None = None,
    child_energy_plan_id: str | None = None,
    receipt_id: str | None = None,
    outcome: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return make_crossing(
        action,
        signer=signer,
        authority_id=authority["authority_id"],
        worker_id=worker_id,
        worker_node_id=node_id(),
        hold_id=hold_id,
        dispatch_id=dispatch_id,
        lease_id=lease_id,
        lease_seconds=lease_seconds,
        child_energy_plan_id=child_energy_plan_id,
        receipt_id=receipt_id,
        outcome=outcome,
        error=error,
        return_address=None,
    )


def poll(
    base_url: str,
    *,
    authority: dict[str, Any],
    signer: IdentityKey,
    worker_id: str,
) -> dict[str, Any]:
    crossing = crossing_for(
        "POLL",
        authority=authority,
        signer=signer,
        worker_id=worker_id,
    )
    return post_crossing(base_url, crossing, authority=authority)


def claim(
    base_url: str,
    *,
    authority: dict[str, Any],
    signer: IdentityKey,
    worker_id: str,
    dispatch: dict[str, Any],
    lease_seconds: float,
) -> dict[str, Any]:
    crossing = crossing_for(
        "CLAIM",
        authority=authority,
        signer=signer,
        worker_id=worker_id,
        hold_id=dispatch["hold_id"],
        dispatch_id=dispatch["dispatch_id"],
        lease_seconds=lease_seconds,
    )
    return post_crossing(base_url, crossing, authority=authority)


def renew(
    base_url: str,
    *,
    authority: dict[str, Any],
    signer: IdentityKey,
    worker_id: str,
    hold_id: str,
    lease_id: str,
    lease_seconds: float,
) -> dict[str, Any]:
    crossing = crossing_for(
        "RENEW",
        authority=authority,
        signer=signer,
        worker_id=worker_id,
        hold_id=hold_id,
        lease_id=lease_id,
        lease_seconds=lease_seconds,
    )
    return post_crossing(base_url, crossing, authority=authority)


def complete(
    base_url: str,
    *,
    authority: dict[str, Any],
    signer: IdentityKey,
    worker_id: str,
    hold_id: str,
    lease_id: str,
    child_energy_plan_id: str,
    receipt_id: str | None,
    outcome: str,
    error: str | None,
) -> dict[str, Any]:
    crossing = crossing_for(
        "COMPLETE",
        authority=authority,
        signer=signer,
        worker_id=worker_id,
        hold_id=hold_id,
        lease_id=lease_id,
        child_energy_plan_id=child_energy_plan_id,
        receipt_id=receipt_id,
        outcome=outcome,
        error=error,
    )
    return post_crossing(base_url, crossing, authority=authority)


def abandon(
    base_url: str,
    *,
    authority: dict[str, Any],
    signer: IdentityKey,
    worker_id: str,
    hold_id: str,
    lease_id: str,
    reason: str,
) -> dict[str, Any]:
    crossing = crossing_for(
        "ABANDON",
        authority=authority,
        signer=signer,
        worker_id=worker_id,
        hold_id=hold_id,
        lease_id=lease_id,
        error=reason,
    )
    return post_crossing(base_url, crossing, authority=authority)


class RemoteRenewal:
    def __init__(
        self,
        base_url: str,
        *,
        authority: dict[str, Any],
        signer: IdentityKey,
        worker_id: str,
        hold_id: str,
        lease_id: str,
        lease_seconds: float,
    ) -> None:
        self.base_url = base_url
        self.authority = authority
        self.signer = signer
        self.worker_id = worker_id
        self.hold_id = hold_id
        self.lease_id = lease_id
        self.lease_seconds = lease_seconds
        self.interval = max(0.5, min(10.0, lease_seconds / 3.0))
        self.stop = threading.Event()
        self.lost = threading.Event()
        self.error: str | None = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.stop.wait(self.interval):
            try:
                receipt = renew(
                    self.base_url,
                    authority=self.authority,
                    signer=self.signer,
                    worker_id=self.worker_id,
                    hold_id=self.hold_id,
                    lease_id=self.lease_id,
                    lease_seconds=self.lease_seconds,
                )
                if receipt.get("kind") == "REFUSED":
                    self.error = receipt.get("note") or "renewal refused"
                    self.lost.set()
                    return
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                self.lost.set()
                return

    def __enter__(self) -> "RemoteRenewal":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop.set()
        self.thread.join(timeout=max(1.0, self.interval + 0.5))


def work_one(
    base_url: str,
    *,
    worker_id: str,
    lease_seconds: float,
) -> dict[str, Any]:
    signer = body_signer()
    authority = get_authority(base_url)

    poll_receipt = poll(
        base_url,
        authority=authority,
        signer=signer,
        worker_id=worker_id,
    )
    dispatches = extension(poll_receipt).get("dispatches") or []
    if not dispatches:
        return {
            "status": "no-dispatch",
            "worker_id": worker_id,
            "worker_particular": signer.particular(),
            "authority_id": authority.get("authority_id"),
            "authority_particular": authority.get("particular"),
            "authority_url": base_url,
        }

    dispatch = dispatches[0]
    claim_receipt = claim(
        base_url,
        authority=authority,
        signer=signer,
        worker_id=worker_id,
        dispatch=dispatch,
        lease_seconds=lease_seconds,
    )
    if claim_receipt.get("kind") == "REFUSED":
        return {
            "status": "claim-refused",
            "receipt": claim_receipt,
        }

    claim_ext = extension(claim_receipt)
    claim_record = claim_ext["claim"]
    granted_dispatch = claim_ext["dispatch"]
    hold = claim_ext["hold"]

    lease_id = claim_record["lease_id"]
    with RemoteRenewal(
        base_url,
        authority=authority,
        signer=signer,
        worker_id=worker_id,
        hold_id=hold["hold_id"],
        lease_id=lease_id,
        lease_seconds=lease_seconds,
    ) as renewal:
        task, local_receipt = execute(
            hold["capability"],
            hold.get("payload"),
            requester_node_id=f"ghot-authority:{authority['authority_id']}",
            constraints={
                "portable_lease": True,
                "authority_id": authority["authority_id"],
                "authority_particular": authority["particular"],
                "authority_url_observed": base_url,
                "dispatch_id": granted_dispatch["dispatch_id"],
                "lease_id": lease_id,
                "child_energy_plan_id": granted_dispatch["child_energy_plan_id"],
            },
        )

    if renewal.lost.is_set():
        return {
            "status": "lease-lost",
            "error": renewal.error,
            "task": task,
            "local_receipt": local_receipt,
        }

    completion = complete(
        base_url,
        authority=authority,
        signer=signer,
        worker_id=worker_id,
        hold_id=hold["hold_id"],
        lease_id=lease_id,
        child_energy_plan_id=granted_dispatch["child_energy_plan_id"],
        receipt_id=local_receipt.get("receipt_id"),
        outcome=local_receipt.get("status", "error"),
        error=local_receipt.get("error"),
    )
    return {
        "status": (
            "completed"
            if completion.get("kind") == "EXECUTED"
            else "completion-not-accepted"
        ),
        "authority_url": base_url,
        "authority_particular": authority["particular"],
        "task": task,
        "local_receipt": local_receipt,
        "authority_receipt": completion,
    }


def authority_urls(
    explicit_url: str | None,
    *,
    discover_timeout: float,
) -> list[str]:
    if explicit_url:
        return [explicit_url]
    observations = resolve_trusted_authorities(discover_timeout)
    return [item["authority_url"] for item in observations]


def poll_available(
    urls: list[str],
    *,
    worker_id: str,
) -> dict[str, Any]:
    signer = body_signer()
    results: list[dict[str, Any]] = []
    for url in urls:
        try:
            authority = get_authority(url)
            receipt = poll(
                url,
                authority=authority,
                signer=signer,
                worker_id=worker_id,
            )
            results.append({
                "authority_url": url,
                "authority_particular": authority["particular"],
                "receipt": receipt,
            })
        except Exception as exc:
            results.append({
                "authority_url": url,
                "error": f"{type(exc).__name__}: {exc}",
            })
    return {
        "kind": "ghot.remote.poll.result",
        "version": "0",
        "authority_count": len(urls),
        "results": results,
    }


def work_available(
    urls: list[str],
    *,
    worker_id: str,
    lease_seconds: float,
) -> dict[str, Any]:
    if not urls:
        return {
            "status": "no-trusted-authority",
            "worker_id": worker_id,
            "reason": (
                "no pinned or previously admitted authority porch was discovered"
            ),
        }

    quiet: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for url in urls:
        try:
            result = work_one(
                url,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
            )
        except Exception as exc:
            errors.append({
                "authority_url": url,
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        if result.get("status") != "no-dispatch":
            return result
        quiet.append(result)

    return {
        "status": "no-dispatch",
        "worker_id": worker_id,
        "authority_count": len(urls),
        "authorities": quiet,
        "errors": errors,
    }


def _normalized_argv(argv: list[str]) -> list[str]:
    """Preserve the 012 form: lease_remote.py URL watch ..."""
    if len(argv) >= 3 and argv[1].startswith(("http://", "https://")):
        url = argv[1]
        command = argv[2]
        return [argv[0], command, "--authority-url", url, *argv[3:]]
    return argv


def main(argv: list[str] | None = None) -> int:
    argv = _normalized_argv(list(argv or sys.argv))
    parser = argparse.ArgumentParser(description="Run a GHoT portable remote organ.")
    parser.add_argument(
        "--worker-id",
        default=None,
        help="selected BODY id; defaults to this body's stable node_id",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_authority_args(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--authority-url",
            default=None,
            help="explicit authority road; omit to discover trusted authority porches",
        )
        command.add_argument("--discover-timeout", type=float, default=2.0)

    poll_parser = sub.add_parser("poll")
    add_authority_args(poll_parser)

    work = sub.add_parser("work")
    add_authority_args(work)
    work.add_argument("--lease-seconds", type=float, default=60.0)

    watch = sub.add_parser("watch")
    add_authority_args(watch)
    watch.add_argument("--lease-seconds", type=float, default=60.0)
    watch.add_argument("--interval", type=float, default=5.0)

    args = parser.parse_args(argv[1:])
    worker_id = args.worker_id or node_id()

    if args.command == "poll":
        urls = authority_urls(
            args.authority_url,
            discover_timeout=args.discover_timeout,
        )
        result = poll_available(urls, worker_id=worker_id)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "work":
        urls = authority_urls(
            args.authority_url,
            discover_timeout=args.discover_timeout,
        )
        result = work_available(
            urls,
            worker_id=worker_id,
            lease_seconds=args.lease_seconds,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") in {
            "completed",
            "no-dispatch",
            "no-trusted-authority",
        } else 1

    if args.command == "watch":
        if args.interval <= 0:
            raise SystemExit("--interval must be > 0")
        try:
            while True:
                urls = authority_urls(
                    args.authority_url,
                    discover_timeout=args.discover_timeout,
                )
                result = work_available(
                    urls,
                    worker_id=worker_id,
                    lease_seconds=args.lease_seconds,
                )
                if result.get("status") not in {"no-dispatch", "no-trusted-authority"}:
                    print(json.dumps(result, indent=2))
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
