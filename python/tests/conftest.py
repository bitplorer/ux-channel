"""Shared fixtures for the uxchannel suite.

Collection order is controlled by ``tool.pytest.ini_options.testpaths``
(ontological packages, core → stress).
"""
from __future__ import annotations

import pytest

# Ensure helpers importable as tests.helpers.*
_pytest_plugins_disabled: list[str] = []


@pytest.fixture
def secret() -> str:
    return "test-secret-key-32-chars-minimum!!"
