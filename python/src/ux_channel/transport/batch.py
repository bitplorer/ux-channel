"""
Batch dispatch — multiple Intents, one HTTP round-trip.

First principles
----------------
Dashboards often need several actions at once. Batch keeps **isolation**
(per-item Result, per-item cap) while sharing one POST.

Safety defaults (long-term)
--------------------------
- ``retry_retryable`` default **False**
- When retries are on, actions must be ``idempotent=True``
  (``retry_require_idempotent`` default True)
- Once-caps still consume on first verify — do not expect replay
- Envelope HTTP: 200 / 207 mixed / worst status / 413 oversize
- Retry-After on items overrides backoff (max mode)

See: docs/ERRORS.md (batch envelope, retry, Retry-After).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Mapping, Optional, Sequence

from ux_channel.transport.backoff import (
    BackoffPolicy,
    DEFAULT_MAX_MS as DEFAULT_BACKOFF_MAX_MS,
    delay_with_retry_after,
)
from ux_channel.protocol.error_map import enrich_batch_envelope, should_retry
from ux_channel.host.registry import ActionRegistry
from ux_channel.protocol.types import Intent, Result

DEFAULT_MAX_BATCH = 16
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_BACKOFF_MS = 50
MAX_RETRIES_CAP = 5  # hard ceiling per item


def _batch_want_parallel(
    n_items: int,
    *,
    stop_on_error: bool,
    parallel: bool | None,
    retry_retryable: bool,
) -> bool:
    """Batch item concurrency: opt-in, never with stop_on_error or retries."""
    if stop_on_error or retry_retryable:
        return False
    from ux_channel.transport.concurrency import get_concurrency_settings, should_parallelize

    s = get_concurrency_settings()
    flag = s.batch_parallel if parallel is None else bool(parallel)
    if not flag:
        return False
    return should_parallelize(n_items, parallel=True)



def _envelope_error(result: Result) -> dict[str, Any]:
    return enrich_batch_envelope(result.to_dict())


def action_allows_retry(
    registry: ActionRegistry,
    action_name: str,
    *,
    require_idempotent: bool = True,
) -> bool:
    """
    Whether automatic batch retry is allowed for this action.

    Long-term rule: only **idempotent** actions are auto-retried unless
    ``require_idempotent=False`` (escape hatch for tests / known-safe reads
    registered without the flag).
    """
    if not require_idempotent:
        return True
    return bool(getattr(registry, "is_idempotent", lambda _n: False)(action_name))


def item_is_retryable(result: Result) -> bool:
    """
    Whether a failed item Result is eligible for batch retry.

    Uses explicit ``error.retryable`` when set; otherwise ``should_retry(code)``.
    """
    if result.ok or not result.error:
        return False
    explicit = result.error.retryable
    if explicit is True:
        return True
    if explicit is False:
        return False
    return should_retry(result.error.code)


def _parse_intent(raw: Mapping[str, Any] | Intent) -> Intent:
    return Intent.from_dict(raw) if not isinstance(raw, Intent) else raw


def _clamp_retries(max_retries: int) -> int:
    try:
        n = int(max_retries)
    except (TypeError, ValueError):
        n = DEFAULT_MAX_RETRIES
    if n < 0:
        n = 0
    if n > MAX_RETRIES_CAP:
        n = MAX_RETRIES_CAP
    return n


def _attach_retry_meta(
    body: dict[str, Any],
    *,
    enabled: bool,
    max_retries: int,
    policy: BackoffPolicy,
    attempts: list[int],
    retried_indices: list[int],
    recovered: int,
    exhausted: int,
    delays_ms: list[list[float]],
    delay_details: Optional[list[list[dict]]] = None,
    retry_after_mode: str = "max",
) -> dict[str, Any]:
    env = enrich_batch_envelope(body)
    meta = dict(env.get("meta") or {})
    meta["retry"] = {
        "enabled": enabled,
        "max_retries": max_retries,
        "backoff": policy.to_meta(),
        # base delay (ms); also on policy.to_meta()
        "backoff_ms": policy.base_ms,
        "retry_after_mode": retry_after_mode,
        "attempts": attempts,
        "retried_indices": retried_indices,
        "recovered": recovered,
        "exhausted": exhausted,
        "delays_ms": delays_ms,
        "delay_details": delay_details or [],
    }
    env["meta"] = meta
    return env


async def dispatch_batch_async(
    registry: ActionRegistry,
    items: Sequence[Mapping[str, Any]],
    *,
    max_items: int = DEFAULT_MAX_BATCH,
    merge_ops: bool = True,
    stop_on_error: bool = False,
    retry_retryable: bool = False,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_ms: float = DEFAULT_RETRY_BACKOFF_MS,
    retry_backoff_max_ms: float = DEFAULT_BACKOFF_MAX_MS,
    retry_backoff_strategy: str = "fixed",
    retry_backoff_factor: float = 2.0,
    backoff_policy: Optional[BackoffPolicy] = None,
    retry_after_mode: str = "max",
    retry_require_idempotent: bool = True,
    parallel: bool | None = None,
    parallel_limit: int | None = None,
) -> dict[str, Any]:
    """
    Async batch dispatch with optional per-item retry for retryable failures.

    Retries require ``idempotent=True`` on the action (``retry_require_idempotent``).
    """
    policy = backoff_policy or BackoffPolicy.from_mapping(
        {
            "strategy": retry_backoff_strategy,
            "base_ms": retry_backoff_ms,
            "max_ms": retry_backoff_max_ms,
            "factor": retry_backoff_factor,
        }
    )
    if not items:
        return _attach_retry_meta(
            {"v": "1", "ok": True, "batch": [], "ops": []},
            enabled=retry_retryable,
            max_retries=_clamp_retries(max_retries),
            policy=policy,
            attempts=[],
            retried_indices=[],
            recovered=0,
            exhausted=0,
            delays_ms=[],
            delay_details=[],
            retry_after_mode=retry_after_mode,
        )
    if len(items) > max_items:
        return _envelope_error(
            Result.failure(
                "payload_too_large",
                f"batch size {len(items)} exceeds max {max_items}",
            )
        )

    retries = _clamp_retries(max_retries) if retry_retryable else 0

    results: list[Result] = []
    attempts: list[int] = []
    retried_indices: list[int] = []
    delays_all: list[list[float]] = []
    delay_details_all: list[list[dict]] = []
    recovered = 0
    exhausted = 0

    use_par = _batch_want_parallel(
        len(items),
        stop_on_error=stop_on_error,
        parallel=parallel,
        retry_retryable=retry_retryable,
    )
    if use_par:
        from ux_channel.transport.concurrency import get_concurrency_settings

        lim = parallel_limit
        if lim is None:
            lim = get_concurrency_settings().batch_parallel_limit
        sem = asyncio.Semaphore(max(1, int(lim)))

        async def _one(idx_raw):
            idx, raw = idx_raw
            intent = _parse_intent(raw)
            async with sem:
                return idx, await _dispatch_item_with_retry_async(
                    registry,
                    intent,
                    max_retries=retries,
                    policy=policy,
                    retry_enabled=retry_retryable,
                    retry_after_mode=retry_after_mode,
                    require_idempotent=retry_require_idempotent,
                )

        gathered = await asyncio.gather(*[_one(ir) for ir in enumerate(items)])
        gathered.sort(key=lambda x: x[0])
        for idx, (r, n_att, did_retry, rec, exh, delays, delay_details) in gathered:
            results.append(r)
            attempts.append(n_att)
            delays_all.append(delays)
            delay_details_all.append(delay_details)
            if did_retry:
                retried_indices.append(idx)
            if rec:
                recovered += 1
            if exh:
                exhausted += 1
    else:
        for idx, raw in enumerate(items):
            intent = _parse_intent(raw)
            r, n_att, did_retry, rec, exh, delays, delay_details = await _dispatch_item_with_retry_async(
                registry,
                intent,
                max_retries=retries,
                policy=policy,
                retry_enabled=retry_retryable,
                retry_after_mode=retry_after_mode,
                require_idempotent=retry_require_idempotent,
            )
            results.append(r)
            attempts.append(n_att)
            delays_all.append(delays)
            delay_details_all.append(delay_details)
            if did_retry:
                retried_indices.append(idx)
            if rec:
                recovered += 1
            if exh:
                exhausted += 1
            if not r.ok and stop_on_error:
                break

    merged: list[dict[str, Any]] = []
    if merge_ops:
        for r in results:
            merged.extend(list(r.ops))

    body: dict[str, Any] = {
        "v": "1",
        "ok": all(r.ok for r in results),
        "batch": [r.to_dict() for r in results],
    }
    if merge_ops:
        body["ops"] = merged
    return _attach_retry_meta(
        body,
        enabled=bool(retry_retryable),
        max_retries=retries,
        policy=policy,
        attempts=attempts,
        retried_indices=retried_indices,
        recovered=recovered,
        exhausted=exhausted,
        delays_ms=delays_all,
        delay_details=delay_details_all,
        retry_after_mode=retry_after_mode,
    )


def dispatch_batch(
    registry: ActionRegistry,
    items: Sequence[Mapping[str, Any]],
    *,
    max_items: int = DEFAULT_MAX_BATCH,
    merge_ops: bool = True,
    stop_on_error: bool = False,
    retry_retryable: bool = False,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_ms: float = DEFAULT_RETRY_BACKOFF_MS,
    retry_backoff_max_ms: float = DEFAULT_BACKOFF_MAX_MS,
    retry_backoff_strategy: str = "fixed",
    retry_backoff_factor: float = 2.0,
    backoff_policy: Optional[BackoffPolicy] = None,
    retry_after_mode: str = "max",
    retry_require_idempotent: bool = True,
    parallel: bool | None = None,
    parallel_limit: int | None = None,
) -> dict[str, Any]:
    """Sync batch with optional per-item retry for retryable failures."""
    policy = backoff_policy or BackoffPolicy.from_mapping(
        {
            "strategy": retry_backoff_strategy,
            "base_ms": retry_backoff_ms,
            "max_ms": retry_backoff_max_ms,
            "factor": retry_backoff_factor,
        }
    )
    if not items:
        return _attach_retry_meta(
            {"v": "1", "ok": True, "batch": [], "ops": []},
            enabled=retry_retryable,
            max_retries=_clamp_retries(max_retries),
            policy=policy,
            attempts=[],
            retried_indices=[],
            recovered=0,
            exhausted=0,
            delays_ms=[],
            delay_details=[],
            retry_after_mode=retry_after_mode,
        )
    if len(items) > max_items:
        return _envelope_error(
            Result.failure(
                "payload_too_large",
                f"batch size {len(items)} exceeds max {max_items}",
            )
        )

    retries = _clamp_retries(max_retries) if retry_retryable else 0

    results: list[Result] = []
    attempts: list[int] = []
    retried_indices: list[int] = []
    delays_all: list[list[float]] = []
    delay_details_all: list[list[dict]] = []
    recovered = 0
    exhausted = 0

    use_par = _batch_want_parallel(
        len(items),
        stop_on_error=stop_on_error,
        parallel=parallel,
        retry_retryable=retry_retryable,
    )
    if use_par:
        from concurrent.futures import ThreadPoolExecutor
        from ux_channel.transport.concurrency import get_concurrency_settings

        lim = parallel_limit
        if lim is None:
            lim = get_concurrency_settings().batch_parallel_limit
        lim = max(1, int(lim))

        def _one(idx_raw):
            idx, raw = idx_raw
            intent = _parse_intent(raw)
            return idx, _dispatch_item_with_retry_sync(
                registry,
                intent,
                max_retries=retries,
                policy=policy,
                retry_enabled=retry_retryable,
                retry_after_mode=retry_after_mode,
                require_idempotent=retry_require_idempotent,
            )

        with ThreadPoolExecutor(max_workers=min(lim, len(items)), thread_name_prefix="uxch-batch") as ex:
            gathered = list(ex.map(_one, list(enumerate(items))))
        gathered.sort(key=lambda x: x[0])
        for idx, (r, n_att, did_retry, rec, exh, delays, delay_details) in gathered:
            results.append(r)
            attempts.append(n_att)
            delays_all.append(delays)
            delay_details_all.append(delay_details)
            if did_retry:
                retried_indices.append(idx)
            if rec:
                recovered += 1
            if exh:
                exhausted += 1
    else:
        for idx, raw in enumerate(items):
            intent = _parse_intent(raw)
            r, n_att, did_retry, rec, exh, delays, delay_details = _dispatch_item_with_retry_sync(
                registry,
                intent,
                max_retries=retries,
                policy=policy,
                retry_enabled=retry_retryable,
                retry_after_mode=retry_after_mode,
                require_idempotent=retry_require_idempotent,
            )
            results.append(r)
            attempts.append(n_att)
            delays_all.append(delays)
            delay_details_all.append(delay_details)
            if did_retry:
                retried_indices.append(idx)
            if rec:
                recovered += 1
            if exh:
                exhausted += 1
            if not r.ok and stop_on_error:
                break

    merged: list[dict[str, Any]] = []
    if merge_ops:
        for r in results:
            merged.extend(list(r.ops))

    body: dict[str, Any] = {
        "v": "1",
        "ok": all(r.ok for r in results),
        "batch": [r.to_dict() for r in results],
    }
    if merge_ops:
        body["ops"] = merged
    return _attach_retry_meta(
        body,
        enabled=bool(retry_retryable),
        max_retries=retries,
        policy=policy,
        attempts=attempts,
        retried_indices=retried_indices,
        recovered=recovered,
        exhausted=exhausted,
        delays_ms=delays_all,
        delay_details=delay_details_all,
        retry_after_mode=retry_after_mode,
    )


def _dispatch_item_with_retry_sync(
    registry: ActionRegistry,
    intent: Intent,
    *,
    max_retries: int,
    policy: BackoffPolicy,
    retry_enabled: bool,
    retry_after_mode: str = "max",
    require_idempotent: bool = True,
) -> tuple[Result, int, bool, bool, bool, list[float], list[dict]]:
    """
    Returns (result, attempts, did_retry, recovered, exhausted, delays_ms, delay_details).

    ``max_retries`` = extra attempts after the first (0 = no retry).
    Wait = backoff policy, then **Retry-After override** from failed Result meta.
    Auto-retry only when action is idempotent (unless require_idempotent=False).
    """
    r = registry.dispatch(intent)
    attempts = 1
    did_retry = False
    recovered = False
    exhausted = False
    delays: list[float] = []
    details: list[dict] = []

    if not retry_enabled or max_retries <= 0:
        return r, attempts, did_retry, recovered, exhausted, delays, details

    while (
        not r.ok
        and item_is_retryable(r)
        and attempts <= max_retries
        and action_allows_retry(
            registry, intent.action, require_idempotent=require_idempotent
        )
    ):
        did_retry = True
        decision = delay_with_retry_after(
            attempts, r, policy=policy, retry_after_mode=retry_after_mode
        )
        wait_ms = float(decision["wait_ms"])
        delays.append(round(wait_ms, 3))
        details.append(decision)
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)
        r = registry.dispatch(intent)
        attempts += 1
        if r.ok:
            recovered = True
            return r, attempts, did_retry, recovered, exhausted, delays, details

    if did_retry and not r.ok and item_is_retryable(r):
        exhausted = True
    return r, attempts, did_retry, recovered, exhausted, delays, details


async def _dispatch_item_with_retry_async(
    registry: ActionRegistry,
    intent: Intent,
    *,
    max_retries: int,
    policy: BackoffPolicy,
    retry_enabled: bool,
    retry_after_mode: str = "max",
    require_idempotent: bool = True,
) -> tuple[Result, int, bool, bool, bool, list[float], list[dict]]:
    r = await registry.async_dispatch(intent)
    attempts = 1
    did_retry = False
    recovered = False
    exhausted = False
    delays: list[float] = []
    details: list[dict] = []

    if not retry_enabled or max_retries <= 0:
        return r, attempts, did_retry, recovered, exhausted, delays, details

    while (
        not r.ok
        and item_is_retryable(r)
        and attempts <= max_retries
        and action_allows_retry(
            registry, intent.action, require_idempotent=require_idempotent
        )
    ):
        did_retry = True
        decision = delay_with_retry_after(
            attempts, r, policy=policy, retry_after_mode=retry_after_mode
        )
        wait_ms = float(decision["wait_ms"])
        delays.append(round(wait_ms, 3))
        details.append(decision)
        if wait_ms > 0:
            await asyncio.sleep(wait_ms / 1000.0)
        r = await registry.async_dispatch(intent)
        attempts += 1
        if r.ok:
            recovered = True
            return r, attempts, did_retry, recovered, exhausted, delays, details

    if did_retry and not r.ok and item_is_retryable(r):
        exhausted = True
    return r, attempts, did_retry, recovered, exhausted, delays, details
