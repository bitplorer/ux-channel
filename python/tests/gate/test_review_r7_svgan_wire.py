"""p28 and the six SVG animate/set vectors, on every transport.

Off mode on bf6f6ef kept ``javascript:`` in the consumer output. Strict
already sent none. Both modes must now send none, including the MCP
resource stream.
"""

from __future__ import annotations

import pytest

from gate.test_server_refused_vectors import _deliver
from gate.test_strict_html_payloads import PAYLOADS

_KEEP = "KEEP-SVG"
_TRANSPORTS = ("json", "sse", "push", "ws", "mcp", "redis", "format_sse")

# Payload 28 is the review list entry. The six svgan shapes are the other
# animate/set URL forms that off mode on bf6f6ef left intact.
_VECTORS: tuple[tuple[str, str], ...] = (
    ("p28", PAYLOADS[27]),
    (
        "svgan-animate-href",
        '<svg><animate attributeName="href" values="javascript:alert(1)"></animate></svg>',
    ),
    (
        "svgan-set-href",
        '<svg><set attributeName="href" to="javascript:alert(1)"></set></svg>',
    ),
    (
        "svgan-animate-xlink",
        '<svg><animate attributeName="xlink:href" values="javascript:alert(1)"></animate></svg>',
    ),
    (
        "svgan-set-xlink",
        '<svg><set attributeName="xlink:href" to="javascript:alert(1)"></set></svg>',
    ),
    (
        "svgan-animate-from",
        '<svg><animate attributeName="fill" from="javascript:alert(1)"></animate></svg>',
    ),
    (
        "svgan-motion",
        '<svg><animateMotion to="javascript:alert(1)"></animateMotion></svg>',
    ),
)


def _javascript_messages(blob: str) -> list[str]:
    """Consumer messages that still contain a script scheme.

    SSE, push, MCP, Redis, and ``format_sse`` are ``data:`` lines. JSON and
    WebSocket are one body.
    """
    data = [line for line in blob.splitlines() if line.startswith("data:")]
    messages = data if data else [blob]
    return [item for item in messages if "javascript:" in item.lower()]


@pytest.mark.parametrize("policy", ("off", "strict"))
@pytest.mark.parametrize("transport", _TRANSPORTS)
@pytest.mark.parametrize(("name", "html"), _VECTORS, ids=[item[0] for item in _VECTORS])
def test_animate_vector_sends_no_javascript(
    policy: str, transport: str, name: str, html: str
) -> None:
    blob = _deliver(policy, transport, html + f"<b>{_KEEP}</b>")
    assert _KEEP in blob, (policy, transport, name)
    hits = _javascript_messages(blob)
    assert hits == [], (policy, transport, name, hits)
