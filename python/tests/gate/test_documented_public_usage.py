"""Characterization of documented public usage.

Pins the contracts application code is told to rely on: golden path
(``Channel.boot``, ``@region``, ``@on``, ``control``, ``draft``, ``done``),
the counter and login-form examples, ``CapService``, wire JSON, and the
op builders. These are the behaviors a later refactor must keep.

Does not pin defects already called out for repair (published secrets,
identity taken from form fields, idempotency short-circuit, push without
config, client bulkhead flags, sync-handler timeouts, and the rest of
that list).
"""

from __future__ import annotations

import pytest

from ux_channel import (
    ActionRegistry,
    CapError,
    CapService,
    Channel,
    ChannelConfig,
    Intent,
    Principal,
    Result,
    morph,
    navigate,
    signal_set,
    state,
    toast,
)
from ux_channel.host.ssr_state import reading_as
from ux_channel.host.stores import MemoryStateStore
from ux_channel.protocol.error_map import http_status_for
from ux_channel.protocol.errors import ActionError
from ux_channel.wire import decode, encode

# Documented local secret. Production rejection of this value is a separate
# contract and is intentionally not asserted here.
DEV_SECRET = "dev-secret-key-32chars-minimum!!!!"
PROD_SECRET = "prod-characterization-secret-48chars-minimum!!"


@pytest.fixture(autouse=True)
def _isolate_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve-dev file and Redis wiring must not leak into these cases."""
    monkeypatch.delenv("UXCOMPOSE_STATE_STORE", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)


def _dev_channel() -> Channel:
    return Channel.boot(
        config=ChannelConfig.development(
            secret=DEV_SECRET,
            allow_memory_stores=True,
        ),
        state=MemoryStateStore(),
    )


def test_golden_path_region_control_and_dispatch_updates_draft():
    """GOLDEN_PATH: region paint, sealed control, dispatch, caller HTML comes back."""
    ch = _dev_channel()

    @ch.region
    def badge(ctx):
        n = ch.draft.get("n", 0) or 0
        return f'<span data-channel-id="badge">Cart ({n})</span>'

    @ch.on(refresh=[badge])
    def add(product_id: str = "sku"):
        ch.draft.change("n", lambda n: (n or 0) + 1, default=0)

    assert add.action == "add"
    page = ch.html(badge)
    assert "Cart (0)" in page
    assert 'data-channel-id="badge"' in page

    control = ch.control(add, trust_product_id="sku")
    attrs = control.as_dict()
    assert attrs["data-channel-action"] == "add"
    assert attrs["data-channel-cap"]
    assert "product_id" in attrs["data-channel-args"]

    body = ch.body_attrs()
    assert body["data-channel-endpoint"].endswith("/ux-channel/action")
    runtime = ch.runtime()
    assert runtime.client["endpoint"].endswith("/action")
    assert any(ref.src.endswith("/static/ux-channel.js") for ref in runtime.scripts)

    result = ch.registry.dispatch(
        Intent(action="add", args={"product_id": "sku"}, cap=control.cap)
    )
    assert result.ok
    morphs = [op for op in result.ops if op.get("op") == "morph"]
    assert morphs
    assert "Cart (1)" in morphs[0]["html"]
    assert 'data-channel-id="badge"' in morphs[0]["html"]


def test_control_string_escapes_and_sealed_args_reject_tamper():
    """Product embedding is ``str(control)``; a changed sealed arg is unauthorized."""
    ch = _dev_channel()

    @ch.on
    def add(product_id: str = "sku"):
        return ch.done(notice="added")

    control = ch.control(add, trust_product_id='say "hi"')
    html = str(control)
    assert 'data-channel-action="add"' in html
    assert "&quot;" in html
    assert control.cap

    ok = ch.registry.dispatch(
        Intent(action="add", args={"product_id": 'say "hi"'}, cap=control.cap)
    )
    assert ok.ok
    assert any(op.get("op") == "toast" and op.get("message") == "added" for op in ok.ops)

    tampered = ch.registry.dispatch(
        Intent(action="add", args={"product_id": "other"}, cap=control.cap)
    )
    assert tampered.ok is False
    assert tampered.error.code == "unauthorized"


def test_done_and_fail_match_documented_result_shapes():
    ch = _dev_channel()
    paid = ch.done(notice="paid")
    assert paid.ok
    assert any(op.get("op") == "toast" and op.get("message") == "paid" for op in paid.ops)

    auth = ch.fail.auth("Sign in to continue")
    assert auth.ok is False
    assert auth.error.code == "unauthorized"
    assert http_status_for(auth) == 401

    form = ch.fail.valid(
        {"email": ["required"]},
        region="Form:root",
        html="<form id='Form:root'>bad</form>",
        message="Fix the form",
    )
    assert form.ok is False
    assert form.error.code == "validation"
    assert form.error.fields["email"] == ["required"]
    assert http_status_for(form) == 422
    assert any(op.get("op") == "morph" for op in form.ops)

    conflict = ch.fail.code("conflict", "Order already paid")
    assert conflict.error.code == "conflict"
    assert http_status_for(conflict) == 409


def test_cap_service_and_json_wire_roundtrip():
    svc = CapService(DEV_SECRET)
    args = {"sku": "a", "qty": 1}
    token = svc.mint("Cart.add", args, sub="alice")
    verified = svc.verify(token, action="Cart.add", args=args)
    assert verified["action"] == "Cart.add"
    assert verified["sub"] == "alice"
    try:
        svc.verify(token, action="Cart.add", args={"sku": "a", "qty": 2})
        raise AssertionError("tampered args must not verify")
    except CapError:
        pass

    blob = encode({"v": "1", "action": "Cart.add", "args": args})
    assert blob.format == "json"
    assert decode(blob.data)["action"] == "Cart.add"
    assert decode(blob.data)["args"] == args


def test_op_builders_use_documented_wire_names():
    painted = morph(target='[data-channel-id="badge"]', html="<b>1</b>")
    assert painted["op"] == "morph"
    assert painted["target"] == '[data-channel-id="badge"]'
    assert painted["html"] == "<b>1</b>"

    note = toast("Saved", level="info")
    assert note["op"] == "toast"
    assert note["message"] == "Saved"

    go = navigate("/welcome")
    assert go["op"] == "navigate"
    assert go["href"] == "/welcome"

    blocked = navigate("javascript:alert(1)")
    assert blocked["op"] == "noop"
    assert blocked["meta"]["reason"] == "unsafe_href"

    signal = signal_set("cart.sku", "abc-123")
    assert signal["op"] == "signal.set"
    assert signal["path"] == "cart.sku"
    assert signal["value"] == "abc-123"


def test_state_session_roundtrip_and_secret_path_rejected():
    ch = _dev_channel()
    st = state(ch, allow=["ui.theme"])
    theme = st.session("ui.theme", "light")
    assert theme.get() == "light"

    @ch.on
    def dark():
        theme.set("dark")

    # A session value is per visitor: the Cap names the visitor.
    ch.registry.auth_resolver = lambda request: Principal(id="visitor-1")
    r = ch.registry.dispatch(Intent(action="dark", args={}, cap=ch.mint("dark", {}, sub="visitor-1")))
    assert r.ok, r
    with reading_as("visitor-1"):
        assert st.session("ui.theme").get() == "dark"
    assert st.session("ui.theme").get() == "light"

    with pytest.raises(ValueError):
        st.client("password", "hunter2")


def test_login_form_pattern_empty_cap_accepts_form_fields():
    """examples/forms: cap is minted over {} and fields arrive on intent.form."""
    reg = ActionRegistry(secret=DEV_SECRET, require_cap=True)

    @reg.action("Login.save")
    def save(email: str = "", password: str = ""):
        if "@" not in email or len(password) < 8:
            return Result.failure("validation", "Fix the highlighted fields")
        return Result.success(toast(f"welcome {email}"))

    cap = reg.mint("Login.save", {})
    bad = reg.dispatch(
        Intent(
            action="Login.save",
            args={},
            form={"email": "nope", "password": "short"},
            cap=cap,
        )
    )
    assert bad.ok is False
    assert bad.error.code == "validation"

    good = reg.dispatch(
        Intent(
            action="Login.save",
            args={},
            form={"email": "demo@uid.dev", "password": "password1"},
            cap=cap,
        )
    )
    assert good.ok
    assert any("demo@uid.dev" in (op.get("message") or "") for op in good.ops)


def test_counter_registry_returns_caller_html_and_reset_toast():
    """examples/counter: mint, dispatch, morph the caller's markup, toast on reset."""
    reg = ActionRegistry(secret=DEV_SECRET, require_cap=True)

    def counter_html(n: int) -> str:
        return f'<div data-channel-id="Counter:root">{n}</div>'

    @reg.action("Counter.inc")
    def inc(n: int = 0):
        return Result.success(morph(target='[data-channel-id="Counter:root"]', html=counter_html(n + 1)))

    @reg.action("Counter.reset")
    def reset():
        return Result.success(
            morph(target='[data-channel-id="Counter:root"]', html=counter_html(0)),
            toast("Reset", level="info"),
        )

    cap = reg.mint("Counter.inc", {"n": 1})
    result = reg.dispatch(Intent(action="Counter.inc", args={"n": 1}, cap=cap))
    assert result.ok
    assert result.ops[0]["html"] == '<div data-channel-id="Counter:root">2</div>'

    reset_cap = reg.mint("Counter.reset", {})
    cleared = reg.dispatch(Intent(action="Counter.reset", args={}, cap=reset_cap))
    assert cleared.ok
    assert any(op.get("op") == "toast" and op.get("message") == "Reset" for op in cleared.ops)


def test_action_error_and_unknown_action():
    reg = ActionRegistry(secret=DEV_SECRET, require_cap=False)

    @reg.action("signup")
    def signup(email: str = ""):
        if "@" not in email:
            raise ActionError("validation", "Invalid email", fields={"email": ["required"]})
        return Result.success(toast("welcome"))

    missing = reg.dispatch(Intent(action="signup", args={"email": ""}))
    assert missing.ok is False
    assert missing.error.code == "validation"
    assert missing.error.fields["email"] == ["required"]

    unknown = reg.dispatch(Intent(action="Nope.missing", args={}))
    assert unknown.ok is False
    assert unknown.error.code == "not_found"


def test_present_cap_is_verified_even_when_require_cap_is_off():
    reg = ActionRegistry(secret=DEV_SECRET, require_cap=False)

    @reg.action("ping")
    def ping():
        return Result.success(toast("pong"))

    opened = reg.dispatch(Intent(action="ping", args={}))
    assert opened.ok

    presented = reg.dispatch(Intent(action="ping", args={}, cap="not-a-capability"))
    assert presented.ok is False
    assert presented.error.code == "unauthorized"


def test_once_cap_second_dispatch_is_refused_in_process():
    ch = _dev_channel()

    @ch.on
    def pay():
        return ch.done(notice="paid")

    cap = ch.mint("pay", {}, once=True)
    first = ch.registry.dispatch(Intent(action="pay", args={}, cap=cap))
    second = ch.registry.dispatch(Intent(action="pay", args={}, cap=cap))
    assert first.ok
    assert second.ok is False
    assert second.error.code == "unauthorized"


def test_production_config_keeps_cap_and_channel_header():
    cfg = ChannelConfig.production(
        secret=PROD_SECRET,
        allow_memory_stores=True,
        allowed_origins=("https://app.example",),
    )
    assert cfg.environment == "production"
    assert cfg.require_cap is True
    assert cfg.require_channel_header is True
    assert cfg.audit is True
    assert cfg.navigate_allowed_hosts == ("app.example",)

    ch = Channel.boot(config=cfg)
    assert ch.config.require_cap is True
    assert "boot" in Channel.public_api_names()
    described = Channel.describe()
    assert "Public API" in described
    assert "boot" in described
