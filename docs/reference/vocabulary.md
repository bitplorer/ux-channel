# Vocabulary (do not invent synonyms)

> **Diátaxis:** reference · **Canonical:** `docs/reference/vocabulary.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).
Full glossary: [../../TERMINOLOGY.md](../../TERMINOLOGY.md).

## 2. Vocabulary (do not invent synonyms)

| Term | What it is | What it is **not** |
|------|------------|---------------------|
| **Intent** | Message: `{ action, args, cap?, form?, request_id? }` | A database row |
| **Action** | Named server function registered on the channel (`"Cart.add"`) | A React event handler alone |
| **Cap / capability** | Signed token: action + **args hash** + expiry (+ optional sub/scopes) | A login session by itself |
| **args_hash** | SHA-256 of **sorted compact JSON** of args (Rust-parity) | Hash of the whole HTTP body |
| **Result** | `{ ok, ops[], error?, meta? }` | Free HTML string as the only response type |
| **Op** | One ordered effect: morph, toast, navigate, set_attr, … | Random JS eval |
| **Region** | Server-owned UI fragment with a stable **uid** | A CSS “region” |
| **Morph** | Replace/patch DOM for a region (idiomorph-style) | Full page reload (unless you `navigate`) |
| **Channel** | App façade: boot, register actions/regions, mint controls, dispatch | The HTTP framework |
| **Registry** | Table of action name → handler + hooks + cap service | Flask blueprints |
| **Principal** | Who is acting (`user_id`, roles) for authz | The cap secret |
| **state()** | App façade over session / client / db **guards** | SQLAlchemy |
| **agents()** | Non-human tool façade into the **same** registry | A second Channel |
| **Wire** | Encode/decode Intent & Result (JSON / CXB) | ASGI server |
| **CXB** | Compact binary codec for the same IR | A different product protocol |
| **Plane** | Optional product layer (realtime, MCP, bridge) | Core IR |
| **Hook** | `before` / `after` on dispatch (policy, rate limit, audit) | Express middleware for static files |

Full glossary: [TERMINOLOGY.md](../../TERMINOLOGY.md).

---
