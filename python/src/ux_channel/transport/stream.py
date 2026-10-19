"""SSE streaming of Result chunks — progressive apply for long actions.
Some actions (reports, multi-step dashboards) should update the UI **before**
the final answer: toast \"Working…\", then morph a panel, then toast \"Done\".
HTTP JSON returns one body; Server-Sent Events allow **ordered chunks** that
the client applies incrementally (see RESULT.md stream envelope).
Extends the protocol…"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Optional

from ux_channel.protocol import serde as _serde
from ux_channel.protocol.types import PROTOCOL_VERSION, Result
from ux_channel.security.security import filter_outbound_ops


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
        policy: str | None = None,
        allowed_hosts: tuple[str, ...] | list[str] | None = None,
        origin_host: str | None = None,
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
            "result": _filter_result_body(
                result.to_dict(),
                policy=policy,
                allowed_hosts=allowed_hosts,
                origin_host=origin_host,
            ),
        }
        self.chunk_index += 1
        return env


def resolve_stream_policy(policy: str | None) -> str:
    """A stream with no channel (``policy is None``) is strict.

    A channel passes ``off`` or ``strict`` exactly. Anything else raises.
    """
    if policy is None:
        return "strict"
    if policy not in ("off", "strict"):
        raise ValueError('morph_html_policy must be "off" or "strict"')
    return policy


def _filter_result_body(
    body: dict[str, Any],
    *,
    policy: str | None,
    allowed_hosts: tuple[str, ...] | list[str] | None,
    origin_host: str | None = None,
) -> dict[str, Any]:
    """Href-check and strict-strip ``result.ops``. No channel policy is strict."""
    ops = body.get("ops")
    if not isinstance(ops, list):
        return body
    cleaned = dict(body)
    cleaned["ops"] = filter_outbound_ops(
        list(ops),
        policy=resolve_stream_policy(policy),
        allowed_hosts=allowed_hosts,
        origin_host=origin_host,
    )
    return cleaned


def _filter_sse_tree(
    node: Any,
    *,
    policy: str | None,
    allowed_hosts: tuple[str, ...] | list[str] | None,
    origin_host: str | None,
) -> Any:
    """Copy ``node`` and filter every ``ops`` list, including nested ones.

    The caller's object is not rewritten. A dict or list that is not an op
    envelope is still walked, so ``result.result.ops``, ``events[].ops``,
    and ``data.ops`` get the same filter as a top-level result.
    """
    if isinstance(node, Result):
        node = node.to_dict()
    if isinstance(node, dict):
        out = {
            key: _filter_sse_tree(
                value,
                policy=policy,
                allowed_hosts=allowed_hosts,
                origin_host=origin_host,
            )
            for key, value in node.items()
        }
        ops = out.get("ops")
        if isinstance(ops, list):
            out["ops"] = filter_outbound_ops(
                list(ops),
                policy=resolve_stream_policy(policy),
                allowed_hosts=allowed_hosts,
                origin_host=origin_host,
            )
        return out
    if isinstance(node, list):
        return [
            _filter_sse_tree(
                item,
                policy=policy,
                allowed_hosts=allowed_hosts,
                origin_host=origin_host,
            )
            for item in node
        ]
    return node


def format_sse(
    envelope: dict[str, Any],
    *,
    event: Optional[str] = None,
    event_id: Optional[str] = None,
    policy: str | None = None,
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
    origin_host: str | None = None,
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
    payload = _filter_sse_tree(
        envelope,
        policy=policy,
        allowed_hosts=allowed_hosts,
        origin_host=origin_host,
    )
    data = _serde.dumps(payload, default=str)
    # SSE: each data line; we use a single line JSON payload
    lines.append(f"data: {data}")
    lines.append("")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def iter_result_sse(
    results: Iterator[Result],
    *,
    final_done: bool = True,
    policy: str | None = None,
    allowed_hosts: tuple[str, ...] | list[str] | None = None,
    origin_host: str | None = None,
) -> Iterator[bytes]:
    """
    Convenience: wrap an iterator of Result into SSE byte chunks.

    The last Result is marked done=True when final_done is set.
    """
    stream = ResultStream()
    items = list(results)
    for i, r in enumerate(items):
        done = final_done and (i == len(items) - 1)
        yield format_sse(
            stream.chunk(
                r,
                done=done,
                policy=policy,
                allowed_hosts=allowed_hosts,
                origin_host=origin_host,
            ),
            policy=policy,
            allowed_hosts=allowed_hosts,
            origin_host=origin_host,
        )
