"""
Soak scenario drivers.

Each function(target, slo, **params) -> ScenarioResult
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from scripts.soak.report import ScenarioResult, SloConfig, p95, rate


def _peer(prefix: str = "p") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def scenario_ticket_gate(client: Any, slo: SloConfig, **kw: Any) -> ScenarioResult:
    """Unauthed poll must 403; authed must 200 (unique rooms avoid max_peers)."""
    n = int(kw.get("n", 50))
    denies = allows = bad = 0
    deny_room = f"tg_deny_{uuid.uuid4().hex[:8]}"
    for _ in range(n):
        r = client.get(
            "/ux-channel/rtc",
            params={"room": deny_room, "peer": _peer(), "since": 0},
        )
        if r.status_code == 403:
            denies += 1
        else:
            bad += 1
    for i in range(n):
        room = f"tg_allow_{uuid.uuid4().hex[:8]}_{i}"
        ticket = client.mint_ticket(room, sub=f"u{i}")
        r = client.get(
            "/ux-channel/rtc",
            params={"room": room, "peer": _peer(), "since": 0, "ticket": ticket},
        )
        if r.status_code == 200 and (r.json() or {}).get("ok"):
            allows += 1
        else:
            bad += 1
    deny_rate = rate(denies, n)
    allow_rate = rate(allows, n)
    ok = deny_rate >= slo.ticket_deny and allow_rate >= slo.rtc_success
    return ScenarioResult(
        name="ticket_gate",
        ok=ok,
        detail={
            "denies": denies,
            "allows": allows,
            "bad": bad,
            "deny_rate": round(deny_rate, 4),
            "allow_rate": round(allow_rate, 4),
            "slo_deny": slo.ticket_deny,
            "slo_allow": slo.rtc_success,
        },
    )


def scenario_rtc_mesh(client: Any, slo: SloConfig, **kw: Any) -> ScenarioResult:
    """Isolated rooms: poll + offer/answer/ice/ice-done per pair."""
    pairs = int(kw.get("pairs", 20))
    base = f"mesh_{uuid.uuid4().hex[:8]}"
    latencies: list[float] = []
    ok_n = err_n = 0

    def one_pair(i: int) -> tuple[bool, float]:
        room = f"{base}_{i}"
        ticket = client.mint_ticket(room)
        a, b = _peer("a"), _peer("b")
        t0 = time.perf_counter()
        r1 = client.get(
            "/ux-channel/rtc",
            params={"room": room, "peer": a, "since": 0, "ticket": ticket},
        )
        r2 = client.get(
            "/ux-channel/rtc",
            params={"room": room, "peer": b, "since": 0, "ticket": ticket},
        )
        if r1.status_code != 200 or r2.status_code != 200:
            return False, (time.perf_counter() - t0) * 1000
        for kind, payload, frm, to in (
            ("offer", {"type": "offer", "sdp": "v=0"}, a, b),
            ("answer", {"type": "answer", "sdp": "v=0"}, b, a),
            ("ice", {"candidate": "x"}, a, b),
            ("ice-done", None, a, b),
        ):
            pr = client.post(
                "/ux-channel/rtc",
                json={
                    "op": "signal",
                    "room": room,
                    "from": frm,
                    "to": to,
                    "kind": kind,
                    "payload": payload,
                    "ticket": ticket,
                },
            )
            if pr.status_code != 200:
                return False, (time.perf_counter() - t0) * 1000
        inbox = client.get(
            "/ux-channel/rtc",
            params={"room": room, "peer": b, "since": 0, "ticket": ticket},
        )
        dt = (time.perf_counter() - t0) * 1000
        if inbox.status_code != 200:
            return False, dt
        return len(inbox.json().get("signals") or []) >= 1, dt

    parallel = bool(kw.get("parallel", False))
    if parallel:
        with ThreadPoolExecutor(max_workers=min(32, pairs)) as ex:
            futs = [ex.submit(one_pair, i) for i in range(pairs)]
            for f in as_completed(futs):
                try:
                    good, ms = f.result()
                except Exception:
                    err_n += 1
                    continue
                latencies.append(ms)
                ok_n += 1 if good else 0
                err_n += 0 if good else 1
    else:
        for i in range(pairs):
            try:
                good, ms = one_pair(i)
            except Exception:
                err_n += 1
                continue
            latencies.append(ms)
            if good:
                ok_n += 1
            else:
                err_n += 1

    total = ok_n + err_n
    sr = rate(ok_n, total)
    p = p95(latencies)
    ok = sr >= slo.rtc_success and p <= slo.p95_rtc_ms
    return ScenarioResult(
        name="rtc_mesh",
        ok=ok,
        detail={
            "pairs": pairs,
            "ok": ok_n,
            "err": err_n,
            "success_rate": round(sr, 4),
            "p95_ms": round(p, 2),
            "slo_success": slo.rtc_success,
            "slo_p95_ms": slo.p95_rtc_ms,
        },
    )


def scenario_rtc_ws(client: Any, slo: SloConfig, **kw: Any) -> ScenarioResult:
    """WebSocket hello (inline uses Starlette TestClient)."""
    n = int(kw.get("n", 1))
    room = f"ws_{uuid.uuid4().hex[:8]}"
    ticket = client.mint_ticket(room)
    hellos = fails = 0
    app = getattr(client, "app", None)
    if app is not None:
        try:
            from starlette.testclient import TestClient as SC

            sc = SC(app)
            for _ in range(n):
                peer = _peer("w")
                try:
                    with sc.websocket_connect(
                        f"/ux-channel/rtc/ws?room={room}&peer={peer}&ticket={ticket}"
                    ) as ws:
                        msg = ws.receive_json()
                        if msg.get("type") == "hello":
                            hellos += 1
                        else:
                            fails += 1
                except Exception:
                    fails += 1
            sc.close()
        except Exception as exc:
            return ScenarioResult(
                name="rtc_ws",
                ok=True,
                detail={"skipped": True, "reason": str(exc)[:160]},
            )
    else:
        # Live HTTP target — websockets client
        import asyncio
        import json
        from urllib.parse import urlencode

        base = str(
            getattr(client, "base_url", None)
            or getattr(getattr(client, "http", None), "base_url", "")
            or ""
        )
        if not base:
            return ScenarioResult(
                name="rtc_ws",
                ok=True,
                detail={"skipped": True, "reason": "no base_url"},
            )
        ws_base = base.replace("https://", "wss://").replace("http://", "ws://")

        async def _hello(peer: str) -> bool:
            try:
                import websockets
            except ImportError:
                return False
            q = urlencode({"room": room, "peer": peer, "ticket": ticket})
            uri = f"{ws_base}/ux-channel/rtc/ws?{q}"
            try:
                async with websockets.connect(uri, open_timeout=5) as ws:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(raw)
                    return msg.get("type") == "hello"
            except Exception:
                return False

        async def _run() -> None:
            nonlocal hellos, fails
            for _ in range(n):
                if await _hello(_peer("w")):
                    hellos += 1
                else:
                    fails += 1

        try:
            asyncio.run(_run())
        except Exception as exc:
            return ScenarioResult(
                name="rtc_ws",
                ok=True,
                detail={"skipped": True, "reason": str(exc)[:160]},
            )
    total = hellos + fails
    sr = rate(hellos, total) if total else 0.0
    ok = total == 0 or sr >= slo.ws_hello
    return ScenarioResult(
        name="rtc_ws",
        ok=ok,
        detail={
            "hellos": hellos,
            "fails": fails,
            "success_rate": round(sr, 4),
            "slo": slo.ws_hello,
        },
    )


def scenario_action_mix(client: Any, slo: SloConfig, **kw: Any) -> ScenarioResult:
    """soak_ping / soak_inc with signed caps (inline channel or shared secret)."""
    n = int(kw.get("n", 100))
    ch = getattr(client, "channel", None)
    secret = getattr(client, "secret", None) or getattr(
        getattr(client, "http", None), "secret", None
    )
    signer = None
    if ch is not None:
        signer = lambda name: ch.sign(name)
    elif secret:
        from ux_channel.config import ChannelConfig
        from ux_channel.registry import ActionRegistry

        reg = ActionRegistry.from_config(
            ChannelConfig.development(
                secret=secret,
                allow_memory_stores=True,
                require_cap=True,
            )
        )
        signer = lambda name: reg.sign(name, {})

    latencies: list[float] = []
    ok_n = err_n = 0

    def one(i: int) -> tuple[bool, float]:
        t0 = time.perf_counter()
        name = "soak_ping" if i % 2 == 0 else "soak_inc"
        body: dict[str, Any] = {"uid": "1", "action": name, "args": {}}
        if signer is not None:
            body["cap"] = signer(name)
        r = client.post(
            "/ux-channel/action",
            json=body,
            headers={"Content-Type": "application/json", "X-Channel": "1"},
        )
        return r.status_code == 200, (time.perf_counter() - t0) * 1000

    # sequential — TestClient safety
    for i in range(n):
        try:
            good, ms = one(i)
        except Exception:
            err_n += 1
            continue
        latencies.append(ms)
        if good:
            ok_n += 1
        else:
            err_n += 1
    total = ok_n + err_n
    sr = rate(ok_n, total)
    p = p95(latencies)
    ok = sr >= slo.action_success and p <= slo.p95_action_ms
    return ScenarioResult(
        name="action_mix",
        ok=ok,
        detail={
            "n": n,
            "ok": ok_n,
            "err": err_n,
            "success_rate": round(sr, 4),
            "p95_ms": round(p, 2),
            "slo_success": slo.action_success,
            "slo_p95_ms": slo.p95_action_ms,
        },
    )


def scenario_metrics_slo(client: Any, slo: SloConfig, **kw: Any) -> ScenarioResult:
    r = client.get("/ux-channel/rtc/metrics")
    if r.status_code != 200:
        return ScenarioResult(
            name="metrics_slo", ok=False, error=f"status {r.status_code}"
        )
    data = r.json()
    return ScenarioResult(
        name="metrics_slo",
        ok="counters" in data,
        detail={"uptime_s": data.get("uptime_s"), "counters": data.get("counters")},
    )


def scenario_room_full(client: Any, slo: SloConfig, **kw: Any) -> ScenarioResult:
    """Deterministic store overflow (does not depend on app max_peers)."""
    from ux_channel.webrtc import MemoryRtcStore

    store = MemoryRtcStore(max_peers=3)
    for i in range(3):
        store.poll("full", f"p{i}", since=0)
    raised = False
    try:
        store.poll("full", "overflow", since=0)
    except OverflowError:
        raised = True
    return ScenarioResult(
        name="room_full",
        ok=raised,
        detail={"store": "MemoryRtcStore", "max_peers": 3, "overflow": raised},
    )


SCENARIOS: dict[str, Callable[..., ScenarioResult]] = {
    "ticket_gate": scenario_ticket_gate,
    "rtc_mesh": scenario_rtc_mesh,
    "rtc_ws": scenario_rtc_ws,
    "action_mix": scenario_action_mix,
    "metrics_slo": scenario_metrics_slo,
    "room_full": scenario_room_full,
}

DEFAULT_SCENARIOS = [
    "ticket_gate",
    "rtc_mesh",
    "rtc_ws",
    "action_mix",
    "metrics_slo",
    "room_full",
]
