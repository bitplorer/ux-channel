"""Minimal channel factories used by multiple suites."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

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


VISITOR = "visitor-1"


@contextmanager
def as_visitor(subject: str = VISITOR) -> Iterator[None]:
    """Session reads and writes as ``subject``, outside a dispatch.

    Inside a dispatch the registry binds the dispatched Cap's own subject.
    """
    from ux_channel.host.context import VerifiedContext, _verified

    token = _verified.set(VerifiedContext.from_claims({"action": "test", "subject": subject}))
    try:
        yield
    finally:
        _verified.reset(token)


def visitor_caller(ch: Channel, subject: str = VISITOR) -> None:
    """Every request to ``ch`` is from ``subject``: Caps minted ``sub=subject`` run."""
    from ux_channel import Principal

    ch.registry.auth_resolver = lambda request: Principal(id=subject)
