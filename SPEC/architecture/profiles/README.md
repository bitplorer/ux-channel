# Profiles

## Definition

A **profile** is a versioned vocabulary of effect methods a peer can apply.

## Negotiation

- Peer **claims** profiles in hello: `profiles: ["web.v1"]`.  
- Host **projects** ops to the **intersection** of claimed profiles and host knowledge.  
- Missing/empty claims → **classic only**.

## Versioning

- Within `web.v1`, methods are **append-only**.  
- Breaking changes require `web.v2`.  
- Peers MAY claim multiple profiles.

## Projection policy

- Default: **minimal** (only ops needed for the action outcome).  
- Maximal multi-profile emit is **explicit** config only.

## Documents

- [web.v1.md](web.v1.md)  
- [agent.v1.md](agent.v1.md)  
- [trace.v1.md](trace.v1.md)  
- [wire.v1.md](wire.v1.md)  
