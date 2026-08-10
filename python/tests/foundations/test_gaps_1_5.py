"""Gap-fill tests for 1.5: rotation, JSON limits, CORS, OpenAPI models."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ux_channel import ActionRegistry, Result, toast
from ux_channel.protocol.capability import CapService
from ux_channel.protocol.jsonutil import JsonLimitError, check_json_limits
from ux_channel.protocol.types import Intent


def test_capability_secret_rotation():
    old = "old-secret-key-32chars-minimum!!xx"
    new = "new-secret-key-32chars-minimum!!xx"
    old_svc = CapService(old)
    token = old_svc.mint("Pay", {"n": 1})
    # new service with previous_secrets can verify old token
    rotated = CapService(new, previous_secrets=[old])
    data = rotated.verify(token, "Pay", {"n": 1})
    assert data["action"] == "Pay"
    # signing uses new secret
    tok2 = rotated.mint("Pay", {"n": 2})
    rotated.verify(tok2, "Pay", {"n": 2})
    # old-only service cannot verify new token
    with pytest.raises(Exception):
        old_svc.verify(tok2, "Pay", {"n": 2})


def test_registry_rotation_via_previous_secrets():
    old = "old-secret-key-32chars-minimum!!xx"
    new = "new-secret-key-32chars-minimum!!xx"
    reg_old = ActionRegistry(secret=old, require_cap=True)

    @reg_old.action("Hi")
    def hi():
        return Result.success(toast("hi"))

    cap = reg_old.mint("Hi", {})
    reg_new = ActionRegistry(secret=new, require_cap=True, previous_secrets=[old])
    reg_new.replace("Hi", hi)
    r = reg_new.dispatch(Intent(action="Hi", args={}, cap=cap))
    assert r.ok


def test_json_depth_limit():
    deep = {}
    cur = deep
    for _ in range(20):
        cur["a"] = {}
        cur = cur["a"]
    with pytest.raises(JsonLimitError):
        check_json_limits(deep, max_depth=5)

    reg = ActionRegistry(secret="test-secret-key-32chars-minimum!!", require_cap=False)

    @reg.action("Deep")
    def deep_fn(**kwargs):
        return Result.success(toast("x"))

    # build depth > 12
    args = {}
    cur = args
    for _ in range(20):
        cur["n"] = {}
        cur = cur["n"]
    r = reg.dispatch(Intent(action="Deep", args=args))
    assert not r.ok
    assert r.error.code == "bad_request"


def test_cors_helper():
    from ux_channel.transport.cors import apply_cors

    app = FastAPI()
    apply_cors(app, origins=["https://app.example.com"])
    # middleware registered
    assert app.user_middleware  # CORSMiddleware attached


def test_schema_models_optional():
    pytest.importorskip("pydantic")
    from ux_channel.ops_dx.schema_models import IntentModel, ResultModel

    m = IntentModel(action="Orders.place", args={"id": "1"})
    assert m.action == "Orders.place"
    r = ResultModel(ok=True, ops=[{"op": "toast", "message": "x"}])
    assert r.ok
