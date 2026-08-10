"""Region morph fragments must keep data-channel-id for client replaceWith morphs."""

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig, Region


def test_refresh_morph_html_includes_data_channel_id():
    app = FastAPI()
    ch = Channel.boot(
        app,
        config=ChannelConfig.development(secret="dev-secret-key-32chars-minimum!!!!"),
    )

    class Box(Region):
        def render(self, ctx):
            # no data-channel-id on root (common pattern)
            return f'<div class="box">{self.ch.draft.get("n", 0)}</div>'

    Box(ch, uid="box").mount()
    ch.draft.set("n", 1)
    result = ch.refresh("box")
    assert result.ok
    assert result.ops
    html = result.ops[0]["html"]
    assert 'data-channel-id="box"' in html, html
    assert "class=\"box\"" in html or "class='box'" in html or "box" in html


def test_client_js_preserves_uid_on_morph():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[2] / "src/ux_channel/static/ux-channel.js").read_text()
    assert "data-channel-id" in js
    assert "replaceWith" in js
    # preservation logic present
    assert "next.setAttribute(\"data-channel-id\"" in js or "next.setAttribute('data-channel-id'" in js
    assert "onWsMessage" in js
