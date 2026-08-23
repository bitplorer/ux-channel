# Common mistakes

> **Diátaxis:** how-to · **Canonical:** `docs/guides/common-mistakes.md` · **Layer:** ux-channel  
> Map: [INDEX.md](../INDEX.md).

Extracted from root `START_HERE.md` (Phase 2 mixed-mode split). The 5-minute path stays at [../../START_HERE.md](../../START_HERE.md).

## 11. Common mistakes (read before your first PR)

1. **Unsigned business args** — price/qty only in HTML, not in cap args.  
2. **Client path for money** — `st.client("amount")` is wrong by design.  
3. **Assuming root has everything** — `MemoryStateStore` / `ChannelTest` / `AgentRunner` are package imports.  
4. **Skipping scripts()** — caps without a client runtime look “broken.”  
5. **Treating Result as optional** — handlers should return Result/ops-friendly values; arbitrary dicts are not silently “ok.”  
6. **Using agents as a second app** — agents must hit the same actions humans do.  
7. **Changing IR without vectors** — if you touch Intent/Result/cap/CXB, add conformance.  
8. **Production with memory stores** — multi-worker will lie; use Redis (or your durable backends).  
9. **Short secrets** — cap signing is only as strong as the secret.  
10. **Confusing toast with logging** — `toast` is a **client op**; host logs use logging/audit.

---
