"""Ghost packages on disk must be mapped — silence is a dual door.

Evidence (tree + tests) for mapping rather than deleting:

* ``ops/``: Wave A composition (``Op`` / ``plan`` / ``to_classic``). Imported by
  ``cek.project``, ``enhance.delta``, and ``tests/gate/test_enhance_waves.py``.
  Distinct from ``protocol.ops`` wire dicts.
* ``enhance/``: Waves B–G additive envelopes. Attached by ``Channel.boot``
  (opt-out) and gated by ``test_enhance_*.py``.

Neither package is a leftover stub. Map + lock; do not delete.
"""

from __future__ import annotations

import json
from pathlib import Path

import ux_channel

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "python" / "src" / "ux_channel"
MAP = PKG / "PACKAGE_MAP.json"


def _disk_packages() -> set[str]:
    names: set[str] = set()
    for d in PKG.iterdir():
        if not d.is_dir() or d.name.startswith((".", "_")) or d.name == "__pycache__":
            continue
        if (d / "__init__.py").is_file():
            names.add(d.name)
    return names


def test_every_on_disk_package_is_in_package_map():
    """A whole extra directory must not be invisible to make layout."""
    meta = json.loads(MAP.read_text(encoding="utf-8"))
    mapped = set(meta["packages"])
    disk = _disk_packages()
    ghosts = sorted(disk - mapped)
    assert ghosts == [], f"on disk but absent from PACKAGE_MAP.packages: {ghosts}"


def test_ops_and_enhance_are_mapped_honestly():
    meta = json.loads(MAP.read_text(encoding="utf-8"))
    packages = meta["packages"]
    strata = meta["strata"]
    docs = meta["package_docs"]

    assert "ops" in packages
    assert "enhance" in packages
    assert set(packages["ops"]) >= {"catalog", "macros", "translate"}
    assert set(packages["enhance"]) >= {
        "attach",
        "asgi_wire",
        "continuations",
        "envelopes",
        "handshake",
    }

    assert strata["ops"] in ("L3", "L4")
    assert strata["enhance"] == "L4"
    assert "enhance" in meta["plane_packages"]

    ops_doc = docs["ops"].lower()
    assert "protocol.ops" in ops_doc or "wire" in ops_doc
    assert "composition" in ops_doc or "wave" in ops_doc
    assert "envelope" in docs["enhance"].lower() or "additive" in docs["enhance"].lower()


def test_ops_and_enhance_stay_off_root_all():
    """Longevity: mapping a plane must not dump it onto application speech."""
    assert "ops" not in ux_channel.__all__
    assert "enhance" not in ux_channel.__all__
    from ux_channel.protocol import Op as WireOp
    from ux_channel.ops import Op as ComposeOp

    assert WireOp is not ComposeOp
    assert ux_channel.Op is WireOp
