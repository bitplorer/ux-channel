"""ch.control + trust params (0.4 surface)."""

from ux_channel import Channel

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_control_trust_dict():
    ch = Channel.boot(secret=SECRET)

    @ch.on
    def add(product_id: str = ""):
        return None

    b = ch.control(add, trust={"product_id": "x"})
    d = b.as_dict()
    assert d["data-channel-action"] == "add"
    assert "x" in d["data-channel-args"]
    assert d["data-channel-cap"]


def test_control_trust_field():
    ch = Channel.boot(secret=SECRET)

    @ch.on
    def add_item(sku: str = ""):
        return None

    b = ch.control(add_item, trust_sku="sku-a")
    assert "sku-a" in b.as_dict()["data-channel-args"]


def test_control_no_trust():
    ch = Channel.boot(secret=SECRET)

    @ch.on
    def reset():
        return None

    assert "data-channel-cap" in ch.control(reset).as_dict()


def test_control_surface_from_surface():
    ch = Channel.boot(secret=SECRET)
    assert not hasattr(ch, "bind")
    assert not hasattr(ch, "do")
    assert hasattr(ch, "control") and hasattr(ch, "on")
