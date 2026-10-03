#!/usr/bin/env python3
"""Install / render GHoT Organ Daemon startup surfaces — Experiment 015.

Default policy:
- Linux: systemd --user service (no root required)
- Termux: ~/.termux/boot launcher (requires Termux:Boot to actually run at boot)
- live USB: render a systemd system unit for explicit image integration

The installer never installs a lease authority. It only starts ghot/organ.py.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ORGAN = REPO_ROOT / "ghot" / "organ.py"


def default_state_home() -> Path:
    explicit = os.environ.get("GHOT_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return (Path(xdg).expanduser() / "ghot").resolve()
    return (Path.home() / ".local" / "state" / "ghot").resolve()


def q_systemd(value: str | Path) -> str:
    """Quote one systemd ExecStart/Environment value."""
    text = str(value).replace("\\", "\\\\").replace('"', '\"')
    return f'"{text}"'


def render_systemd_user_unit(
    *,
    python: Path,
    repo_root: Path,
    state_home: Path,
) -> str:
    return f"""[Unit]
Description=GHoT Organ Daemon
After=network.target
Wants=network.target

[Service]
Type=simple
WorkingDirectory={q_systemd(repo_root)}
Environment=PYTHONUNBUFFERED=1
Environment=GHOT_HOME={q_systemd(state_home)}
ExecStart={q_systemd(python)} {q_systemd(repo_root / "ghot" / "organ.py")}
Restart=on-failure
RestartSec=5
TimeoutStopSec=20

# User-scoped containment. GHoT still needs network and local filesystem access.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={q_systemd(state_home)}

[Install]
WantedBy=default.target
"""


def render_systemd_system_unit(
    *,
    python: Path,
    repo_root: Path,
    state_home: Path,
    user: str,
) -> str:
    return f"""[Unit]
Description=GHoT Organ Daemon (boot body)
After=network.target
Wants=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={q_systemd(repo_root)}
Environment=PYTHONUNBUFFERED=1
Environment=GHOT_HOME={q_systemd(state_home)}
ExecStart={q_systemd(python)} {q_systemd(repo_root / "ghot" / "organ.py")}
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={q_systemd(state_home)}

[Install]
WantedBy=multi-user.target
"""


def render_termux_boot_script(
    *,
    python: Path,
    repo_root: Path,
    state_home: Path,
) -> str:
    log_dir = state_home / "logs"
    log_path = log_dir / "organ.log"
    return f"""#!/data/data/com.termux/files/usr/bin/sh
set -eu

export GHOT_HOME={shlex.quote(str(state_home))}
export PYTHONUNBUFFERED=1

mkdir -p {shlex.quote(str(state_home))} {shlex.quote(str(log_dir))}
cd {shlex.quote(str(repo_root))}

# Termux:Boot launches this file. nohup keeps the organ alive after the boot
# launcher returns. One pid file is advisory only; GHoT identity remains in
# GHOT_HOME, not in the process id.
nohup {shlex.quote(str(python))} {shlex.quote(str(repo_root / "ghot" / "organ.py"))} \
  >> {shlex.quote(str(log_path))} 2>&1 &
echo $! > {shlex.quote(str(state_home / "organ.pid"))}
"""


def write_atomic(path: Path, content: str, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        if mode is not None:
            tmp.chmod(mode)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def systemctl_user(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def install_systemd_user(
    *,
    python: Path,
    repo_root: Path,
    state_home: Path,
    unit_dir: Path,
    enable_now: bool,
) -> dict[str, Any]:
    unit_path = unit_dir / "ghot-organ.service"
    state_home.mkdir(parents=True, exist_ok=True)
    write_atomic(
        unit_path,
        render_systemd_user_unit(
            python=python,
            repo_root=repo_root,
            state_home=state_home,
        ),
        mode=0o644,
    )

    result: dict[str, Any] = {
        "kind": "ghot.install.result",
        "version": "0",
        "target": "systemd-user",
        "unit_path": str(unit_path),
        "state_home": str(state_home),
        "enabled_now": False,
        "commands": [
            "systemctl --user daemon-reload",
            "systemctl --user enable --now ghot-organ.service",
        ],
    }

    if enable_now:
        if shutil.which("systemctl") is None:
            result["error"] = "systemctl not found"
            return result
        reload_result = systemctl_user("daemon-reload")
        enable_result = systemctl_user("enable", "--now", "ghot-organ.service")
        result["systemctl"] = {
            "daemon_reload": {
                "returncode": reload_result.returncode,
                "stderr": reload_result.stderr.strip(),
            },
            "enable_now": {
                "returncode": enable_result.returncode,
                "stderr": enable_result.stderr.strip(),
            },
        }
        result["enabled_now"] = (
            reload_result.returncode == 0 and enable_result.returncode == 0
        )
    return result


def uninstall_systemd_user(*, unit_dir: Path, disable_now: bool) -> dict[str, Any]:
    unit_path = unit_dir / "ghot-organ.service"
    actions: list[str] = []
    if disable_now and shutil.which("systemctl"):
        result = systemctl_user("disable", "--now", "ghot-organ.service")
        actions.append(f"systemctl disable --now rc={result.returncode}")
    if unit_path.exists():
        unit_path.unlink()
        actions.append("unit removed")
    if shutil.which("systemctl"):
        result = systemctl_user("daemon-reload")
        actions.append(f"systemctl daemon-reload rc={result.returncode}")
    return {
        "kind": "ghot.install.result",
        "version": "0",
        "target": "systemd-user",
        "removed": not unit_path.exists(),
        "actions": actions,
    }


def install_termux(
    *,
    python: Path,
    repo_root: Path,
    state_home: Path,
    boot_dir: Path,
) -> dict[str, Any]:
    script_path = boot_dir / "ghot-organ"
    state_home.mkdir(parents=True, exist_ok=True)
    write_atomic(
        script_path,
        render_termux_boot_script(
            python=python,
            repo_root=repo_root,
            state_home=state_home,
        ),
        mode=0o700,
    )
    return {
        "kind": "ghot.install.result",
        "version": "0",
        "target": "termux-boot",
        "script_path": str(script_path),
        "state_home": str(state_home),
        "requires": [
            "Termux",
            "Termux:Boot",
            "launch Termux:Boot once after installation",
        ],
        "installed": True,
    }


def uninstall_termux(*, boot_dir: Path) -> dict[str, Any]:
    script_path = boot_dir / "ghot-organ"
    if script_path.exists():
        script_path.unlink()
    return {
        "kind": "ghot.install.result",
        "version": "0",
        "target": "termux-boot",
        "removed": not script_path.exists(),
    }


def render_live_usb_bundle(
    *,
    output_dir: Path,
    python: Path,
    repo_root: Path,
    state_home: Path,
    user: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    unit_path = output_dir / "ghot-organ.service"
    readme_path = output_dir / "INSTALL.txt"
    write_atomic(
        unit_path,
        render_systemd_system_unit(
            python=python,
            repo_root=repo_root,
            state_home=state_home,
            user=user,
        ),
        mode=0o644,
    )
    instructions = f"""GHoT live-USB autostart bundle

This directory is a render artifact. It does NOT modify the current machine.

During live-image construction:

1. Ensure the GHoT repository is present at:
   {repo_root}

2. Ensure Python exists at:
   {python}

3. Ensure runtime user exists:
   {user}

4. Copy ghot-organ.service into /etc/systemd/system/.

5. Enable it inside the image:
   systemctl enable ghot-organ.service

6. Ensure the runtime user can write:
   {state_home}

The unit starts only ghot/organ.py. It does not automatically create or grant
lease authority.
"""
    write_atomic(readme_path, instructions, mode=0o644)
    return {
        "kind": "ghot.install.result",
        "version": "0",
        "target": "live-usb-bundle",
        "output_dir": str(output_dir),
        "unit_path": str(unit_path),
        "instructions_path": str(readme_path),
        "modified_host": False,
    }


def resolved_python(value: str | None) -> Path:
    candidate = value or sys.executable
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        found = shutil.which(candidate)
        if not found:
            raise SystemExit(f"python executable not found: {candidate}")
        path = Path(found)
    return path.resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Install GHoT organ boot surfaces.")
    parser.add_argument("--python", default=None)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--state-home", default=None)

    sub = parser.add_subparsers(dest="command", required=True)

    su = sub.add_parser("systemd-user")
    su.add_argument("--unit-dir", default=None)
    su.add_argument("--enable-now", action="store_true")
    su.add_argument("--uninstall", action="store_true")

    tx = sub.add_parser("termux")
    tx.add_argument("--boot-dir", default=None)
    tx.add_argument("--uninstall", action="store_true")

    live = sub.add_parser("live-usb")
    live.add_argument("--output-dir", required=True)
    live.add_argument("--user", default="ghot")

    sub.add_parser("status")

    args = parser.parse_args()
    python = resolved_python(args.python)
    repo_root = Path(args.repo_root).expanduser().resolve()
    state_home = (
        Path(args.state_home).expanduser().resolve()
        if args.state_home
        else default_state_home()
    )

    if args.command == "systemd-user":
        unit_dir = (
            Path(args.unit_dir).expanduser().resolve()
            if args.unit_dir
            else (Path.home() / ".config" / "systemd" / "user")
        )
        result = (
            uninstall_systemd_user(unit_dir=unit_dir, disable_now=args.enable_now)
            if args.uninstall
            else install_systemd_user(
                python=python,
                repo_root=repo_root,
                state_home=state_home,
                unit_dir=unit_dir,
                enable_now=args.enable_now,
            )
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "termux":
        boot_dir = (
            Path(args.boot_dir).expanduser().resolve()
            if args.boot_dir
            else (Path.home() / ".termux" / "boot")
        )
        result = (
            uninstall_termux(boot_dir=boot_dir)
            if args.uninstall
            else install_termux(
                python=python,
                repo_root=repo_root,
                state_home=state_home,
                boot_dir=boot_dir,
            )
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "live-usb":
        result = render_live_usb_bundle(
            output_dir=Path(args.output_dir).expanduser().resolve(),
            python=python,
            repo_root=repo_root,
            state_home=state_home,
            user=args.user,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "status":
        unit = Path.home() / ".config" / "systemd" / "user" / "ghot-organ.service"
        termux = Path.home() / ".termux" / "boot" / "ghot-organ"
        print(json.dumps({
            "kind": "ghot.install.status",
            "version": "0",
            "repo_root": str(repo_root),
            "python": str(python),
            "state_home": str(state_home),
            "systemd_user_unit": {
                "path": str(unit),
                "installed": unit.exists(),
            },
            "termux_boot": {
                "path": str(termux),
                "installed": termux.exists(),
            },
        }, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
