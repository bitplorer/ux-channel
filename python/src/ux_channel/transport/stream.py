"""SSE streaming of Result chunks — progressive apply for long actions.
Some actions (reports, multi-step dashboards) should update the UI **before**
the final answer: toast \"Working…\", then morph a panel, then toast \"Done\".
HTTP JSON returns one body; Server-Sent Events allow **ordered chunks** that
the client applies incrementally (see RESULT.md stream envelope).
Extends the protocol…"""

from __future__ import annotations

from ux_channel.protocol import serde as _serde

import json
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from ux_channel.protocol.types import PROTOCOL_VERSION, Result


@dataclass
class ResultStream:
    """
    Stateful helper that stamps chunk indices for a single action response.

    Designed for one request lifetime — create per action invocation.
    """

    chunk_index: int = 0
    uid: str = PROTOCOL_VERSION

    def chunk(
        self,
        result: Result,
        *,
        done: bool = False,
        merge: str = "append",
    ) -> dict[str, Any]:
        """
        Build a stream envelope dict for one SSE ``data:`` line.

        merge:
          - \"append\" — client concatenates ops (default)
          - \"replace\" — client replaces accumulated ops (rare)
        """
        env = {
            "uid": self.uid,
            "stream": True,
            "chunk": self.chunk_index,
            "merge": merge,
            "done": done,
            "result": result.to_dict(),
        }
        self.chunk_index += 1
        return env


def format_sse(
    envelope: dict[str, Any],
    *,
    event: Optional[str] = None,
    event_id: Optional[str] = None,
) -> bytes:
    """
    Encode one SSE message (including trailing blank line).

    Contributes: host-agnostic bytes you can yield from Starlette StreamingResponse.
    """
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    if event_id is not None:
        lines.append(f"id: {event_id}")
    data = _serde.dumps(envelope, default=str)
    # SSE: each data line; we use a single line JSON payload
    lines.append(f"data: {data}")
    lines.append("")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def iter_result_sse(
    results: Iterator[Result],
    *,
    final_done: bool = True,
) -> Iterator[bytes]:
    """
    Convenience: wrap an iterator of Result into SSE byte chunks.

    The last Result is marked done=True when final_done is set.
    """
    stream = ResultStream()
    items = list(results)
    for i, r in enumerate(items):
        done = final_done and (i == len(items) - 1)
        yield format_sse(stream.chunk(r, done=done))
