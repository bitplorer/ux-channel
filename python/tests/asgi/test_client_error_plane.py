
"""Static + light behavioral checks for client error plane."""

from pathlib import Path

JS = Path("src/ux_channel/static/ux-channel.js").read_text()


def test_error_plane_api_exported():
    for token in (
        "reportError",
        "configureErrors",
        "lastErrors",
        "clearErrorLog",
        "applyFieldErrors",
        "clearFieldErrors",
        "syntheticFailure",
        "preventApply",
        "channel:fieldErrors",
        "channel:networkError",
        "channel:opError",
        "channel:applyCancelled",
        "err.handled",
        "data-channel-auto-toast",
        "data-channel-toast-refresh-errors",
    ):
        assert token in JS, token


def test_no_double_network_report_block():
    # network catch should not call reportError before applyResult
    idx = JS.find('err && err.name === "AbortError"')
    assert idx > 0
    chunk = JS[idx : idx + 800]
    # applyResult is there; reportError("network" should NOT be in catch before apply
    assert "applyResult(body, { source: \"network\" })" in chunk or "source: \"network\"" in chunk
    assert 'reportError("network"' not in chunk


def test_docs_exist():
    assert Path("docs/core/CLIENT_ERRORS.md").is_file()


def test_min_js_synced():
    a = Path("src/ux_channel/static/ux-channel.js").read_text()
    b = Path("src/ux_channel/static/ux-channel.min.js").read_text()
    assert "reportError" in b
    # keep in sync for 0.1 (min is full copy)
    assert a == b
