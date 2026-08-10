# Payment agents demo

Quantity from durable store (`Quantity.from_store` + provenance). Session chrome = ids/steps only.  
Agents share `@st.action` / `@ch.on` with buttons.

```bash
PYTHONPATH=src:. python examples/payment_agents/run_demo.py
# HTTP UI
PYTHONPATH=src:. uvicorn examples.payment_agents.app:app --host 0.0.0.0 --port 8080
```

Brutal tests: `pytest tests/test_payment_agents_brutal.py -q`
