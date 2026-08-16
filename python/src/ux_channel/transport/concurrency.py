# Copyright (c) 2026 UX-CHANNEL
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
"""Internal parallel + concurrent dispatch for **ux-channel**.

**Application code should not tune this for application work.**
Use ``registry.dispatch`` / HTTP / regions. Parallelism, bulkheads, and batch
ordering are library-internal safety defaults.

Maintainer tools: :mod:`ux_channel.profiling` and ``scripts/profile_p95.py``.
"""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional, Sequence, Union

from ux_channel.transport.batch import (  # noqa: F401
    DEFAULT_MAX_BATCH,
    dispatch_batch,
    dispatch_batch_async,
)
from ux_channel.security.bulkhead import (  # noqa: F401
    ConcurrencyLimiter,
    bulkhead_after_hook,
    bulkhead_hook,
    install_bulkhead,
)
from ux_channel.protocol.types import Intent, Result

__all__ = [
    "ConcurrencySettings",
    "configure_concurrency",
    "get_concurrency_settings",
    "reset_concurrency_settings",
    "should_parallelize",
    "default_workers",
    "dispatch_parallel",
    "dispatch_parallel_async",
    "map_dispatch",
    "ConcurrencyLimiter",
    "install_bulkhead",
    "bulkhead_hook",
    "bulkhead_after_hook",
    "dispatch_batch",
    "dispatch_batch_async",
    "DEFAULT_MAX_BATCH",
]

IntentLike = Union[Intent, Mapping[str, Any]]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: Optional[int]) -> Optional[int]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class ConcurrencySettings:
    """Process-level concurrency policy for ux-channel."""

    parallel_enabled: bool = True
    max_workers: Optional[int] = None
    min_items_for_parallel: int = 2
    batch_parallel: bool = False  # opt-in: concurrent items inside batch
    batch_parallel_limit: int = 8
    max_in_flight: Optional[int] = None  # None = no auto bulkhead

    @classmethod
    def from_env(cls) -> "ConcurrencySettings":
        return cls(
            parallel_enabled=_env_bool("UX_CHANNEL_PARALLEL", True),
            max_workers=_env_int("UX_CHANNEL_MAX_WORKERS", None),
            min_items_for_parallel=max(
                1, _env_int("UX_CHANNEL_PARALLEL_MIN_ITEMS", 2) or 2
            ),
            batch_parallel=_env_bool("UX_CHANNEL_BATCH_PARALLEL", False),
            batch_parallel_limit=max(
                1, _env_int("UX_CHANNEL_BATCH_PARALLEL_LIMIT", 8) or 8
            ),
            max_in_flight=_env_int("UX_CHANNEL_MAX_IN_FLIGHT", None),
        )


_SETTINGS = ConcurrencySettings.from_env()
_SETTINGS_GUARD = threading.RLock()


def get_concurrency_settings() -> ConcurrencySettings:
    with _SETTINGS_GUARD:
        return _SETTINGS


def configure_concurrency(
    *,
    parallel_enabled: Optional[bool] = None,
    max_workers: Optional[int] = None,
    min_items_for_parallel: Optional[int] = None,
    batch_parallel: Optional[bool] = None,
    batch_parallel_limit: Optional[int] = None,
    max_in_flight: Optional[int] = None,
) -> ConcurrencySettings:
    """Opt-in / opt-out parallel behaviour; returns effective settings."""
    global _SETTINGS
    with _SETTINGS_GUARD:
        cur = _SETTINGS
        _SETTINGS = replace(
            cur,
            parallel_enabled=cur.parallel_enabled
            if parallel_enabled is None
            else bool(parallel_enabled),
            max_workers=cur.max_workers if max_workers is None else max_workers,
            min_items_for_parallel=cur.min_items_for_parallel
            if min_items_for_parallel is None
            else max(1, int(min_items_for_parallel)),
            batch_parallel=cur.batch_parallel
            if batch_parallel is None
            else bool(batch_parallel),
            batch_parallel_limit=cur.batch_parallel_limit
            if batch_parallel_limit is None
            else max(1, int(batch_parallel_limit)),
            max_in_flight=cur.max_in_flight if max_in_flight is None else max_in_flight,
        )
        return _SETTINGS


def reset_concurrency_settings() -> ConcurrencySettings:
    global _SETTINGS
    with _SETTINGS_GUARD:
        _SETTINGS = ConcurrencySettings.from_env()
        return _SETTINGS


def default_workers() -> int:
    s = get_concurrency_settings()
    if s.max_workers is not None:
        return max(1, min(32, int(s.max_workers)))
    n = os.cpu_count() or 4
    return max(2, min(32, n))


def should_parallelize(
    n_items: int,
    *,
    max_workers: Optional[int] = None,
    parallel: Optional[bool] = None,
) -> bool:
    s = get_concurrency_settings()
    enabled = s.parallel_enabled if parallel is None else bool(parallel)
    if not enabled:
        return False
    workers = max_workers if max_workers is not None else s.max_workers
    if workers is not None and int(workers) <= 1:
        return False
    if n_items < s.min_items_for_parallel or n_items <= 1:
        return False
    return True


def dispatch_parallel(
    registry: Any,
    intents: Sequence[IntentLike],
    *,
    max_workers: Optional[int] = None,
    principal: Any = None,
    parallel: Optional[bool] = None,
) -> list[Result]:
    """Dispatch many Intents — parallel when policy allows, else sequential."""
    if not intents:
        return []

    def one(raw: IntentLike) -> Result:
        try:
            return registry.dispatch(raw, principal=principal)
        except Exception as exc:  # pragma: no cover
            return Result.failure(
                "internal",
                f"parallel dispatch error: {exc}",
                retryable=True,
            )

    if not should_parallelize(len(intents), max_workers=max_workers, parallel=parallel):
        return [one(it) for it in intents]

    workers = max_workers if max_workers is not None else min(default_workers(), len(intents))
    workers = max(1, int(workers))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="uxch-par") as ex:
        futs = [ex.submit(one, it) for it in intents]
        return [f.result() for f in futs]


async def dispatch_parallel_async(
    registry: Any,
    intents: Sequence[IntentLike],
    *,
    limit: Optional[int] = None,
    principal: Any = None,
    parallel: Optional[bool] = None,
) -> list[Result]:
    """Async dispatch many Intents — concurrent when policy allows."""
    if not intents:
        return []

    async def one(raw: IntentLike) -> Result:
        try:
            return await registry.async_dispatch(raw, principal=principal)
        except Exception as exc:  # pragma: no cover
            return Result.failure(
                "internal",
                f"parallel async dispatch error: {exc}",
                retryable=True,
            )

    if not should_parallelize(len(intents), parallel=parallel):
        out: list[Result] = []
        for it in intents:
            out.append(await one(it))
        return out

    s = get_concurrency_settings()
    eff_limit = limit if limit is not None else s.batch_parallel_limit
    sem: Optional[asyncio.Semaphore] = None
    if eff_limit is not None and int(eff_limit) > 0:
        sem = asyncio.Semaphore(int(eff_limit))

    async def gated(raw: IntentLike) -> Result:
        if sem is None:
            return await one(raw)
        async with sem:
            return await one(raw)

    return list(await asyncio.gather(*[gated(it) for it in intents]))


def map_dispatch(
    registry: Any,
    action: str,
    args_list: Sequence[Mapping[str, Any]],
    *,
    max_workers: Optional[int] = None,
    principal: Any = None,
    request_id_prefix: str = "par",
    parallel: Optional[bool] = None,
) -> list[Result]:
    intents: list[Intent] = []
    for i, args in enumerate(args_list):
        intents.append(
            Intent(
                action=action,
                args=dict(args or {}),
                request_id=f"{request_id_prefix}-{i}",
            )
        )
    return dispatch_parallel(
        registry,
        intents,
        max_workers=max_workers,
        principal=principal,
        parallel=parallel,
    )
