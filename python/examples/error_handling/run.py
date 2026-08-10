#!/usr/bin/env python3
"""Print error-handling examples.

  PYTHONPATH=src python examples/error_handling/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from patterns import run_all  # noqa: E402


def main() -> int:
    print("ux-channel · error handling examples")
    print("=" * 52)
    print("Brand lines")
    print("  PyPI / pip : ux-channel")
    print("  import     : ux_channel")
    print("  CLI        : uxchannel")
    print("-" * 52)
    for row in run_all():
        name = row["name"]
        if "map" in row:
            m = row["map"]
            print(
                f"{name:<22} ok={m['ok']!s:<5} code={m['code']!s:<16} "
                f"http={m['http_status']} kind={m.get('error_kind')}"
            )
        elif "dx" in row:
            d = row["dx"]
            print(f"{name:<22} code={d['code']} exit={d['exit_code']} hint={d['hint']!r}")
    print("-" * 52)
    print("Docs: docs/start/ERROR_HANDLING.md · docs/core/ERRORS.md")
    print("=" * 52)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
