"""
Lab cell workplace vertical — budgeted DUT flash + mesh membership.

  PYTHONPATH=src uvicorn examples.workplace_lab.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ux_channel import Channel, ChannelConfig, attach_audit
from ux_channel.paint.demo import script_tags
from ux_channel.io_adapters import LabDutAdapter
from ux_channel.foundations.quantity import Quantity
from ux_channel.workplace import (
    issue_mesh_membership,
    revoke_mesh_membership,
    workplace_from_membership,
)

SECRET = os.environ.get("UX_CHANNEL_SECRET", "workplace-lab-secret-key-32bytes-min!!")
app = FastAPI(title="Workplace Lab")
ch = Channel.boot(
    app,
    config=ChannelConfig.development(
        secret=SECRET,
        allow_memory_stores=True,
        require_cap=True,
        require_channel_header=True,
        audit=True,
    ),
)
attach_audit(ch)
lab = LabDutAdapter(dut_id=os.environ.get("UID_DUT_ID", "dut-42"))

RUNTIME: dict[str, Any] = {}
RUNTIME["membership"] = issue_mesh_membership(
    ch,
    "lab-cell",
    sub=os.environ.get("UID_LAB_TECH", "tech-1"),
    scopes=["lab", "lab.flash", "view"],
    trust={"bench": "A"},
    max_age=900,
)
# Prefer ch.webrtc.issue_membership for the same shape:
# RUNTIME["membership"] = ch.webrtc.issue_membership("lab-cell", sub="tech-1", scopes=[...])
RUNTIME["wp"] = workplace_from_membership(ch, RUNTIME["membership"]).allow(lab)


def wp():
    return RUNTIME["wp"]


def _hdr(x: Optional[str]) -> None:
    if x != "1":
        raise HTTPException(403, "X-Channel required")


@ch.on
def lab_id() -> Any:
    info = wp().run_io("lab.dut", "id")
    return ch.done(notice=str(info), refresh=["bench"])


@ch.on
def lab_flash() -> Any:
    q = Quantity.from_store(
        1, "count", source="lab.policy.flash_budget", revision=lab.flash_count + 1
    )
    try:
        out = wp().run_io("lab.dut", "flash", quantity=q)
    except Exception as exc:
        return ch.fail.validation(str(exc))
    return ch.done(notice=f"flash ok {out.get('flash_count')}", refresh=["bench"])


@ch.region("bench")
def bench_region(ctx: Any) -> str:
    info = lab.call("id", [], claim=wp().claim)
    snap = wp().snapshot()
    return (
        f'<div class="card" data-channel-id="bench"><h2>Lab cell</h2>'
        f"<p>DUT <code>{info['dut_id']}</code> flashes=<b>{info['flashes']}</b></p>"
        f"<p class='muted'>room={snap['room']} peer={snap['peer_id']} "
        f"scopes={snap['scopes']}</p></div>"
    )


@app.post("/api/membership")
async def api_membership(
    request: Request,
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    _hdr(x_ux_channel)
    try:
        body = await request.json()
    except Exception:
        body = {}
    sub = str((body or {}).get("sub") or RUNTIME["membership"].sub)[:64]
    RUNTIME["membership"] = ch.webrtc.issue_membership(
        "lab-cell",
        sub=sub,
        scopes=["lab", "lab.flash", "view"],
        trust={"bench": "A"},
        max_age=900,
    )
    RUNTIME["wp"] = workplace_from_membership(ch, RUNTIME["membership"]).allow(lab)
    return JSONResponse(RUNTIME["membership"].to_dict())


@app.post("/api/logout")
def api_logout(
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    """Revoke mesh membership (workplace + RTC tickets)."""
    _hdr(x_ux_channel)
    mem = RUNTIME["membership"]
    revoke_mesh_membership(mem, channel=ch)
    return JSONResponse({"revoked": True, "room": mem.room, "sub": mem.sub})


@app.get("/api/audit")
def api_audit(
    x_ux_channel: Optional[str] = Header(default=None, alias="X-Channel"),
) -> JSONResponse:
    _hdr(x_ux_channel)
    return JSONResponse({"io": wp().export_io_audit(), "workplace": wp().snapshot()})


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    w = wp()
    b_id = w.control(lab_id)
    b_flash = w.control(lab_flash)

    def btn(label: str, ctrl) -> str:
        return f"<button type='button' {ctrl}>{label}</button>"

    css = """
    body{font-family:system-ui,sans-serif;margin:0;background:#0c121c;color:#e8eef8}
    main{max-width:640px;margin:0 auto;padding:1.25rem;display:grid;gap:1rem}
    .card{background:#152033;border:1px solid #2a3a52;border-radius:12px;padding:1rem}
    button{background:#0d9488;color:#fff;border:0;border-radius:8px;padding:.5rem .9rem;margin-right:.4rem;cursor:pointer}
    .muted{opacity:.75;font-size:.9rem} code{background:#0a1018;padding:.1rem .3rem;border-radius:4px}
    """
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Lab Workplace</title>{script_tags(ch)}<style>{css}</style>
</head><body {ch.body_attr_string()}>
<main>
{bench_region(None)}
<div class="card">
  <h3>Lab actions (claim-aware)</h3>
  {btn("Read id", b_id)}
  {btn("Flash (budget 1)", b_flash)}
  <p class="muted">logout: POST /api/logout · membership: POST /api/membership</p>
</div>
</main></body></html>"""
    )
