"""Shared fixtures for monorepo Python gate tests."""
from __future__ import annotations

import pytest

DEV_SECRET = "dev-secret-key-32chars-minimum!!!!"
ORACLE_SECRET = "conformance-oracle-secret-32chars!!"


@pytest.fixture
def secret() -> str:
    return DEV_SECRET


@pytest.fixture
def oracle_secret() -> str:
    return ORACLE_SECRET
