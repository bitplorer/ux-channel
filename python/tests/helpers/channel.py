"""Minimal channel factories used by multiple suites."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig


def dev_config(**overrides: Any) -> ChannelConfig:
    base = dict(
        secret="test-secret-key-32-chars-minimum!!",
        allow_memory_stores=True,
        rate_limit_per_minute=0,
        enforce_same_origin=False,
    )
    base.update(overrides)
    return ChannelConfig.development(**base)


def boot_channel(app: FastAPI | None = None, **cfg_kw: Any) -> tuple[FastAPI, Channel]:
    app = app or FastAPI()
    ch = Channel.boot(app, config=dev_config(**cfg_kw))
    return app, ch
