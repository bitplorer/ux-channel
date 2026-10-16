"""Every shipped module must at least compile; ux_channel.catalog once did not."""
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
MODULES = sorted(SRC.rglob("*.py"))


@pytest.mark.parametrize("path", MODULES, ids=lambda p: str(p.relative_to(SRC)))
def test_module_compiles(path):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_catalog_help_is_importable_and_multiline():
    from ux_channel.catalog import help_package, help_public

    text = help_public()
    assert text.startswith("Public: ") and text.count("\n") >= 5
    assert help_package("no-such-package") == "unknown package: no-such-package\n"
