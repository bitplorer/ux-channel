## Unreleased

- `data-ux-keep-value` keeps the visitor's live `.value` across a morph or
  outer swap for a `textarea`, or for an `input` of type `password`, `text`,
  `email`, `search`, `tel`, or `url`. Those six types are one class, so Show
  can switch `password` to `text` and the value stays. Textarea matches only
  textarea. A change into or out of the class (`hidden`, `checkbox`, `radio`,
  `file`, `select`, and anything else) restores nothing, and each ignored mark
  logs one console warning. The key is `JSON.stringify` of four strings:
  the closest ancestor `data-channel-id` (or `""`), the form identity, the
  field `name`, and the kind class. Form identity is `id:` plus the form id,
  `name:` plus the form name, `unnamed`, or `none`. Every form is scoped by
  its component, so a form id moving from component a to component b does
  not keep the value. An unnamed form with no component root restores
  nothing and logs one warning, the same as a field with no form and no
  component root. One warning is logged per ignored field per morph. A
  marked field with no `name` restores nothing and logs one warning,
  including inside a form or a component. A field that has a name, inside
  a named form or inside a component, does not log that warning. `id` is
  not the key. Shared keys restore nothing.
  After the fragment is in the DOM, the client writes `el.value` inside its
  own try/catch. A throw while reading or writing one marked field skips
  that field and logs one warning that names the error; the other fields
  continue. The name is `error.message` when that is a non-empty string.
  An empty message uses the constructor name, or `Error` when that name is
  empty. Otherwise the name is `String(error)`, or `unknown error` when
  that throws. The thrown value is the
  second `console.warn` argument. Two fields that throw the same message
  each log a warning; the same field logs one, including when a nested morph
  runs during this one. If Idiomorph throws, the
  error is reported the same way as any other failed morph, and kept values
  for the other fields are still restored. The partial morph is left in
  place. A throw while restoring kept values, including while listing the
  marked fields, only logs that warning. It does not replace a morph error,
  and it does not create an op error when the morph succeeded. The same
  holds when the page has no Idiomorph and the client uses `replaceWith`.
  If the saved element throws while it is being matched, or a node's key
  cannot be decided, that field is not restored and the value is not written
  into a different field. A different field's throw does not clear the
  others. The throw logs the same warning.
  It does not set the value attribute, parse the value, or
  insert a node, and it does not send the value to the server. Focus restore
  is unchanged. The server should paint `value=""` for secrets.
- `set_attr` URL attributes (`href`, `src`, `action`, `formaction`, `xlink:href`, `poster`, and the other URL attributes) go through `safe_href`. Refused on every URL attribute: `javascript:`, `vbscript:`, `file:`, `jar:`, `blob:` except on src-type attributes, `data:` other than the src image types below (including `data:text/html` and `data:image/svg+xml`), any other scheme besides `http`, `https`, `mailto`, and `tel`, and those schemes with whitespace, control-character, or HTML-entity obfuscation (`&#106;`, `&#x6A;`, `&colon;`, `&#38;#106;`, `java&#115;cript:`, and the same shapes). The builder and the Result href sanitizer do this on the server; the client `set_attr` path calls `safeHref` the way `navigate` and `push_url` already do. The server and the client apply the same rule: a dict or a list is refused and is never stringified, and protocol-relative `//` is recognized only after trimming whitespace, so `\x01//x` and `/\t/x` are refused on both. Relative, `http(s)`, `mailto`, `tel`, and empty values still apply. Non-URL attributes are unchanged. `navigate` and `push_url` still refuse protocol-relative URLs.
- Kept on URL attributes: protocol-relative `//cdn/...` URLs. Kept on src-type attributes only (`src` and names ending in `:src`): `blob:` and `data:image/png`, `data:image/jpeg`, `data:image/gif`, `data:image/webp`, `data:image/avif`. The same image and blob values on `href` or `poster` are still refused.
- `set_attr` refuses event-handler names (`on*`, including `onclick`, `onerror`, and `ONLOAD`) and `srcdoc` as a noop (`reason=unsafe_attr`) on every channel patch and push. Markup is not a JavaScript trust marker: `Markup("select({})").format(user)`, `Markup("go(%s)") % user`, and `markupsafe.escape(js)` are refused the same way a plain string is. `data-onclick` is not an event-handler name and is unchanged.
- Dict and list values are refused on the server and the client and are never stringified. `href=["javascript:alert(1)"]`, `href=["https://example.com/a"]`, `src=["data:text/html,…"]`, and `href={"a": 1}` are omitted. Other non-string values are still turned into a string the way `setAttribute` does, so a numeric href is stored as its string form (`1` → `"1"`). The push policy is stored on each channel's bus, not on the process. A channel with no policy is `off` for patches and pushes, over JSON and SSE. Strict is opt-in. A bare `PushBus()` or a stream with no channel is strict. An unknown value, including `strict `, ` strict`, `strcit`, and `on`, raises. `Strict` is not accepted. `set_push_bus()` after boot keeps that channel's policy, and booting another channel does not change it.
- `seq`, `timer.set`, `invoke`, and any other op that carries nested `ops` are href-checked and, when `morph_html_policy` is `strict`, stripped. `PushBus.publish` runs that same filter, using the policy stamped from `ChannelConfig` at boot. A strict `seq(swap(...))` no longer keeps `onerror`, and a nested `javascript:` href is omitted on the way out.
- `morph_html_policy="strict"` strips `swap` HTML with the same rules as `morph` and toast. The default `"off"` still leaves swap, morph, and toast markup unchanged.
- That strict stripper parses with html5lib (scripting on, so svg/math are foreign content and `noscript` is raw text) and serializes the scrubbed tree. `style` stays raw text in HTML and is dropped in svg/math. If main's regex pass would still change that serialization, or the parser raises, the fragment is empty. `data-*` attributes and custom elements stay.
- html5lib 1.1 was last released on 2020-06-22 and is tracked as a dependency to watch. Only the strict sanitizer imports it, and only inside the strip function. Policy `off` does not import it. If the import fails or the parser raises, the strict patch is refused. Intake: `python/docs/security/html5lib-intake.md`.
- A message that arrives on the Redis push bus is filtered with that channel's policy before a local subscriber sees it. A raw `onclick` published straight to Redis does not reach `/push` when the policy would have removed it.
- `format_sse` applies the outbound policy to a bare Result dict and to a `Result` object under `result`. A stream with no channel is strict.
- Under `strict`, `navigate`, `push_url`, and `redirect` keep an absolute http(s) URL only when its host is the request `Host` or `navigate_allowed_hosts`. `//x`, `/\t/x`, `\x01//x`, and `javascript:` stay refused. A push has no request. Policy `off` still uses `safe_href`.
- The client `set_attr` path refuses the same `on*` and `srcdoc` names the server drops.
## 0.1.2 — dead-code cleanup

- Version bump 0.1.1 → 0.1.2 (patch: no runtime behaviour change; version strings in
  `pyproject.toml`, `VERSION`, `_version.py`, client JS `VERSION`, docs, and the
  conformance `package_version` provenance field).
- Removed unused imports across `python/src` (about 460, all non-`__init__` modules).
  `__init__.py` re-exports are untouched. `protocol/encode.py` keeps its
  `Go`/`Navigate` re-export, now marked `# noqa: F401`.
- Removed unreachable code: the second `raise RuntimeError` after the
  `try/finally` in `ActionRegistry.dispatch` (`host/registry.py`), the dead
  `else: ticket_err = None` after a returning `try` in `security/push_security.py`,
  and the no-op `staticmethod(paginate) if False else paginate` assignment in
  `devtools/enterprise.py`.
- `asgi/starlette.py`: dropped the unused `allowed_origins` / `enforce_same` locals.
  Origin checks were already enforced (fail closed) by `asgi.pipeline.preflight_action`;
  new `tests/security/test_starlette_origin.py` locks that for the Starlette adapter.
- f-strings without placeholders made plain strings (3 sites).
- Examples: `composites_demo` no longer has the broken `class ux-dom:` rename
  (now `DomNode`); `plugins_demo` and `ux_dom_threejs` import from
  `bridge_api` after `from __future__` (they failed to import before).
- Kept on purpose: `tb` in `host/stores.py` `__exit__`/`__aexit__` (protocol
  signature); the F821 hit in `scaffold/region_cli.py` is inside a template string.
- New locks: `tests/core/test_no_unused_imports.py`, `tests/core/test_dead_code_removed.py`.

## 0.1.1 — remove deprecations

- Version bump 0.1.0 → 0.1.1 (patch: no runtime behaviour change; docs, version strings, regenerated conformance provenance and harness) (`pyproject.toml`, `_version.py`, client JS
  `VERSION` in `static/*.js`).
- Docs no longer teach removed shims: `ch.button` / `ch.page`
  DeprecationWarning note (DX.md), root `ux_channel.region_component` /
  `ux_channel.regions` shims (TERMINOLOGY.md), "legacy shims" (ONTOLOGY.md,
  NAMING.md). The code paths were already gone.
- New lock `tests/gate/test_no_deprecations.py`.
- Conformance: `expected/cxb/index.json` `package_version` is now read from the
  oracle's `ux_channel.__version__` at regeneration (was hard-coded `0.1.0`).
  Regenerated with 0.1.1: all 14 `.cxb` blobs are byte-identical; only the
  provenance field changed. The suite id `ux-channel-cxb-expected-0.1` is the
  fixture-format version and stays. Harnesses no longer search stale
  `ux-channel-0.1.0` zip paths; the oracle is in-repo `python/src`
  (override: `UX_CHANNEL_SRC`).
- `.gitignore`: `soak-report.json` (written by the soak test).

## 2026-09-24 — cek-host 0.2.0 floor

- Required deps are `cek-host>=0.2.0` and `cek-surface>=0.2.0`.
  Versions before 0.2.0 teach `cek_host.legal`. Do not pin them.
  `0.1.0`, `0.1.2`, and `0.1.3` are yanked. An exact pin still installs them.
  The git pin of cek-python `0626a10` is gone.
- `require_cek_min` refuses a Host older than 0.2.0.
- HMAC `previous_secrets` is still classic CapService only. 0.2.0
  did not add that API.

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
