## 2026-09-12 — Soft: Python >=3.14 floor (match compose/dom)

- Pin-lockstep: Poetry `python = ">=3.14,<4"` (compose-open, not ux-dom
  `<3.15`), classifiers 3.14, mypy `python_version = 3.14`. Ruff was
  already `target-version = "py314"`. CI runs 3.14.
- Docs / README / CONTRIBUTING leftover 3.10 floor claims raised.
  No scaffold `python_requires` 3.10 existed.
- KEEP: Cap / `Channel.boot` / `mount_channel`. `asgi/fastapi.py` not
  gutted. Soft 1–4 leftover-teach not redone. #17 thin-boot stays closed.

## 2026-09-12 — Soft 4: response HTML helpers via ux_dom.response

- Leftover: `render/response.py` (`HTMLResponse` / `html_response` /
  `render_content`). Channel does not own response HTML helpers that
  belong to ux-dom. Live owner is `ux_dom.response` when present;
  leftover clone if absent. No hard ux-dom dep. No root `__all__` names.
- KEEP: `mount_channel`, isolation/`wire/`, Cap HTTP door, ASGI Cap
  surface (`asgi/fastapi.py` not gutted). Soft 3 kit teaching is not
  in this change.
- Plan: ux-compose#76 ownership map (KEEP-HEAD) S4 contract.

## 2026-09-12 — Soft 3: demote kit teaching (honesty)

- Leftover: `ChannelComponent` / `components/` kit teaching is **not Cap product**,
  **not a sixth product**. Product UI is ux-dom + `ch.control`.
  Do not port into compose `kit/`.
- Teaching / encyclopedia leftover-teach. Kit code kept (YAGNI teaching).
  Isolation/`wire/` / `mount_channel` untouched. Soft 4 (`render/response.py`)
  not in this change.
- Plan: ux-compose#76 ownership map (KEEP-HEAD) S3 contract.

## 2026-09-12 — Soft 2: create-app honesty (lab, not product)

- Leftover: `uxchannel create-app` is a lab FastAPI scaffold, **not the product Cap door**.
  Product create-app is `uxcompose create-app` (Clock A). Cap HTTP door is
  `mount_channel` (KEEP). Do not gut `asgi/fastapi.py`.
- CLI help / DX strings / generated README leftover-teach. Verb kept.
  Isolation/`wire/` untouched. Soft 3–4 not in this change.
- Plan: ux-compose#76 ownership map (KEEP-HEAD) S2 contract.

## 2026-09-11 — Soft 1: HTML lower via ux-dom when present

- `lower_html` / `to_html` / ChannelComponent HTML paths prefer ux-dom
  serialize / escape (pin e8be99a) when importable.
- Stdlib `html.escape` if ux-dom is absent. No hard ux-dom dep.
  No root `__all__` names.
- Leftover teaching: channel does not own HTML. Live owner is ux-dom
  when present. Do not teach the channel HTML clone as the product path.
- KEEP: `mount_channel`, isolation/`wire/`, Cap HTTP door, ASGI Cap
  surface (`asgi/fastapi.py` not gutted). Soft 2–4 not in this change.
- Plan: ux-compose#76 ownership map (KEEP-HEAD).

## 2026-09-11 — Cut C: empty Content-Type fail-closed

- Python HTTP `/action` and `/batch` require a declared JSON or form
  `Content-Type`. Missing / empty is `bad_request` (was fail-open
  leftover: `http_action_content_type_ok(None)=True`).
- CXB Content-Type stays `bad_request`. JSON / form / charset params
  unchanged. Public verbs unchanged. Compose Kit/helpers untouched.
- Lock: `python/tests/gate/test_http_surface_honesty.py` + live FastAPI
  post without CT.

## 2026-09-11 — Cut A: leftover teaching + `_ch_g0` absence

- Encyclopedia names Cuts 1–2 leftovers as leftovers (compose Cut 4
  pattern). Live: `uxchannel` → `ux_channel.devtools.cli:main`;
  `ops/` + `enhance/` mapped (`ops/` ≠ `protocol.ops`); region CLI in
  `scaffold/region_cli.py`.
- Leftover (never existed / retired): `ux_channel.cli:main`, fashion
  `cli/`, `host/region_cli.py`, unmapped `ops/`/`enhance/` ghosts.
- Delete `host/_ch_g0.py` (1-line PLACEHOLDER transport stub). Not a
  product. Absence lock + leftover teaching. Do not map a ghost.

## 2026-09-11 — Cut 2: ghosts + region ownership

- Map `ops/` (Wave A composition, L3) and `enhance/` (additive
  envelopes, L4) onto `PACKAGE_MAP`. They were on disk and gated,
  but invisible to layout. Lock: every on-disk package must be mapped.
- Move `uxchannel region` body `host/region_cli.py` →
  `scaffold/region_cli.py`. Public verb names unchanged; argv
  dispatcher stays `devtools.cli`. Runtime `host.regions` stays L2.

## 2026-09-11 — Cut 1: CLI honesty (console script)

- Poetry script `uxchannel` now points at the live owner
  `ux_channel.devtools.cli:main` (was `ux_channel.cli:main`, which
  did not exist). Public CLI verbs unchanged. No `cli/` package.
- Gate lock: the script target must import-resolve to that live `main`.

## 2026-09-09 — FileStateStore (serve-dev sqlite)

- `FileStateStore` in `host.stores`: JSON sqlite WAL, same StateStore
  protocol as Memory. Values JSON (`default=str`), matching Redis —
  not pickle.
- `Channel.boot` opens it when `UXCOMPOSE_STATE_STORE` is set and
  `REDIS_URL` is not. Explicit `state=` and Redis still win.
- `change()` uses `BEGIN IMMEDIATE` so two processes cannot lose
  increments (ui + channel workers).
- Compose serve-dev prepares the path; Channel owns the class (ADR
  0006 on ux-compose).

## 2026-09-01 — Organization: core in host, L4 lazy, FastAPI is an adapter


- `Channel.__init__` attaches only L2 core (regions, flow, live, document,
  enterprise mint policy). Cap plane = `cek/` (cek-runtime Host façade);
  `arch` deleted cut #4. `ch.webrtc` / `ch.media` / `ch.bridge`
  attach on first attribute access. Public names unchanged.
- `bridge/__init__.py` is PEP 562 lazy so `bridge.plugins` (Door D hub)
  does not import `bridge_plane` at factory boot.
- One-page PE map: `python/src/ux_channel/LAYERS.md`. Encyclopedia
  `python/docs/start/LAYERS.md` points at it.
- START_HERE / README / MENTAL_MODEL lead with the protocol, then HTTP.
  FastAPI stays `asgi/` (Door F).
- Gate: headless boot must not import L4 planes; lazy planes are
  idempotent; ux-compose frozen import paths exist.
- No package moves. No public-API renames. Compose `wire/` untouched.

## 2026-09-01 — Adapter residuals + island kernel

- `ux-bridge.js`: one `scan`; `hostFor` reads `op._el` first.
- `bridge.update` is generic: `adapter.update` → `handle.update` → remount.
  Same idea as `bridge.call` (`adapter.call` → `handle[method]`).
- Stock packs no longer re-wrap `update`/`call`. Methods live on the handle.
- Pack files: `adapters/builtins.js` (`builtin/*`) and `adapters/widgets.js`
  (vendor names). Shims `ux-fx.js` / `ux-ui.js` removed.
- `builtin/confetti`: `destroy` drops the resize listener; `rain` honors `raining`.
- `lottie-web` lives in widgets.js; `handle.update` remounts on the real host.
- Spotlight overlay is pack-private class `.ux-spotlight`.
- Kit: `builtins_script_tags()` / `widgets_script_tags()`.
- Docs teaching keys follow the running package `chart.js` (`CHART_PACKAGE`).
  Folder / CLI slugs (`chartjs`) stay.
- Public surface unchanged: `register` / `apply` / `scan` / `instances` / `version`.

## 2026-08-31 — Door H: closed core, four doors

- Browser runtime is a closed core. Python (or a driver) mints `Result.ops[]`.
  JS only applies. New client behaviour enters through doors, not new
  `applyOp` cases: `registerOp`, `on` (beforeApply / beforeOp / afterOp /
  afterApply), `configure` (existing error-plane knobs), `uxBridge.register`.
- Client bag is `uxChannel.signals`, written only by `signal.set`.
  No `store` alias.
- Persist is the existing Python flag: `st.client(..., persist=True)` after
  `state(ch, allow=[...])`. JS writes `localStorage["channel:sig:"+path]`
  and silently hydrates that prefix on boot (`SIG_PREFIX.length`, not
  `slice(8)`). No hydrate / restore-focus body attrs or configure knobs.
- Morph focus/scroll restore stays always-on. It is not persist.
- Docs: `docs/reference/client-runtime.md`, EXTENSIONS Door H, LONGEVITY
  Door H, `python/docs/client/JS_RUNTIME.md`, FEATURES §4.1 / §6,
  `python/docs/state/STATE.md` (dead `PLANES.md` link → state-planes),
  `python/docs/ts-client.stub.d.ts` (`registerOp`, `signals`).
- Test: `test_js_runtime_multi_load.py::test_client_runtime_doors`.
- Python `ClientPlane` / persist minting unchanged.

---

## 2026-08-28 — Live field latest-wins

- `input` / `change` on the same control abort the in-flight Intent
  (AbortController already on `postIntent`). Replaced Results do not
  morph and do not toast timeout. Click / swipe / longpress still drop
  while in-flight.
- Docs: JS_RUNTIME live fields. Test: `test_js_live_field_last_wins.py`.

---

## 2026-08-27 — Signal → Intent

- Client: `data-channel-on` grammar (`delay:`, `threshold:`, `throttle:`, `once`).
- Signals: click, change, input, blur, longpress, swipe.*; synth horizontal|vertical.
- Form attach on control signals; inherit on/target.
- No `data-channel-swipe*` / `on-debounce` / `on-threshold` attribute families.
- Docs: `python/docs/client/JS_RUNTIME.md`, `python/docs/FEATURES.md` §1.3b.

---

## 2026-08-15 — Enhance runtime wiring

- `enhance/attach.py` — HandshakeRegistry + SessionRecorder façade on Channel
- `enhance/asgi_wire.py` — pure helpers for hello + post-dispatch project
- `asgi/enhance_routes.py` — `POST {path}/hello` without editing core fastapi.py
- `Channel.boot` attaches enhance plane (opt-out: `config.enhance=False`)
- `ch.enhance.mint_continuation` mints real attenuated Caps
- Gate: `python/tests/gate/test_enhance_runtime.py` (8 passed)
- Classic IR 0.1 clients unchanged

---

## 2026-08-15 — Enhance plane activation

- Host handshake: `HandshakeRegistry` / `PeerSession` project Result.ops via PeerHello surfaces
- Real DOM drivers: `static/ux-peer-dom-drivers.js`
- Demo: `demos/enhance_search/`
- Waves A–G remain additive; classic IR 0.1 unchanged
