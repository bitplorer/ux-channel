# Lab workplace vertical

Budgeted DUT flash under mesh membership.

| API | Role |
|-----|------|
| `ch.webrtc.issue_membership` | RTC + workplace tickets |
| `wp.run_io("lab.dut", "flash", quantity=…)` | Gate + budget |
| `POST /api/logout` | `revoke_mesh_membership` |

```bash
PYTHONPATH=src uvicorn examples.workplace_lab.app:app --host 0.0.0.0 --port 8080
```
