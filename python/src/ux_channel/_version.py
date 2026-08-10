"""Library semver (PEP 440). Product line: **ux-channel** 0.1 / CLI ``uxchannel``.

Wire protocol field names (``data-channel-*``, Intent/Result ``v`` protocol version)
are separate from this library version — do not confuse the two.
"""

__version__ = "0.1.0"
__version_info__ = tuple(int(x) for x in __version__.split(".")[:3])
