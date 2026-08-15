"""Top-20 first-week failures go through explain() with a fix."""

from __future__ import annotations

from ux_channel.devtools.explain import TEACH, explain_code

REQUIRED = {
    "unauthorized",
    "missing_capability",
    "capability_expired",
    "invalid_capability",
    "cap_mismatch",
    "unsigned_args",
    "validation",
    "not_found",
    "missing_scripts",
    "rate_limited",
    "forbidden",
    "conflict",
    "unavailable",
    "memory_stores",
    "short_secret",
    "require_cap_false",
    "open_sfu_token",
    "sfu_not_configured",
    "rtc_ticket",
    "origin",
}


def test_top20_catalog():
    missing = REQUIRED - set(TEACH)
    assert not missing, missing
    assert len(TEACH) >= 20


def test_each_entry_names_a_fix():
    for code in REQUIRED:
        out = explain_code(code)
        assert out["teach"], code
        assert out["cli"], code
