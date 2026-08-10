"""Cognitive-load DX: recipes, help, aliases, public API freeze, strict warnings."""

from __future__ import annotations

import os
import warnings

from fastapi import FastAPI

from ux_channel import Channel, ChannelConfig
from ux_channel.paint.demo import attr_string, demo_button, demo_page, demo_scripts, script_tags
from ux_channel.devtools.cli import main as cli_main
from ux_channel.host.channel import CHANNEL_PUBLIC_API
from ux_channel.host.recipes import RECIPE_NAMES, decision_tree, recipe_text


def test_public_api_freeze_size():
    # Long-term: do not grow public API without a major version discussion
    assert len(CHANNEL_PUBLIC_API) <= 18
    assert "control" in CHANNEL_PUBLIC_API and "media" in CHANNEL_PUBLIC_API
    assert "button" not in CHANNEL_PUBLIC_API and "page" not in CHANNEL_PUBLIC_API


def test_decision_tree_and_recipes():
    tree = decision_tree()
    assert "ch.control" in tree and "media.plugin" in tree
    for name in RECIPE_NAMES:
        code = recipe_text(name)
        assert len(code) > 20


def test_channel_help_and_aliases():
    assert "ch.control" in Channel.help()
    prefer = Channel.help("prefer")
    assert "done" in prefer and "media.plugin" in prefer
    assert "Channel.boot" in Channel.help("day1") or "boot" in Channel.help("day1")
    assert "draft" in Channel.help("counter")
    assert not hasattr(Channel, "aliases")


def test_cli_recipe_and_help():
    assert cli_main(["recipe", "--list"]) == 0
    assert cli_main(["recipe", "counter"]) == 0
    assert cli_main(["recipe", "--tree"]) == 0
    assert cli_main(["help-topic", "prefer"]) == 0


def test_demo_button_is_supported_path():
    """demo_button is the official string-HTML path — no deprecation noise."""
    ch = Channel.boot(
        FastAPI(),
        config=ChannelConfig.development(
            secret="dev-secret-key-32chars-minimum!!!!",
            allow_memory_stores=True,
            require_cap=False,
        ),
    )

    @ch.on
    def ping():
        return ch.done()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        html = demo_button(ch, "X", ping)
        assert "data-channel-action" in html
        dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert dep == []
