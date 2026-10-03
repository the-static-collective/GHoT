#!/usr/bin/env python3
"""Typed, non-executing launch descriptors — Experiment 027.

A launch descriptor is portable routing context for a Static-OS shell.

It does not contain argv, a shell command, an executable URL, consent, or
permission. The destination named by the descriptor must revalidate context
before it may even propose an invocation.

Laws:
    LAUNCH != EXECUTE
    CONTEXT != CONSENT
    ROUTE != PERMISSION
    DESCRIPTOR != COMMAND
    DESTINATION REVALIDATES AUTHORITY
"""

from __future__ import annotations

import hashlib
from typing import Any

from relatte_identity import identity_safe, jcs_bytes


LAUNCH_KIND = "ghot.launch.descriptor"
LAUNCH_VERSION = "0"
LAUNCH_ID_DOMAIN = b"GHoT-LaunchDescriptor-v0|"

APP_COMPOSITION_WANTS = "composition-wants"
APP_PLUGIN_PARCEL = "merge-plugin-parcel"
APP_MERGE_PANTRY = "merge-contract-pantry"

ROUTES: dict[str, dict[str, Any]] = {
    APP_COMPOSITION_WANTS: {
        "owner_contract": "ghot.composition-wants@0",
        "entrypoint": "ghot/composition_want.py",
        "operations": {
            "show-want",
            "refresh-candidates",
            "request-candidate",
        },
    },
    APP_PLUGIN_PARCEL: {
        "owner_contract": "ghot.merge-plugin-parcel-inbox@0",
        "entrypoint": "ghot/merge_plugin_parcel.py",
        "operations": {
            "show-parcel",
            "validate-parcel",
            "install-parcel",
        },
    },
    APP_MERGE_PANTRY: {
        "owner_contract": "ghot.merge-contract-pantry@0",
        "entrypoint": "ghot/merge_contract_pantry.py",
        "operations": {
            "inspect-parcel",
        },
    },
}


def _launch_body(descriptor: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": descriptor.get("kind"),
        "version": descriptor.get("version"),
        "label": descriptor.get("label"),
        "source": descriptor.get("source"),
        "destination": descriptor.get("destination"),
        "context": descriptor.get("context"),
        "effect_if_executed": descriptor.get("effect_if_executed"),
        "requirements": descriptor.get("requirements"),
        "executes": descriptor.get("executes"),
        "permission_transfer": descriptor.get("permission_transfer"),
        "consent_granted": descriptor.get("consent_granted"),
    }


def derive_launch_id(descriptor: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        LAUNCH_ID_DOMAIN
        + jcs_bytes(identity_safe(_launch_body(descriptor)))
    ).hexdigest()
    return "ghot-launch-v0:" + digest


def make_launch_descriptor(
    *,
    label: str,
    door_id: str,
    want_id: str,
    door_state: str,
    app_id: str,
    operation: str,
    context: dict[str, Any],
    effect_if_executed: str,
) -> dict[str, Any]:
    route = ROUTES.get(app_id)
    if route is None:
        raise ValueError(f"unknown launch destination app: {app_id}")
    if operation not in route["operations"]:
        raise ValueError(
            f"unsupported operation for {app_id}: {operation}"
        )

    descriptor = identity_safe({
        "kind": LAUNCH_KIND,
        "version": LAUNCH_VERSION,
        "launch_id": "",
        "label": label,
        "source": {
            "surface_contract": "ghot.curious-doors@2",
            "door_id": door_id,
            "want_id": want_id,
            "door_state": door_state,
        },
        "destination": {
            "app_id": app_id,
            "owner_contract": route["owner_contract"],
            "operation": operation,
        },
        "context": context,
        "effect_if_executed": effect_if_executed,
        "requirements": {
            "explicit_user_selection": True,
            "destination_revalidation": True,
            "execution_revalidation": True,
            "consent_required_for_effectful_action": (
                effect_if_executed != "read-only"
            ),
        },
        "executes": False,
        "permission_transfer": False,
        "consent_granted": False,
    })
    descriptor["launch_id"] = derive_launch_id(descriptor)
    return descriptor


def verify_launch_descriptor(
    descriptor: dict[str, Any],
) -> bool:
    try:
        if (
            descriptor.get("kind") != LAUNCH_KIND
            or descriptor.get("version") != LAUNCH_VERSION
        ):
            return False
        if descriptor.get("launch_id") != derive_launch_id(descriptor):
            return False
        if descriptor.get("executes") is not False:
            return False
        if descriptor.get("permission_transfer") is not False:
            return False
        if descriptor.get("consent_granted") is not False:
            return False

        source = descriptor.get("source")
        destination = descriptor.get("destination")
        context = descriptor.get("context")
        requirements = descriptor.get("requirements")
        if not isinstance(source, dict):
            return False
        if not isinstance(destination, dict):
            return False
        if not isinstance(context, dict):
            return False
        if not isinstance(requirements, dict):
            return False

        if source.get("surface_contract") != "ghot.curious-doors@2":
            return False
        for field in ("door_id", "want_id", "door_state"):
            if not isinstance(source.get(field), str) or not source.get(field):
                return False

        app_id = destination.get("app_id")
        operation = destination.get("operation")
        owner_contract = destination.get("owner_contract")
        if not isinstance(app_id, str) or app_id not in ROUTES:
            return False
        route = ROUTES[app_id]
        if owner_contract != route["owner_contract"]:
            return False
        if operation not in route["operations"]:
            return False

        if requirements.get("explicit_user_selection") is not True:
            return False
        if requirements.get("destination_revalidation") is not True:
            return False
        if requirements.get("execution_revalidation") is not True:
            return False
        if (
            requirements.get("consent_required_for_effectful_action")
            is not (
                descriptor.get("effect_if_executed") != "read-only"
            )
        ):
            return False

        forbidden = {
            "argv",
            "href",
            "url",
            "command",
            "display_command",
            "shell",
            "executable",
            "consent_token",
            "authorization",
        }
        if any(field in descriptor for field in forbidden):
            return False
        if any(field in destination for field in forbidden):
            return False
        return True
    except Exception:
        return False
