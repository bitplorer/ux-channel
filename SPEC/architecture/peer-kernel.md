# Peer kernel

## Scope

Generic apply machine for **all** peers. **MUST NOT** import browser DOM APIs.

## Modules

| Module | Responsibility |
|--------|----------------|
| `hello` | Build claim: profiles, proofs bit, codecs, features |
| `apply` | single-flight applyResult → applyOps → applyOp |
| `session` | gen; cancel timers on bump |
| `budgets` | enforce limits before walk |
| `proof` | optional verify before any driver call |

## applyResult (MUST)

1. If proofs required for this session and verify fails → apply nothing.  
2. Enter single-flight lock (queue or reject per runtime policy).  
3. Enforce budgets on ops tree.  
4. applyOps.  
5. Release lock.  

## applyOp

- `seq` → applyOps(children)  
- else → lookup driver method for op; if missing, ignore or strict-fail  
- **MUST NOT** call ambient platform globals by string name  

## Assumptions

- Drivers are registered at startup for claimed profiles only.  
- Transport and X-Channel headers live in **peer runtime / transport adapter**, not kernel.
