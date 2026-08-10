"""CLI: add/remove methods in contract.json."""

import json
import tempfile
from pathlib import Path

from ux_channel.bridge_meta.bridge_scaffold import (
    add_contract_method,
    create_bridge_package,
    list_contract_methods,
    remove_contract_method,
)
from ux_channel.ops_dx.cli import main


def test_add_remove_methods_api():
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_package(td, "chartjs", methods=("update",), force=True)
        r = add_contract_method(
            "chartjs",
            "resetZoom",
            start=td,
            description="reset zoom",
        )
        assert "resetZoom" in r["methods"]
        data = json.loads(Path(r["path"]).read_text())
        assert "resetZoom" in data["methods"]
        assert data["methods"]["resetZoom"]["description"] == "reset zoom"

        r2 = add_contract_method(
            "chartjs",
            "setData",
            start=td,
            args=["data:object:required"],
            kwargs=True,
        )
        assert data  # path still
        data = json.loads(Path(r2["path"]).read_text())
        assert data["methods"]["setData"]["kwargs"] is True
        assert data["methods"]["setData"]["args"][0]["name"] == "data"
        assert data["methods"]["setData"]["args"][0]["required"] is True

        listed = list_contract_methods("chartjs", start=td)
        assert "setData" in listed["names"] and "resetZoom" in listed["names"]

        r3 = remove_contract_method("chartjs", "resetZoom", start=td)
        assert "resetZoom" not in r3["methods"]
        data = json.loads(Path(r3["path"]).read_text())
        assert "resetZoom" not in data["methods"]

        # register.py synced
        reg = (root / "register.py").read_text()
        assert "setData" in reg
        assert "resetZoom" not in reg


def test_cli_add_remove_methods():
    with tempfile.TemporaryDirectory() as td:
        # free-form package (no pre-seeded method_specs conflict)
        assert main(["bridge", "new", "my-map", "--out", td, "--force", "--methods", "update,destroy"]) == 0
        assert (
            main(
                [
                    "bridge",
                    "add-method",
                    "my-map",
                    "flyTo",
                    "--out",
                    td,
                    "--arg",
                    "lat:number:required",
                    "--arg",
                    "lng:number:required",
                ]
            )
            == 0
        )
        assert main(["bridge", "methods", "my-map", "--out", td]) == 0
        assert main(["bridge", "remove-method", "my-map", "flyTo", "--out", td]) == 0
        info = list_contract_methods("my-map", start=td)
        assert "flyTo" not in info["names"]
