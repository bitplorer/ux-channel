"""Backoff strategies for retries (batch, clients, workers).
WHY
---
Fixed sleep is fine for one retry; under load (rate_limited / unavailable)
many clients retrying on the same schedule create **retry storms**.
Exponential + jitter spreads load.
STRATEGIES
``fixed``
    Always ``base_ms``. Simple, predictable. Default for batch (low max_retries).
``linear``"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional

BackoffStrategy = Literal[
    "fixed",
    "linear",
    "exponential",
    "exponential_full_jitter",
    "exponential_equal_jitter",
]

STRATEGY_ALIASES: dict[str, BackoffStrategy] = {
    "fixed": "fixed",
    "const": "fixed",
    "constant": "fixed",
    "linear": "linear",
    "exp": "exponential",
    "exponential": "exponential",
    "exponential_jitter": "exponential_full_jitter",
    "full_jitter": "exponential_full_jitter",
    "exponential_full_jitter": "exponential_full_jitter",
    "equal_jitter": "exponential_equal_jitter",
    "exponential_equal_jitter": "exponential_equal_jitter",
}

DEFAULT_STRATEGY: BackoffStrategy = "fixed"
DEFAULT_BASE_MS = 50.0
DEFAULT_MAX_MS = 5_000.0
DEFAULT_FACTOR = 2.0


def normalize_strategy(name: str | None) -> BackoffStrategy:
    if not name:
        return DEFAULT_STRATEGY
    key = str(name).strip().lower().replace("-", "_")
    return STRATEGY_ALIASES.get(key, DEFAULT_STRATEGY)


def compute_backoff_ms(
    attempt: int,
    *,
    strategy: str | BackoffStrategy = DEFAULT_STRATEGY,
    base_ms: float = DEFAULT_BASE_MS,
    max_ms: float = DEFAULT_MAX_MS,
    factor: float = DEFAULT_FACTOR,
    rng: Optional[random.Random] = None,
) -> float:
    """
    Milliseconds to wait **before** the next try.

    ``attempt`` is 1-based count of failures so far (1 = after first failure,
    before second dispatch). Values < 1 are treated as 1.
    """
    strat = normalize_strategy(str(strategy) if strategy is not None else None)
    base = max(0.0, float(base_ms or 0))
    cap = max(base, float(max_ms or base or DEFAULT_MAX_MS))
    fac = float(factor) if factor and float(factor) > 1 else DEFAULT_FACTOR
    n = int(attempt) if attempt else 1
    if n < 1:
        n = 1

    if base <= 0:
        return 0.0

    if strat == "fixed":
        return min(base, cap)

    if strat == "linear":
        return min(base * n, cap)

    # exponential family
    exp = base * (fac ** (n - 1))
    exp = min(exp, cap)

    if strat == "exponential":
        return exp

    r = rng.random() if rng is not None else random.random()

    if strat == "exponential_full_jitter":
        # U(0, exp)
        return exp * r

    if strat == "exponential_equal_jitter":
        # exp/2 + U(0, exp/2)
        return (exp / 2.0) + (exp / 2.0) * r

    return min(base, cap)


@dataclass
class BackoffPolicy:
    """Reusable policy object for batch / workers / tests."""

    strategy: BackoffStrategy = DEFAULT_STRATEGY
    base_ms: float = DEFAULT_BASE_MS
    max_ms: float = DEFAULT_MAX_MS
    factor: float = DEFAULT_FACTOR
    rng: Optional[random.Random] = None

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> "BackoffPolicy":
        data = dict(data or {})
        data.update(kwargs)
        return cls(
            strategy=normalize_strategy(data.get("strategy") or data.get("retry_backoff_strategy")),
            base_ms=float(
                data.get("base_ms", data.get("retry_backoff_ms", DEFAULT_BASE_MS)) or 0
            ),
            max_ms=float(
                data.get("max_ms", data.get("retry_backoff_max_ms", DEFAULT_MAX_MS))
                or DEFAULT_MAX_MS
            ),
            factor=float(data.get("factor", data.get("retry_backoff_factor", DEFAULT_FACTOR)) or DEFAULT_FACTOR),
        )

    def delay_ms(self, attempt: int) -> float:
        return compute_backoff_ms(
            attempt,
            strategy=self.strategy,
            base_ms=self.base_ms,
            max_ms=self.max_ms,
            factor=self.factor,
            rng=self.rng,
        )

    def delay_s(self, attempt: int) -> float:
        return self.delay_ms(attempt) / 1000.0

    def to_meta(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "base_ms": self.base_ms,
            "max_ms": self.max_ms,
            "factor": self.factor,
        }


# Retry-After (RFC 7231) override
# When a Result or HTTP response carries Retry-After, clients and batch retry
# MUST NOT wait less than that interval. Policy:
#   - If Retry-After present → wait = max(computed_backoff_ms, retry_after_ms)
#     (never retry *sooner* than the server asked; may wait longer if exp grows)
#   - mode="replace" → wait = retry_after_ms only (strict server schedule)
# Default mode for batch: "max" (safer under mixed policies).

from email.utils import parsedate_to_datetime
from datetime import datetime, timezone


def parse_retry_after(value: Any) -> Optional[float]:
    """
    Parse Retry-After header or meta value → seconds (≥ 0), or None.

    Accepts:
      - int / float seconds
      - digit string "120"
      - HTTP-date (RFC 7231)
    """
    if value is None or value is False:
        return None
    if isinstance(value, (int, float)):
        sec = float(value)
        return max(0.0, sec) if sec == sec else None  # NaN guard
    s = str(value).strip()
    if not s:
        return None
    # delta-seconds
    if s.isdigit() or (s.replace(".", "", 1).isdigit() and s.count(".") < 2):
        try:
            return max(0.0, float(s))
        except ValueError:
            pass
    # HTTP-date
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        sec = (dt - now).total_seconds()
        return max(0.0, sec)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def extract_retry_after_s(result: Any) -> Optional[float]:
    """
    Pull retry-after seconds from a Result / Result-dict.

    Looks at (first hit wins):
      meta.retry_after, meta.retry_after_s, meta["Retry-After"]
      error.details.retry_after (if details is mapping)
    """
    meta = None
    err = None
    if hasattr(result, "meta"):
        meta = getattr(result, "meta", None) or {}
        err = getattr(result, "error", None)
    elif isinstance(result, Mapping):
        meta = result.get("meta") or {}
        err = result.get("error")
    else:
        return None

    if isinstance(meta, Mapping):
        for key in ("retry_after", "retry_after_s", "Retry-After", "retry-after"):
            if key in meta and meta[key] is not None:
                parsed = parse_retry_after(meta[key])
                if parsed is not None:
                    return parsed

    details = None
    if err is not None:
        details = getattr(err, "details", None) if not isinstance(err, Mapping) else err.get("details")
    if isinstance(details, Mapping):
        for key in ("retry_after", "retry_after_s", "Retry-After"):
            if key in details and details[key] is not None:
                parsed = parse_retry_after(details[key])
                if parsed is not None:
                    return parsed
    return None


def apply_retry_after_override(
    computed_ms: float,
    retry_after_s: Optional[float],
    *,
    mode: str = "max",
) -> tuple[float, bool]:
    """
    Combine computed backoff with Retry-After seconds.

    Returns (wait_ms, used_override).

    mode:
      - ``max``     — max(computed, retry_after*1000)  [default]
      - ``replace`` — retry_after*1000 when present
      - ``min``     — min(computed, retry_after*1000) when both > 0 (rarely useful)
    """
    computed = max(0.0, float(computed_ms or 0))
    if retry_after_s is None:
        return computed, False
    ra_ms = max(0.0, float(retry_after_s) * 1000.0)
    m = (mode or "max").lower()
    if m == "replace":
        return ra_ms, True
    if m == "min":
        if computed <= 0:
            return ra_ms, True
        if ra_ms <= 0:
            return computed, False
        return min(computed, ra_ms), True
    # max (default)
    return max(computed, ra_ms), True


def delay_with_retry_after(
    attempt: int,
    result: Any = None,
    *,
    policy: Optional[BackoffPolicy] = None,
    strategy: str = DEFAULT_STRATEGY,
    base_ms: float = DEFAULT_BASE_MS,
    max_ms: float = DEFAULT_MAX_MS,
    factor: float = DEFAULT_FACTOR,
    retry_after_mode: str = "max",
    rng: Optional[random.Random] = None,
) -> dict[str, Any]:
    """
    Full wait decision for one retry step.

    Returns dict: computed_ms, retry_after_s, wait_ms, override, strategy.
    """
    if policy is not None:
        computed = policy.delay_ms(attempt)
        strat = policy.strategy
    else:
        computed = compute_backoff_ms(
            attempt,
            strategy=strategy,
            base_ms=base_ms,
            max_ms=max_ms,
            factor=factor,
            rng=rng,
        )
        strat = normalize_strategy(strategy)
    ra = extract_retry_after_s(result) if result is not None else None
    wait, used = apply_retry_after_override(computed, ra, mode=retry_after_mode)
    # still honor policy max_ms as hard ceiling unless Retry-After is larger
    # (server said wait longer → allow it; don't clamp below RA)
    if policy is not None:
        cap = float(policy.max_ms or DEFAULT_MAX_MS)
    else:
        cap = float(max_ms or DEFAULT_MAX_MS)
    if ra is None and wait > cap:
        wait = cap
    elif ra is not None and not used:
        wait = min(wait, cap)
    # When override with large RA, do not clamp below RA
    if ra is not None and used:
        wait = max(wait, ra * 1000.0)
    return {
        "computed_ms": round(computed, 3),
        "retry_after_s": ra,
        "wait_ms": round(wait, 3),
        "override": used,
        "strategy": strat,
        "mode": retry_after_mode,
    }
