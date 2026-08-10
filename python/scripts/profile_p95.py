#!/usr/bin/env python3
"""Maintainer alias → first-class DX: ``uxchannel profile``."""
from __future__ import annotations
import sys
from ux_channel.devtools.cli import main
if __name__ == "__main__":
    out = "reports/p95"
    raise SystemExit(main(["profile", "--out", out]))
