from ux_channel.render.html import action_attrs, attr_escape, button, json_attr


def test_json_attr_escapes_quotes():
    s = json_attr({"n": 1, "s": 'a"b'})
    assert "quot" in s or "&" in s
    s2 = json_attr({"x": "<script>"})
    assert "script" in s2
    assert "<script>" not in s2 or "lt" in s2


def test_action_attrs():
    a = action_attrs("Counter.inc", trust={"n": 1}, cap="tok", target="#c")
    assert "data-channel-action" in a and "Counter.inc" in a
    assert "data-channel-cap" in a
    assert "data-channel-target" in a


def test_button():
    b = button("+", "Counter.inc", trust={"n": 0}, cap="c")
    assert b.startswith("<button")
    assert "Counter.inc" in b
    escaped = attr_escape("<x>")
    assert "x" in escaped
    assert "<x>" != escaped or escaped.startswith("&")
