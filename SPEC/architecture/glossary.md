# Glossary (canonical names)

Use these terms in code, config, and docs. Do not invent synonyms in public APIs.

| Term | Meaning |
|------|---------|
| **Intent** | Peer → host request: `action`, `args`, optional `cap`, `request_id` |
| **Cap** | Sealed capability token authorizing one action with sealed `args_hash` |
| **Result** | Host → peer outcome: `ok`, `ops`, optional `error`, optional `meta` |
| **ops** | Ordered list of effect objects to apply |
| **action** | String name of host handler (e.g. `Cart.add`) |
| **args** | JSON object of action arguments |
| **dispatch** | Host runs Intent through Cap gate then handler |
| **project** | Host lowers an effect graph into `ops` for a given peer hello |
| **apply** | Peer runs `ops` (after optional proof verify) |
| **profile** | Versioned set of effect methods a peer claims (e.g. `web.v1`) |
| **driver** | Code that implements one profile’s methods on a platform |
| **host** | Process that verifies Caps and emits Results |
| **peer** | Process that sends Intents and applies Results |
| **session** | Shared connection identity; has monotonic **gen** |
| **gen** | Session generation; incremented on revoke |
| **proof** | Optional host signature over a Result envelope |
| **stamp** | Host-tracked id for a surface right (invoke path) |
| **once** | Cap claim: single successful consume |
| **jti** | Unique id for once-consume / replay detection |
| **flow_id** | Optional correlation id for multi-step work (not authority) |
| **EffectGraph** | Host-side structure of intended effects before project |
| **hello** | Peer declaration of profiles and capability bits |
| **effects** (config) | `"auto"` \| `"classic"` — encoding mode for project |
| **proofs** (config) | `"auto"` \| `"require"` \| `"off"` |
| **flow** (config) | `"auto"` \| `"off"` — whether host may attach flow meta |

## Explicitly not synonyms

- **Cap** ≠ session cookie ≠ proof  
- **profile** ≠ user profile ≠ Cap  
- **driver** ≠ host action handler  
- **flow_id** ≠ permission to run next step  
