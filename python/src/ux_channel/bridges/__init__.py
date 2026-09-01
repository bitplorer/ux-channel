"""
Bridge **presets** — data + ops for stock scenes / vendor widgets.

Markup belongs in **ux-dom** (or templates). Bridges only provide Placement + ops.

Charts & effects::

    from ux_channel.bridges import ChartBridge, ConfettiBridge, AuroraBridge

Vendor widget islands::

    from ux_channel.bridges import (
        LeafletBridge, CodeMirrorBridge, SelectBridge, DatePickerBridge,
        SortableBridge, SwiperBridge, MermaidBridge, QuillBridge,
        GenericBridge,
    )

    maps = LeafletBridge(ch)
    m = maps("hq", center=[28.6, 77.2], zoom=11)
    # host: Div(**m.mount_attrs(class_name="h-80 rounded-xl"))

Any package without a preset::

    widgets = GenericBridge(ch, package="my-lib", methods=("update", "destroy"))
    w = widgets("w1", theme="dark")
"""

from ux_channel.bridges.aurora import AuroraBridge
from ux_channel.bridges.chartjs import ChartBridge, ChartSeries
from ux_channel.bridges.codemirror import CodeMirrorBridge
from ux_channel.bridges.confetti import ConfettiBridge
from ux_channel.bridges.countup import CountUpBridge
from ux_channel.bridges.datepicker import DatePickerBridge
from ux_channel.bridges.generic import GenericBridge
from ux_channel.bridges.leaflet import LeafletBridge
from ux_channel.bridges.lottie import LottieBridge
from ux_channel.bridges.mermaid import MermaidBridge
from ux_channel.bridges.particles import ParticlesBridge
from ux_channel.bridges.quill import QuillBridge
from ux_channel.bridges.select import SelectBridge
from ux_channel.bridges.sortable import SortableBridge
from ux_channel.bridges.spotlight import SpotlightBridge
from ux_channel.bridges.swiper import SwiperBridge

__all__ = [
    # charts
    "ChartBridge",
    "ChartSeries",
    # scenes (stock visual islands)
    "ConfettiBridge",
    "ParticlesBridge",
    "AuroraBridge",
    "CountUpBridge",
    "SpotlightBridge",
    "LottieBridge",
    # widgets (vendor islands)
    "LeafletBridge",
    "CodeMirrorBridge",
    "SelectBridge",
    "DatePickerBridge",
    "SortableBridge",
    "SwiperBridge",
    "MermaidBridge",
    "QuillBridge",
    "GenericBridge",
    # script paths
    "SCENES_SCRIPT",
    "WIDGETS_SCRIPT",
    "FX_SCRIPT",
    "UI_SCRIPT",
]

SCENES_SCRIPT = "/ux-channel/static/adapters/scenes.js"
WIDGETS_SCRIPT = "/ux-channel/static/adapters/widgets.js"
FX_SCRIPT = SCENES_SCRIPT  # old name
UI_SCRIPT = WIDGETS_SCRIPT  # old name
