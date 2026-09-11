"""uxchannel CLI — parser + dispatch only.

Brand lines
-----------
| Layer | Name |
|-------|------|
| **PyPI / pip** | ``ux-channel`` |
| **Import** | ``ux_channel`` |
| **CLI** | ``uxchannel`` |

Console entry: ``uxchannel <subcommand>`` · ``python -m ux_channel``.
Both resolve to this module's ``main`` (not ``ux_channel.cli`` — that path
is forbidden as a top-level shim).

Keep this module thin: argparse + DxLog. Implementations live on the
owner named in ``cli_catalog.CLI_VERBS``. Owners load on dispatch.
"""

from __future__ import annotations

import argparse
import importlib
from typing import Any, Optional

from ux_channel.devtools.cli_catalog import CLI_VERBS, format_epilog
from ux_channel.devtools.errors import DxError, DxUsageError
from ux_channel.devtools.log import configure_log, log_exception


def _dispatch(args: Any) -> int:
    verb = args.cmd
    spec = CLI_VERBS[verb]
    mod = importlib.import_module(spec["owner"])
    fn = getattr(mod, "cmd_" + verb.replace("-", "_"))
    return int(fn(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uxchannel",
        description=(
            "uxchannel — CLI for ux-channel 0.1 "
            "(PyPI: ux-channel · import: ux_channel). "
            "Happy path: create-app, then doctor --fail."
        ),
        epilog=format_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="debug-level DX logs",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only errors (still never silent on failure)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="structured JSON logs (one object per line) for automation",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help=CLI_VERBS["info"]["help"])
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("check", help=CLI_VERBS["check"]["help"])
    p.add_argument("--env", default="production", choices=("production", "development"))
    p.add_argument("--secret", default="")
    p.add_argument("--redis-url", default="")
    p.add_argument("--allow-memory", action="store_true")
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("new", help=CLI_VERBS["new"]["help"])
    p.add_argument("--path", default="app.py")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("create-app", help=CLI_VERBS["create-app"]["help"])
    p.add_argument("name", nargs="?", default="myapp", help="app directory / name")
    p.add_argument(
        "--template",
        "-t",
        default="minimal",
        choices=("minimal", "live", "webrtc", "media", "full"),
        help="minimal | live | webrtc | media | full",
    )
    p.add_argument("--dir", default="", help="parent or exact destination path")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--force", action="store_true")
    p.add_argument("--ux-dom", action="store_true", help="add uxdom to requirements")
    p.add_argument(
        "--webrtc",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="force enable/disable webrtc files (default: from template)",
    )
    p.add_argument(
        "--list-templates",
        action="store_true",
        help="print templates and exit",
    )
    p.add_argument(
        "--bridge",
        action="append",
        default=[],
        dest="bridges",
        help="auto-generate bridge preset into project (repeatable: chartjs, leaflet, …)",
    )
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("scaffold-check", help=CLI_VERBS["scaffold-check"]["help"])
    p.add_argument("path", type=str)
    p.add_argument("--template", default=None)
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("doctor", help=CLI_VERBS["doctor"]["help"])
    p.add_argument("--secret", default="", help="secret for throwaway boot")
    p.add_argument(
        "--env",
        default="development",
        choices=("development", "production"),
        help="which factory to doctor (production exercises the deploy checklist)",
    )
    p.add_argument(
        "--allow-memory",
        action="store_true",
        help="pass allow_memory_stores=True (single-worker prod opt-in)",
    )
    p.add_argument(
        "--fail",
        action="store_true",
        help="exit 1 when the checklist is NO-GO (CI)",
    )
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("explain", help=CLI_VERBS["explain"]["help"])
    p.add_argument("code", help="error code or message, e.g. missing_scripts")
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("profile", help=CLI_VERBS["profile"]["help"])
    p.add_argument("--out", default=None, help="output directory")
    p.add_argument("--rounds", type=int, default=50)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--profile-rounds", type=int, default=25, dest="profile_rounds")
    p.add_argument(
        "--json-report",
        action="store_true",
        dest="json_report",
        help="print latency JSON report to stdout",
    )
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("dashboard", help=CLI_VERBS["dashboard"]["help"])
    p.add_argument("--out", default=None, help="output directory")
    p.add_argument("--rounds", type=int, default=40)
    p.add_argument("--warmup", type=int, default=4)
    p.add_argument("--profile-rounds", type=int, default=15, dest="profile_rounds")
    p.add_argument("--no-profile", action="store_true", help="doctor-only dashboard")
    p.add_argument("--json-report", action="store_true", dest="json_report")
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("dx", help=CLI_VERBS["dx"]["help"])
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("templates", help=CLI_VERBS["templates"]["help"])
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("recipe", help=CLI_VERBS["recipe"]["help"])
    p.add_argument("name", nargs="?", default="", help="counter|form|media-mesh|…")
    p.add_argument("--list", action="store_true", help="list recipe names")
    p.add_argument("--tree", action="store_true", help="decision tree")
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("help-topic", help=CLI_VERBS["help-topic"]["help"])
    p.add_argument("topic", nargs="?", default=None)
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("bridge", help=CLI_VERBS["bridge"]["help"])
    p.add_argument(
        "bridge_action",
        nargs="?",
        default="explain",
        help="catalog | preset | new | methods | add-method | remove-method | recipe | list",
    )
    p.add_argument("package", nargs="?", help="adapter package key")
    p.add_argument(
        "method",
        nargs="?",
        help="method name for add-method / remove-method",
    )
    p.add_argument(
        "--methods",
        default="",
        help="comma methods for 'new' (default update,destroy)",
    )
    p.add_argument("--npm", default="", help="npm package name for peerDep (e.g. chart.js)")
    p.add_argument("--import-name", default="", dest="import_name", help="ESM import path")
    p.add_argument("--global-name", default="", dest="global_name", help="UMD global")
    p.add_argument(
        "--out",
        default="bridges",
        help="search/output root (default ./bridges for new; . for contract search)",
    )
    p.add_argument(
        "--contract",
        default="",
        help="path to contract.json (add/remove/methods)",
    )
    p.add_argument(
        "--arg",
        action="append",
        default=[],
        help="method arg for add-method: name | name:type | name:type:required (repeatable)",
    )
    p.add_argument(
        "--kwargs",
        action="store_true",
        help="add-method: accept object kwargs on the wire",
    )
    p.add_argument("--desc", default="", help="add-method description")
    p.add_argument(
        "--no-sync",
        action="store_true",
        help="do not rewrite register.py methods=(...)",
    )
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("region", help=CLI_VERBS["region"]["help"])
    p.add_argument(
        "region_action",
        nargs="?",
        default="list",
        help="add | list | show | check | recipes",
    )
    p.add_argument("path", nargs="?", help="path for add/show e.g. pay/desk")
    p.add_argument("--recipe", default="default", help="default|payment|learn|banner")
    p.add_argument("--out", default="app/regions", help="regions root directory")
    p.add_argument("--uid", default=None, help="freeze uid on generated class")
    p.add_argument("--force", action="store_true")
    p.add_argument("--strict", action="store_true", help="check: exit 1 on issues")
    p.set_defaults(func=_dispatch)

    p = sub.add_parser("upgrade-check", help=CLI_VERBS["upgrade-check"]["help"])
    p.add_argument("path", nargs="?", default=".", help="project root (default .)")
    p.add_argument(
        "--fail",
        action="store_true",
        help="exit 1 when findings exist",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="alias of --fail",
    )
    p.set_defaults(func=_dispatch)

    registered: set[str] = set()
    for action in parser._subparsers._group_actions:  # noqa: SLF001
        if getattr(action, "choices", None):
            registered.update(action.choices)
    if registered != set(CLI_VERBS):
        raise RuntimeError(
            f"CLI catalog/parser drift missing={set(CLI_VERBS) - registered} extra={registered - set(CLI_VERBS)}"
        )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log = configure_log(
        verbose=bool(args.verbose),
        quiet=bool(args.quiet),
        json_logs=True if getattr(args, "json", False) else None,
    )
    log.debug("ux_channel cli start", cmd=getattr(args, "cmd", None))
    try:
        if not hasattr(args, "func"):
            raise DxUsageError(
                "missing command",
                hint="uxchannel --help",
            )
        code = int(args.func(args))
        log.debug("ux_channel cli done", exit=code)
        return code
    except DxError as exc:
        return log_exception(exc, log=log)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        return log_exception(exc, log=log)


if __name__ == "__main__":
    raise SystemExit(main())
