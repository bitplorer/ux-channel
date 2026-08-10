"""DX logging + exceptions — nothing silent."""

import tempfile

from ux_channel.cli import main
from ux_channel.dx_errors import DxConflictError, DxNotFoundError, DxUsageError
from ux_channel.dx_log import DxLog, Level, configure_log, get_log, log_exception


def test_log_levels_and_capture():
    log = get_log()
    log.capture = True
    log.clear()
    log.configure(verbose=True)
    log.debug("d")
    log.info("i")
    log.ok("o")
    log.warn("w")
    log.error("e")
    levels = [r["level"] for r in log.records() if not r.get("skipped")]
    assert levels == ["debug", "info", "ok", "warn", "error"]
    log.capture = False
    log.configure(verbose=False)


def test_log_exception_codes():
    log = get_log()
    log.capture = True
    log.clear()
    log.configure(verbose=False)
    assert log_exception(DxUsageError("bad"), log=log) == 2
    assert log_exception(DxNotFoundError("nope"), log=log) == 3
    assert log_exception(DxConflictError("clash"), log=log) == 4
    msgs = " ".join(r["message"] for r in log.records())
    assert "dx.usage" in msgs or "bad" in msgs
    log.capture = False


def test_cli_bridge_missing_package_logs_usage():
    # exit 2
    code = main(["bridge", "add-method"])
    assert code == 2


def test_cli_bridge_verbose_ok():
    with tempfile.TemporaryDirectory() as td:
        assert main(["-v", "bridge", "new", "z", "--out", td, "--force"]) == 0
        assert main(["bridge", "add-method", "z", "foo", "--out", td]) == 0
        assert main(["bridge", "add-method", "z", "foo", "--out", td]) == 0  # idempotent
