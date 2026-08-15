"""Project generator for ux-channel.

Application Developer tooling should match React/Vue ``create-*`` tools: one command, runnable app,
opinionated defaults, readable generated sources.

MAINTENANCE RULES (read before editing templates)
* Prefer **string templates with clear sections** over deep metaprogramming.
* Every generated file starts with a short module docstring (intent + run…"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ScaffoldOptions",
    "available_templates",
    "create_app",
    "validate_scaffold",
]

# Template catalogue — single source of truth for CLI help + validation

_TEMPLATES = (
    "minimal",  # counter + region morph
    "live",  # multi-region live board
    "webrtc",  # mesh plugin (ux-webrtc.js)
    "media",  # ch.media.plugin — mesh | LiveKit SFU auto
    "full",  # live + media + health + structured package
)


def available_templates() -> list[str]:
    """Return template names (stable order for CLI)."""
    return list(_TEMPLATES)


def _slug(name: str) -> str:
    """Filesystem-safe Python package-ish name."""
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip())
    s = s.strip("_").lower() or "app"
    if s[0].isdigit():
        s = "app_" + s
    return s


@dataclass
class ScaffoldOptions:
    """
    Options for :func:`create_app`.

    Defaults are intentional plug-and-play choices:
    * ``template="minimal"`` — smallest working channel app
    * ``with_webrtc`` follows template (webrtc/full → True)
    * ``port=8080`` — matches common preview contracts
    """

    app_name: str
    dest: Path | None = None
    template: str = "minimal"
    with_webrtc: bool | None = None  # None → derive from template
    with_ux_dom: bool = False
    force: bool = False
    port: int = 8080
    # catalog keys or npm package names → auto bridge presets under bridges/
    bridges: list[str] | None = None

    def __post_init__(self) -> None:
        self.app_name = _slug(self.app_name)
        if self.template not in _TEMPLATES:
            raise ValueError(
                f"unknown template {self.template!r}; choose from {list(_TEMPLATES)}"
            )
        if self.with_webrtc is None:
            self.with_webrtc = self.template in ("webrtc", "media", "full")
        if self.dest is None:
            self.dest = Path.cwd() / self.app_name
        else:
            self.dest = Path(self.dest)
        if self.bridges is None:
            self.bridges = []
        else:
            self.bridges = [str(b).strip() for b in self.bridges if str(b).strip()]


# File writers


def create_app(opts: ScaffoldOptions) -> Path:
    """
    Materialize a runnable project under ``opts.dest``.

    Returns the project root path. Raises ``FileExistsError`` unless ``force``.
    """
    root = Path(opts.dest)  # type: ignore[arg-type]
    if root.exists() and any(root.iterdir()) and not opts.force:
        raise FileExistsError(
            f"{root} is not empty — pass force=True / --force to overwrite files"
        )
    root.mkdir(parents=True, exist_ok=True)

    secret = secrets.token_urlsafe(32)
    files = _render_project(opts, secret=secret)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if rel.endswith(".sh"):
            path.chmod(path.stat().st_mode | 0o111)

    # Auto bridge presets (importable bridges/<name>/)
    if opts.bridges:
        from ux_channel.bridge.bridge_preset_gen import create_bridge_preset, write_bridges_index

        bridges_root = root / "bridges"
        bridges_root.mkdir(parents=True, exist_ok=True)
        for name in opts.bridges:
            create_bridge_preset(bridges_root, name, force=True)
        write_bridges_index(bridges_root)
        static_b = root / "app" / "static" / "bridges"
        static_b.mkdir(parents=True, exist_ok=True)
        for js in bridges_root.glob("*/ux-bridge-*.js"):
            (static_b / js.name).write_text(
                js.read_text(encoding="utf-8"), encoding="utf-8"
            )
        (bridges_root / "README.md").write_text(
            "\n".join(
                [
                    "# Bridge presets (auto-generated)",
                    "",
                    "```bash",
                    "uxchannel create-app myapp --bridge chartjs",
                    "```",
                    "",
                    "```python",
                    "from bridges.chartjs import ChartJsBridge",
                    "w = ChartJsBridge(ch, 'revenue', props={...})",
                    "return ch.done(*w.update(...))",
                    "spec = w.mount_spec()  # ux-dom",
                    "```",
                    "",
                    "JS: app/static/bridges/ after channel scripts.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    return root


def validate_scaffold(root: Path, *, template: str | None = None) -> dict:
    """
    Post-create / CI integrity check.

    Returns ``{"ok": bool, "errors": [...], "warnings": [...], "files": [...]}``.
    """
    root = Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    required = [
        "README.md",
        "requirements.txt",
        ".env.example",
        ".gitignore",
        "app/main.py",
        "app/__init__.py",
    ]
    for rel in required:
        if not (root / rel).is_file():
            errors.append(f"missing {rel}")

    main = root / "app" / "main.py"
    if main.is_file():
        text = main.read_text(encoding="utf-8")
        for token in ("Channel.boot", "FastAPI", "get_channel_config"):
            if token not in text:
                errors.append(f"app/main.py missing {token}")
        cfg_py = root / "app" / "config.py"
        if cfg_py.is_file() and "ChannelConfig" not in cfg_py.read_text(
            encoding="utf-8"
        ):
            errors.append("app/config.py missing ChannelConfig")
        try:
            compile(text, str(main), "exec")
        except SyntaxError as exc:
            errors.append(f"app/main.py syntax: {exc}")

    if template in ("webrtc", "media", "full") or (
        main.is_file() and "webrtc" in main.read_text(encoding="utf-8").lower()
    ):
        text_main = main.read_text(encoding="utf-8") if main.is_file() else ""
        if template == "media" and "media.plugin" not in text_main:
            errors.append("media template should call ch.media.plugin")
        if template in ("webrtc", "full") and "plugin" not in text_main and "scripts(" not in text_main:
            warnings.append("webrtc/full should use ch.webrtc.plugin or demo_scripts(ch, )")

    files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "files": files,
    }


def _render_project(opts: ScaffoldOptions, *, secret: str) -> dict[str, str]:
    """Build path → content map for the chosen template."""
    name = opts.app_name
    port = opts.port
    title = name.replace("_", " ").title()

    files: dict[str, str] = {}
    files[".gitignore"] = _GITIGNORE
    files[".env.example"] = _env_example(port=port)
    files[".env"] = (
        f"# Generated by uxchannel create-app — do not commit\n"
        f"UX_CHANNEL_SECRET={secret}\n"
        f"PORT={port}\n"
        f"UX_CHANNEL_ENV=development\n"
    )
    files["requirements.txt"] = _requirements(with_ux_dom=opts.with_ux_dom)
    files["README.md"] = _readme(opts, title=title, port=port)
    files["app/__init__.py"] = (
        f'"""{title} — uxchannel scaffold ({opts.template})."""\n'
        f'__all__ = ["app"]\n'
        f"\n"
        f"# Re-export ASGI app for `uvicorn app.main:app`\n"
        f"from app.main import app  # noqa: E402\n"
    )
    files["app/config.py"] = _config_py()
    files["app/main.py"] = _main_py(opts, title=title, port=port)
    files["scripts/run.sh"] = _run_sh(port=port)
    files["docs/ARCHITECTURE.md"] = _arch_md(opts)
    files[".ux_channel.json"] = _meta_json(opts)

    if opts.template in ("live", "full"):
        files["app/regions.py"] = _regions_py()
    if opts.with_webrtc:
        files["app/webrtc_page.py"] = _webrtc_page_snippet()

    return files


# Static fragments (heavily commented for maintainers of *generated* apps)

_GITIGNORE = """\
# uxchannel scaffold defaults
.env
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.DS_Store
"""


def _meta_json(opts: ScaffoldOptions) -> str:
    import json

    return (
        json.dumps(
            {
                "generator": "uxchannel create-app",
                "template": opts.template,
                "app_name": opts.app_name,
                "with_webrtc": bool(opts.with_webrtc),
                "with_ux_dom": bool(opts.with_ux_dom),
                "port": opts.port,
                "public_api": [
                    "Channel.boot",
                    "@region",
                    "@on",
                    "control",
                    "scripts",
                    "media.plugin",
                ],
            },
            indent=2,
        )
        + "\n"
    )


def _env_example(*, port: int) -> str:
    return f"""\
# Copy to .env and adjust. Never commit real production secrets.
UX_CHANNEL_SECRET=change-me-to-a-long-random-string-at-least-32-chars
UX_CHANNEL_ENV=development
PORT={port}

# Optional multi-worker (production):
# REDIS_URL=redis://localhost:6379/0

# Optional WebRTC TURN (mesh NATs) — see docs/WEBRTC_DX.md / ice.live
# UX_CHANNEL_TURN_URLS=turn:turn.example.com:3478
# UX_CHANNEL_TURN_SECRET=coturn-static-auth-secret

# Optional LiveKit SFU (ch.media mode=sfu when set):
# LIVEKIT_URL=wss://your-project.livekit.cloud
# LIVEKIT_API_KEY=APIxxxx
# LIVEKIT_API_SECRET=…
# (mapped in app/config.py → sfu_*)
"""


def _requirements(*, with_ux_dom: bool) -> str:
    lines = [
        "# Plug-and-play deps for the scaffolded app",
        "fastapi>=0.100",
        "uvicorn[standard]>=0.27",
        "ux-channel[fastapi]>=0.1.0",
    ]
    if with_ux_dom:
        lines.append("ux-dom>=0.1.0")
    lines.append("")
    return "\n".join(lines)


def _readme(opts: ScaffoldOptions, *, title: str, port: int) -> str:
    tpl = opts.template
    webrtc = "yes" if opts.with_webrtc else "no"
    return f"""\
# {title}

Scaffolded with **ux-channel** (`template={tpl}`, webrtc={webrtc}).

## Quick start

```bash
cd {opts.app_name}
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# secret already in .env from create-app
uvicorn app.main:app --host 0.0.0.0 --port {port} --reload
```

Open http://127.0.0.1:{port}/

## What you got

| Piece | Role |
|-------|------|
| `app/config.py` | Env defaults (`ChannelConfig.development`) |
| `app/main.py` | FastAPI + `Channel.boot` + routes |
| `.env` | Local secret (gitignored) |
| `scripts/run.sh` | One-shot runner |

## Mental model

```text
Your HTML / ux-dom  →  markup, layout
uxchannel →  actions, caps, regions, SSE/WS, WebRTC signaling
Browser peers      →  WebRTC data + A/V (never via your server body)
```

## Templates

| Name | Intent |
|------|--------|
| `minimal` | Counter + region morph |
| `live` | Multi-region board |
| `webrtc` | Mesh plugin (UxWebRTC) |
| `media` | `ch.media.plugin` mesh|LiveKit (DX dream) |
| `full` | Live board + media + structured docs |

## Next steps

1. Replace demo HTML with ux-dom `Document` + `demo_scripts(ch, )` / `ch.control(...)`.
2. Production: `ChannelConfig.production(secret)`, Redis, TURN for WebRTC.
3. Read `docs/ARCHITECTURE.md` in this folder and upstream `uxchannel` docs.

## Commands

```bash
uxchannel doctor --fail
uxchannel upgrade-check . --fail
export UX_CHANNEL_STRICT_DX=1
uxchannel check --env development
uxchannel info
```

`ch.doctor()` is the go/no-go. Production: `UX_CHANNEL_ENV=production` + `UX_CHANNEL_SECRET` (≥32) + `REDIS_URL`. Never `require_cap=False`.
"""


def _config_py() -> str:
    return '''\
"""
Application configuration — single place for channel defaults.

WHY
---
Keep secrets and environment out of route modules. Every process should load
the same defaults so DX (local) and production only differ by env vars.
"""

from __future__ import annotations

import os
from functools import lru_cache

from ux_channel import ChannelConfig


def _secret() -> str:
    """Resolve HMAC secret for caps / tickets.

    Prefer ``UX_CHANNEL_SECRET`` (from ``.env``). Fall back to a dev-only
    placeholder so the app still boots if env is missing — never use the
    placeholder in production (``ChannelConfig.production`` rejects weak secrets).
    """
    return os.environ.get(
        "UX_CHANNEL_SECRET",
        "dev-only-change-me-use-dotenv-32b!!",
    )


@lru_cache(maxsize=1)
def get_channel_config() -> ChannelConfig:
    """
    Build ChannelConfig via **factory only** (never raw ChannelConfig(...)).

    * local → ``ChannelConfig.development``
    * deploy → ``ChannelConfig.production``

    Defaults chosen for first-run success:
    * ``allow_memory_stores=True`` — no Redis required
    * ``enforce_same_origin=False`` — easier local multi-port testing
    * ``require_channel_header=False`` — simpler HTML demos (enable in prod)
    * ``webrtc_enabled=True`` — signaling + client JS out of the box

    Production: switch on ``UX_CHANNEL_ENV=production`` and supply a strong secret.
    """
    env = (os.environ.get("UX_CHANNEL_ENV") or "development").lower()
    secret = _secret()

    if env == "production":
        # Fail-closed; requires real secret + typically Redis for multi-worker.
        return ChannelConfig.production(
            secret,
            webrtc_enabled=True,
            # allow_memory_stores=False by default in production
        )

    # LiveKit → ch.media mode=sfu when LIVEKIT_URL is set
    sfu_url = os.environ.get("LIVEKIT_URL") or os.environ.get("UX_CHANNEL_SFU_URL") or ""
    sfu_key = os.environ.get("LIVEKIT_API_KEY") or os.environ.get("UX_CHANNEL_SFU_API_KEY") or ""
    sfu_secret = os.environ.get("LIVEKIT_API_SECRET") or os.environ.get("UX_CHANNEL_SFU_API_SECRET") or ""
    sfu_provider = "livekit" if sfu_url and sfu_key and sfu_secret else "none"

    return ChannelConfig.development(
        secret=secret,
        allow_memory_stores=True,
        enforce_same_origin=False,
        require_channel_header=False,
        webrtc_enabled=True,
        sfu_provider=sfu_provider,
        sfu_url=sfu_url,
        sfu_api_key=sfu_key,
        sfu_api_secret=sfu_secret,
    )
'''


def _main_py(opts: ScaffoldOptions, *, title: str, port: int) -> str:
    """Generate main.py — branches by template, always heavily commented."""
    if opts.template == "minimal":
        return _main_minimal(title=title, port=port)
    if opts.template == "live":
        return _main_live(title=title, port=port)
    if opts.template == "webrtc":
        return _main_webrtc(title=title, port=port)
    if opts.template == "media":
        return _main_media(title=title, port=port)
    # full
    return _main_full(title=title, port=port)


def _main_minimal(*, title: str, port: int) -> str:
    return f'''\
"""
{title} — minimal uxchannel app (plug-and-play).

Run::

    uvicorn app.main:app --host 0.0.0.0 --port {port} --reload

Mental model
------------
* ``Channel.boot`` mounts ``/ux-channel/action``, static JS, optional ``/rtc``, SSE, WS.
* ``@ch.region`` defines a morph target (stable ``data-channel-id``).
* ``@ch.on(refresh=[...])`` mutates state and re-renders regions.
* Demo HTML uses ``ux_channel.render.kit``; production apps use ux-dom + ``ch.control``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel
from ux_channel.render.kit import demo_button, demo_page, demo_scripts, attr_string

from app.config import get_channel_config

# Process bootstrap — one Channel per process

app = FastAPI(title="{title}", version="0.1.0")
ch = Channel.boot(app, config=get_channel_config())


# Regions — HTML fragments the client can morph without full reload

@ch.region
def counter(ctx):
    """Live counter badge. ``ctx`` is reserved for future request scope."""
    n = ch.draft.get("n", 0)
    return f'<strong data-channel-id="counter">{{n}}</strong>'


# Actions — Intent → mutate → Result(ops) including region refresh

@ch.on(refresh=[counter], idempotent=False)
def inc():
    """Increment. Non-idempotent so clients do not auto-retry blindly."""
    ch.draft.set("n", int(ch.draft.get("n", 0) or 0) + 1)


@ch.on(refresh=[counter], idempotent=False)
def reset():
    ch.draft.set("n", 0)


# HTTP routes — your app surface (channel is under /ux-channel/*)

@app.get("/health")
def health():
    """Liveness for orchestrators + scaffold smoke tests."""
    return {{"ok": True, "app": "{title}", "n": ch.draft.get("n", 0)}}


@app.get("/", response_class=HTMLResponse)
def index():
    """
    Demo page.

    For ux-dom apps, replace this with Document(...) and::

        head=[raw(str(demo_scripts(ch, )))]
        body attrs: attr_string(ch.body_attrs())
        buttons: **ch.control(inc).as_ux_dom()
    """
    return demo_page(ch, 
        counter,
        demo_button(ch, "+1", inc),
        demo_button(ch, "Reset", reset),
        title="{title}",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port={port}, reload=True)
'''


def _main_live(*, title: str, port: int) -> str:
    return f'''\
"""
{title} — multi-region live board (ux-channel).

Shows how several regions refresh together from one action.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import Channel
from ux_channel.render.kit import demo_button, demo_page

from app.config import get_channel_config

app = FastAPI(title="{title}")
ch = Channel.boot(app, config=get_channel_config())


@ch.region
def stats(ctx):
    clicks = int(ch.draft.get("clicks", 0) or 0)
    return f'<div data-channel-id="stats">Clicks: <b>{{clicks}}</b></div>'


@ch.region
def feed(ctx):
    items = ch.draft.get("feed") or []
    lis = "".join(f"<li>{{x}}</li>" for x in items[:8])
    return f'<ul data-channel-id="feed">{{lis or "<li>empty</li>"}}</ul>'


@ch.on(refresh=[stats, feed], idempotent=False)
def ping(msg: str = "ping"):
    clicks = int(ch.draft.get("clicks", 0) or 0) + 1
    ch.draft.set("clicks", clicks)
    feed_items = list(ch.draft.get("feed") or [])
    feed_items.insert(0, f"{{clicks}}: {{msg}}")
    ch.draft.set("feed", feed_items[:20])


@app.get("/health")
def health():
    return {{"ok": True, "template": "live"}}


@app.get("/", response_class=HTMLResponse)
def index():
    return demo_page(ch, 
        "<h1>Live board</h1>",
        stats,
        feed,
        demo_button(ch, "Ping", ping),
        title="{title}",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port={port}, reload=True)
'''


def _main_webrtc(*, title: str, port: int) -> str:
    """WebRTC template — raw source from templates_src (no CSS f-string issues)."""
    from ux_channel.scaffold.templates_src import WEBRTC_MAIN

    return WEBRTC_MAIN.replace("__TITLE__", title).replace("__PORT__", str(port))


def _main_media(*, title: str, port: int) -> str:
    """ch.media.plugin — mesh or LiveKit; host-owned video tags."""
    from ux_channel.scaffold.templates_src import MEDIA_MAIN

    return (
        MEDIA_MAIN.replace("__TITLE__", title)
        .replace("__PORT__", str(port))
    )


def _main_full(*, title: str, port: int) -> str:
    """Full template — live morph + /call."""
    from ux_channel.scaffold.templates_src import FULL_MAIN

    return FULL_MAIN.replace("__TITLE__", title).replace("__PORT__", str(port))


def _regions_py() -> str:
    return '''\
"""
Optional home for region renderers when main.py grows.

Import and register from main after Channel.boot, or pass ``ch`` in.
Keeping regions pure (HTML in, draft reads) lowers cognitive load.
"""
'''


def _webrtc_page_snippet() -> str:
    return '''\
"""
Optional: extract WebRTC HTML builders here.

Prefer keeping signaling URL from ``ch.webrtc.path`` and scripts from
``demo_scripts(ch, )`` so asset paths never diverge from the mounted channel.
"""
'''


def _run_sh(*, port: int) -> str:
    return f"""\
#!/usr/bin/env sh
# Plug-and-play runner — load .env if present, then uvicorn.
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
export PORT="${{PORT:-{port}}}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
"""


def _arch_md(opts: ScaffoldOptions) -> str:
    return f"""\
# Architecture (scaffolded app)

Template: **{opts.template}**

```text
Browser
  ├─ ux-channel.js     → POST /ux-channel/action (Intents)
  ├─ ux-webrtc.js      → GET/POST /ux-channel/rtc (signaling only)
  │     └─ RTCPeerConnection
  │           ├─ data channel "uid"   (messages)
  │           └─ media tracks        (audio/video)
  └─ optional EventSource/WS        → server push morph

Server (this app)
  ├─ FastAPI routes                 → your pages / APIs
  └─ Channel.boot                   → protocol runtime
        regions · caps · draft · static · rtc
```

## Rules of thumb

1. **Do not** put business secrets in the browser mesh.
2. **Do** use `@ch.on` + caps for trusted mutations.
3. **Do** keep `get_channel_config()` as the only config entry.
4. Production: strong secret, Redis, TURN, `require_channel_header=True`.
"""
