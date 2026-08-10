"""python -m ux_channel → CLI.

Brand lines: PyPI ``ux-channel`` · import ``ux_channel`` · CLI ``uxchannel``.
Same entry as console script ``uxchannel``.

Importing this module (e.g. pkgutil.walk_packages) is a no-op unless ``__name__ == "__main__"``.
"""

from ux_channel.devtools.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
