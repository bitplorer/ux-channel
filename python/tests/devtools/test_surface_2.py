from ux_channel import Channel

SECRET = "dev-secret-key-32chars-minimum!!!!"


def test_legacy_names_removed():
    ch = Channel.boot(secret=SECRET)
    for name in (
        "view", "ok", "err", "sync", "notify", "search",
        "islands", "island", "command", "revalidate", "form_ok", "fail_auth",
        "bind", "do", "attrs", "document", "shell",
    ):
        assert not hasattr(ch, name), name


def test_core_present():
    ch = Channel.boot(secret=SECRET)
    for name in (
        "region", "regions", "on", "done", "fail", "refresh", "patch",
        "notice", "html", "control", "runtime", "body_attrs", "draft",
    ):
        assert hasattr(ch, name), name
    for name in ("page", "button", "scripts", "link", "form"):
        assert not hasattr(ch, name), name
