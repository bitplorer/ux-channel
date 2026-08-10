# Capability Tokens — Cap 0.1 (normative draft)

**Purpose:** Portable, attenuable authority that travels with an Intent.  
**Law:** Mesh membership ≠ trust. Caps authorize; transports only deliver.

---

## 1. What a capability is

A capability (cap) is a server-minted, cryptographically signed token that binds:

- a specific **action** name
- a hash of the **sealed / trusted args**
- optional **subject** (principal)
- optional **scopes**
- optional **once** semantics (jti + nonce store)
- **issued-at** and implied expiry

The client sends the token back on the Intent. The receiving peer verifies it *before* running the action handler.

---

## 2. Logical payload (before signing)

```text
{
  "action": "Cart.add",
  "args_hash": "<sha256-hex-32 of canonical sealed args>",
  "extra": { ... },          // optional opaque claims
  "iat": 1710000000,         // unix seconds
  "sub": "user:42",          // optional principal
  "scopes": ["cart:write"],  // optional
  "jti": "<uuid>",           // required when once=true
  "once": true               // optional single-use
}
```

**Canonical args hash**
- Serialize the sealed args with a stable JSON subset (sorted keys, no insignificant whitespace, default=str for non-JSON types).
- SHA-256, take first 32 hex characters (implementation detail of current Python; vectors will freeze the exact bytes).

Unknown fields in the payload are preserved by verifiers that understand the same major version but must not be required for basic verification.

---

## 3. Verification rules (must hold)

A peer must reject the Intent if any of the following fail:

1. Signature invalid or unknown key (or previous-key window exhausted).
2. Token expired (`iat + max_age`).
3. `action` in token ≠ `action` in Intent.
4. `args_hash` ≠ hash of the sealed args actually presented.
5. `sub` present and does not match the expected principal (when the action requires it).
6. Required scopes are not a subset of the token’s scopes (unless `"*"` is present).
7. `once=true` and the `jti` has already been consumed.

On failure the Result is `ok=false` with an appropriate `error.code` (typically `unauthorized`).

---

## 4. Attenuation

Caps may be attenuated (narrowed) by a peer before forwarding:

- Reduce scopes
- Bind a more specific action
- Shorten remaining lifetime
- Add hop limits (`max_hops`) for the causal spine
- Require trace

An attenuated cap must still verify under the same root keys (or a designated attenuation key hierarchy). The exact attenuation encoding is an extension point; the core requirement is that the final verifier can still check action + args_hash + expiry + principal.

---

## 5. Once / nonce semantics

When `once=true`:

- A unique `jti` is required at mint time.
- The verifying peer records the `jti` (with TTL ≥ remaining token life) in a nonce store.
- Re-use of the same `jti` fails closed.

This is the mechanism for single-use controls (e.g. “confirm destructive action”).

---

## 6. Minting surface (Python reference)

```python
cap = capability_service.mint(
    action="Cart.add",
    args={"sku": "abc", "qty": 1},   # sealed portion
    sub="user:42",
    scopes=["cart:write"],
    once=False,
)
# client later posts Intent { action, args, cap }
```

Handlers never trust client-supplied full state; they re-read truth from the store and only use the sealed args that the cap covers.

---

## 7. Language-agnostic test vectors (required for Phase 1 exit)

Vectors must cover:

- Valid mint → verify round-trip
- Expired token
- Action mismatch
- Args hash mismatch
- Principal mismatch
- Missing required scopes
- Once-token replay
- Previous-key window (key rotation)

A second implementation (even a small Rust test binary) must accept the same vectors.

---

## 8. Non-goals for Cap 0.1

- Full certificate chains / PKI
- Capability passports that survive across completely untrusted administrative domains without a shared root
- Embedding large argument values inside the token (hash only)

---

## 9. Relation to IR

- Intent carries the opaque `cap` string.
- Result never needs to echo the full cap; `trace.hops[].cap_fingerprint` (optional) is enough for audit.
- See [intent-result-ops.md](intent-result-ops.md) and the causal design note.

---

**Exit criteria**
- Canonical byte sequences for the payload + signature scheme are frozen in golden files.
- Python and at least one other implementation agree on the vectors.
- Attenuation and `max_hops` are documented even if the first runtime only supports basic mint/verify.
