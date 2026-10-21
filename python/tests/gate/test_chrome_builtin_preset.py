"""Chrome: a generated builtin preset must not replace the real builtins.js adapter.

The page loads the app's channel scripts (ux-bridge.js, builtins.js), then what
the preset README says to load, then every generated ``ux-bridge-*.js`` (what
``create-app`` copies to ``app/static/bridges/``).

Skips when Chrome is not installed. ``UX_CHANNEL_REQUIRE_CHROME=1`` fails
instead, so the gated CI job cannot pass with a skip.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from gate.test_chrome_navigate_style import _dump_dom
from ux_channel.bridge.bridge_preset_gen import create_bridge_preset

_STATIC = Path(__file__).resolve().parents[2] / "src" / "ux_channel" / "static"


def _readme_scripts(readme: str) -> str:
    """Inline every script the README tells the app to load, in order."""
    out = []
    for src in re.findall(r'<script src="/ux-channel/static/([^"]+)"', readme):
        out.append(f"<script>{(_STATIC / src).read_text(encoding='utf-8')}</script>")
    for rel in re.findall(r'import "\./([^"]+)"', readme):
        out.append(f"__MODULE__{rel}")
    return "\n".join(out)


def test_confetti_preset_loaded_per_readme_mounts_canvas():
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_preset(td, "confetti", force=True)
        package = json.loads((root / "PRESET.json").read_text())["package"]
        scripts = _readme_scripts((root / "README.md").read_text())
        scripts = re.sub(
            r"__MODULE__(\S+)",
            lambda m: f'<script type="module">{(root / m.group(1)).read_text()}</script>',
            scripts,
        )
        generated = "\n".join(
            f'<script type="module">{js.read_text()}</script>'
            for js in sorted(root.glob("ux-bridge-*.js"))
        )
    channel = "\n".join(
        f"<script>{(_STATIC / rel).read_text(encoding='utf-8')}</script>"
        for rel in ("ux-bridge.js", "adapters/builtins.js")
    )
    page = f"""<!doctype html>
<html><body>
<div id="host" data-channel-bridge-id="c1" data-channel-bridge-package="{package}"
     style="position:relative;width:200px;height:100px"></div>
<pre id="score">PENDING</pre>
{channel}
{scripts}
{generated}
<script type="module">
// The bridge.mount op the host sends once the page is up.
await window.uxBridge.apply({{ op: "bridge.mount", id: "c1", package: "{package}", props: {{}} }});
const host = document.getElementById("host");
document.getElementById("score").textContent = JSON.stringify({{
  canvas: host.querySelectorAll("canvas").length,
  text: host.textContent.trim()
}});
</script>
</body></html>"""
    dom = _dump_dom(page)
    score = json.loads(re.search(r'<pre id="score">(.*?)</pre>', dom, re.S).group(1))
    assert score == {"canvas": 1, "text": ""}, score
