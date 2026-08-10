"""Property-based tests for CapService (Hypothesis) — Rust-parity law."""
from __future__ import annotations

import json

import pytest
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from ux_channel.protocol.capability import CapError, CapService

SECRET = "hypothesis-cap-secret-32chars-min!!"
settings.register_profile(
    "cap_props",
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("cap_props")

_json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10**6), max_value=10**6),
    st.text(max_size=24),
)
_args = st.dictionaries(
    st.from_regex(r"[a-z][a-z0-9_]{0,10}", fullmatch=True),
    _json_scalars,
    max_size=6,
)
_action = st.from_regex(r"[A-Za-z][A-Za-z0-9_.]{0,24}", fullmatch=True)


@given(args=_args)
def test_hash_args_deterministic(args):
    h1 = CapService.hash_args(args)
    h2 = CapService.hash_args(args)
    assert h1 == h2
    assert len(h1) == 32


@given(args=_args)
def test_hash_args_key_order_independent(args):
    # rebuild with reverse insertion order
    rev = {k: args[k] for k in reversed(list(args.keys()))}
    assert CapService.hash_args(args) == CapService.hash_args(rev)


@given(action=_action, args=_args)
def test_mint_verify_roundtrip(action, args):
    svc = CapService(SECRET)
    tok = svc.mint(action, args)
    svc.verify(tok, action, args)


@given(action=_action, other=_action, args=_args)
def test_verify_rejects_wrong_action(action, other, args):
    assume(action != other)
    svc = CapService(SECRET)
    tok = svc.mint(action, args)
    with pytest.raises(CapError):
        svc.verify(tok, other, args)


@given(action=_action, args=_args, extra=st.from_regex(r"[a-z]{3,8}", fullmatch=True))
def test_verify_rejects_tampered_args(action, args, extra):
    assume(extra not in args)
    svc = CapService(SECRET)
    tok = svc.mint(action, args)
    bad = dict(args)
    bad[extra] = 1
    with pytest.raises(CapError):
        svc.verify(tok, action, bad)


def test_oracle_vector_hash():
    """Frozen conformance hash (same as Rust)."""
    args = {"sku": "abc-123", "qty": 2}
    assert CapService.hash_args(args) == "96e4f83e3793b646323a67f314b51044"
