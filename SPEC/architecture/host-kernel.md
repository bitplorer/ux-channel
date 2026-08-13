# Host kernel

## Modules (cohesive)

| Module | Responsibility | MUST NOT |
|--------|----------------|----------|
| `cap` | mint, verify, hash_args | HTML, timers |
| `nonce` | `use_once(key, ttl) -> bool` | business logic |
| `registry` | dispatch, hooks, Cap gate order | DOM |
| `effects` | EffectGraph builders | crypto |
| `project` | pure lower(graph, hello) → ops | I/O |
| `proof` | optional sign envelope | Cap secret |

## Dispatch order (MUST)

1. Parse Intent  
2. Resolve principal if configured  
3. Cap gate (require and/or present-cap-must-verify)  
4. once consume if applicable  
5. Handler  
6. Build EffectGraph (handler return or helpers)  
7. `project(graph, session.peer_hello, effects_mode)`  
8. Optional proof sign  
9. Return Result  

**Vector:** integration via registry tests; once ordering `concurrency/once-before-handler`

## Assumptions

- Handlers are app-provided and trusted for domain rules after Cap gate.  
- Kernel does not interpret HTML content.
