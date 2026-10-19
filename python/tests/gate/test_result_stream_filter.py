"""SSE results go through the same outbound filter as dispatch and push.

A stream with no policy is strict: a swap must not keep ``onerror``, and a
``javascript:`` href must not be delivered.
"""

from __future__ import annotations

import json

from ux_channel import Result, swap
from ux_channel.transport.stream import ResultStream, format_sse, iter_result_sse

_HTML = '<img src="x" onerror="alert(1)">'


def _result() -> Result:
    return Result.success(
        swap("#t", _HTML),
        {
            "op": "set_attr",
            "target": "#a",
            "attrs": {"href": "javascript:alert(1)", "class": "keep"},
        },
    )


def _assert_clean(blob: str) -> None:
    assert "onerror" not in blob.lower()
    assert "javascript:" not in blob.lower()
    assert "keep" in blob


def test_result_stream_chunk_filters_outbound_ops() -> None:
    chunk = ResultStream().chunk(_result())
    _assert_clean(json.dumps(chunk["result"]))


def test_format_sse_filters_outbound_ops() -> None:
    envelope = {"result": _result().to_dict()}
    text = format_sse(envelope).decode("utf-8")
    _assert_clean(text)
    # The caller's envelope is not rewritten.
    assert "onerror" in json.dumps(envelope).lower()


def test_format_sse_filters_a_bare_result() -> None:
    """A Result with no channel and no ``result`` wrapper is still strict."""
    bare = _result().to_dict()
    text = format_sse(bare).decode("utf-8")
    _assert_clean(text)
    assert "onerror" in json.dumps(bare).lower()


def test_format_sse_filters_a_result_object() -> None:
    """``{"result": Result}`` is filtered the same way as ``Result.to_dict()``."""
    result = _result()
    text = format_sse({"result": result}).decode("utf-8")
    _assert_clean(text)


def test_iter_result_sse_filters_outbound_ops() -> None:
    text = b"".join(iter_result_sse([_result()])).decode("utf-8")
    _assert_clean(text)
