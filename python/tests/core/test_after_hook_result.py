"""After-hooks must not clobber Result with None / non-Result."""

from ux_channel import Channel, Intent

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_after_none_keeps_result():
    ch = Channel.boot(secret=SECRET)

    @ch.on(name="A.ok")
    def ok():
        return ch.done(notice="x")

    @ch.after
    def broken(intent, result):
        return None

    r = ch.registry.dispatch(Intent(action="A.ok", args={}, cap=ch.mint("A.ok", {})))
    assert r.ok
    assert r.ops


def test_after_dict_ignored():
    ch = Channel.boot(secret=SECRET)

    @ch.on(name="B.ok")
    def ok():
        return ch.done()

    @ch.after
    def broken(intent, result):
        return {"ok": True}

    r = ch.registry.dispatch(Intent(action="B.ok", args={}, cap=ch.mint("B.ok", {})))
    assert r.ok
    assert hasattr(r, "ops")


def test_diagnose_unique_keys():
    ch = Channel.boot(secret=SECRET)
    d = ch.diagnose()
    assert list(d.keys()).count("regions") == 1
    assert d["action_endpoint"].endswith("/action")
