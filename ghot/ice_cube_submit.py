#!/usr/bin/env python3
"""Submit one Ice Cube job to GHoT's power-aware background scheduler."""

from __future__ import annotations

import argparse
import json

from energy_scheduler import schedule
from ice_cube import ICE_CUBE_CAPABILITY


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Queue or run one power-aware background Ice Cube job."
    )
    parser.add_argument("--lucas-index", type=int, default=5)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument("--max-halley-iter", type=int, default=14)
    parser.add_argument("--c-re", default="0")
    parser.add_argument("--c-im", default="0")
    parser.add_argument("--tolerance", default="1e-9")
    parser.add_argument("--fiber-count", type=int, default=72)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--hold-for-seconds", type=float, default=None)
    parser.add_argument(
        "--allow-background-battery",
        action="store_true",
        help="allow immediate execution on ordinary battery power",
    )
    args = parser.parse_args()

    payload = {
        "lucas_index": args.lucas_index,
        "width": args.width,
        "height": args.height,
        "max_halley_iter": args.max_halley_iter,
        "c_re": args.c_re,
        "c_im": args.c_im,
        "tolerance": args.tolerance,
        "fiber_count": args.fiber_count,
    }
    result = schedule(
        ICE_CUBE_CAPABILITY,
        payload,
        urgency="background",
        deferrable=True,
        timeout=args.timeout,
        prefer_surplus_for_background=not args.allow_background_battery,
        hold_for_seconds=args.hold_for_seconds,
        trigger="ice-cube.submit",
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in {"ok", "held"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
