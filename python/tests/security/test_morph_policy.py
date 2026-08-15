def test_registry_finalize_honors_policy():
    from fastapi import FastAPI

    from ux_channel import Channel, ChannelConfig
    from ux_channel.protocol.types import Intent, Result

    cfg = ChannelConfig.development(
        secret="morph-policy-secret-32chars-min!!",
        allow_memory_stores=True,
        require_cap=False,
        morph_html_policy="strict",
        observe="off",
        trace_enabled=False,
    )
    ch = Channel.boot(FastAPI(), config=cfg)

    @ch.on
    def paint():
        return Result.success(
            {"op": "morph", "target": "#x", "html": "<script>alert(1)</script><b>hi</b>"}
        )

    r = ch.registry.dispatch(Intent(action="paint", args={}))
    assert r.ok
    html = ""
    for op in r.ops:
        body = op.to_dict() if hasattr(op, "to_dict") else op
        if isinstance(body, dict) and body.get("op") == "morph":
            html = str(body.get("html") or "")
    assert "<script" not in html.lower()
    assert "hi" in html