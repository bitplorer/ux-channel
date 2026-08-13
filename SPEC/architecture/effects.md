# Effects / EffectGraph

## Purpose

Host-side structure for intended effects **before** project. Apps SHOULD use builders instead of hand-built op dicts.

## Abstract nodes (informative API)

- `morph(target, html)`  
- `toast(message, ...)`  
- `navigate(href, ...)`  
- `seq([...])`  
- `after(ms, [...])` → timer + body ops  
- `dispatch(name, ...)`  

## Law

- EffectGraph is **not** sent on the wire unless projected to `ops`.  
- Project MAY emit classic leaves only (`effects: "classic"`).  
- Project MAY emit seq/invoke when `effects: "auto"` and peer supports them.
