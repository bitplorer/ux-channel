#!/usr/bin/env python3
"""
Generate architecture diagrams that match uxchannel 1.5.x reality.

Source of truth checked against:
  - FastAPI routes in asgi/fastapi.py
  - ops helpers in ops.py
  - types Intent/Result fields
  - agents + mcp packages
  - static assets
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "docs" / "book" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

# Keep labels aligned with library version
LIB_VER = "0.1.0"
PROTOCOL = 'uid: "1"'


def _save(fig, name: str) -> Path:
    path = OUT / name
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", path)
    return path


def _box(ax, x, y, w, h, text, fc="#E8F1FB", ec="#1E3A5F", fs=8.5, bold=False, tc="#0F172A"):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        facecolor=fc, edgecolor=ec, linewidth=1.3,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center", fontsize=fs,
        fontweight="bold" if bold else "normal", color=tc,
    )


def _arrow(ax, x1, y1, x2, y2, color="#334155", lw=1.4):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color, lw=lw),
    )


def diagram_system_context():
    """C4-style context: real doors and real optional backends."""
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.set_title(
        f"System context — uxchannel {LIB_VER} ({PROTOCOL})",
        fontsize=13, fontweight="bold", pad=10,
    )

    _box(ax, 0.25, 3.6, 2.0, 1.5, "Browser\nux-channel.js\nux-bridge.js", fc="#FEF3C7", ec="#B45309", bold=True)
    _box(ax, 0.25, 1.0, 2.0, 1.5, "AI Agent /\nMCP host", fc="#FCE7F3", ec="#9D174D", bold=True)

    _box(ax, 3.0, 0.7, 4.4, 4.8, "", fc="#F8FAFC", ec="#64748B")
    ax.text(5.2, 5.15, "Your Python app (FastAPI / Starlette)", ha="center", fontsize=10, fontweight="bold")

    _box(ax, 3.25, 3.5, 3.9, 1.35,
         "uxchannel host\nmount_channel → /ux-channel/*\nActionRegistry + caps",
         fc="#DBEAFE", ec="#1D4ED8", bold=True, fs=8.5)
    _box(ax, 3.25, 2.0, 3.9, 1.2,
         "Your @action handlers\ndomain / DB / services",
         fc="#E0E7FF", ec="#4338CA", fs=8.5)
    _box(ax, 3.25, 0.95, 3.9, 0.85,
         "static: ux-channel.js · ux-bridge.js · inspector",
         fc="#EEF2FF", ec="#6366F1", fs=7.5)

    _box(ax, 8.0, 3.8, 2.7, 1.4,
         "Redis (optional)\nrate · nonce\nidempotency · push",
         fc="#D1FAE5", ec="#047857", bold=True, fs=8)
    _box(ax, 8.0, 2.0, 2.7, 1.4,
         "npm islands\nbridge.* ops\nsparkline / Chart.js",
         fc="#E0E7FF", ec="#3730A3", bold=True, fs=8)
    _box(ax, 8.0, 0.5, 2.7, 1.2,
         "Probes\n/health /ready /version",
         fc="#F1F5F9", ec="#475569", fs=8)

    _arrow(ax, 2.25, 4.5, 3.25, 4.3)
    ax.text(2.55, 4.75, "POST /ux-channel/action\nIntent+cap", fontsize=7, color="#1D4ED8")
    _arrow(ax, 3.25, 4.0, 2.25, 4.0)
    ax.text(2.5, 3.55, "Result.ops", fontsize=7, color="#047857")

    _arrow(ax, 2.25, 1.7, 3.25, 2.4)
    ax.text(2.35, 2.15, "AgentRunner\nor /ux-channel/mcp/*", fontsize=7, color="#9D174D")

    _arrow(ax, 7.15, 4.3, 8.0, 4.4)
    ax.text(7.3, 4.65, "stores", fontsize=7)
    _arrow(ax, 7.15, 3.7, 8.0, 2.7)
    ax.text(7.25, 3.15, "bridge.*", fontsize=7)

    ax.text(5.5, 0.25,
            "Two front doors share one ActionRegistry — UI caps vs agent policy",
            ha="center", fontsize=8, style="italic", color="#475569")
    _save(fig, "01_system_context.png")


def diagram_sequence_intent():
    """Sequence matching real host + registry pipeline."""
    fig, ax = plt.subplots(figsize=(11, 7.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7.5)
    ax.axis("off")
    ax.set_title(
        "Sequence — Intent → Result (actual pipeline)",
        fontsize=13, fontweight="bold",
    )

    lanes = [
        ("Browser\nux-channel.js", 1.3),
        ("Host ASGI\n/ux-channel/action", 3.7),
        ("ActionRegistry", 6.2),
        ("@action\nhandler", 8.9),
    ]
    for name, x in lanes:
        ax.plot([x, x], [0.6, 6.5], color="#94A3B8", lw=1, ls="--")
        _box(ax, x - 0.85, 6.55, 1.7, 0.75, name, fc="#1E3A5F", ec="#1E3A5F", fs=7.5, bold=True, tc="white")

    # ordered messages reflecting real code
    msgs = [
        (1.3, 6.1, 3.7, "1 POST Intent + X-Channel + cap"),
        (3.7, 5.5, 3.7, "2 size / Origin / rate / client-ver"),
        (3.7, 4.9, 6.2, "3 dispatch_async"),
        (6.2, 4.3, 6.2, "4 name+JSON limits, idempotency"),
        (6.2, 3.7, 6.2, "5 CapabilityService.verify"),
        (6.2, 3.1, 6.2, "6 before hooks → bind ctx/args"),
        (6.2, 2.5, 8.9, "7 invoke handler"),
        (8.9, 1.9, 6.2, "8 raw → encode_result"),
        (6.2, 1.3, 3.7, "9 sanitize hrefs + after hooks"),
        (3.7, 0.85, 1.3, "10 application/uid+json Result"),
    ]
    # draw as horizontal arrows between lane x positions only for cross-lane
    cross = [
        (1.3, 6.1, 3.7, "POST Intent"),
        (3.7, 5.2, 6.2, "dispatch_async"),
        (6.2, 4.0, 6.2, None),
        (6.2, 2.6, 8.9, "call"),
        (8.9, 2.0, 6.2, "return"),
        (6.2, 1.4, 3.7, "Result"),
        (3.7, 0.9, 1.3, "JSON ops"),
    ]
    y = 6.0
    steps = [
        (1.3, 3.7, "POST /ux-channel/action Intent"),
        (3.7, 3.7, "origin · header · rate · size"),
        (3.7, 6.2, "dispatch_async"),
        (6.2, 6.2, "limits · idempotency · cap.verify"),
        (6.2, 6.2, "hooks · ActionContext · bind"),
        (6.2, 8.9, "handler()"),
        (8.9, 6.2, "encode_result"),
        (6.2, 3.7, "sanitize navigate hrefs"),
        (3.7, 1.3, "Result JSON → applyOp"),
    ]
    ys = [5.9, 5.25, 4.6, 3.95, 3.3, 2.65, 2.0, 1.35, 0.75]
    for (x1, x2, label), y in zip(steps, ys):
        if x1 != x2:
            _arrow(ax, x1, y, x2, y)
            ax.text((x1 + x2) / 2, y + 0.12, label, ha="center", fontsize=7.2, color="#1E3A5F")
        else:
            ax.text(x1 + 0.15, y, "• " + label, ha="left", va="center", fontsize=7.2, color="#334155")

    ax.text(5.5, 0.25,
            "Cap binds action+args_hash (+ optional sub/scopes/once). Agent path uses AgentRunner policy instead of browser Origin.",
            ha="center", fontsize=7.5, style="italic", color="#64748B")
    _save(fig, "02_sequence_intent.png")


def diagram_class_core():
    """UML-ish core types with real field names."""
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title(f"Core types — uxchannel {LIB_VER}", fontsize=13, fontweight="bold")

    def klass(x, y, w, h, title, body, fc="#EFF6FF"):
        _box(ax, x, y + h - 0.5, w, 0.5, title, fc="#1E40AF", ec="#1E40AF", fs=8.5, bold=True, tc="white")
        rect = FancyBboxPatch(
            (x, y), w, h - 0.5,
            boxstyle="round,pad=0.01,rounding_size=0.04",
            facecolor=fc, edgecolor="#1E40AF", linewidth=1.1,
        )
        ax.add_patch(rect)
        ax.text(x + 0.1, y + h - 0.7, body, ha="left", va="top", fontsize=7,
                family="monospace", color="#0F172A")

    klass(0.25, 4.4, 3.3, 3.3, "Intent",
          f'+ uid = {PROTOCOL}\n'
          "+ action: str\n+ args: dict\n+ cap: str?\n"
          "+ target: str?\n+ form: dict?\n+ request_id: str?\n"
          "+ idempotency_key: str?\n+ accept_stream: bool\n+ meta: dict?")
    klass(3.75, 4.4, 3.3, 3.3, "Result",
          f'+ uid = {PROTOCOL}\n'
          "+ ok: bool\n+ ops: Op[]\n+ error: ErrorObject?\n"
          "+ meta: dict\n---\n"
          "+ Result.success(...)\n+ Result.failure(...)")
    klass(7.25, 4.4, 3.4, 3.3, "Op (dict)",
          "+ op: str\n"
          "Document:\n  morph swap remove\n  set_text set_attr clear_errors\n"
          "Bridge:\n  bridge.mount|update|call|destroy\n"
          "Chrome:\n  toast navigate push_url\n  focus scroll dispatch signal.set")

    klass(0.25, 0.35, 3.5, 3.7, "ActionRegistry",
          "+ require_cap\n+ hooks / nonce / idempotency\n"
          "+ auth_resolver\n---\n"
          "+ @action / register\n+ sign(...) → cap\n"
          "+ dispatch / dispatch_async\n+ bind_request")
    klass(4.0, 0.35, 3.3, 3.7, "CapabilityService",
          "+ sign(action, args,\n    sub?, scopes?, once?)\n"
          "+ verify(token, action, args)\n"
          "+ previous_secrets (rotation)\n---\n"
          "HMAC URLSafeTimedSerializer\nargs_hash = sha256 JSON")
    klass(7.5, 0.35, 3.15, 3.7, "ActionContext",
          "+ intent: Intent\n+ request?\n"
          "+ principal: Principal?\n"
          "    id, scopes, claims\n"
          "+ registry\n---\n"
          "inject as param name ctx")

    _arrow(ax, 3.55, 6.0, 3.75, 6.0)
    _arrow(ax, 7.05, 6.0, 7.25, 6.0)
    _arrow(ax, 1.9, 4.4, 1.9, 4.05)
    _arrow(ax, 5.4, 4.4, 5.4, 4.05)
    _save(fig, "03_class_core.png")


def diagram_op_planes():
    """Exact op names from ops.py."""
    fig, ax = plt.subplots(figsize=(11, 5.8))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.8)
    ax.axis("off")
    ax.set_title("Result.ops planes (constructors in ux_channel.ops)", fontsize=13, fontweight="bold")

    planes = [
        (0.3, "#DBEAFE", "#1D4ED8", "Document plane",
         "morph\nswap\nremove\nset_text\nset_attr\nclear_errors\n\nHTML structure"),
        (3.85, "#D1FAE5", "#047857", "Bridge plane",
         "bridge_mount\nbridge_update\nbridge_call\nbridge_destroy\n\nnpm islands\n(ux-bridge.js)"),
        (7.4, "#FEF3C7", "#B45309", "Chrome plane",
         "toast  navigate\npush_url  reload\nfocus  scroll\ndispatch\nsignal_set  noop\n\nUX / navigation"),
    ]
    for x, fc, ec, title, body in planes:
        _box(ax, x, 0.7, 3.3, 4.5, "", fc=fc, ec=ec)
        ax.text(x + 1.65, 4.7, title, ha="center", fontsize=11, fontweight="bold", color=ec)
        ax.text(x + 1.65, 2.5, body, ha="center", va="center", fontsize=9, color="#0F172A",
                family="monospace")

    ax.text(5.5, 0.3,
            "navigate/push_url hrefs: safe_href blocks javascript:/data:/vbscript: (server + client)",
            ha="center", fontsize=8, style="italic", color="#64748B")
    _save(fig, "04_op_planes.png")


def diagram_security_doors():
    """Real paths for UI vs agent."""
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.set_title("Two front doors → one ActionRegistry", fontsize=13, fontweight="bold")

    _box(ax, 0.3, 3.5, 3.0, 2.2,
         "Browser UI door\n\nPOST /ux-channel/action\nOrigin + X-Channel\ncap (HMAC)\noptional min_client_version",
         fc="#FEF3C7", ec="#B45309", bold=True, fs=8)
    _box(ax, 0.3, 0.5, 3.0, 2.5,
         "Agent / MCP door\n\nAgentRunner.call_tool\nGET/POST /ux-channel/mcp/*\nBearer agent_token\nAgentPolicy allowlist\nbudget · confirm · audit",
         fc="#FCE7F3", ec="#9D174D", bold=True, fs=8)

    _box(ax, 4.2, 1.5, 3.3, 3.5,
         "ActionRegistry\n\nverify / hooks\nhandlers\nencode_result\nlimits + href sanitize",
         fc="#DBEAFE", ec="#1D4ED8", bold=True, fs=9)

    _box(ax, 8.2, 2.3, 2.5, 2.0,
         "Result.ops\n\napply in browser\nor structuredContent\nfor MCP",
         fc="#D1FAE5", ec="#047857", bold=True, fs=8)

    _arrow(ax, 3.3, 4.5, 4.2, 3.8)
    _arrow(ax, 3.3, 1.7, 4.2, 2.6)
    _arrow(ax, 7.5, 3.2, 8.2, 3.2)

    ax.text(5.5, 0.25,
            "Never point agents at open /action without policy — use AgentRunner or token-gated /mcp",
            ha="center", fontsize=8, style="italic", color="#64748B")
    _save(fig, "05_security_doors.png")


def diagram_deploy():
    """Multi-worker with real Redis modules."""
    fig, ax = plt.subplots(figsize=(11, 5.8))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.8)
    ax.axis("off")
    ax.set_title("Production multi-worker deploy", fontsize=13, fontweight="bold")

    _box(ax, 0.3, 2.0, 2.0, 2.0, "TLS edge\nXFF rewrite\ntimeouts", fc="#F1F5F9", ec="#475569", bold=True, fs=8)
    _box(ax, 2.7, 1.3, 2.8, 3.4,
         "Pods × N\nuvicorn\nChannelConfig\n.production\nshared SECRET\n(+ PREVIOUS_SECRETS)",
         fc="#DBEAFE", ec="#1D4ED8", bold=True, fs=8)
    _box(ax, 6.0, 3.3, 2.3, 1.5,
         "Redis\nRateLimiter\nNonceStore\nIdempotencyStore",
         fc="#D1FAE5", ec="#047857", bold=True, fs=7.5)
    _box(ax, 6.0, 1.3, 2.3, 1.5,
         "RedisPushBus\npub/sub topics\n/ux-channel/push/{topic}",
         fc="#D1FAE5", ec="#047857", bold=True, fs=7.5)
    _box(ax, 8.7, 2.0, 2.0, 2.0, "DB /\nDomain", fc="#E0E7FF", ec="#4338CA", bold=True, fs=8)

    _arrow(ax, 2.3, 3.0, 2.7, 3.0)
    _arrow(ax, 5.5, 3.8, 6.0, 4.0)
    _arrow(ax, 5.5, 2.4, 6.0, 2.0)
    _arrow(ax, 5.5, 3.0, 8.7, 3.0)

    ax.text(5.5, 0.45,
            "create_channel auto-wires REDIS_URL when redis package installed · Memory* stores are process-local only",
            ha="center", fontsize=7.5, style="italic", color="#64748B")
    ax.text(5.5, 0.15,
            "Probes: GET /ux-channel/health · /ux-channel/ready · /ux-channel/version",
            ha="center", fontsize=7.5, color="#475569")
    _save(fig, "06_deploy.png")


def diagram_workflow():
    """Developer loop matching real API names."""
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    ax.set_title("Developer workflow", fontsize=13, fontweight="bold")

    steps = [
        (0.25, "1. Register\n@reg.action"),
        (2.4, "2. Render HTML\nreg.sign + attrs"),
        (4.55, "3. Client POST\n/ux-channel/action"),
        (6.7, "4. Handler\nResult.ops"),
        (8.85, "5. Apply\nmorph/bridge/toast"),
    ]
    for x, label in steps:
        _box(ax, x, 1.3, 1.95, 1.7, label, fc="#EEF2FF", ec="#4338CA", bold=True, fs=8)
    for x in (2.2, 4.35, 6.5, 8.65):
        _arrow(ax, x, 2.15, x + 0.2, 2.15)

    ax.text(5.5, 0.55,
            "Re-sign caps whenever signed args change · escape user HTML with user_content/esc",
            ha="center", fontsize=8, style="italic", color="#475569")
    ax.text(5.5, 0.2,
            f"Client runtime VERSION={LIB_VER} sends X-Channel-Client-Version",
            ha="center", fontsize=7.5, color="#64748B")
    _save(fig, "07_workflow.png")


def diagram_http_surface():
    """All real HTTP routes under /ux-channel."""
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.5)
    ax.axis("off")
    ax.set_title(f"HTTP surface — default path /ux-channel  ({LIB_VER})", fontsize=13, fontweight="bold")

    groups = [
        (0.3, 3.4, 3.4, 2.7, "#DBEAFE", "#1D4ED8", "Core channel",
         "POST /action\nGET  /health\nGET  /ready\nGET  /version\nGET  /metrics\nGET  /catalog\nGET  /static/*"),
        (3.9, 3.4, 3.4, 2.7, "#FEF3C7", "#B45309", "Debug (gated)",
         "GET  /trace\nGET  /trace/conversations\nPOST /trace/client\nDELETE /trace\nGET  /docs/howto"),
        (7.5, 3.4, 3.2, 2.7, "#FCE7F3", "#9D174D", "Agents / push",
         "GET  /mcp/tools\nPOST /mcp/tools/call\nPOST /mcp/rpc\nGET  /push/{topic}"),
    ]
    for x, y, w, h, fc, ec, title, body in groups:
        _box(ax, x, y, w, h, "", fc=fc, ec=ec)
        ax.text(x + w / 2, y + h - 0.35, title, ha="center", fontsize=10, fontweight="bold", color=ec)
        ax.text(x + w / 2, y + h / 2 - 0.15, body, ha="center", va="center",
                fontsize=8, family="monospace", color="#0F172A")

    _box(ax, 0.3, 0.4, 10.4, 2.6, "", fc="#F8FAFC", ec="#64748B")
    ax.text(5.5, 2.65, "Request guards on POST /action (order)", ha="center", fontsize=9, fontweight="bold")
    ax.text(5.5, 1.5,
            "1 Content-Length  →  2 Origin / Origin:null deny  →  3 X-Channel (prod)\n"
            "4 X-Channel-Client-Version vs min_client_version  →  5 IP rate limit\n"
            "6 parse Intent  →  7 registry.dispatch_async  →  8 negotiate JSON | HTML | SSE",
            ha="center", va="center", fontsize=8, color="#0F172A")
    _save(fig, "08_http_surface.png")


def diagram_modules():
    """Package map matching src/ux_channel."""
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.set_title(f"Package map — ux_channel/ ({LIB_VER})", fontsize=13, fontweight="bold")

    mods = [
        (0.25, 4.3, 3.4, 1.6, "Protocol core",
         "types · ops · encode\ncapability · registry\ncontext · hooks · limits"),
        (3.85, 4.3, 3.4, 1.6, "HTTP hosts",
         "asgi/fastapi.py\nasgi/starlette.py\nasgi/core.py"),
        (7.45, 4.3, 3.3, 1.6, "Browser assets",
         "static/ux-channel.js\nstatic/ux-bridge.js\nstatic/ux-inspector.js"),
        (0.25, 2.3, 3.4, 1.6, "Agents / MCP",
         "agents/policy session\n  runner tools audit\nmcp/adapter"),
        (3.85, 2.3, 3.4, 1.6, "Scale / safety",
         "redis_extra\nratelimit nonce\nidempotency security\ncors middleware"),
        (7.45, 2.3, 3.3, 1.6, "DX",
         "trace inspector\ncatalog codegen\nschema_models\ninfo factory"),
        (0.25, 0.4, 10.5, 1.5, "HTML multi-library",
         "render (String/Chain/Jinja/UxDom) · plugins · bridge_api · html · html_safe · actions_file · pydantic_actions"),
    ]
    colors = [
        ("#DBEAFE", "#1D4ED8"), ("#E0E7FF", "#4338CA"), ("#FEF3C7", "#B45309"),
        ("#FCE7F3", "#9D174D"), ("#D1FAE5", "#047857"), ("#F1F5F9", "#475569"),
        ("#EEF2FF", "#6366F1"),
    ]
    for (x, y, w, h, title, body), (fc, ec) in zip(mods, colors):
        _box(ax, x, y, w, h, "", fc=fc, ec=ec)
        ax.text(x + w / 2, y + h - 0.32, title, ha="center", fontsize=9, fontweight="bold", color=ec)
        ax.text(x + w / 2, y + h / 2 - 0.15, body, ha="center", va="center", fontsize=7.5, color="#0F172A")
    _save(fig, "09_modules.png")


def diagram_client_apply():
    """Client apply order matching ux-channel.js."""
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4.5)
    ax.axis("off")
    ax.set_title("Browser apply pipeline (ux-channel.js)", fontsize=13, fontweight="bold")

    steps = [
        (0.3, "fetch\nIntent"),
        (2.3, "parse\nResult"),
        (4.3, "uid:before\nApply"),
        (6.3, "for each op\napplyOp"),
        (8.3, "bridge\nreaper"),
    ]
    for x, label in steps:
        _box(ax, x, 2.0, 1.8, 1.5, label, fc="#FEF3C7", ec="#B45309", bold=True, fs=8)
    for x in (2.1, 4.1, 6.1, 8.1):
        _arrow(ax, x, 2.75, x + 0.2, 2.75)

    ax.text(5.5, 1.2,
            "applyOp: morph/swap/remove/set_* | bridge.* → uxBridge | toast/navigate/focus/scroll/signal/dispatch",
            ha="center", fontsize=8, color="#0F172A")
    ax.text(5.5, 0.6,
            "Focus + scroll restored after morph when possible · concurrency via data-channel-concurrency",
            ha="center", fontsize=7.5, style="italic", color="#64748B")
    ax.text(5.5, 0.25,
            f"Headers: Content-Type application/uid+json · X-Channel: 1 · X-Channel-Client-Version: {LIB_VER}",
            ha="center", fontsize=7.5, color="#475569")
    _save(fig, "10_client_apply.png")


def main():
    diagram_system_context()
    diagram_sequence_intent()
    diagram_class_core()
    diagram_op_planes()
    diagram_security_doors()
    diagram_deploy()
    diagram_workflow()
    diagram_http_surface()
    diagram_modules()
    diagram_client_apply()
    # write a machine-readable accuracy note
    note = OUT / "FIGURE_ACCURACY.md"
    note.write_text(
        f"""# Figure accuracy notes (generated with library {LIB_VER})

| File | Represents | Verified against |
|------|------------|------------------|
| 01_system_context.png | Actors + doors + Redis + bridges + probes | asgi routes, static/, redis_extra, agents |
| 02_sequence_intent.png | POST /action pipeline steps | fastapi.py + registry dispatch |
| 03_class_core.png | Intent/Result/Op/Registry/Cap/Context fields | types.py, capability.py, context.py |
| 04_op_planes.png | ops constructors by plane | ops.py public helpers |
| 05_security_doors.png | /ux-channel/action vs AgentRunner + /mcp | agents/, mcp/, fastapi mcp routes |
| 06_deploy.png | multi-worker Redis pieces | redis_extra, push, factory REDIS_URL |
| 07_workflow.png | @action → sign → POST → Result → apply | public API |
| 08_http_surface.png | all /ux-channel routes + guard order | fastapi.py route list |
| 09_modules.png | package layout | src/ux_channel tree |
| 10_client_apply.png | browser apply pipeline | static/ux-channel.js |

Protocol wire version: {PROTOCOL}
"""
    )
    print("done", OUT)


if __name__ == "__main__":
    main()
