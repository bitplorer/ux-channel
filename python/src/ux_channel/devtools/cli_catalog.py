"""Single inventory of public ``uxchannel`` verbs.

This is the map. Parser, tests, and ``--help`` teach from here.
Do not add a verb without an owner module. Do not rename verbs for cleanliness.

Owner is the implementation module (not a barrel, not this catalog).
"""

from __future__ import annotations

from typing import TypedDict

__all__ = [
    "CLI_VERBS",
    "GROUP_ORDER",
    "HAPPY_PATH",
    "verb_names",
    "owner_of",
    "format_epilog",
]


class VerbSpec(TypedDict):
    group: str
    owner: str
    help: str
    happy_path: bool


# Taught order: make something → is it shippable → how → look → islands.
GROUP_ORDER: tuple[str, ...] = (
    "scaffold",
    "health",
    "teach",
    "observe",
    "islands",
)

GROUP_BLURB: dict[str, str] = {
    "scaffold": "make an app (happy path: create-app)",
    "health": "is this shippable (happy path: doctor --fail)",
    "teach": "how do I (recipe / help-topic)",
    "observe": "look at dispatch cost / DX snapshot",
    "islands": "npm bridges + file-based regions",
}

CLI_VERBS: dict[str, VerbSpec] = {
    "create-app": {
        "group": "scaffold",
        "owner": "ux_channel.scaffold.create",
        "help": "plug-and-play project scaffold (recommended)",
        "happy_path": True,
    },
    "new": {
        "group": "scaffold",
        "owner": "ux_channel.scaffold.create",
        "help": "write a single-file app.py (simple scaffold)",
        "happy_path": False,
    },
    "scaffold-check": {
        "group": "scaffold",
        "owner": "ux_channel.scaffold.create",
        "help": "validate an existing scaffold tree",
        "happy_path": False,
    },
    "templates": {
        "group": "scaffold",
        "owner": "ux_channel.scaffold.create",
        "help": "list create-app templates",
        "happy_path": False,
    },
    "info": {
        "group": "health",
        "owner": "ux_channel.devtools.info",
        "help": "package info",
        "happy_path": False,
    },
    "check": {
        "group": "health",
        "owner": "ux_channel.devtools.info",
        "help": "validate ChannelConfig for env",
        "happy_path": False,
    },
    "doctor": {
        "group": "health",
        "owner": "ux_channel.devtools.doctor",
        "help": "DX health snapshot — go/no-go ≡ SECURITY_AUDIT",
        "happy_path": True,
    },
    "explain": {
        "group": "health",
        "owner": "ux_channel.devtools.explain",
        "help": "teach a failure code (what / why / the one fix)",
        "happy_path": False,
    },
    "upgrade-check": {
        "group": "health",
        "owner": "ux_channel.devtools.upgrade_check",
        "help": "scan project for outdated DX patterns (ch.button, raw ChannelConfig, …)",
        "happy_path": False,
    },
    "dx": {
        "group": "teach",
        "owner": "ux_channel.host.patterns",
        "help": "print mental model + application DX guide",
        "happy_path": False,
    },
    "recipe": {
        "group": "teach",
        "owner": "ux_channel.host.patterns",
        "help": "print a named application recipe (code)",
        "happy_path": False,
    },
    "help-topic": {
        "group": "teach",
        "owner": "ux_channel.host.patterns",
        "help": "Channel.help(topic) — progressive DX",
        "happy_path": False,
    },
    "profile": {
        "group": "observe",
        "owner": "ux_channel.devtools.profiling",
        "help": "p95 latency + flamegraph (reports/p95) — first-class DX",
        "happy_path": False,
    },
    "dashboard": {
        "group": "observe",
        "owner": "ux_channel.devtools.dashboard",
        "help": "DX dashboard: status/guidance/perf/inventory → reports/dx",
        "happy_path": False,
    },
    "bridge": {
        "group": "islands",
        "owner": "ux_channel.bridge.bridge_scaffold",
        "help": "npm bridge DX: explain | new <pkg> | recipe | list",
        "happy_path": False,
    },
    "region": {
        "group": "islands",
        "owner": "ux_channel.host.region_cli",
        "help": "file-based regions shell: add | list | show | check | recipes",
        "happy_path": False,
    },
}

HAPPY_PATH: tuple[str, ...] = tuple(
    name for name, spec in CLI_VERBS.items() if spec["happy_path"]
)


def verb_names() -> tuple[str, ...]:
    return tuple(CLI_VERBS)


def owner_of(verb: str) -> str:
    return CLI_VERBS[verb]["owner"]


def format_epilog() -> str:
    lines = ["taught groups (verbs unchanged):"]
    for group in GROUP_ORDER:
        names = [n for n, s in CLI_VERBS.items() if s["group"] == group]
        mark = " ← happy path" if any(CLI_VERBS[n]["happy_path"] for n in names) else ""
        lines.append(f"  {group}: {', '.join(names)}{mark}")
        lines.append(f"    {GROUP_BLURB[group]}")
    lines.append("owner map: uxchannel <verb> is implemented in CLI_VERBS[verb]['owner']")
    lines.append("console script + python -m ux_channel → ux_channel.devtools.cli:main")
    return "\n".join(lines)
