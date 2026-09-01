"""
Bridge **presets** — data + ops for first-party builtins / vendor widgets.

Markup belongs in **ux-dom** (or templates). Bridges only provide Placement + ops.
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
    "ChartBridge",
    "ChartSeries",
    "ConfettiBridge",
    "ParticlesBridge",
    "AuroraBridge",
    "CountUpBridge",
    "SpotlightBridge",
    "LottieBridge",
    "LeafletBridge",
    "CodeMirrorBridge",
    "SelectBridge",
    "DatePickerBridge",
    "SortableBridge",
    "SwiperBridge",
    "MermaidBridge",
    "QuillBridge",
    "GenericBridge",
    "BUILTINS_SCRIPT",
    "WIDGETS_SCRIPT",
]

BUILTINS_SCRIPT = "/ux-channel/static/adapters/builtins.js"
WIDGETS_SCRIPT = "/ux-channel/static/adapters/widgets.js"
