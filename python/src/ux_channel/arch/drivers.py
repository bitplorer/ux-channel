"""web.v1 and agent.v1 drivers (log/test + invoke). No DOM in this module."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional


def safe_href(href: Any) -> Optional[str]:
    if not href or not isinstance(href, str):
        return None
    h = href.strip()
    if not h or h.startswith("//"):
        return None
    lower = h.lower()
    path = h.split("?")[0].split("#")[0]
    if ":" in path:
        scheme = lower.split(":", 1)[0]
        if scheme in ("javascript", "data", "vbscript", "file"):
            return None
        if scheme not in ("http", "https", "mailto", "tel") and scheme.isalpha():
            return None
    return h


def make_web_drivers(
    *,
    apply_ops: Optional[Callable[[list, MutableMapping[str, Any]], None]] = None,
    max_timer_ms: int = 600_000,
) -> Dict[str, Callable[[Mapping[str, Any], MutableMapping[str, Any]], None]]:
    def toast(op, ctx):
        ctx.setdefault("log", []).append(("toast", op.get("message"), op.get("level", "info")))

    def morph(op, ctx):
        ctx.setdefault("log", []).append(("morph", op.get("target"), op.get("html")))

    def navigate(op, ctx):
        if ctx.get("result_ok") is False:
            return
        href = safe_href(op.get("href"))
        if not href:
            return
        ctx.setdefault("log", []).append(("navigate", href, bool(op.get("replace"))))

    def push_url(op, ctx):
        href = safe_href(op.get("href"))
        if not href:
            return
        ctx.setdefault("log", []).append(("push_url", href, bool(op.get("replace"))))

    def reload(op, ctx):
        if ctx.get("result_ok") is False:
            return
        ctx.setdefault("log", []).append(("reload",))

    def focus(op, ctx):
        ctx.setdefault("log", []).append(("focus", op.get("target"), bool(op.get("select"))))

    def set_text(op, ctx):
        ctx.setdefault("log", []).append(("set_text", op.get("target"), op.get("text")))

    def dispatch(op, ctx):
        ctx.setdefault("log", []).append(("dispatch", op.get("name"), op.get("detail")))

    def timer_set(op, ctx):
        ms = max(0, min(int(op.get("ms") or 0), max_timer_ms))
        tid = str(op.get("id") or "t")
        gen = ctx.get("gen")
        body = list(op.get("ops") or [])

        def fire():
            if ctx.get("gen") != gen:
                return
            runner = apply_ops or ctx.get("apply_ops")
            if runner:
                runner(body, ctx)
            else:
                ctx.setdefault("log", []).append(("timer_fire", tid, body))

        ctx.setdefault("timers", {})[tid] = {"ms": ms, "fire": fire, "gen": gen}
        if ms == 0:
            fire()

    def timer_clear(op, ctx):
        ctx.setdefault("timers", {}).pop(str(op.get("id") or ""), None)

    def invoke_default(op, ctx):
        ctx.setdefault("log", []).append(
            ("invoke", op.get("ref"), op.get("method"), op.get("args"))
        )

    return {
        "toast": toast,
        "morph": morph,
        "navigate": navigate,
        "push_url": push_url,
        "reload": reload,
        "focus": focus,
        "set_text": set_text,
        "dispatch": dispatch,
        "timer.set": timer_set,
        "timer.clear": timer_clear,
        "invoke": invoke_default,
    }


def make_agent_drivers(
    tools: Optional[Dict[str, Callable[[Mapping[str, Any]], Any]]] = None,
) -> Dict[str, Callable[[Mapping[str, Any], MutableMapping[str, Any]], None]]:
    tools = tools or {}

    def tool(op, ctx):
        name = str(op.get("name") or "")
        fn = tools.get(name)
        if fn is None:
            ctx.setdefault("log", []).append(("tool_missing", name))
            return
        try:
            out = fn(dict(op.get("args") or {}))
        except Exception as exc:
            ctx.setdefault("log", []).append(("tool_error", name, type(exc).__name__))
            return
        ctx.setdefault("log", []).append(("tool", name, out))

    def log(op, ctx):
        ctx.setdefault("log", []).append(("log", op.get("message"), op.get("level")))

    return {"tool": tool, "log": log}


def make_trace_drivers() -> Dict[str, Callable[[Mapping[str, Any], MutableMapping[str, Any]], None]]:
    def record(op, ctx):
        ctx.setdefault("trace", []).append(dict(op))
        ctx.setdefault("log", []).append(("record", op.get("name") or op.get("op")))

    def assert_frag(op, ctx):
        ctx.setdefault("log", []).append(("assert", op.get("expect")))

    return {"record": record, "assert": assert_frag}


def make_wire_drivers(
    *,
    forward: Optional[Callable[[Mapping[str, Any]], None]] = None,
) -> Dict[str, Callable[[Mapping[str, Any], MutableMapping[str, Any]], None]]:
    def fwd(op, ctx):
        if forward:
            forward(op)
        ctx.setdefault("log", []).append(("forward", op.get("to")))

    def noop(op, ctx):
        ctx.setdefault("log", []).append(("noop",))

    return {"forward": fwd, "noop": noop}
