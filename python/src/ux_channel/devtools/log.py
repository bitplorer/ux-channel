"""
Developer tooling console logging — nothing silent; text or structured JSON for automation.

Text::

    info  | loading contract  path='…'

JSON (one object per line)::

    {"ts":1710000000.1,"level":"info","msg":"loading contract","path":"…",…}

Enable JSON: ``ux_channel --json …`` · ``UX_CHANNEL_DX_JSON=1`` · ``configure_log(json_logs=True)``
"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
import os
import sys
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional, TextIO

__all__ = [
    "Level",
    "DxLog",
    "get_log",
    "configure_log",
    "log_exception",
]


class Level(IntEnum):
    DEBUG = 10
    INFO = 20
    OK = 25
    WARN = 30
    ERROR = 40
    SILENT = 100


_LEVEL_LABEL = {
    Level.DEBUG: "debug",
    Level.INFO: "info",
    Level.OK: "ok",
    Level.WARN: "warn",
    Level.ERROR: "error",
}


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass
class DxLog:
    min_level: Level = Level.INFO
    stream: TextIO = field(default_factory=lambda: sys.stderr)
    use_stdout_for_ok: bool = False
    json_mode: bool = False
    service: str = "ux_channel"
    _records: list[dict[str, Any]] = field(default_factory=list)
    capture: bool = False

    def configure(
        self,
        *,
        verbose: bool = False,
        quiet: bool = False,
        json_logs: Optional[bool] = None,
        stream: Optional[TextIO] = None,
        service: Optional[str] = None,
    ) -> None:
        if quiet and verbose:
            verbose = False
        if quiet:
            self.min_level = Level.ERROR
        elif verbose or _env_truthy("UX_CHANNEL_DX_VERBOSE"):
            self.min_level = Level.DEBUG
        else:
            self.min_level = Level.INFO
        if json_logs is None:
            self.json_mode = _env_truthy("UX_CHANNEL_DX_JSON")
        else:
            self.json_mode = bool(json_logs)
        if stream is not None:
            self.stream = stream
        if service is not None:
            self.service = service

    def _emit(
        self,
        level: Level,
        message: str,
        *,
        extra: str = "",
        event: str = "",
        fields: Optional[dict[str, Any]] = None,
    ) -> None:
        label = _LEVEL_LABEL[level]
        fields = {k: v for k, v in (fields or {}).items() if v is not None}
        if level < self.min_level:
            if self.capture:
                self._records.append(
                    {
                        "level": label,
                        "message": message,
                        "skipped": True,
                        "fields": fields,
                    }
                )
            return

        out = (
            sys.stdout
            if (self.use_stdout_for_ok and level == Level.OK)
            else self.stream
        )

        if self.json_mode:
            rec: dict[str, Any] = {
                "ts": time.time(),
                "level": label,
                "msg": message,
                "logger": "ux_channel.dx",
                "service": self.service,
            }
            if event:
                rec["event"] = event
            if extra:
                # strip leading "hint: " for structured field
                hint = extra[6:].strip() if extra.startswith("hint:") else extra
                rec["hint"] = hint
            rec.update(fields)
            print(_serde.dumps(rec, default=str), file=out)
        else:
            line_msg = message
            if fields:
                tail = " ".join(
                    f"{k}={v!r}"
                    if not isinstance(v, (int, float, bool))
                    else f"{k}={v}"
                    for k, v in fields.items()
                )
                line_msg = f"{message}  {tail}" if message else tail
            print(f"{label:5} | {line_msg}", file=out)
            if extra:
                for el in extra.splitlines():
                    print(f"      | {el}", file=out)

        if self.capture:
            self._records.append(
                {
                    "level": label,
                    "message": message,
                    "extra": extra,
                    "fields": fields,
                    "event": event,
                    "skipped": False,
                    "json": self.json_mode,
                }
            )

    def debug(self, message: str, **kv: Any) -> None:
        event = str(kv.pop("event", "") or "")
        self._emit(Level.DEBUG, message, fields=kv, event=event)

    def info(self, message: str, **kv: Any) -> None:
        event = str(kv.pop("event", "") or "")
        self._emit(Level.INFO, message, fields=kv, event=event)

    def ok(self, message: str, **kv: Any) -> None:
        event = str(kv.pop("event", "") or "ok")
        self._emit(Level.OK, message, fields=kv, event=event)

    def warn(self, message: str, **kv: Any) -> None:
        event = str(kv.pop("event", "") or "")
        self._emit(Level.WARN, message, fields=kv, event=event)

    def error(self, message: str, **kv: Any) -> None:
        event = str(kv.pop("event", "") or "error")
        self._emit(Level.ERROR, message, fields=kv, event=event)

    def section(self, title: str) -> None:
        self.info(f"── {title} ──", event="section", section=title)

    def kv(self, **items: Any) -> None:
        for k, v in items.items():
            self.info(f"{k}={v}", **{k: v})

    def exception(self, exc: BaseException) -> None:
        log_exception(exc, log=self)

    def records(self) -> list[dict[str, Any]]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


_LOG = DxLog()


def get_log() -> DxLog:
    return _LOG


def configure_log(
    *,
    verbose: bool = False,
    quiet: bool = False,
    json_logs: Optional[bool] = None,
) -> DxLog:
    _LOG.configure(verbose=verbose, quiet=quiet, json_logs=json_logs)
    return _LOG


def log_exception(exc: BaseException, *, log: Optional[DxLog] = None) -> int:
    log = log or get_log()
    from ux_channel.devtools.errors import DxError

    if isinstance(exc, DxError):
        fields: dict = {
            "event": "dx_error",
            "code": exc.code,
            "exit_code": exc.exit_code,
        }
        if exc.hint:
            fields["hint"] = exc.hint
        if exc.details is not None:
            fields["details"] = exc.details
        log.error(f"{exc.code}: {exc.message}", **fields)
        if exc.hint and not log.json_mode:
            log._emit(
                Level.ERROR,
                f"hint: {exc.hint}",
                event="dx_hint",
                fields={"hint": exc.hint, "code": exc.code},
            )
        return int(exc.exit_code)

    if isinstance(exc, FileNotFoundError):
        log.error(
            f"dx.not_found: {exc}",
            event="dx_error",
            code="dx.not_found",
        )
        log.error(
            "hint: pass --contract PATH or uxchannel bridge new <pkg>",
            event="dx_hint",
            hint="pass --contract PATH or uxchannel bridge new <pkg>",
        )
        return 3
    if isinstance(exc, KeyError):
        log.error(f"dx.not_found: {exc}", event="dx_error", code="dx.not_found")
        return 3
    if isinstance(exc, ValueError):
        msg = str(exc)
        if "--force" in msg or "different signature" in msg or "conflict" in msg.lower():
            log.error(f"dx.conflict: {msg}", event="dx_error", code="dx.conflict")
            log.error(
                "hint: re-run with --force to update the method",
                event="dx_hint",
                hint="re-run with --force to update the method",
            )
            return 4
        log.error(f"dx.validation: {msg}", event="dx_error", code="dx.validation")
        return 1
    log.error(
        f"dx.internal: {type(exc).__name__}: {exc}",
        event="dx_error",
        code="dx.internal",
    )
    return 1
