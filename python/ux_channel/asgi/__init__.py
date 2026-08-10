"""
ASGI host adapters package.

Host adapters are optional plug-and-play modules:

  ux_channel.asgi.fastapi    — FastAPI (most common)
  ux_channel.asgi.starlette  — Starlette-only

Import the submodule you need; core ux_channel never imports these at
package import time so installs without FastAPI stay light.
"""
