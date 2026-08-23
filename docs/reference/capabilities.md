# Capabilities

> **Diátaxis:** reference · **Canonical:** `docs/reference/capabilities.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 4. Capabilities (the part people under-assume)

### Why caps exist

If the client could call `Refund.run` with `{ "amount": 1 }` after you rendered a button for `{ "amount": 50 }`, the UI is theater.  
A **cap** seals: *this principal may run this action with these args until expiry*.

### What is signed (simplified)

```text
mint(action, args) → token
  includes: action name
            args_hash = sha256(compact_json_sorted(args))[:32 hex]   # Rust-parity
            exp / once / sub / scopes as configured
verify(token, action, args) → ok or CapError
  recomputes args_hash from the Intent’s args; mismatch ⇒ fail
```

**Implication you must not miss:** if the handler reads `product_id` from args, that value must be in the **signed** args (often via `ch.control(..., trust_product_id=...)`). Putting the price only in a hidden HTML field **without** putting it in signed args is a bug.

### API names (Python ↔ Rust)

| Concept | Python | Rust |
|---------|--------|------|
| Mint | `CapService.mint` / `registry.mint` / control helpers | `CapService::mint` |
| Verify | `CapService.verify` | `CapService::verify` |
| Hash args | `CapService.hash_args` | `hash_args` |
| Error | `CapError` | cap errors |

There is **no** public `CapService.sign` for this path — that word was retired to avoid confusion with ticket signing (`sign_push` / WebRTC tickets are different).

### Development vs production

| Mode | Typical choice |
|------|----------------|
| Local demo | `ChannelConfig.development(secret=…, allow_memory_stores=True)` |
| Production | Strong secret, durable nonce/idempotency stores (e.g. Redis), `require_cap=True` |

**Secret:** long random string; treat like a signing key. If it leaks, mint caps offline.

---
