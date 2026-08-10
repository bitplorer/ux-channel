#!/usr/bin/env python3
"""Repo health: stale paths, broken relative markdown links, required files.

Exit 0 = healthy. Designed for CI and ./verify.sh so humans do not re-audit by hand.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "target", "node_modules", "__pycache__"}
SKIP_PREFIXES = (
    "python/src/ux_channel/",
    "python/src/ux_channel_ux_dom/",
    "python/docs/",
)

STALE = [
    r"peers/ux_channel_rs",
    r"peers/python_forward",
    r"cd peers/",
]

# ../../conformance is wrong when cwd is rust/ (should be ../conformance)
STALE_SOFT = [
    (r"uxc_check -- ../../conformance", "use ../conformance from rust/"),
]

REQUIRED = [
    "ARCHITECTURE.md",
    "TERMINOLOGY.md",
    "HOW_IT_WORKS.md",
    "REFERENCE.md",
    "FAQ.md",
    "OPERATIONAL.md",
    "STRUCTURE.md",
    "CHANGELOG.md",
    "README.md",
    "DOCS.md",
    "NAMING.md",
    "AGENTS.md",
    "verify.sh",
    "startup-peer.sh",
    "python/README.md",
    "rust/README.md",
    "rust/Cargo.toml",
    "demos/README.md",
    "SPEC/INVARIANTS.md",
    "conformance/manifest.json",
    ".github/workflows/ci.yml",
    "LICENSE",
    "requirements-dev.txt",
    "python/tests/gate/test_interop_conformance.py",
    "python/ONTOLOGY.md",
    "python/tests/gate/test_public_api_freeze.py",
    "python/tests/gate/test_day1_regions.py",
    "python/src/ux_channel/day1/__init__.py",
    "python/STRUCTURE.md",
    "python/LAYOUT.md",
    "scripts/sync_python_layout.py",
    "python/STABILITY.md",
    "python/src/ux_channel/PACKAGE_MAP.json",
    "Makefile",
    "pytest.ini",
]

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def skip_path(p: Path) -> bool:
    try:
        rel = p.relative_to(ROOT).as_posix()
    except ValueError:
        return True
    if any(part in SKIP_PARTS for part in p.parts):
        return True
    if any(rel.startswith(pref) for pref in SKIP_PREFIXES):
        return True
    if rel.endswith(".zip"):
        return True
    # this script contains the patterns it searches for
    if rel in {"scripts/repo_health.py"}:
        return True
    return False


def main() -> int:
    issues: list[str] = []

    for r in REQUIRED:
        if not (ROOT / r).exists():
            issues.append(f"MISSING required file: {r}")

    # verify.sh must exercise BOTH languages (regression: Rust-only green)
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
        }:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        # historical docs may mention old peers/ nesting
        if p.name in {"ARCHITECTURE.md", "CHANGELOG.md"}:
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
