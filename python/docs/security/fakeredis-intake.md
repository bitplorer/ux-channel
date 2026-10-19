# fakeredis intake

Test dependency only. It is not imported by `ux_channel` and it is not in
`[tool.poetry.dependencies]`. Prototyper's Redis and MCP transport tests
need a Redis stand-in, and the gate already uses `fakeredis.FakeRedis`.

| Field | Value |
| --- | --- |
| Requirement | `fakeredis>=2.39,<2.40` |
| Installed for the audit | 2.39.0 |
| License | BSD-3-Clause |
| Release date | 2026-10-01 |
| Why this pin | 2.40.0 was uploaded on 2026-10-14. On 2026-10-19 that wheel is five days old, so the ceiling stays below it. 2.39.0 is the newest release that is at least 14 days old. |
| Why it is here | Redis pub/sub and the Redis state store are exercised without a live Redis. The package is listed in `requirements-dev.txt` and in the Poetry `dev` and `test` groups. |
| Transitive test deps | `redis` 8.1.0 (MIT), `sortedcontainers` 2.4.0 (Apache-2.0). No extras (`bf`, `lua`, `valkey`, `vectorset`) are installed. `redis` is already an optional runtime extra (`redis>=5.0`); this intake does not add it to the runtime set. |

## pip-audit

Command, against the pinned version and the tree it resolved on 2026-10-19:

```text
uvx pip-audit -r <fakeredis==2.39.0>
# fakeredis==2.39.0
# redis==8.1.0
# sortedcontainers==2.4.0
```

Output:

```text
No known vulnerabilities found
```

No known CVEs on fakeredis 2.39.0, redis 8.1.0, or sortedcontainers 2.4.0.
