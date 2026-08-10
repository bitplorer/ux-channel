"""Login form demo — validation + navigate.

  uvicorn examples.forms.app:app --reload --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ux_channel import ActionRegistry, Go, Result, focus, form_open, morph, toast
from ux_channel.asgi.fastapi import mount_channel
from ux_channel.render.html import attr_escape

SECRET = "dev-only-change-me"
# Form posts put fields in intent.form; cap is signed with empty args
reg = ActionRegistry(secret=SECRET, require_cap=True, expose_internal_errors=True)


def login_form_html(email: str = "", errors: dict | None = None) -> str:
    errors = errors or {}
    cap = reg.mint("Login.save", {})
    email_err = (errors.get("email") or [None])[0]
    pw_err = (errors.get("password") or [None])[0]

    def err_p(name: str, msg: str | None) -> str:
        if msg:
            return (
                f'<p data-channel-error="{name}" style="color:#b91c1c;font-size:.85rem">'
                f"{attr_escape(msg)}</p>"
            )
        return f'<p data-channel-error="{name}" hidden></p>'

    return f"""
{form_open("Login.save", cap=cap, target='[data-channel-id="Login:root"]', uid_id="Login:root", **{"class": "login", "style": "display:grid;gap:.75rem;max-width:20rem"})}
  <label>Email
    <input id="email" name="email" type="email" value="{attr_escape(email)}"
      style="display:block;width:100%;padding:.5rem;margin-top:.25rem"
      {"aria-invalid=true" if email_err else ""}/>
    {err_p("email", email_err)}
  </label>
  <label>Password
    <input id="password" name="password" type="password"
      style="display:block;width:100%;padding:.5rem;margin-top:.25rem"
      {"aria-invalid=true" if pw_err else ""}/>
    {err_p("password", pw_err)}
  </label>
  <button type="submit">Sign in</button>
</form>
"""


@reg.action("Login.save")
def save(email: str = "", password: str = ""):
    fields: dict[str, list[str]] = {}
    if not email or "@" not in email:
        fields["email"] = ["Enter a valid email"]
    if not password or len(password) < 8:
        fields["password"] = ["Min 8 characters"]
    if fields:
        html = login_form_html(email=email, errors=fields)
        return Result.failure(
            "validation",
            "Fix the highlighted fields",
            morph(target='[data-channel-id="Login:root"]', html=html),
            focus(target="#email", select=True),
            toast("Fix the highlighted fields", level="error"),
        )
    if email == "demo@uid.dev" and password == "password1":
        return Go("/welcome")
    html = login_form_html(email=email, errors={"email": ["Invalid credentials"]})
    return Result.failure(
        "unauthorized",
        "Invalid credentials",
        morph(target='[data-channel-id="Login:root"]', html=html),
        toast("Invalid credentials", level="error"),
    )


app = FastAPI(title="uxchannel forms")
mount_channel(app, reg)


@app.get("/", response_class=HTMLResponse)
def index():
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>uxchannel forms</title>
  <script src="/ux-channel/static/ux-channel.js" defer></script>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 28rem; margin: 3rem auto; padding: 0 1rem; }}
    .hint {{ color: #64748b; font-size: .9rem; }}
    code {{ background: #f1f5f9; padding: .1rem .3rem; border-radius: 4px; }}
  </style>
</head>
<body data-channel-endpoint="/ux-channel/action" data-channel-dev>
  <h1>Uid Channel — form</h1>
  <p class="hint">Try <code>demo@uid.dev</code> / <code>password1</code></p>
  {login_form_html()}
</body>
</html>"""


@app.get("/welcome", response_class=HTMLResponse)
def welcome():
    return """<!doctype html><html><body style="font-family:system-ui;margin:3rem">
    <h1>Welcome</h1><p>Login succeeded via navigate op.</p>
    <p><a href="/">Back</a></p></body></html>"""
