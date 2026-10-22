"""Shared fixtures for the uxchannel suite.

Collection order is controlled by ``tool.pytest.ini_options.testpaths``
(ontological packages, core → stress).
"""
from __future__ import annotations

import gc

import pytest

# Ensure helpers importable as tests.helpers.*
_pytest_plugins_disabled: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_push_bus():
    """Drop process push-bus state between tests.

    FastAPI caches each mounted endpoint, so a ``Channel.boot`` app stays
    reachable after the test that created it. Owner tracking would then see
    every past boot as live and ``get_push_bus()`` would raise. Two channels
    booted inside one test are still live together and still raise.
    """
    from ux_channel.transport import push as push_mod

    def _wipe() -> None:
        push_mod._bus = None
        push_mod._owners.clear()
        gc.collect()

    _wipe()
    yield
    _wipe()


@pytest.fixture(autouse=True)
def _isolate_revocation_list():
    """Drop the process ticket revocation list between tests.

    ``create_channel(redis_url=...)`` installs a Redis-backed list. Ticket
    verify fails closed when that store is unreachable, so it must not leak.
    """
    from ux_channel.devtools import ticket_revoke

    ticket_revoke._list = None
    yield
    ticket_revoke._list = None


@pytest.fixture
def secret() -> str:
    return "test-secret-key-32-chars-minimum!!"
