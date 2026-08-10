"""Contracts resolve unknown npm surfaces without FFI."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.bridge_meta.bridge_contract import BridgeContract, MethodSpec, ValidationError
from ux_channel.bridge_meta.bridge_scaffold import create_bridge_package


def _ch():
    return Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
        ),
    )


def test_contract_validates_method_and_args():
    ch = _ch()
    c = BridgeContract(
        package="chartjs",
        methods={
            "setData": MethodSpec(
                name="setData",
                args=({"name": "data", "required": True},),
                kwargs=True,
            )
        },
    )
    ch.bridge.register("chartjs", contract=c)
    ops = ch.bridge.call("c1", "setData", package="chartjs", data={"labels": []})
    assert ops[0]["args"] == [{"labels": []}]
    with pytest.raises(ValidationError):
        ch.bridge.call("c1", "nope", package="chartjs")
    with pytest.raises(ValidationError):
        ch.bridge.call("c1", "setData", package="chartjs")  # missing data


def test_load_contract_from_scaffold():
    ch = _ch()
    with tempfile.TemporaryDirectory() as td:
        root = create_bridge_package(td, "leaflet", methods=("flyTo",), force=True)
        path = root / "contract.json"
        assert path.is_file()
        c = ch.bridge.load_contract(path)
        assert c.package == "leaflet"
        assert "flyTo" in c.method_names()
        d = ch.bridge.describe("leaflet")
        assert d["known"] is True
        assert "flyTo" in d["methods"]


def test_describe_unknown():
    ch = _ch()
    d = ch.bridge.describe("unknown-pkg")
    assert d["known"] is False
