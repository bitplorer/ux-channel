# Documented assumptions (nothing silent)

These are **explicit** environmental or product assumptions. Ports MUST restate any they rely on.

1. **TLS (or equivalent)** protects Intent/Result in transit. Cap is not a substitute for transport security.  
2. **App encodes** user-controlled strings in morph HTML. Protocol does not HTML-sanitize.  
3. **Multi-instance hosts** share nonce and idempotency stores. MemoryNonceStore is single-process only.  
4. **Classic-only peers** do not run delayed `after(ms>0)` bodies from a single Result; host uses multi-Result or non-classic timer ops.  
5. **Flow durability** (resume after days) is application database state, not peer kernel state.  
6. **Production Cap crypto** matches existing ux-channel CapService / Rust cap (itsdangerous-compatible); this package’s CapClaims helpers are order/semantics references.  
7. **Peer honest claims** — lying about `web.v1` wastes ops; it does not grant Caps.  
8. **Clock skew** for Cap/proof exp is bounded by deployment; prefer short TTLs.  
9. **Browser document** exists only when web.v1 drivers are loaded in a browser (or test double).  
10. **Idempotency-Key** semantics are host-defined and separate from once/jti.  
