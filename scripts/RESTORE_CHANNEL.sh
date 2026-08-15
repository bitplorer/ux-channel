#!/bin/bash
# Run from repo root on feat/enhance-runtime-wire
set -euo pipefail
curl -fsSL https://raw.githubusercontent.com/bitplorer/ux-channel/main/python/src/ux_channel/host/channel.py -o /tmp/ch.py
python3 - <<'PY'
from pathlib import Path
content = Path("/tmp/ch.py").read_text()
old = """        try:
            from ux_channel.devtools.inspect_api import inspect_channel

            ch.inspect = lambda region=None, **kw: inspect_channel(  # type: ignore
                ch, region, **kw
            )
        except Exception:
            _blog.exception("inspect helper bind failed")
        return ch"""
new = """        try:
            from ux_channel.devtools.inspect_api import inspect_channel

            ch.inspect = lambda region=None, **kw: inspect_channel(  # type: ignore
                ch, region, **kw
            )
        except Exception:
            _blog.exception("inspect helper bind failed")
        try:
            if cfg is None or getattr(cfg, "enhance", True) is not False:
                from ux_channel.enhance.attach import attach_enhance
                attach_enhance(ch)
                try:
                    ch.registry.channel = ch  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            _blog.exception("enhance plane attach failed (non-fatal)")
        return ch"""
assert old in content, "boot anchor missing — main channel.py changed"
Path("python/src/ux_channel/host/channel.py").write_text(content.replace(old, new, 1))
print("channel.py restored + enhance attach")
PY
git add python/src/ux_channel/host/channel.py
git commit -m "restore channel.py + enhance attach on boot"
git push
