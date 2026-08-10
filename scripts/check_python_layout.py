#!/usr/bin/env python3
"""Backward-compatible entry → sync_python_layout.py --check."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

script = Path(__file__).resolve().parent / "sync_python_layout.py"
raise SystemExit(subprocess.call([sys.executable, str(script), "--check"]))
