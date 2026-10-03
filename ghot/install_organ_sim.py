#!/usr/bin/env python3
"""Deterministic simulation for GHoT Experiment 015."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from install_organ import (
    install_systemd_user,
    install_termux,
    render_live_usb_bundle,
    uninstall_systemd_user,
    uninstall_termux,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        unit_dir = root / "systemd-user"
        boot_dir = root / "termux-boot"
        state_home = root / "state"
        live_dir = root / "live-bundle"
        python = Path("/usr/bin/python3")

        (repo / "ghot").mkdir(parents=True)
        (repo / "ghot" / "organ.py").write_text(
            "# simulated organ entrypoint\n",
            encoding="utf-8",
        )

        systemd_result = install_systemd_user(
            python=python,
            repo_root=repo,
            state_home=state_home,
            unit_dir=unit_dir,
            enable_now=False,
        )
        unit_path = Path(systemd_result["unit_path"])
        unit = unit_path.read_text(encoding="utf-8")

        assert "ExecStart=" in unit
        assert str(repo / "ghot" / "organ.py") in unit
        assert "lease_authority.py" not in unit
        assert "User=root" not in unit
        assert "NoNewPrivileges=true" in unit
        assert "ProtectSystem=strict" in unit
        assert "Environment=GHOT_BOOT_SURFACE=systemd-user" in unit
        assert "Environment=GHOT_BOOT_INSTANCE=ghot-organ.service" in unit
        assert str(state_home) in unit
        assert systemd_result["enabled_now"] is False

        # Reinstall should be an atomic replacement, not a duplicate hook.
        reinstall = install_systemd_user(
            python=python,
            repo_root=repo,
            state_home=state_home,
            unit_dir=unit_dir,
            enable_now=False,
        )
        assert Path(reinstall["unit_path"]) == unit_path
        idempotent_install = len(list(unit_dir.glob("ghot-organ.service"))) == 1
        assert idempotent_install

        termux_result = install_termux(
            python=python,
            repo_root=repo,
            state_home=state_home,
            boot_dir=boot_dir,
        )
        termux_path = Path(termux_result["script_path"])
        termux = termux_path.read_text(encoding="utf-8")
        mode = stat.S_IMODE(termux_path.stat().st_mode)

        assert str(repo / "ghot" / "organ.py") in termux
        assert "lease_authority.py" not in termux
        assert "kill -0" in termux
        assert "PID_FILE=" in termux
        assert "nohup" in termux
        assert "export GHOT_BOOT_SURFACE=termux-boot" in termux
        assert "export GHOT_BOOT_INSTANCE=ghot-organ" in termux
        assert mode == 0o700

        live_result = render_live_usb_bundle(
            output_dir=live_dir,
            python=Path("/usr/bin/python3"),
            repo_root=Path("/opt/GHoT"),
            state_home=Path("/var/lib/ghot"),
            user="ghot",
        )
        live_unit = Path(live_result["unit_path"]).read_text(encoding="utf-8")
        live_instructions = Path(
            live_result["instructions_path"]
        ).read_text(encoding="utf-8")

        assert "User=ghot" in live_unit
        assert '"/opt/GHoT/ghot/organ.py"' in live_unit
        assert '"/var/lib/ghot"' in live_unit
        assert "lease_authority.py" not in live_unit
        assert "Environment=GHOT_BOOT_SURFACE=live-usb-systemd" in live_unit
        assert "Environment=GHOT_BOOT_INSTANCE=ghot-organ.service" in live_unit
        assert live_result["modified_host"] is False
        assert "systemctl enable ghot-organ.service" in live_instructions

        # Installation removal must not delete state.
        sentinel = state_home / "identity-sentinel"
        sentinel.write_text("keep", encoding="utf-8")

        removed_systemd = uninstall_systemd_user(
            unit_dir=unit_dir,
            disable_now=False,
        )
        removed_termux = uninstall_termux(boot_dir=boot_dir)

        assert removed_systemd["removed"] is True
        assert removed_termux["removed"] is True
        assert not unit_path.exists()
        assert not termux_path.exists()
        assert sentinel.read_text(encoding="utf-8") == "keep"

        passed = (
            not unit_path.exists()
            and not termux_path.exists()
            and sentinel.exists()
            and live_result["modified_host"] is False
            and "kill -0" in termux
        )

        print(json.dumps({
            "simulation_passed": passed,
            "systemd_user": {
                "rootless_unit": "User=root" not in unit,
                "no_new_privileges": "NoNewPrivileges=true" in unit,
                "organ_only": "lease_authority.py" not in unit,
                "boot_surface_tagged": "GHOT_BOOT_SURFACE=systemd-user" in unit,
                "idempotent_install": idempotent_install,
            },
            "termux": {
                "mode": oct(mode),
                "duplicate_launch_guard": "kill -0" in termux,
                "organ_only": "lease_authority.py" not in termux,
                "boot_surface_tagged": "GHOT_BOOT_SURFACE=termux-boot" in termux,
            },
            "live_usb": {
                "render_only": live_result["modified_host"] is False,
                "target_repo": "/opt/GHoT" in live_unit,
                "target_state": "/var/lib/ghot" in live_unit,
                "boot_surface_tagged": "GHOT_BOOT_SURFACE=live-usb-systemd" in live_unit,
            },
            "uninstall_preserves_state": sentinel.exists(),
        }, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
