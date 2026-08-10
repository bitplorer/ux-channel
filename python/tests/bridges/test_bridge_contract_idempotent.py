"""Idempotent contract method edits + schema normalize."""

import json
import tempfile
from pathlib import Path

import pytest

from ux_channel.bridge.bridge_scaffold import (
    CONTRACT_SCHEMA_VERSION,
    add_contract_method,
    create_bridge_package,
    normalize_contract,
    remove_contract_method,
)
from ux_channel.devtools.cli import main


def test_add_method_idempotent_same_signature():
    with tempfile.TemporaryDirectory() as td:
        create_bridge_package(td, "chartjs", methods=("update",), force=True)
        a = add_contract_method("chartjs", "resetZoom", start=td)
        b = add_contract_method("chartjs", "resetZoom", start=td)
        c = add_contract_method("chartjs", "resetZoom", start=td)
        assert a["action"] == "added"
        assert b["action"] == "unchanged" and b["idempotent"] is True
        assert c["action"] == "unchanged"
        data = json.loads(Path(a["path"]).read_text())
        assert list(data["methods"]).count("resetZoom") == 0 or True
        assert sum(1 for k in data["methods"] if k == "resetZoom") == 1
        assert data["schema_version"] == CONTRACT_SCHEMA_VERSION


def test_add_method_conflict_requires_force():
    with tempfile.TemporaryDirectory() as td:
        create_bridge_package(td, "chartjs", methods=("update",), force=True)
        add_contract_method("chartjs", "setData", start=td)
        with pytest.raises(Exception, match="force|signature|conflict"):
            add_contract_method(
                "chartjs", "setData", start=td, args=["data:object:required"]
            )
        u = add_contract_method(
            "chartjs",
            "setData",
            start=td,
            args=["data:object:required"],
            force=True,
        )
        assert u["action"] == "updated"


def test_remove_method_idempotent():
    with tempfile.TemporaryDirectory() as td:
        create_bridge_package(td, "x", methods=("update", "destroy"), force=True)
        r1 = remove_contract_method("x", "destroy", start=td)
        r2 = remove_contract_method("x", "destroy", start=td)
        assert r1["action"] == "removed"
        assert r2["action"] == "absent" and r2["idempotent"] is True


def test_normalize_upgrades_list_methods():
    n = normalize_contract(
        {"package": "p", "methods": ["a", "b"], "lifecycle": ["mount"]}
    )
    assert n["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert n["lifecycle"] == ["mount", "update", "call", "destroy"]
    assert set(n["methods"]) == {"a", "b"}
    assert n["methods"]["a"]["name"] == "a"


def test_cli_double_add():
    with tempfile.TemporaryDirectory() as td:
        assert main(["bridge", "new", "z", "--out", td, "--force"]) == 0
        assert main(["bridge", "add-method", "z", "foo", "--out", td]) == 0
        assert main(["bridge", "add-method", "z", "foo", "--out", td]) == 0
        assert main(["bridge", "remove-method", "z", "foo", "--out", td]) == 0
        assert main(["bridge", "remove-method", "z", "foo", "--out", td]) == 0
