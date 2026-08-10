"""
Minimal agent/MCP demo — run:

  UX_CHANNEL_AGENT_TOKEN=dev-token uvicorn examples.agent_mcp.app:app --port 8090

Then:
  curl -H "Authorization: Bearer dev-token" http://127.0.0.1:8090/ux-channel/mcp/tools
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import ActionRegistry, Result, toast
from ux_channel.agent_runtime import AgentPolicy, agent_tool
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.host.config import ChannelConfig

app = FastAPI(title="uxchannel agent demo")
cfg = ChannelConfig.development(
    secret="demo-secret-key-32chars-minimum!!",
    mount_agent_mcp=True,
    agent_token="dev-token",
    rate_limit_per_minute=0,
    enforce_same_origin=False,
)
reg = ActionRegistry.from_config(cfg)


@reg.action("Search.query")
@agent_tool("Search demo knowledge base", read_only=True, tags=("search",))
def search(q: str = ""):
    return Result.success(toast(f"found: {q or '(empty)'}"))


@reg.action("Echo.say")
@agent_tool("Echo a message", read_only=True)
def echo(msg: str = ""):
    return Result.success(toast(msg or "…"))


app.state.uid_agent_policy = AgentPolicy.production(
    allow=["Search.query", "Echo.say"],
    max_calls_per_session=100,
)
mount_channel(app, reg, config=cfg, mount_agent_mcp=True)


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><html><body>
    <h1>Agent/MCP demo</h1>
    <p>Use <code>GET /ux-channel/mcp/tools</code> with Bearer dev-token.</p>
    </body></html>"""
