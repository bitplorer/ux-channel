# Principles — uxchannel 0.1

These principles match the implementation (see `docs/start/COURSE.md`).

## 1. Protocol, not framework

Intent → Action → Result(ops) is the product. Everything else is a layer
(host, live, bridge, components, agents).

## 2. HTML libraries own trees

ux-dom / Jinja / Django templates own markup. Channel owns **control**,
**trust**, **regions**, **ops**. Demo `ch.button` / `ch.page` are not the
product path (`ux_channel.render.kit`).

## 3. One name per concept

| Concept | Name |
|---------|------|
| Morph slot | **region** |
| Re-render | **refresh** |
| Signed args | **trust** / capability |
| npm widget | **bridge** |
| In-process topic map | **live.bind** |
| Fan-out transport | **push bus** |

## 4. Fail closed

Invalid caps, missing CSRF header (prod), unsafe `navigate` hrefs, private
push topics without tickets — reject. Prefer soft UI noop only when documented
(e.g. navigate block → noop op with reason).

## 5. Caps seal authority; loaders re-read truth

Sealed `trust_*` args identify *what* was clicked. Handlers reload DB/draft
state rather than trusting a full client snapshot.

## 6. Idempotent by declaration

Automatic retries (batch) require `@ch.on(idempotent=True)`. Mutations stay
default non-idempotent. Once-caps remain single-use.

## 7. Result body is truth; HTTP is secondary

Clients branch on `ok` / `error.code`. Status codes come from `error_map` for
proxies and logs.

## 8. Live.bind ≠ Redis

`ch.live.bind` is process-local. Multi-worker fan-out is the push bus
(`ux_channel.push`) with a Redis backend when needed.

## 9. Optional kits never pollute core

`from ux_channel import Channel, Region, Result` stays small. Components,
agents, MCP, redis_extra are explicit submodule imports.
