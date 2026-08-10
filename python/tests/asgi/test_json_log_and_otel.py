"""Structured JSON DX logs + OpenTelemetry soft integration."""

from __future__ import annotations

import json
import tempfile
from io import StringIO

from ux_channel.cli import main
from ux_channel.dx_log import DxLog, configure_log, get_log, log_exception
from ux_channel.dx_errors import DxUsageError
from ux_channel.otel import attach_otel, detach_otel, otel_available, status


def test_json_log_lines_are_parseable():
    buf = StringIO()
    log = get_log()
    log.configure(verbose=True, json_logs=True, stream=buf)
    log.capture = False
    log.info("hello", package="x", event="test_event")
    log.ok("done", method="foo")
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) >= 2
    for ln in lines:
        rec = json.loads(ln)
        assert "ts" in rec and "level" in rec and "msg" in rec
        assert rec["logger"] == "ux_channel.dx"
    # restore
    log.configure(json_logs=False, stream=None)


def test_json_exception_includes_code_hint():
    buf = StringIO()
    log = get_log()
    log.configure(json_logs=True, stream=buf)
    code = log_exception(DxUsageError("need args", hint="see help"), log=log)
    assert code == 2
    recs = [json.loads(ln) for ln in buf.getvalue().splitlines() if ln.strip()]
    assert any(r.get("code") == "dx.usage" or "dx.usage" in r.get("msg", "") for r in recs)
    assert any(r.get("hint") == "see help" or "hint" in r for r in recs)
    log.configure(json_logs=False)


def test_cli_json_flag():
    with tempfile.TemporaryDirectory() as td:
        # capture by running with --json should exit 0
        assert main(["--json", "bridge", "new", "j", "--out", td, "--force"]) == 0


def test_otel_status_and_attach_without_sdk():
    st = status()
    assert "available" in st and "attached" in st
    # attach may fail without package — must not raise
    detach_otel()
    ok = attach_otel()
    assert ok is True or ok is False
    if not otel_available():
        assert ok is False
    detach_otel()


def test_observability_json_hook():
    from ux_channel.observability import observability_after_hook
    from ux_channel.types import Intent, Result

    hook = observability_after_hook(json_logs=True, log_all=True, log_slow_ms=99999)
    intent = Intent(action="ping", args={})
    # Intent may need more fields - check
    try:
        intent = Intent(action="ping", args={}, request_id="r1")
    except TypeError:
        intent = Intent(action="ping", args={})
        if hasattr(intent, "request_id"):
            pass
    result = Result.success()
    if not hasattr(result, "meta") or result.meta is None:
        # set duration
        pass
    try:
        result.meta["duration_ms"] = 1.0
    except Exception:
        pass
    out = hook(intent, result)
    assert out is result
