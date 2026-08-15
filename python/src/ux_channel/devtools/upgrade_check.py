"""
Scan a project tree for outdated / high-cognitive-load patterns.

CI::

    uxchannel upgrade-check .
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

__all__ = ["Finding", "scan_path", "format_report"]


@dataclass
class Finding:
    path: str
    line: int
    rule: str
    message: str
    prefer: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def ok(self) -> bool:
        return not self.findings


# rule_id → (regex, message, prefer)
_RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    (
        "demo-button",
        re.compile(r"""\bch\.button\s*\("""),
        "ch.button was removed from Channel",
        "ux-dom + ch.control(...).as_dict()  or  ux_channel.render.kit.demo_button",
    ),
    (
        "demo-scripts",
        re.compile(r"""\bch\.scripts\s*\("""),
        "ch.scripts was removed from Channel",
        "ch.runtime().scripts + ux_channel.render.kit.script_tags",
    ),
    (
        "demo-page",
        re.compile(r"""\bch\.page\s*\("""),
        "ch.page was removed from Channel",
        "ux_channel.render.kit.demo_page / ux-dom + ch.runtime()",
    ),
    (
        "webrtc-plugin",
        re.compile(r"""\bch\.webrtc\.plugin\s*\("""),
        "prefer unified media façade",
        "ch.media.plugin(..., mode='mesh')",
    ),
    (
        "raw-channelconfig",
        re.compile(r"""ChannelConfig\s*\("""),
        "prefer factory constructors",
        "ChannelConfig.development(...) or ChannelConfig.production(...)",
    ),
    (
        "require-cap-false",
        re.compile(r"""require_cap\s*=\s*False"""),
        "require_cap=False weakens integrity",
        "keep require_cap=True; use ch.control for caps",
    ),
    (
        "sfu-token-http",
        re.compile(r"""/ux-channel/sfu/token|sfu/token"""),
        "open HTTP mint is easy to misuse",
        "ch.media.plugin(mode='sfu') after your auth",
    ),
    (
        "prod-memory-stores",
        re.compile(r"""ChannelConfig\.production\([^)]*allow_memory_stores\s*=\s*True"""),
        "production factory + memory stores is a multi-worker no-go",
        "REDIS_URL / .with_redis() or keep allow_memory_stores only for single-worker",
    ),
]


def _iter_py(root: Path) -> Iterable[Path]:
    skip = {".venv", "venv", "node_modules", ".git", "__pycache__", "dist", "build"}
    if root.is_file() and root.suffix == ".py":
        yield root
        return
    for p in root.rglob("*.py"):
        if any(part in skip for part in p.parts):
            continue
        yield p


def scan_path(root: Path | str, *, strict: bool = False) -> Report:
    """
    Scan *root* for upgrade findings.

    ``strict=True`` treats demo-button/page as findings (default).
    ``ChannelConfig(`` findings skip lines that already use .development/.production
    """
    root = Path(root)
    report = Report()
    for path in _iter_py(root):
        report.files_scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for rule_id, rx, msg, prefer in _RULES:
                if not rx.search(line):
                    continue
                if rule_id == "raw-channelconfig":
                    if ".development" in line or ".production" in line:
                        continue
                    if "ChannelConfig.development" in text and "ChannelConfig(" not in line:
                        continue
                    # allow type annotations ChannelConfig)
                    if re.search(r"ChannelConfig\s*\|", line) or "Optional[ChannelConfig" in line:
                        continue
                report.findings.append(
                    Finding(
                        path=str(path),
                        line=i,
                        rule=rule_id,
                        message=msg,
                        prefer=prefer,
                    )
                )
    return report


def format_report(report: Report) -> str:
    lines = [
        f"uxchannel upgrade-check — {report.files_scanned} files, "
        f"{len(report.findings)} finding(s)",
    ]
    for f in report.findings:
        lines.append(f"{f.path}:{f.line}: [{f.rule}] {f.message}")
        lines.append(f"  → prefer: {f.prefer}")
    if not report.findings:
        lines.append("OK — no outdated patterns found")
    return "\n".join(lines)
