"""Push topic body attrs + client exports."""

from pathlib import Path

from ux_channel import Channel, ChannelConfig
from ux_channel.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags

ROOT = Path(__file__).resolve().parents[2]


def test_body_attr_push_topic():
    ch = Channel.boot(
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        )
    )
    s = attr_string(ch.body_attrs(push_topic="live.board", push_token="sec"))
    assert 'data-channel-push-topic="live.board"' in s
    assert 'data-channel-push-token="sec"' in s


def test_client_js_has_subscribe_push():
    js = (ROOT / "src/ux_channel/static/ux-channel.js").read_text()
    assert "function subscribePush" in js
    assert "function autoSubscribePush" in js
    assert "data-channel-push-topic" in js
    assert "subscribePush: subscribePush" in js
