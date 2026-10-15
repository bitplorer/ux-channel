"""Redis backends for multi-worker production."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Optional

from ux_channel.host.idempotency import IdempotencyCapacityError
from ux_channel.protocol import serde as _serde


def _client(url: str | Any):
    if not isinstance(url, str):
        return url
    try:
        import redis  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "redis package required: pip install 'ux-channel[redis]'"
        ) from exc
    return redis.Redis.from_url(url, decode_responses=True)


class RedisRateLimiter:
    """
    Token-bucket-ish rate limiter using Redis INCR + EXPIRE window.

    Simple fixed window per minute (not perfect token bucket) — good enough
    for multi-worker API protection.
    """

    def __init__(
        self,
        redis_url: str | Any,
        *,
        rate_per_minute: float = 120,
        burst: float = 30,
        prefix: str = "uidch:rl:",
    ):
        self.r = _client(redis_url)
        self.rate = max(1, int(rate_per_minute + burst))  # window budget
        self.prefix = prefix

    def allow(self, key: str, *, cost: float = 1.0) -> bool:
        import time

        window = int(time.time() // 60)
        rkey = f"{self.prefix}{key}:{window}"
        n = self.r.incrby(rkey, int(cost))
        if n == int(cost):
            self.r.expire(rkey, 120)
        return n <= self.rate


class RedisNonceStore:
    def __init__(self, redis_url: str | Any, *, prefix: str = "uidch:nonce:"):
        self.r = _client(redis_url)
        self.prefix = prefix

    def use_once(self, key: str, *, ttl_s: float = 3600) -> bool:
        rkey = f"{self.prefix}{key}"
        try:
            # SET NX EX — atomic consume. Connection/store failure refuses
            # (fail closed) rather than allowing a once-cap replay.
            ok = self.r.set(rkey, "1", nx=True, ex=int(ttl_s))
            return bool(ok)
        except Exception:
            return False


# In-flight reservation. Not a stored Result. ``get`` hides it.
# The token is appended so compare-and-delete / compare-and-set need no JSON parser.
_PENDING_PREFIX = "uxidem:v1:pending:"

# SET NX reserves. The ZSET score is the expiry second. Sweep with
# ZREMRANGEBYSCORE before counting. No per-member EXISTS.
_IDEM_CLAIM_LUA = """
local key = KEYS[1]
local index = KEYS[2]
local payload = ARGV[1]
local ttl = tonumber(ARGV[2])
local max_keys = tonumber(ARGV[3])
local pending_prefix = ARGV[4]
local raw = redis.call('GET', key)
if raw then
  local n = string.len(pending_prefix)
  if string.sub(raw, 1, n) == pending_prefix then
    return {'pending', ''}
  end
  return {'hit', raw}
end
local now_s = tonumber(redis.call('TIME')[1])
redis.call('ZREMRANGEBYSCORE', index, '-inf', now_s)
local count = redis.call('ZCARD', index)
if count >= max_keys then
  return {'full', ''}
end
local ok = redis.call('SET', key, payload, 'NX', 'EX', ttl)
if not ok then
  raw = redis.call('GET', key)
  if not raw then
    return {'pending', ''}
  end
  local n = string.len(pending_prefix)
  if string.sub(raw, 1, n) == pending_prefix then
    return {'pending', ''}
  end
  return {'hit', raw}
end
redis.call('ZADD', index, now_s + ttl, key)
return {'reserved', ''}
"""

# Compare-and-delete. A missing or different token leaves the slot alone.
_IDEM_RELEASE_LUA = """
local key = KEYS[1]
local index = KEYS[2]
local token = ARGV[1]
local pending_prefix = ARGV[2]
if token == '' then
  return 0
end
local raw = redis.call('GET', key)
if not raw then
  return 0
end
if raw ~= (pending_prefix .. token) then
  return 0
end
redis.call('DEL', key)
redis.call('ZREM', index, key)
return 1
"""

# Compare-and-set. -1 not owner, -2 lost claim, -3 full, 0 left a finished
# result alone, 1 wrote.
_IDEM_SET_LUA = """
local key = KEYS[1]
local index = KEYS[2]
local token = ARGV[1]
local payload = ARGV[2]
local ttl = tonumber(ARGV[3])
local max_keys = tonumber(ARGV[4])
local pending_prefix = ARGV[5]
local raw = redis.call('GET', key)
local pending_n = string.len(pending_prefix)
local is_pending = raw
  and string.sub(raw, 1, pending_n) == pending_prefix
if is_pending then
  if token == '' or raw ~= (pending_prefix .. token) then
    return -1
  end
  local now_s = tonumber(redis.call('TIME')[1])
  redis.call('SET', key, payload, 'EX', ttl)
  redis.call('ZADD', index, now_s + ttl, key)
  return 1
end
if token ~= '' then
  if raw then
    return 0
  end
  return -2
end
if raw then
  redis.call('SET', key, payload, 'KEEPTTL')
  return 1
end
local now_s = tonumber(redis.call('TIME')[1])
redis.call('ZREMRANGEBYSCORE', index, '-inf', now_s)
local count = redis.call('ZCARD', index)
if count >= max_keys then
  return -3
end
redis.call('SET', key, payload, 'EX', ttl)
redis.call('ZADD', index, now_s + ttl, key)
return 1
"""


def _idem_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    return str(value)


def _idem_seconds(ttl_s: float) -> int:
    """Whole seconds. Redis EX rejects 0, so a shorter window is one second."""
    seconds = int(ttl_s)
    return seconds if seconds >= 1 else 1


def _idem_index(prefix: str) -> str:
    """Capacity ZSET. Same hash tag as the data key: ``{prefix}``."""
    return "{" + prefix + "}.cap"


def _idem_pair(reply: Any) -> tuple[str, str]:
    if not isinstance(reply, (list, tuple)) or len(reply) < 2:
        raise RuntimeError("idempotency store returned an unexpected reply")
    return _idem_text(reply[0]), _idem_text(reply[1])


def _idem_code(reply: Any) -> int:
    if isinstance(reply, bool):
        return int(reply)
    if isinstance(reply, (bytes, bytearray)):
        reply = reply.decode("utf-8")
    return int(reply)


class RedisIdempotencyStore:
    """Shared idempotency map for workers on one Redis.

    ``claim`` reserves with ``SET NX`` and an in-flight sentinel plus a
    token. ``release`` and ``set`` change that slot only when the token
    matches. ``get`` hides the sentinel. A new key past ``max_keys`` raises
    ``IdempotencyCapacityError`` instead of dropping a live one.

    Residuals. ``max_keys`` is one cap for the whole prefix, not a cap per
    principal. Deploy every worker on this store together: a rolling mix is
    unsafe, because an old worker's ``get`` does not hide the pending
    sentinel and fails when it reads one. Expiry uses Redis ``EX``, which
    has whole-second granularity.
    """

    def __init__(
        self,
        redis_url: str | Any,
        *,
        prefix: str = "uidch:idem:",
        max_keys: int = 50_000,
    ):
        self.r = _client(redis_url)
        self.prefix = prefix
        self.max_keys = max_keys

    def _redis_key(self, key: str) -> str:
        # Hash tag matches ``_idem_index`` so the script stays in one slot.
        return "{" + self.prefix + "}" + key

    def _legacy_key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def _finished(self, raw: Any) -> Optional[dict[str, Any]]:
        if not raw:
            return None
        text = _idem_text(raw)
        if text.startswith(_PENDING_PREFIX):
            return None
        body = _serde.loads(text)
        if not isinstance(body, dict):
            return None
        return body

    def get(self, key: str) -> Optional[dict]:
        raw = self.r.get(self._redis_key(key))
        if raw:
            text = _idem_text(raw)
            if text.startswith(_PENDING_PREFIX):
                return None
            return _serde.loads(text)
        return self._finished(self.r.get(self._legacy_key(key)))

    def claim(
        self, key: str, *, ttl_s: float = 3600
    ) -> tuple[str, Optional[dict[str, Any]], Optional[str]]:
        """Reserve ``key`` before the handler runs.

        Returns ``("hit", result, None)``, ``("pending", None, None)``, or
        ``("reserved", None, token)``. Only that token may release or
        finish the slot.
        """
        token = uuid.uuid4().hex
        # Legacy names are untagged, so they must not enter this script.
        if not self.r.get(self._redis_key(key)):
            legacy = self._finished(self.r.get(self._legacy_key(key)))
            if legacy is not None:
                return "hit", legacy, None
        reply = self.r.eval(
            _IDEM_CLAIM_LUA,
            2,
            self._redis_key(key),
            _idem_index(self.prefix),
            f"{_PENDING_PREFIX}{token}",
            str(_idem_seconds(ttl_s)),
            str(int(self.max_keys)),
            _PENDING_PREFIX,
        )
        status, raw = _idem_pair(reply)
        if status == "reserved":
            return "reserved", None, token
        if status == "pending":
            return "pending", None, None
        if status == "full":
            raise IdempotencyCapacityError(self.max_keys)
        if status == "hit":
            body = _serde.loads(raw)
            if not isinstance(body, dict):
                raise RuntimeError("idempotency hit was not an object")
            return "hit", body, None
        raise RuntimeError("idempotency claim returned an unexpected reply")

    def release(self, key: str, token: str | None = None) -> None:
        """Drop this call's in-flight reservation.

        A missing or different token does not touch the slot, so a nested
        dispatch cannot release the reservation its parent still owns.
        """
        if not token:
            return
        self.r.eval(
            _IDEM_RELEASE_LUA,
            2,
            self._redis_key(key),
            _idem_index(self.prefix),
            token,
            _PENDING_PREFIX,
        )

    def set(
        self,
        key: str,
        result: dict,
        *,
        ttl_s: float = 3600,
        token: str | None = None,
    ) -> None:
        """Store ``result`` for ``key``.

        A pending claim is overwritten only when ``token`` is the token
        ``claim`` returned. A different token, or a direct ``set`` with no
        token, leaves the pending claim and raises. A token does not
        replace a finished result. ``set`` without a token inserts a
        missing key. On a finished key it replaces the body and keeps the
        existing TTL and capacity score (``KEEPTTL``).
        """
        reply = self.r.eval(
            _IDEM_SET_LUA,
            2,
            self._redis_key(key),
            _idem_index(self.prefix),
            token or "",
            _serde.dumps(result, default=str),
            str(_idem_seconds(ttl_s)),
            str(int(self.max_keys)),
            _PENDING_PREFIX,
        )
        code = _idem_code(reply)
        if code in (0, 1):
            return
        if code == -1:
            raise RuntimeError("idempotency set does not own the pending claim")
        if code == -2:
            raise RuntimeError("idempotency set lost its pending claim")
        if code == -3:
            raise IdempotencyCapacityError(self.max_keys)
        raise RuntimeError("idempotency set returned an unexpected reply")


class RedisPushBackend:
    """
    Multi-worker push via Redis pub/sub.

    Local subscribers receive messages from a background listener thread
    that redistributes to asyncio queues (best-effort).
    """

    def __init__(
        self,
        redis_url: str | Any,
        *,
        channel_prefix: str = "uidch:push:",
        soft_fail: bool = True,
    ):
        from ux_channel.redis_extra.resilience import ResilientRedis

        self._rr = ResilientRedis(redis_url, soft_fail=soft_fail)
        self.r = None  # filled on first use
        try:
            self.r = self._rr.client()
        except Exception:
            self.r = None
        self.prefix = channel_prefix
        self._local: dict = {}  # topic -> set of queues
        self._lock = __import__("threading").Lock()
        self._pubsub = None
        self._thread: threading.Thread | None = None
        self._started = False
        self._soft_fail = soft_fail
        self._redis_topics: set[str] = set()

    def _ch(self, topic: str) -> str:
        return f"{self.prefix}{topic}"

    def publish(self, topic: str, payload: dict) -> int:
        import json

        def _pub(r: Any) -> int:
            return int(r.publish(self._ch(topic), _serde.dumps(payload, default=str)) or 0)

        n = self._rr.execute(_pub, default=0)
        with self._lock:
            qs = list(self._local.get(topic, ()))
            listener_alive = self._thread is not None and self._thread.is_alive()
            # This process is subscribed on Redis, so the listener echoes the
            # publish back. A second local put would deliver the push twice.
            echo = (
                topic in self._redis_topics
                and self._started
                and self._pubsub is not None
                and listener_alive
                and int(n or 0) > 0
            )
        if echo:
            return int(n)
        for q in qs:
            try:
                q.put_nowait(payload)
            except Exception:
                pass
        return int(n) if n else len(qs)

    def subscribe_local(self, topic: str, queue):
        with self._lock:
            self._local.setdefault(topic, set()).add(queue)
        self._ensure_listener()
        # subscribe redis channel
        if self._pubsub is not None:
            self._pubsub.subscribe(self._ch(topic))
            with self._lock:
                self._redis_topics.add(topic)

    def unsubscribe_local(self, topic: str, queue):
        with self._lock:
            if topic in self._local:
                self._local[topic].discard(queue)
                if not self._local[topic]:
                    del self._local[topic]

    def _ensure_listener(self):
        if self._started:
            return
        self._started = True
        import threading, json
        try:
            self.r = self._rr.client()
        except Exception:
            self._started = False
            return
        self._pubsub = self.r.pubsub(ignore_subscribe_messages=True)

        def loop():
            while True:
                try:
                    msg = self._pubsub.get_message(timeout=1.0)
                    if not msg or msg.get("type") != "message":
                        continue
                    ch = msg.get("channel")
                    if isinstance(ch, bytes):
                        ch = ch.decode()
                    topic = ch[len(self.prefix):] if ch and ch.startswith(self.prefix) else ch
                    data = _serde.loads(msg["data"])
                    with self._lock:
                        qs = list(self._local.get(topic, ()))
                    for q in qs:
                        try:
                            q.put_nowait(data)
                        except Exception:
                            pass
                except Exception:
                    pass

        self._thread = threading.Thread(target=loop, name="ux-redis-push", daemon=True)
        self._thread.start()


def RedisPushBus(redis_url: str | Any, **kwargs):
    from ux_channel.transport.push import PushBus
    return PushBus(RedisPushBackend(redis_url, **kwargs))


__all__ = [
    "RedisRateLimiter",
    "RedisNonceStore",
    "RedisIdempotencyStore",
    "RedisPushBackend",
    "RedisPushBus",
    "RedisIntentLog"]


class RedisStateStore:
    """
    Multi-worker region state (JSON values).

    ::

        ch = Channel.boot(app, redis_url=os.environ["REDIS_URL"])
        # ch.state is RedisStateStore when redis available
    """

    def __init__(self, redis_url: str | Any, *, prefix: str = "uidch:state:", default_ttl_s: int = 0):
        self.r = _client(redis_url)
        self.prefix = prefix
        self.default_ttl_s = int(default_ttl_s or 0)

    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def get(self, key: str, default: Any = None) -> Any:
        import json
        import copy

        raw = self.r.get(self._k(key))
        if raw is None:
            return copy.deepcopy(default)
        return _serde.loads(raw)

    def set(self, key: str, value: Any) -> None:
        import json

        payload = _serde.dumps(value, default=str)
        if self.default_ttl_s > 0:
            self.r.set(self._k(key), payload, ex=self.default_ttl_s)
        else:
            self.r.set(self._k(key), payload)

    def delete(self, key: str) -> None:
        self.r.delete(self._k(key))

    def patch(self, key: str, updates: dict, *, default: Any = None) -> Any:
        """Merge under WATCH/MULTI (retry). Safer than bare get→set."""
        return self.update(
            key,
            lambda base: {**(base if isinstance(base, dict) else {}), **dict(updates)},
            default=default if default is not None else {},
        )

    def change(self, key: str, mutator: Any, *, default: Any = None) -> Any:
        return self.update(key, mutator, default=default)

    def merge(self, key: str, updates: dict, *, default: Any = None) -> Any:
        return self.patch(key, updates, default=default)


    def edit(self, key: str, *, default: Any = None):
        """
        Sync/async context manager (same ``EditSlot`` as memory).

        CAS is content-based: commit fails with ``StateConflict`` if the Redis
        value changed since enter. ``async with`` uses the same path (sync
        Redis client); await only yields the event loop between enter/exit.
        """
        import copy
        import json

        from ux_channel.host.stores import EditSlot, StateConflict

        k = self._k(key)
        raw = self.r.get(k)
        if raw is None:
            value = copy.deepcopy(default)
            expected: Any = None
        else:
            if isinstance(raw, bytes):
                raw_s = raw.decode("utf-8")
            else:
                raw_s = str(raw)
            value = _serde.loads(raw_s)
            expected = raw_s

        store = self

        class _Backend:
            def _cas_set(self, _key: str, _ver: int, new_value: Any) -> None:
                import time

                payload = _serde.dumps(new_value, default=str)
                for attempt in range(16):
                    try:
                        store.r.watch(k)
                        cur = store.r.get(k)
                        if cur is None:
                            cur_s = None
                        elif isinstance(cur, bytes):
                            cur_s = cur.decode("utf-8")
                        else:
                            cur_s = str(cur)
                        if cur_s != expected:
                            raise StateConflict(
                                f"redis state key {key!r} changed during edit; retry"
                            )
                        pipe = store.r.pipeline(True)
                        pipe.multi()
                        if store.default_ttl_s > 0:
                            pipe.set(k, payload, ex=store.default_ttl_s)
                        else:
                            pipe.set(k, payload)
                        pipe.execute()
                        return
                    except StateConflict:
                        try:
                            store.r.unwatch()
                        except Exception:
                            pass
                        raise
                    except Exception as exc:
                        name = type(exc).__name__
                        if "WatchError" in name:
                            time.sleep(0.001 * (attempt + 1))
                            continue
                        try:
                            store.r.unwatch()
                        except Exception:
                            pass
                        raise
                    finally:
                        try:
                            store.r.unwatch()
                        except Exception:
                            pass
                raise StateConflict(f"redis state key {key!r} CAS retries exhausted")

            async def _acas_set(self, _key: str, _ver: int, new_value: Any) -> None:
                # Redis client is sync; run CAS off the event loop if possible.
                import asyncio

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._cas_set(_key, _ver, new_value))

        return EditSlot(key=key, value=value, _store=_Backend(), _version=0, _default=default)


    def update(self, key: str, mutator: Any, *, default: Any = None) -> Any:
        """
        Optimistic lock RMW via Redis WATCH/MULTI (up to 16 retries).

        For very hot keys prefer a Lua script in the app; this covers common drafts.
        """
        import copy
        import json
        import time

        k = self._k(key)
        for attempt in range(16):
            try:
                self.r.watch(k)
                raw = self.r.get(k)
                if raw is None:
                    current = copy.deepcopy(default)
                else:
                    current = _serde.loads(raw)
                new = mutator(current)
                payload = _serde.dumps(new, default=str)
                pipe = self.r.pipeline(True)
                pipe.multi()
                if self.default_ttl_s > 0:
                    pipe.set(k, payload, ex=self.default_ttl_s)
                else:
                    pipe.set(k, payload)
                pipe.execute()
                return copy.deepcopy(new)
            except Exception as exc:
                # WatchError name varies with client
                name = type(exc).__name__
                if name in ("WatchError", "WatchErrorError") or "WatchError" in name:
                    time.sleep(0.001 * (attempt + 1))
                    continue
                try:
                    self.r.unwatch()
                except Exception:
                    pass
                raise
            finally:
                try:
                    self.r.unwatch()
                except Exception:
                    pass
        # last resort non-atomic
        current = self.get(key, default=default)
        new = mutator(current)
        self.set(key, new)
        return copy.deepcopy(new)

    def incr(self, key: str, delta: float = 1, *, default: float = 0) -> float:
        def _mut(cur: Any) -> Any:
            base = default if cur is None else cur
            try:
                nxt = float(base) + float(delta)
            except (TypeError, ValueError) as exc:
                raise TypeError(
                    f"RedisStateStore.incr expects numeric at {key!r}"
                ) from exc
            if isinstance(base, int) and isinstance(delta, int) and not isinstance(delta, bool):
                return int(base) + int(delta)
            return nxt

        return self.update(key, _mut, default=default)


# WebRTC multi-worker signaling


_ADMIT_PEER_LUA = """
local key = KEYS[1]
local peer = ARGV[1]
local maxp = tonumber(ARGV[2])
local payload = ARGV[3]
local ttl = tonumber(ARGV[4])
if redis.call('HEXISTS', key, peer) == 0 then
  if redis.call('HLEN', key) >= maxp then
    return 0
  end
end
redis.call('HSET', key, peer, payload)
if ttl ~= nil and ttl > 0 then
  redis.call('EXPIRE', key, ttl)
end
return 1
"""

# Compare-and-delete one peer. KEYS: peers hash, inbox list.
# ARGV: peer id, conn id. Optional whitespace around the JSON colon so both
# compact and spaced engines match. Returns 1 when this conn deleted the peer.
_LEAVE_IF_CONN_LUA = """
local key = KEYS[1]
local inbox = KEYS[2]
local peer = ARGV[1]
local conn = ARGV[2]
local raw = redis.call('HGET', key, peer)
if not raw then
  return 0
end
local found = string.match(raw, '"conn_id"%s*:%s*"([^"]*)"')
if found ~= conn then
  return 0
end
redis.call('HDEL', key, peer)
redis.call('DEL', inbox)
return 1
"""


class RedisRtcStore:
    """
    Shared WebRTC signaling store for multi-worker deploys.

    Layout (TTL via EXPIRE on keys)::

        uidch:rtc:seq                 → INCR signal ids
        uidch:rtc:peers:{room}        → HASH peer_id → JSON {name, last_seen}
        uidch:rtc:inbox:{room}:{peer} → LIST JSON signals (capped)
        pubsub uidch:rtc:fan:{room}:{peer} → live WS fanout across workers

    Install: ``pip install 'ux-channel[redis]'`` and set ``REDIS_URL`` /
    ``ChannelConfig.redis_url``. Enable with ``webrtc_use_redis=True`` (default
    when redis_url is set).
    """

    def __init__(
        self,
        redis_url: str | Any,
        *,
        peer_ttl_s: float = 30.0,
        signal_ttl_s: float = 60.0,
        max_peers: int = 8,
        prefix: str = "uidch:rtc:",
        inbox_max: int = 200,
    ):
        self.r = _client(redis_url)
        self.peer_ttl_s = peer_ttl_s
        self.signal_ttl_s = signal_ttl_s
        self.max_peers = max_peers
        self.prefix = prefix
        self.inbox_max = inbox_max
        # local WS queues still process-local; redis pubsub bridges workers
        self._subs: dict[str, dict[str, list]] = {}
        self._lock = __import__("threading").RLock()
        self._pubsub_thread: threading.Thread | None = None
        self._start_pubsub()

    def _pk(self, room: str) -> str:
        return f"{self.prefix}peers:{room}"

    def _ik(self, room: str, peer: str) -> str:
        return f"{self.prefix}inbox:{room}:{peer}"

    def _fan_ch(self, room: str, peer: str) -> str:
        return f"{self.prefix}fan:{room}:{peer}"

    def _start_pubsub(self) -> None:
        import json
        
        def loop() -> None:
            pub = self.r.pubsub(ignore_subscribe_messages=True)
            # pattern subscribe all fan channels
            pub.psubscribe(f"{self.prefix}fan:*")
            for msg in pub.listen():
                if msg is None or msg.get("type") not in ("pmessage", "message"):
                    continue
                try:
                    data = _serde.loads(msg["data"])
                except Exception:
                    continue
                room = data.get("room") or ""
                peer = data.get("to") or data.get("peer") or ""
                with self._lock:
                    for q in list((self._subs.get(room) or {}).get(peer) or []):
                        try:
                            q.put_nowait(data.get("message") or data)
                        except Exception:
                            pass

        self._pubsub_thread = threading.Thread(
            target=loop, name="ux-redis-rtc", daemon=True
        )
        self._pubsub_thread.start()

    def _gc_room(self, room: str) -> None:
        import json
        import time

        now = time.time()
        key = self._pk(room)
        raw = self.r.hgetall(key) or {}
        for pid, blob in list(raw.items()):
            try:
                rec = _serde.loads(blob)
                if now - float(rec.get("last_seen") or 0) > self.peer_ttl_s:
                    self.r.hdel(key, pid)
            except Exception:
                self.r.hdel(key, pid)

    def _roster(self, room: str) -> list[dict[str, str]]:
        import json

        raw = self.r.hgetall(self._pk(room)) or {}
        out = []
        for pid, blob in raw.items():
            try:
                rec = _serde.loads(blob)
                out.append({"id": pid, "name": str(rec.get("name") or "")})
            except Exception:
                out.append({"id": pid, "name": ""})
        out.sort(key=lambda x: x["id"])
        return out

    def _admit_peer(self, key: str, peer_id: str, payload: str, ttl_s: int) -> bool:
        """Atomic check-and-set. False when admitting a new peer would exceed max."""
        try:
            ok = self.r.eval(
                _ADMIT_PEER_LUA,
                1,
                key,
                peer_id,
                str(int(self.max_peers)),
                payload,
                str(int(ttl_s)),
            )
            return int(ok) == 1
        except Exception:
            with self._lock:
                exists = bool(self.r.hexists(key, peer_id))
                if not exists and int(self.r.hlen(key) or 0) >= self.max_peers:
                    return False
                self.r.hset(key, peer_id, payload)
                if ttl_s > 0:
                    self.r.expire(key, int(ttl_s))
                return True

    def poll(
        self,
        room: str,
        peer_id: str,
        *,
        name: str = "",
        since: int = 0,
        conn_id: str | None = None,
    ) -> dict[str, Any]:
        import json
        import time

        room = str(room or "default")[:64]
        peer_id = str(peer_id or "")[:64]
        if not peer_id:
            raise ValueError("peer_id required")
        self._gc_room(room)
        key = self._pk(room)
        now = time.time()
        prev = {}
        if self.r.hexists(key, peer_id):
            try:
                prev = _serde.loads(self.r.hget(key, peer_id) or "{}")
            except Exception:
                prev = {}
        kept_conn = prev.get("conn_id") or ""
        rec = {
            "name": (name or prev.get("name") or "")[:64],
            "last_seen": now,
            "conn_id": conn_id if conn_id is not None else kept_conn,
        }
        ttl = int(self.peer_ttl_s * 3)
        if not self._admit_peer(key, peer_id, _serde.dumps(rec), ttl):
            raise OverflowError(f"room full (max {self.max_peers} peers)")
        roster = self._roster(room)
        # drain inbox after since
        ik = self._ik(room, peer_id)
        raw_list = self.r.lrange(ik, 0, -1) or []
        inbox = []
        for blob in raw_list:
            try:
                s = _serde.loads(blob)
            except Exception:
                continue
            if int(s.get("id") or 0) > int(since):
                inbox.append(
                    {
                        "id": s["id"],
                        "from": s.get("from"),
                        "kind": s.get("kind"),
                        "payload": s.get("payload"),
                    }
                )
        inbox.sort(key=lambda x: x["id"])
        # publish roster to others (best-effort)
        for p in roster:
            if p["id"] != peer_id:
                self._publish(
                    room,
                    p["id"],
                    {"type": "roster", "peers": roster, "room": room, "to": p["id"]},
                )
        return {
            "ok": True,
            "room": room,
            "peer": peer_id,
            "peers": roster,
            "signals": inbox,
            "server_time": now,
        }

    def signal(
        self,
        room: str,
        *,
        from_peer: str,
        to_peer: str,
        kind: str,
        payload: Any,
    ) -> dict[str, Any]:
        import json
        import time

        room = str(room or "default")[:64]
        from_peer = str(from_peer or "")[:64]
        to_peer = str(to_peer or "")[:64]
        kind = (kind or "").lower().strip()
        if kind not in ("offer", "answer", "ice", "ice-done"):
            raise ValueError("kind must be offer|answer|ice|ice-done")
        if not from_peer or not to_peer:
            raise ValueError("from/to required")
        from ux_channel.realtime.webrtc import validate_signal_payload

        payload = validate_signal_payload(kind, payload)
        sid = int(self.r.incr(f"{self.prefix}seq"))
        rec = {
            "id": sid,
            "from": from_peer,
            "kind": kind,
            "payload": payload,
            "ts": time.time(),
        }
        ik = self._ik(room, to_peer)
        self.r.rpush(ik, _serde.dumps(rec, default=str))
        self.r.ltrim(ik, -self.inbox_max, -1)
        self.r.expire(ik, int(self.signal_ttl_s * 2))
        msg = {
            "type": "signal",
            "id": sid,
            "from": from_peer,
            "kind": kind,
            "payload": payload,
            "room": room,
            "to": to_peer,
        }
        self._publish(room, to_peer, msg)
        # local fanout
        with self._lock:
            for q in list((self._subs.get(room) or {}).get(to_peer) or []):
                try:
                    q.put_nowait(msg)
                except Exception:
                    pass
        return {"ok": True, "id": sid}

    def _conn_still_here(self, raw: Any, conn_id: str) -> bool:
        if not raw:
            return False
        try:
            rec = _serde.loads(raw)
        except Exception:
            return False
        return str(rec.get("conn_id") or "") == conn_id

    def _leave_if_conn(self, key: str, peer_id: str, conn_id: str, inbox: str) -> bool:
        """Delete the peer only when its stored conn_id is still ``conn_id``.

        The Lua script is atomic. If ``EVAL`` is unavailable, ``WATCH`` /
        ``MULTI`` retries the compare-and-delete. A changed key aborts the
        transaction.

        Known residual: after eight aborted watches the fallback gives up,
        reports stale, and does not delete. The peer stays in the room until
        its TTL. A busy room can outrun this fallback. The Lua path does not
        have that limit.
        """
        try:
            deleted = self.r.eval(
                _LEAVE_IF_CONN_LUA, 2, key, inbox, peer_id, conn_id
            )
            return int(deleted) == 1
        except Exception:
            pass
        # redis is an optional extra; this module already loads it lazily.
        from redis.exceptions import WatchError

        for _attempt in range(8):
            pipe = self.r.pipeline()
            try:
                pipe.watch(key)
                raw = self.r.hget(key, peer_id)
                if not self._conn_still_here(raw, conn_id):
                    pipe.unwatch()
                    return False
                # The first read can return a value a replace has already
                # overwritten. Confirm before the transaction.
                again = self.r.hget(key, peer_id)
                if not self._conn_still_here(again, conn_id):
                    pipe.unwatch()
                    return False
                pipe.multi()
                pipe.hdel(key, peer_id)
                pipe.delete(inbox)
                executed = pipe.execute()
                if not executed:
                    continue
                return True
            except WatchError:
                continue
            except Exception:
                return False
            finally:
                try:
                    pipe.reset()
                except Exception:
                    pass
        return False

    def leave(
        self, room: str, peer_id: str, conn_id: str | None = None
    ) -> dict[str, Any]:
        room = str(room or "default")[:64]
        peer_id = str(peer_id or "")[:64]
        key = self._pk(room)
        inbox = self._ik(room, peer_id)
        if conn_id is not None:
            if not self._leave_if_conn(key, peer_id, conn_id, inbox):
                return {"ok": True, "stale": True}
        else:
            # HTTP leave has no conn_id and still removes the peer.
            self.r.hdel(key, peer_id)
            self.r.delete(inbox)
        roster = self._roster(room)
        for p in roster:
            self._publish(
                room,
                p["id"],
                {
                    "type": "peer_left",
                    "peer": peer_id,
                    "peers": roster,
                    "room": room,
                    "to": p["id"],
                },
            )
        return {"ok": True}

    def subscribe(self, room: str, peer_id: str, q: Any) -> None:
        with self._lock:
            self._subs.setdefault(room, {}).setdefault(peer_id, []).append(q)

    def unsubscribe(self, room: str, peer_id: str, q: Any) -> None:
        with self._lock:
            lst = (self._subs.get(room) or {}).get(peer_id) or []
            if q in lst:
                lst.remove(q)

    def _publish(self, room: str, peer: str, message: dict) -> None:
        import json

        try:
            self.r.publish(
                self._fan_ch(room, peer),
                _serde.dumps(
                    {"room": room, "to": peer, "message": message},
                    default=str,
                ),
            )
        except Exception:
            pass


__all__ = [
    "RedisRateLimiter",
    "RedisNonceStore",
    "RedisIdempotencyStore",
    "RedisPushBackend",
    "RedisPushBus",
    "RedisStateStore",
    "RedisRtcStore"]


class RedisIntentLog:
    """
    Multi-worker intent log (JSON entries in a Redis list).

    Soft-fails to an in-process buffer when Redis is unavailable
    (``soft_fail=True``, default).
    """

    def __init__(
        self,
        redis_url: str | Any,
        *,
        prefix: str = "uidch:ilog:",
        maxlen: int = 10_000,
        soft_fail: bool = True,
    ) -> None:
        from ux_channel.redis_extra.resilience import ResilientRedis

        self._rr = ResilientRedis(redis_url, soft_fail=soft_fail)
        self.prefix = prefix
        self.maxlen = max(100, int(maxlen))
        self._seq_key = f"{prefix}seq"
        self._list_key = f"{prefix}entries"
        self._soft_fail = soft_fail
        self._local_fallback: list = []
        self._local_seq = 0
        self._lock = threading.Lock()

    def append(
        self,
        intent: Any,
        result: Any,
        *,
        principal: str | None = None,
    ) -> Any:
        import json
        import time

        from ux_channel.devtools.intent_log import IntentLogEntry
        from ux_channel.protocol.types import Intent

        if isinstance(intent, Intent):
            action = intent.action
            args = intent.args or {}
            rid = intent.request_id
        else:
            action = str(intent.get("action", "?"))
            args = dict(intent.get("args") or {})
            rid = intent.get("request_id")
        ops = tuple(
            str(o.get("op", "?"))
            for o in (getattr(result, "ops", None) or [])
            if isinstance(o, dict)
        )
        err = None
        if not getattr(result, "ok", True) and getattr(result, "error", None) is not None:
            e = result.error
            err = getattr(e, "code", None) or str(e)

        def _write(r: Any) -> IntentLogEntry:
            seq = int(r.incr(self._seq_key))
            entry = IntentLogEntry(
                seq=seq,
                ts=time.time(),
                action=action,
                args_keys=tuple(sorted(str(k) for k in args.keys())),
                ok=bool(getattr(result, "ok", True)),
                error_code=err,
                op_kinds=ops,
                principal=principal,
                request_id=rid,
            )
            r.rpush(self._list_key, _serde.dumps(entry.to_dict(), default=str))
            r.ltrim(self._list_key, -self.maxlen, -1)
            return entry

        entry = self._rr.execute(_write, default=None)
        if entry is not None:
            return entry
        # soft-fail local
        with self._lock:
            self._local_seq += 1
            entry = IntentLogEntry(
                seq=self._local_seq,
                ts=time.time(),
                action=action,
                args_keys=tuple(sorted(str(k) for k in args.keys())),
                ok=bool(getattr(result, "ok", True)),
                error_code=err,
                op_kinds=ops,
                principal=principal,
                request_id=rid,
            )
            self._local_fallback.append(entry)
            if len(self._local_fallback) > self.maxlen:
                self._local_fallback = self._local_fallback[-self.maxlen :]
            return entry

    def since(self, seq: int = 0) -> list:
        import json

        from ux_channel.devtools.intent_log import IntentLogEntry

        def _read(r: Any) -> list:
            raw = r.lrange(self._list_key, 0, -1) or []
            out = []
            for item in raw:
                d = _serde.loads(item)
                if int(d.get("seq", 0)) > seq:
                    out.append(
                        IntentLogEntry(
                            seq=int(d["seq"]),
                            ts=float(d.get("ts") or 0),
                            action=str(d.get("action") or "?"),
                            args_keys=tuple(d.get("args_keys") or ()),
                            ok=bool(d.get("ok", True)),
                            error_code=d.get("error_code"),
                            op_kinds=tuple(d.get("op_kinds") or ()),
                            principal=d.get("principal"),
                            request_id=d.get("request_id"),
                            meta=dict(d.get("meta") or {}),
                        )
                    )
            return out

        remote = self._rr.execute(_read, default=None)
        if remote is not None:
            return remote
        with self._lock:
            return [e for e in self._local_fallback if e.seq > seq]

    def replay_ops(self, *, from_seq: int = 0, to_seq: int | None = None) -> list[str]:
        out: list[str] = []
        for e in self.since(from_seq):
            if to_seq is not None and e.seq > to_seq:
                break
            out.extend(e.op_kinds)
        return out

    def __len__(self) -> int:
        def _llen(r: Any) -> int:
            return int(r.llen(self._list_key) or 0)

        n = self._rr.execute(_llen, default=None)
        if n is not None:
            return n
        with self._lock:
            return len(self._local_fallback)

    def healthy(self) -> bool:
        return self._rr.ping()
