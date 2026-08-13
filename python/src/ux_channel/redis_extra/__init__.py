"""Redis backends for multi-worker production."""
from __future__ import annotations

from ux_channel.protocol import serde as _serde
import threading

from typing import Any, Optional


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


class RedisIdempotencyStore:
    def __init__(self, redis_url: str | Any, *, prefix: str = "uidch:idem:"):
        self.r = _client(redis_url)
        self.prefix = prefix

    def get(self, key: str) -> Optional[dict]:
        import json

        raw = self.r.get(f"{self.prefix}{key}")
        if not raw:
            return None
        return _serde.loads(raw)

    def set(self, key: str, result: dict, *, ttl_s: float = 3600) -> None:
        import json

        self.r.set(f"{self.prefix}{key}", _serde.dumps(result, default=str), ex=int(ttl_s))


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

    def _ch(self, topic: str) -> str:
        return f"{self.prefix}{topic}"

    def publish(self, topic: str, payload: dict) -> int:
        import json

        def _pub(r: Any) -> int:
            return int(r.publish(self._ch(topic), _serde.dumps(payload, default=str)) or 0)

        n = self._rr.execute(_pub, default=0)
        # always deliver to local subscribers in this process
        with self._lock:
            qs = list(self._local.get(topic, ()))
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

    def poll(
        self,
        room: str,
        peer_id: str,
        *,
        name: str = "",
        since: int = 0,
    ) -> dict[str, Any]:
        import json
        import time

        room = str(room or "default")[:64]
        peer_id = str(peer_id or "")[:64]
        if not peer_id:
            raise ValueError("peer_id required")
        self._gc_room(room)
        key = self._pk(room)
        n = self.r.hlen(key)
        if not self.r.hexists(key, peer_id) and n >= self.max_peers:
            raise OverflowError(f"room full (max {self.max_peers} peers)")
        now = time.time()
        prev = {}
        if self.r.hexists(key, peer_id):
            try:
                prev = _serde.loads(self.r.hget(key, peer_id) or "{}")
            except Exception:
                prev = {}
        rec = {
            "name": (name or prev.get("name") or "")[:64],
            "last_seen": now,
        }
        self.r.hset(key, peer_id, _serde.dumps(rec))
        self.r.expire(key, int(self.peer_ttl_s * 3))
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

    def leave(self, room: str, peer_id: str) -> dict[str, Any]:
        room = str(room or "default")[:64]
        peer_id = str(peer_id or "")[:64]
        self.r.hdel(self._pk(room), peer_id)
        self.r.delete(self._ik(room, peer_id))
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
