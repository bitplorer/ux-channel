"""Peer kernel + runtime: apply, proof verify, single-flight, session gen, budgets.

No DOM. Drivers (web.v1 / agent.v1) hold surface behavior.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Mapping, MutableMapping, Optional

from ux_channel.arch.proof import ProofService

DriverFn = Callable[[Mapping[str, Any], MutableMapping[str, Any]], None]


class ApplyError(Exception):
    pass


class PeerApply:
    def __init__(
        self,
        drivers: Dict[str, DriverFn],
        *,
        max_nodes: int = 256,
        max_depth: int = 16,
        proof_service: Optional[ProofService] = None,
        proofs_required: bool = False,
        session_id: str = "default",
        stamp_check: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        self.drivers = dict(drivers)
        self.max_nodes = max_nodes
        self.max_depth = max_depth
        self.proof_service = proof_service
        self.proofs_required = proofs_required
        self.session_id = session_id
        self.stamp_check = stamp_check
        self._lock = threading.Lock()
        self.session_gen = 1
        self.ctx: MutableMapping[str, Any] = {
            "gen": 1,
            "timers": {},
            "log": [],
            "session_id": session_id,
            "reject": None,
            "apply_ops": self._apply_from_driver,
        }

    def _apply_from_driver(self, ops: list, ctx: MutableMapping[str, Any]) -> None:
        self._apply_ops(list(ops), 0)

    def bump_gen(self) -> None:
        self.session_gen += 1
        self.ctx["gen"] = self.session_gen
        self.ctx["timers"] = {}
        self.ctx["reject"] = None

    def apply_result(self, result: Mapping[str, Any]) -> None:
        self.ctx["reject"] = None
        if self.proofs_required:
            if self.proof_service is None:
                self.ctx["reject"] = "proof_unavailable"
                return
            if not self.proof_service.verify(
                result, session_id=self.session_id, gen=self.session_gen
            ):
                self.ctx["reject"] = "proof"
                return
        if not self._lock.acquire(blocking=False):
            raise ApplyError("single-flight: apply already in progress")
        try:
            ops = list(result.get("ops") or [])
            if not self._within_budget(ops):
                self.ctx["reject"] = "budget"
                return
            self.ctx["result_ok"] = result.get("ok")
            self._apply_ops(ops, 0)
        finally:
            self._lock.release()

    def _within_budget(self, ops: List[Any]) -> bool:
        count = 0

        def walk(lst: List[Any], d: int) -> bool:
            nonlocal count
            if d > self.max_depth:
                return False
            for op in lst:
                count += 1
                if count > self.max_nodes:
                    return False
                if isinstance(op, dict) and isinstance(op.get("ops"), list):
                    if not walk(list(op["ops"]), d + 1):
                        return False
            return True

        return walk(ops, 0)

    def _apply_ops(self, ops: List[Any], depth: int) -> None:
        if depth > self.max_depth:
            return
        for op in ops:
            if isinstance(op, dict):
                self._apply_op(op, depth)

    def _apply_op(self, op: Mapping[str, Any], depth: int) -> None:
        name = op.get("op")
        if name == "seq":
            self._apply_ops(list(op.get("ops") or []), depth + 1)
            return
        if name == "invoke":
            ref = str(op.get("ref") or "")
            method = str(op.get("method") or "")
            if self.stamp_check and not self.stamp_check(ref, method):
                self.ctx.setdefault("log", []).append(("invoke_denied", ref, method))
                return
            fn = self.drivers.get(f"invoke:{method}") or self.drivers.get("invoke")
            if fn:
                fn(op, self.ctx)
            body = op.get("ops")
            if isinstance(body, list):
                self._apply_ops(body, depth + 1)
            return
        fn = self.drivers.get(str(name)) if name else None
        if fn is None:
            return
        fn(op, self.ctx)


class PeerRuntime:
    def __init__(
        self,
        apply: PeerApply,
        *,
        profiles: Optional[List[str]] = None,
        features: Optional[List[str]] = None,
    ) -> None:
        self.apply = apply
        self.profiles = list(profiles or [])
        self.features = list(features or [])
        self._queue: Deque[Mapping[str, Any]] = deque()
        self._busy = False

    def hello(self) -> dict:
        return {
            "profiles": self.profiles,
            "features": self.features,
            "ir": "1",
            "effect_proof": bool(self.apply.proofs_required or self.apply.proof_service),
        }

    def submit_intent(
        self,
        action: str,
        args: Optional[Mapping[str, Any]] = None,
        cap: Optional[str] = None,
        request_id: Optional[str] = None,
        *,
        transport: Optional[Callable[[Mapping[str, Any]], Optional[Mapping[str, Any]]]] = None,
    ) -> dict:
        """Build an Intent (hello in meta). Optional transport returns a Result to apply.

        Outbox is explicit opt-in via ``enable_outbox()``. Cap is never inferred.
        """
        intent: Dict[str, Any] = {
            "v": "1",
            "action": action,
            "args": dict(args or {}),
            "meta": {"hello": self.hello()},
        }
        if cap:
            intent["cap"] = cap
        if request_id:
            intent["request_id"] = request_id
        if getattr(self, "_outbox", None) is not None:
            self._outbox.append(intent)
        sender = transport or getattr(self, "_transport", None)
        if sender:
            result = sender(intent)
            if result is not None:
                self.on_result(result)
        return intent

    def enable_outbox(self) -> None:
        if getattr(self, "_outbox", None) is None:
            self._outbox: List[dict] = []

    def recorded(self) -> List[dict]:
        return list(getattr(self, "_outbox", None) or [])

    def set_transport(
        self, fn: Callable[[Mapping[str, Any]], Optional[Mapping[str, Any]]]
    ) -> None:
        self._transport = fn

    def on_result(self, result: Mapping[str, Any]) -> None:
        self._queue.append(result)
        self._drain()

    def _drain(self) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            while self._queue:
                self.apply.apply_result(self._queue.popleft())
        finally:
            self._busy = False

    def revoke_local(self) -> None:
        self.apply.bump_gen()
        self._queue.clear()
