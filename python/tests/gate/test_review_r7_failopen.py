"""A to_dict failure and a nested SSE envelope fail closed.

``_filter_one`` and ``_as_op_dict`` used to return the original op when
``to_dict`` raised. Nested ``format_sse`` shapes used to skip the filter
that the top-level ``result`` gets.
"""

from __future__ import annotations

import json
import logging

import pytest

from ux_channel.render.morph_policy import _filter_one, apply_morph_policy
from ux_channel.security.security import _as_op_dict, filter_outbound_ops
from ux_channel.transport.stream import format_sse

_HTML = '<img src="x" onerror="alert(1)"><b>KEEP-SSE</b>'


class _Boom:
    def to_dict(self) -> dict:
        raise RuntimeError("to_dict")


def test_filter_one_to_dict_failure_refuses_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="ux_channel.render.morph_policy"):
        out = _filter_one(_Boom(), lambda html: html)
        ops = apply_morph_policy([_Boom()], policy="off")
    assert out["op"] == "noop"
    assert ops[0]["op"] == "noop"
    assert "onerror" not in json.dumps(ops).lower()
    assert any(
        r.levelno >= logging.ERROR and "to_dict" in r.getMessage()
        for r in caplog.records
    )


def test_as_op_dict_failure_refuses_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="ux_channel.security.security"):
        out = _as_op_dict(_Boom())
        ops = filter_outbound_ops([_Boom()], policy="strict")
    assert isinstance(out, dict)
    assert out["op"] == "noop"
    assert ops[0]["op"] == "noop"
    assert "onerror" not in json.dumps(ops).lower()
    assert any(
        r.levelno >= logging.ERROR and "to_dict" in r.getMessage()
        for r in caplog.records
    )


def _shapes() -> list[dict]:
    op = {"op": "swap", "target": "#t", "html": _HTML, "swap": "innerHTML"}
    return [
        {"result": {"result": {"ok": True, "ops": [op]}}},
        {"events": [{"ops": [op]}]},
        {"data": {"ops": [op]}},
    ]


@pytest.mark.parametrize("policy", ("off", "strict"))
@pytest.mark.parametrize("shape", ("nested-result", "events", "data"))
def test_format_sse_filters_nested_ops(policy: str, shape: str) -> None:
    envelope = _shapes()[{"nested-result": 0, "events": 1, "data": 2}[shape]]
    original = json.dumps(envelope)
    text = format_sse(envelope, policy=policy).decode("utf-8")
    assert "onerror" not in text.lower()
    assert "KEEP-SSE" in text
    assert json.dumps(envelope) == original
