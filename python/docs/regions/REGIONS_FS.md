# File-based regions (opt-in shell)

**Core unchanged:** Intent door, `@ch.on`, hand-mounted `Region`, bridges.

**Opt-in:** discover a package of Region modules.

```python
ChannelConfig.development(secret="...", regions="app.regions")
```

```bash
uxchannel region add pay/desk --recipe payment
uxchannel region list
uxchannel region check
```

```python
ag.tools_for(region="pay.desk", role="cashier")
ch.inspect("pay.desk", role="cashier")  # dev; prod off by default
```

Principles: one door · path defaults uid · freeze `uid =` when public · `ax=False` for pure UI.
