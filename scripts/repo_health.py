#!/usr/bin/env python3
"""Repo health — required files, stale paths, broken links, forbidden layout."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "DOCS.md",
    "MENTAL_MODEL.md",
    "LONGEVITY.md",
    "NAMING.md",
    "verify.sh",
    "Makefile",
    "python/src/ux_channel/PACKAGE_MAP.json",
    "python/src/ux_channel/api/__init__.py",
    "python/src/ux_channel/host/channel.py",
    "python/src/ux_channel/host/stores.py",
    "python/src/ux_channel/protocol/capability.py",
    "python/tests/gate/test_package_layout_contract.py",
    "python/tests/gate/test_api_regions.py",
    "rust/src/lib.rs",
    "conformance/manifest.json",
    "scripts/sync_python_layout.py",
    "scripts/check_longevity.py",
]

STALE = [
    r"ux_channel\.day1\b",
    r"ux_channel\.ops_dx\b",
    r"ux_channel\.bridge_meta\b",
    r"ux_channel\.paint\b",
    r"ux_channel\.host\.dx\b",
    r"host/dx\.py",
    r"python/src/ux_channel/day1/",
    r"python/src/ux_channel/paint/",
    r"python/src/ux_channel/ops_dx/",
    r"python/src/ux_channel/zones/",
]

STALE_SOFT: list[tuple[str, str]] = []

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

SKIP_DIR_PARTS = {
    ".git",
    "__pycache__",
    "target",
    "node_modules",
    ".venv",
    "dist",
    "build",
}


def skip_path(p: Path) -> bool:
    try:
        rel = p.relative_to(ROOT).as_posix()
    except ValueError:
        return True
    if any(part in SKIP_DIR_PARTS for part in p.parts):
        return True
    if rel.startswith("CHANGELOG"):
        return False  # still scan but STALE exempt below
    return False


def check_forbidden_layout(root: Path) -> list[str]:
    issues: list[str] = []
    pkg = root / "python" / "src" / "ux_channel"
    for name in ("day1", "ops_dx", "bridge_meta", "paint", "zones", "security_plane", "agents"):
        # note: package must not be named agents/ (shadows agents() function)

        if (pkg / name).exists():
            issues.append(f"FORBIDDEN package dir: ux_channel/{name}")
    if (pkg / "host" / "dx.py").exists():
        issues.append("FORBIDDEN: host/dx.py (use host/channel.py)")
    if (pkg / "host" / "state.py").exists():
        issues.append("FORBIDDEN: host/state.py (use host/stores.py)")
    return issues


def main() -> int:
    issues: list[str] = []
    issues.extend(check_forbidden_layout(ROOT))

    for r in REQUIRED:
        if not (ROOT / r).exists():
            issues.append(f"MISSING required file: {r}")

    verify = (ROOT / "verify.sh").read_text(encoding="utf-8", errors="replace")
    if "pytest" not in verify:
        issues.append("verify.sh missing Python pytest")
    if "cargo test" not in verify:
        issues.append("verify.sh missing cargo test")
    if "uxc_check" not in verify:
        issues.append("verify.sh missing uxc_check")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8", errors="replace")
    if "verify.sh" not in ci:
        issues.append("CI workflow does not run verify.sh")

    for p in ROOT.rglob("*"):
        if not p.is_file() or skip_path(p):
            continue
        if p.suffix not in {".md", ".sh", ".py", ".rs", ".toml", ".yml", ".yaml"} and p.name not in {
            "verify.sh",
            "startup-peer.sh",
            "Makefile",
        }:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        # historical changelog may mention old names
        if p.name in {"CHANGELOG.md", "STABILITY.md", "NAMING.md", "MENTAL_MODEL.md",
    "LONGEVITY.md", "STRUCTURE.md", "PUBLIC_API_FREEZE.md"} or rel == "scripts/repo_health.py":
            pass
        else:
            for pat in STALE:
                if re.search(pat, text):
                    issues.append(f"STALE path {pat!r} in {rel}")
        for pat, hint in STALE_SOFT:
            if re.search(pat, text):
                issues.append(f"STALE command in {rel}: {hint}")

        if p.suffix == ".md":
            for m in LINK_RE.finditer(text):
                href = m.group(2).strip()
                if href.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                href_path = href.split("#", 1)[0].split("?", 1)[0]
                if not href_path:
                    continue
                target = (p.parent / href_path).resolve()
                try:
                    target.relative_to(ROOT.resolve())
                except ValueError:
                    continue
                if not target.exists():
                    issues.append(f"BROKEN LINK in {rel}: ({href_path})")

    if issues:
        print(f"repo_health: {len(issues)} issue(s)")
        for i in issues:
            print(" -", i)
        return 1
    print("repo_health: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
