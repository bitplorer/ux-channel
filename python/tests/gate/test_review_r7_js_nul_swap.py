"""NUL in a swapped href or src must not come out as U+FFFD plus javascript:.

On bf6f6ef, html5lib rewrote U+0000 to U+FFFD and the scheme check did
not see ``javascript:``. ``swap_a`` leaked in both modes. ``swap_iframe``
leaked in off mode; strict already dropped the iframe element.
"""

from __future__ import annotations

import pytest

from gate.test_server_refused_vectors import _deliver

_KEEP = "KEEP-NUL"
_TRANSPORTS = ("json", "sse", "push", "ws", "mcp", "redis", "format_sse")
_VECTORS: tuple[tuple[str, str], ...] = (
    ("swap_a", f'<a href="\x00javascript:alert(1)">t</a><b>{_KEEP}</b>'),
    (
        "swap_iframe",
        f'<iframe src="\x00javascript:alert(1)"></iframe><b>{_KEEP}</b>',
    ),
)


@pytest.mark.parametrize("policy", ("off", "strict"))
@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize(("name", "html"), _VECTORS, ids=[item[0] for item in _VECTORS])
def test_nul_scheme_is_removed_from_the_swap(
    policy: str, transport: str, name: str, html: str
) -> None:
    blob = _deliver(policy, transport, html)
    assert _KEEP in blob, (policy, transport, name)
    assert "\ufffd" not in blob, (policy, transport, name, blob)
    assert "javascript:" not in blob.lower(), (policy, transport, name, blob)
