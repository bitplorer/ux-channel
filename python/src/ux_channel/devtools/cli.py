"""uxchannel CLI super-command for **ux-channel**.

Brand lines
-----------
| Layer | Name |
|-------|------|
| **PyPI / pip** | ``ux-channel`` |
| **Import** | ``ux_channel`` |
| **CLI** | ``uxchannel`` |

Console entry: ``uxchannel <subcommand>`` · ``python -m ux_channel``.

Keep this module thin: parsing + DxLog output.
Scaffold logic: ``ux_channel.scaffold`` / ``bridge_scaffold``.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path
from typing import Optional

from ux_channel.devtools.errors import DxError, DxUsageError
from ux_channel.render.kit import (
    attr_string,
    demo_button,
    demo_page,
    demo_scripts,
    script_tags,
)
from ux_channel.devtools.log import configure_log, get_log, log_exception


def cmd_info(_: argparse.Namespace) -> int:
    from ux_channel import __version__
    from ux_channel.devtools.info import package_info

    log = get_log()
    log.section("info")
    info = package_info()
    print(f"ux-channel {__version__}")
    print("  PyPI / pip : ux-channel")
    print("  import     : ux_channel")
    print("  CLI        : uxchannel")
    for k, v in info.items():
        print(f"  {k}: {v}")
    log.ok("info complete", version=__version__)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from ux_channel._version import __version__
    from ux_channel.host.config import ChannelConfig

    errors: list[str] = []
    env = (args.env or "production").lower()
    secret = args.secret or ""
    try:
        if env == "development":
            cfg = ChannelConfig.development(secret=secret or None)  # type: ignore[arg-type]
        else:
            if not secret:
                errors.append("production check requires --secret")
                cfg = None
            else:
                kwargs = {"allow_memory_stores": True} if args.allow_memory else {}
                cfg = ChannelConfig.production(secret, **kwargs)
    except ValueError as e:
        errors.append(str(e))
        cfg = None
    if cfg is not None and cfg.environment == "production" and not cfg.allow_memory_stores:
        import os

        if not (args.redis_url or os.environ.get("REDIS_URL")):
            errors.append("pass --allow-memory or set REDIS_URL")
    log = get_log()
    log.section("check")
    log.info(f"uxchannel check (library {__version__})")
    for err in errors:
        log.error(err)
    if errors:
        log.error("check FAIL")
        return 1
    log.ok("check OK")
    return 0


# Minimal single-file scaffold (gists/demos)
_SCAFFOLD = "\n".join(
    [
        '"""Minimal uxchannel app (single file). Prefer: uxchannel create-app."""',
        "",
        "from fastapi import FastAPI",
        "from fastapi.responses import HTMLResponse",
        "",
        "from ux_channel import Channel, ChannelConfig",
        "",
        'app = FastAPI(title="uxchannel app")',
        'ch = Channel.boot(app, config=ChannelConfig.development(secret="{secret}", allow_memory_stores=True))',
        "",
        "",
        "@ch.region",
        "def counter(ctx):",
        '    n = ch.draft.get("n", 0)',
        '    return f"<strong>{n}</strong>"',
        "",
        "",
        "@ch.on(refresh=[counter])",
        "def inc():",
        '    ch.draft.set("n", ch.draft.get("n", 0) + 1)',
        "",
        "",
        '@app.get("/", response_class=HTMLResponse)',
        "def index():",
        "    return demo_page(ch, counter, demo_button(ch, '+', inc), title='ux-channel')",
        "",
        "",
        'if __name__ == "__main__":',
        "    import uvicorn",
        '    uvicorn.run(app, host="0.0.0.0", port=8080)',
    ]
) + "\n"


def cmd_new(args: argparse.Namespace) -> int:
    dest = Path(args.path or "app.py")
    log = get_log()
    if dest.exists() and not args.force:
        raise DxUsageError(
            f"refusing to overwrite {dest}",
            code="cli.file_exists",
            hint="pass --force or choose another --path",
        )
    secret = secrets.token_urlsafe(32)
    dest.write_text(_SCAFFOLD.replace("{secret}", secret), encoding="utf-8")
    log.ok("wrote scaffold", path=str(dest))
    log.info("tip: prefer uxchannel create-app myapp for full projects")
    return 0


def cmd_create_app(args: argparse.Namespace) -> int:
    from ux_channel.scaffold import (
        ScaffoldOptions,
        available_templates,
        create_app,
        validate_scaffold,
    )

    if args.list_templates:
        for t in available_templates():
            print(t)
        return 0

    try:
        opts = ScaffoldOptions(
            app_name=args.name,
            dest=Path(args.dir) if args.dir else None,
            template=args.template,
            with_webrtc=args.webrtc if args.webrtc is not None else None,
            with_ux_dom=bool(args.ux_dom),
            force=bool(args.force),
            port=int(args.port),
            bridges=list(getattr(args, "bridges", None) or []),
        )
        root = create_app(opts)
    except (ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    report = validate_scaffold(root, template=opts.template)
    print(f"created {root}")
    print(f"  template={opts.template} webrtc={opts.with_webrtc}")
    if opts.bridges:
        print(f"  bridges={opts.bridges}")
    if report.get("warnings"):
        for w in report["warnings"]:
            print(f"  warn: {w}")
    if report.get("errors"):
        for e in report["errors"]:
            print(f"  error: {e}")
        return 1
    print("next:")
    print(f"  cd {root}")
    print("  pip install -r requirements.txt")
    print(f"  uvicorn app.main:app --host 0.0.0.0 --port {opts.port} --reload")
    return 0


def cmd_scaffold_check(args: argparse.Namespace) -> int:
    from ux_channel.scaffold import validate_scaffold

    report = validate_scaffold(Path(args.path), template=args.template)
    for e in report.get("errors") or []:
        print(f"ERROR {e}")
    for w in report.get("warnings") or []:
        print(f"WARN  {w}")
    print("OK" if report.get("ok") else "FAIL")
    return 0 if report.get("ok") else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    """Print Channel.doctor() — go/no-go matches SECURITY_AUDIT deploy list."""
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig
    from ux_channel.devtools.doctor import production_go_nogo

    secret = args.secret or "doctor-dev-secret-key-32chars-min!!"
    env = (getattr(args, "env", None) or "development").lower()
    if env == "production":
        kwargs = {}
        if getattr(args, "allow_memory", False):
            kwargs["allow_memory_stores"] = True
        try:
            cfg = ChannelConfig.production(secret, **kwargs)
        except ValueError as exc:
            import json

            report = {
                "ok": False,
                "go": False,
                "no_go": [str(exc)],
                "hints": [str(exc), "uxchannel explain short_secret"],
            }
            print(json.dumps(report, indent=2, default=str))
            return 1 if getattr(args, "fail", False) else 0
    else:
        cfg = ChannelConfig.development(
            secret=secret,
            allow_memory_stores=True,
            webrtc_enabled=True,
        )
    ch = Channel.boot(FastAPI(), config=cfg)
    import json

    report = ch.doctor()
    # Always include the standalone checklist (works even if façade patch missed).
    gn = production_go_nogo(cfg)
    report.setdefault("go", gn["go"])
    report.setdefault("no_go", gn["no_go"])
    print(json.dumps(report, indent=2, default=str))
    if getattr(args, "fail", False) and not report.get("ok", True):
        print("doctor: NO-GO", file=sys.stderr)
        return 1
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Never silent — print the teachable fix for a first-week failure."""
    from ux_channel.devtools.explain import explain_code

    report = explain_code(str(args.code))
    import json

    print(json.dumps(report, indent=2, default=str))
    return 0


def cmd_dx(_: argparse.Namespace) -> int:
    """Print mental model + decision tree (ux-dom-style teaching surface)."""
    from ux_channel import Channel
    from ux_channel.host.patterns import RECIPE_NAMES

    print(Channel.describe())
    print()
    print(Channel.help())
    print()
    print("Application names:", ", ".join(Channel.public_api_names()))
    print("Recipes:", ", ".join(RECIPE_NAMES))
    print()
    print("Scaffold:")
    print("  uxchannel create-app myapp")
    print("  uxchannel create-app call --template media")
    print("  uxchannel recipe counter")
    print("  uxchannel help-topic aliases")
    print("  uxchannel doctor")
    print("  uxchannel profile   # p95 + flamegraph → reports/p95")
    print("  uxchannel dashboard # status · guidance · perf · inventory → reports/dx")
    return 0


def cmd_templates(_: argparse.Namespace) -> int:
    from ux_channel.scaffold import available_templates

    for name in available_templates():
        print(name)
    return 0


def cmd_recipe(args: argparse.Namespace) -> int:
    from ux_channel.host.patterns import RECIPE_NAMES, decision_tree, recipe_text

    if args.list or not args.name:
        if args.tree:
            print(decision_tree())
            return 0
        for n in RECIPE_NAMES:
            print(n)
        return 0
    try:
        print(recipe_text(args.name))
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_help_topic(args: argparse.Namespace) -> int:
    from ux_channel import Channel

    print(Channel.help(args.topic))
    return 0




def cmd_region(args: argparse.Namespace) -> int:
    from ux_channel.host.region_cli import cmd_region as _cmd

    return _cmd(args, get_log=get_log)


def cmd_bridge(args: argparse.Namespace) -> int:
    """DX: scaffold / explain / edit contract methods for npm bridges."""
    log = get_log()
    from ux_channel.bridge.bridge_scaffold import (
        add_contract_method,
        create_bridge_package,
        explain_bridge,
        list_contract_methods,
        remove_contract_method,
        slugify,
    )

    action = (args.bridge_action or "explain").lower().replace("_", "-")
    log.debug("bridge command", action=action, package=getattr(args, "package", None))

    if action in ("explain", "help", ""):
        log.section("bridge explain")
        # body is user-facing content → stdout via print is ok; also log
        log.info("printing bridge overview to stdout")
        print(explain_bridge())
        log.ok("explain complete")
        return 0

    if action == "recipe":
        log.section("bridge recipe")
        from ux_channel.host.patterns import recipe_text

        try:
            body = recipe_text("bridge-npm")
        except Exception as exc:
            log.warn("recipe bridge-npm missing; using inline fallback", error=str(exc))
            body = (
                "# bridge-npm recipe\n"
                'ch.bridge.register("chartjs", methods=("update", "resetZoom"))\n'
            )
        print(body)
        log.ok("recipe printed", name="bridge-npm")
        return 0

    if action in ("catalog", "list-presets"):
        log.section("bridge catalog")
        from ux_channel.bridge.bridge_preset_gen import list_known_presets

        print("Pick a name, then:")
        print("  uxchannel bridge preset <name> --out bridges")
        print("  uxchannel create-app myapp --bridge <name>")
        print()
        for r in list_known_presets():
            builtin = f"  [builtin {r['builtin']}]" if r.get("builtin") else ""
            print(f"  {r['key']:12}  {r['package']:16}  {','.join(r['methods'])}{builtin}")
        log.ok("catalog done")
        log.info("any npm package also works: uxchannel bridge preset my-lib --methods a,b")
        return 0

    if action == "new":
        log.info("bridge new is an alias of bridge preset")
        action = "preset"

    if action in ("preset", "generate", "gen"):
        name = args.package
        if not name:
            raise DxUsageError(
                "bridge preset requires <name|npm>",
                code="bridge.usage_preset",
                hint="uxchannel bridge catalog",
            )
        methods = []
        if args.methods:
            methods = [m.strip() for m in args.methods.split(",") if m.strip()]
        dest = Path(args.out or "bridges")
        log.section("bridge preset")
        from ux_channel.bridge.bridge_preset_gen import create_bridge_preset

        root = create_bridge_preset(
            dest,
            name,
            methods=methods or None,
            npm=args.npm or "",
            npm_import=args.import_name or "",
            global_name=args.global_name or "",
            force=bool(args.force),
        )
        log.ok("preset ready", path=str(root))
        return 0

    if action in ("methods", "list-methods"):
        name = args.package
        if not name:
            raise DxUsageError(
                "bridge methods requires <package>",
                code="bridge.usage_methods",
                hint="uxchannel bridge methods chartjs --out bridges",
            )
        log.section("bridge methods")
        search = args.out or "."
        log.info("loading contract", package=name, search=search)
        info = list_contract_methods(
            name,
            contract_path=args.contract or None,
            start=search,
        )
        log.ok("contract loaded", path=info["path"])
        print(f"package: {info['package']}")
        print(f"contract: {info['path']}")
        if info.get("schema_version") is not None:
            print(f"schema_version: {info['schema_version']}")
        if info.get("npm"):
            print(f"npm: {info['npm']}")
        if not info["names"]:
            log.warn("no methods declared in contract")
            print("methods: (none)")
            return 0
        for m in info["methods"]:
            args_s = ",".join(
                a.get("name", "?") + (":req" if a.get("required") else "")
                for a in (m.get("args") or [])
                if isinstance(a, dict)
            )
            kw = " kwargs" if m.get("kwargs") else ""
            print(f"  - {m['name']}({args_s}){kw}")
        log.ok("listed methods", count=len(info["names"]))
        return 0

    if action in ("add-method", "add"):
        name = args.package
        method = getattr(args, "method", None)
        if not name or not method:
            raise DxUsageError(
                "bridge add-method requires <package> <method>",
                code="bridge.usage_add_method",
                hint=(
                    "uxchannel bridge add-method chartjs setData "
                    "--arg data:object:required --kwargs --out bridges"
                ),
            )
        log.section("bridge add-method")
        log.info(
            "adding method",
            package=name,
            method=method,
            force=bool(args.force),
            args=list(args.arg or []),
        )
        result = add_contract_method(
            name,
            method,
            contract_path=args.contract or None,
            start=args.out or ".",
            args=list(args.arg or []),
            kwargs=bool(args.kwargs),
            description=args.desc or "",
            sync_register=not bool(args.no_sync),
            force=bool(args.force),
        )
        # scaffold already logs ok; reinforce summary
        log.info(
            "result",
            action=result["action"],
            idempotent=result.get("idempotent"),
            methods=",".join(result["methods"]),
        )
        return 0

    if action in ("remove-method", "rm-method", "remove"):
        name = args.package
        method = getattr(args, "method", None)
        if not name or not method:
            raise DxUsageError(
                "bridge remove-method requires <package> <method>",
                code="bridge.usage_remove_method",
                hint="uxchannel bridge remove-method chartjs destroy --out bridges",
            )
        log.section("bridge remove-method")
        log.info("removing method", package=name, method=method)
        result = remove_contract_method(
            name,
            method,
            contract_path=args.contract or None,
            start=args.out or ".",
            sync_register=not bool(args.no_sync),
            missing_ok=not bool(getattr(args, "strict", False)),
        )
        log.info(
            "result",
            action=result["action"],
            idempotent=result.get("idempotent"),
            methods=",".join(result["methods"]) or "(none)",
        )
        return 0

    if action == "list":
        log.section("bridge list")
        log.info("Built-in plane: ch.bridge (widget islands)")
        log.info("Scaffolded packages: ./bridges or packages/@ux-channel/")
        log.info("Contract edits: methods | add-method | remove-method")
        log.ok("list complete")
        return 0

    raise DxUsageError(
        f"unknown bridge action: {action}",
        code="bridge.usage_action",
        hint="explain | new | methods | add-method | remove-method | recipe | list",
    )


def cmd_upgrade_check(args: argparse.Namespace) -> int:
    from ux_channel.devtools.upgrade_check import format_report, scan_path

    log = get_log()
    path = args.path or "."
    log.section("upgrade-check")
    log.info("scanning", path=path)
    report = scan_path(path)
    print(format_report(report))
    n = len(report.findings)
    if n:
        log.warn("findings", count=n)
    else:
        log.ok("no outdated patterns")
    if (args.strict or args.fail) and report.findings:
        log.error("upgrade-check failed (findings with --fail/--strict)")
        return 1
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """First-class DX: p95 latency + flamegraph for dispatch / batch."""
    from pathlib import Path

    from ux_channel.transport.batch import dispatch_batch
    from ux_channel.transport.concurrency import dispatch_parallel
    from ux_channel.devtools.log import get_log
    from ux_channel.devtools.profiling import run_suite
    from ux_channel.host.registry import ActionRegistry
    from ux_channel.protocol.types import Intent, Result

    log = get_log()
    out = Path(args.out) if getattr(args, "out", None) else Path.cwd() / "reports" / "p95"
    rounds = int(getattr(args, "rounds", 50) or 50)
    warmup = int(getattr(args, "warmup", 5) or 5)
    profile_rounds = int(getattr(args, "profile_rounds", 25) or 25)

    reg = ActionRegistry(
        secret="test-secret-key-32chars-minimum!!!!",
        require_cap=False,
    )

    @reg.action("echo")
    def echo(ctx, n: int = 0):
        return Result.success(n=n)

    intents = [
        Intent(action="echo", args={"n": i}, request_id=f"r{i}") for i in range(32)
    ]
    items = [
        {"action": "echo", "args": {"n": i}, "request_id": f"b{i}"} for i in range(16)
    ]

    def one_dispatch():
        reg.dispatch(Intent(action="echo", args={"n": 1}, request_id="solo"))

    def parallel_dispatch():
        dispatch_parallel(reg, intents)

    def batch_dispatch():
        dispatch_batch(reg, items)

    report = run_suite(
        [
            ("dispatch_one", one_dispatch),
            ("dispatch_parallel_32", parallel_dispatch),
            ("dispatch_batch_16", batch_dispatch),
        ],
        out_dir=out,
        title="ux-channel p95 suite",
        rounds=rounds,
        warmup=warmup,
        profile_rounds=profile_rounds,
    )
    log.ok(
        "profile complete",
        out=str(out.resolve()),
        html=str((out / "report.html").resolve()),
        speedscope=str((out / "profile.speedscope.json").resolve()),
    )
    if getattr(args, "json_report", False) or getattr(args, "json", False):
        import json as _json

        print(_json.dumps(report, indent=2))
    else:
        print("uxchannel profile")
        print("=" * 40)
        print("Brand lines")
        print("  PyPI / pip : ux-channel")
        print("  import     : ux_channel")
        print("  CLI        : uxchannel")
        print("-" * 40)
        print("p95 latency (ms)")
        for lat in report.get("latencies") or []:
            print(
                f"  {lat['name']:<28} p50={lat['p50_ms']:<8} "
                f"p95={lat['p95_ms']:<8} p99={lat['p99_ms']}"
            )
        print("-" * 40)
        print(f"out: {out.resolve()}")
        print(f"  html:       {(out / 'report.html').resolve()}")
        print(f"  speedscope: {(out / 'profile.speedscope.json').resolve()}")
        print("Open profile.speedscope.json at https://www.speedscope.app")
        print("=" * 40)
        print("OK — profiling complete (app source untouched)")
    return 0



def cmd_dashboard(args: argparse.Namespace) -> int:
    """Observe-only DX dashboard (status · guidance · performance · inventory)."""
    from pathlib import Path

    from ux_channel.devtools.dashboard import run_dashboard_suite
    from ux_channel.devtools.log import get_log

    log = get_log()
    out = Path(args.out) if getattr(args, "out", None) else Path.cwd() / "reports" / "dx"
    model = run_dashboard_suite(
        out_dir=out,
        include_profile=not getattr(args, "no_profile", False),
        rounds=int(getattr(args, "rounds", 40) or 40),
        warmup=int(getattr(args, "warmup", 4) or 4),
        profile_rounds=int(getattr(args, "profile_rounds", 15) or 15),
    )
    arts = model.get("artifacts") or {}
    log.ok("dashboard ready", html=arts.get("html"), out=str(out.resolve()))
    if getattr(args, "json_report", False):
        from ux_channel.protocol import serde as _serde

        print(_serde.dumps(model, pretty=True))
    else:
        print("uxchannel dashboard")
        print("=" * 40)
        print("Brand lines")
        print("  PyPI / pip : ux-channel")
        print("  import     : ux_channel")
        print("  CLI        : uxchannel")
        print("-" * 40)
        sec = model.get("sections") or {}
        st = sec.get("status") or {}
        print(f"  status     : {st.get('summary', '—')}")
        perf = sec.get("performance") or {}
        if perf.get("available"):
            for lat in perf.get("latencies") or []:
                print(f"  perf       : {lat.get('name', ''):<24} p95={lat.get('p95_ms')}")
        else:
            print(f"  perf       : (not sampled)")
        inv = sec.get("inventory") or {}
        print(f"  inventory  : actions={inv.get('actions')} regions={inv.get('regions')}")
        print("-" * 40)
        print(f"open: {arts.get('html')}")
        print("sections → panels → optional shell (model schema 1)")
        print("live actions: ux-inspector.js (separate from this snapshot)")
        print("=" * 40)
    return 0



def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="uxchannel",
        description=(
            "uxchannel — CLI for ux-channel 0.1 "
            "(PyPI: ux-channel · import: ux_channel). "
            "Scaffold, check, bridge, doctor, profile, dashboard (DxLog: never silent)."
        ),
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

    p = sub.add_parser("info", help="package info")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("check", help="validate ChannelConfig for env")
    p.add_argument("--env", default="production", choices=("production", "development"))
    p.add_argument("--secret", default="")
    p.add_argument("--redis-url", default="")
    p.add_argument("--allow-memory", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("new", help="write a single-file app.py (simple scaffold)")
    p.add_argument("--path", default="app.py")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser(
        "create-app",
        help="plug-and-play project scaffold (recommended)",
    )
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
    p.set_defaults(func=cmd_create_app)

    p = sub.add_parser("scaffold-check", help="validate an existing scaffold tree")
    p.add_argument("path", type=str)
    p.add_argument("--template", default=None)
    p.set_defaults(func=cmd_scaffold_check)

    p = sub.add_parser("doctor", help="DX health snapshot — go/no-go ≡ SECURITY_AUDIT")
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
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("explain", help="teach a failure code (what / why / the one fix)")
    p.add_argument("code", help="error code or message, e.g. missing_scripts")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser(
        "profile",
        help="p95 latency + flamegraph (reports/p95) — first-class DX",
    )
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
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser(
        "dashboard",
        help="DX dashboard: status/guidance/perf/inventory → reports/dx",
    )
    p.add_argument("--out", default=None, help="output directory")
    p.add_argument("--rounds", type=int, default=40)
    p.add_argument("--warmup", type=int, default=4)
    p.add_argument("--profile-rounds", type=int, default=15, dest="profile_rounds")
    p.add_argument("--no-profile", action="store_true", help="doctor-only dashboard")
    p.add_argument("--json-report", action="store_true", dest="json_report")
    p.set_defaults(func=cmd_dashboard)

    p = sub.add_parser("dx", help="print mental model + application DX guide")
    p.set_defaults(func=cmd_dx)

    p = sub.add_parser("templates", help="list create-app templates")
    p.set_defaults(func=cmd_templates)

    p = sub.add_parser("recipe", help="print a named application recipe (code)")
    p.add_argument("name", nargs="?", default="", help="counter|form|media-mesh|…")
    p.add_argument("--list", action="store_true", help="list recipe names")
    p.add_argument("--tree", action="store_true", help="decision tree")
    p.set_defaults(func=cmd_recipe)

    p = sub.add_parser("help-topic", help="Channel.help(topic) — progressive DX")
    p.add_argument("topic", nargs="?", default=None)
    p.set_defaults(func=cmd_help_topic)

    p = sub.add_parser(
        "bridge",
        help="npm bridge DX: explain | new <pkg> | recipe | list",
    )
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
    p.set_defaults(func=cmd_bridge)

    p = sub.add_parser(
        "region",
        help="file-based regions shell: add | list | show | check | recipes",
    )
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
    p.set_defaults(func=cmd_region)

    p = sub.add_parser(
        "upgrade-check",
        help="scan project for outdated DX patterns (ch.button, raw ChannelConfig, …)",
    )
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
    p.set_defaults(func=cmd_upgrade_check)

    args = parser.parse_args(argv)
    log = configure_log(
        verbose=bool(args.verbose),
        quiet=bool(args.quiet),
        json_logs=True if getattr(args, 'json', False) else None,
    )
    log.debug("ux_channel cli start", cmd=getattr(args, "cmd", None))
    try:
        if not hasattr(args, "func"):
            raise DxUsageError(
                "missing command",
                hint="ux_channel --help",
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
