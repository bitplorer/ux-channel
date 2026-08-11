# Operational notes — not tribal knowledge

Glossary: [`TERMINOLOGY.md`](TERMINOLOGY.md). Recipes: [`REFERENCE.md`](REFERENCE.md). FAQ: [`FAQ.md`](FAQ.md).  
Story + diagrams: [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md).  
Permanent vs moving: [`STRUCTURE.md`](STRUCTURE.md).

These rules are **normative for operators** of any peer that uses this package.
They are easy to miss if you only read the IR SPEC.

---

## 1. Capability secrets

| Rule | Detail |
|------|--------|
| **Never ship production with the oracle secret** | `ORACLE_SECRET` / `conformance-oracle-secret-32chars!!` is **public** (in git). Anyone can mint caps for that secret. |
| **Production** | Set a private high-entropy secret (≥ 16 bytes / 16 chars) via `UXC_CAP_SECRET`. Leave `UXC_ALLOW_ORACLE_SECRET` **unset**. |
| **Local demo / CI only** | Set `UXC_ALLOW_ORACLE_SECRET=1` (or `true`). Without it, `uxc_peer` **refuses** to start if the secret is missing, empty, or equal to the public oracle. |
| **Mint endpoint** | `POST /ux-channel/mint` is **dev/demo**. Do not expose it on a public production host without auth + private secret. |
| **Rotation** | Cap verifier supports a previous-secret window; rotate without invalidating all live controls at once. |

**Footgun:** `UXC_CAP_SECRET=conformance-oracle-secret-32chars!!` looks “configured” but is still the public oracle. The peer refuses that value unless allow-listed.

---

## 2. Environment variables (`uxc_peer`)

| Variable | Required | Meaning |
|----------|----------|---------|
| `UXC_CAP_SECRET` | **Production: yes** | Signing/verification secret (≥ 16 chars). Must not equal the public oracle secret unless allow-listed. |
| `UXC_ALLOW_ORACLE_SECRET` | Demo only | Set to `1` / `true` to permit the public conformance oracle secret (or empty/unset secret fallback). |
| `UXC_HOST` | no | Bind host (default `0.0.0.0`) |
| `UXC_PORT` | no | Bind port (default `8787`) |

`uxc_check` and unit tests use the oracle path on purpose; they are not production servers.  
`startup-peer.sh` defaults `UXC_ALLOW_ORACLE_SECRET=1` for local smoke only.

---

## 3. Cap policy (this peer)

| Policy | Behavior |
|--------|----------|
| Cap required | `Cart.add` always needs a valid token → `error.code = unauthorized` |
| Present-cap-must-verify | Any Intent that sets `cap` is verified (open actions cannot carry a bogus token) |
| Args hash | Sealed args must match the token’s `args_hash` (sorted compact JSON, sha256[:32 hex]) |
| Integer args | `qty` / `by` reject non-integers — **no silent coercion** |
| Morph + toast | Free-form strings embedded in morph HTML **and** toast display text are HTML-escaped |
| signal_set | Carries **raw** semantic values (not HTML) — intentional |
| once / jti | **SPEC requires once-semantics; Cap 0.1 Rust peer does not yet consume jti.** Health reports `policy.once_jti_enforced: false`. Treat as a known gap (see `SPEC/INVARIANTS.md`). |

---

## 4. HTTP honesty

| Advertisement | Meaning |
|---------------|---------|
| `formats` | What this HTTP surface actually serves today (`application/ux-channel+json` only on `/action`) |
| `codecs` | What the library can encode/decode (includes `cxb`) |
| `demo_mode` | `true` when the process is running with an allow-listed oracle/public secret |
| `http.action.accept_response` | Response types clients may request **today** |
| `policy.present_cap_must_verify` | Always `true` on this peer |
| `policy.once_jti_enforced` | `false` until jti consumption lands |
| Status codes | `200` when `Result.ok`; `401` when `error.code == unauthorized`; other Result errors → `400`; encode failure → `500` |

Never advertise CXB on HTTP `formats` until Accept negotiation is implemented.  
Clients must still branch on the **Result body**; HTTP status is for proxies/logs.

---

## 5. Limits & failure shapes

- Clients must always be able to parse a **Result** document on the action path (wire/parse failures are mapped to `ok: false`, not a bare non-IR body).
- Oracle tokens in golden vectors may be aged; harnesses use a generous `max_age` for structural verify.
- Default peer is a **demo** surface (`Cart` / `Counter`). Domain actions belong in moving code, not SPEC.
- Error vocabulary used by this peer: `unauthorized`, `validation`, `not_found`, `internal` (see `SPEC/intent-result-ops.md`).

---

## 6. Local automation

Prefer Make targets from [AUTOMATION.md](AUTOMATION.md): `make regen`, `make layout`, `make verify`.

```bash
make peer-demo     # demo peer (oracle allow-listed)
make verify-http   # full smoke including HTTP
make peer-stop
```

## 7. Quick production checklist

1. [ ] `UXC_CAP_SECRET` set to a private value (≥ 16 chars, not the oracle string)  
2. [ ] `UXC_ALLOW_ORACLE_SECRET` **unset**  
3. [ ] `/ux-channel/mint` firewalled or disabled for public hosts  
4. [ ] Health shows `demo_mode: false` and `formats` matches real Accept support  
5. [ ] Health shows `policy.once_jti_enforced: false` — do not rely on single-use caps until green  
6. [ ] HTTPS / network ACLs as appropriate for your deploy  
