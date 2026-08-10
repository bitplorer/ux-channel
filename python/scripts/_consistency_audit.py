"""Internal consistency + surface audit (agent tool; not public API)."""
from __future__ import annotations

import importlib
import inspect
import os
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

import ux_channel
from ux_channel import Channel, ChannelConfig, Result
from ux_channel.host.dx import DAY1_CHANNEL_API
from fastapi import FastAPI

issues: list[tuple[str, str, str]] = []


def note(sev: str, area: str, msg: str) -> None:
    issues.append((sev, area, msg))


def main() -> int:
    assert callable(Result.success)
    assert callable(Result.failure)
    assert not hasattr(Result, "fail")
    assert not hasattr(Channel, "aliases")

    cfg = ChannelConfig.development(
        secret="x" * 40, allow_memory_stores=True, require_cap=False
    )
    ch = Channel.boot(FastAPI(), config=cfg)

    for name in DAY1_CHANNEL_API:
        if not hasattr(ch, name):
            note("critical", "day1", f"missing {name}")

    public = sorted(
        n
        for n in dir(ch)
        if not n.startswith("_") and callable(getattr(ch, n, None))
    )
    note("info", "surface", f"callable surface={len(public)} day1={len(DAY1_CHANNEL_API)}")

    for md in sorted((ROOT / "docs").glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        if "from ux_channel.moat" in text or "ux_channel.moat import" in text:
            note("critical", "docs", f"{md.name}: teaches removed moat package")
        if "from ux_channel.money" in text or "ux_channel.money import" in text:
            note("critical", "docs", f"{md.name}: teaches removed money module")
        if "from ux_channel.authority" in text or "ux_channel.authority import" in text:
            note("critical", "docs", f"{md.name}: teaches removed authority module")

    assert hasattr(ch.bridge, "mount_spec") and callable(ch.bridge.mount_spec)
    assert not hasattr(ch.bridge, "host_spec")
    assert "toast" not in str(inspect.signature(ch.done))

    from ux_channel import agents
    from ux_channel.foundations.quantity import Quantity
    from ux_channel.foundations.io_channel import IO_CONSTITUTION, IO_LAWS, attach_io_gate
    from ux_channel.workplace import workplace, get_workplace, issue_mesh_membership, workplace_from_membership

    assert callable(agents)
    assert callable(Quantity.from_store)
    q = Quantity.from_store(1, "USD", source="db.x", revision=1)
    assert q.provenance.revision == 1
    assert "adapter" in IO_CONSTITUTION.lower()
    assert "mesh_is_not_trust" in IO_LAWS
    attach_io_gate(ch)

    # Workplace product façade
    assert (ROOT / "docs" / "workplace" / "WORKPLACE.md").exists()
    assert (ROOT / "docs" / "workplace" / "IO_CHANNEL.md").exists()
    assert (ROOT / "docs" / "foundations" / "FOUNDATIONS.md").exists()
    assert not (ROOT / "src/ux_channel" / "widgets").exists()

    @ch.on
    def demo_act(x: str = ""):
        return Result.success()

    wp = workplace(
        ch,
        ticket={"room": "audit-room", "peer_id": "p", "scopes": ["demo", "act"]},
    )
    assert get_workplace(ch) is wp
    assert wp.allows_action("demo_act")
    assert wp.dispatch("demo_act", {"x": "1"}).ok
    from ux_channel.workplace import sign_workplace_ticket
    tok = sign_workplace_ticket(ch.config, "audit-room", sub="p", scopes=["demo", "act"])
    wp2 = workplace(ch, ticket_token=tok, attach=False)
    assert wp2.claim.room == "audit-room"
    assert wp.snapshot()["room"] == "audit-room"
    mem = issue_mesh_membership(ch, "mesh-r", sub="m1", scopes=["demo", "act"])
    assert mem.rtc_ticket and mem.workplace_ticket
    wp_m = workplace_from_membership(ch, mem, attach=False)
    assert wp_m.claim.room == "mesh-r"

    for gone in ("moat", "money", "authority", "widgets"):
        if (ROOT / "src/ux_channel" / f"{gone}.py").exists():
            note("critical", "export", f"ux_channel/{gone}.py still present")
        try:
            importlib.import_module(f"ux_channel.{gone}")
            note("critical", "export", f"ux_channel.{gone} still importable")
        except ModuleNotFoundError:
            pass

    morph_ir = importlib.import_module("ux_channel.morph_ir")
    assert callable(morph_ir.region)
    assert not hasattr(morph_ir, "slot")

    for name in ux_channel.__all__:
        if not hasattr(ux_channel, name):
            note("critical", "export", f"missing {name}")

    for m in pkgutil.walk_packages(ux_channel.__path__, ux_channel.__name__ + "."):
        if m.name.endswith(".__main__"):
            continue
        try:
            importlib.import_module(m.name)
        except Exception as e:
            note("medium", "import", f"{m.name}: {e}")

    crit = sum(1 for s, _, _ in issues if s == "critical")
    for sev, area, msg in issues:
        print(f"{sev}: [{area}] {msg}")
    print(f"summary: critical={crit} total={len(issues)}")
    return 1 if crit else 0


if __name__ == "__main__":
    raise SystemExit(main())
