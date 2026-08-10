# Cap vector 01 — valid round-trip (notes)

This case is described rather than fully executable until the exact
canonical serialization + HMAC scheme bytes are frozen from the Python oracle.

**Logical payload**
- action: `Cart.add`
- sealed args: `{"sku": "abc-123", "qty": 2}`
- sub: `user:42`
- scopes: `["cart:write"]`
- once: false

**Expected**
- mint succeeds
- verify with same action + same sealed args succeeds
- verify with different qty fails with args_hash mismatch
- verify after max_age fails with expired

Once the Python `CapService` canonical bytes are extracted, replace
this note with concrete token strings and expected error codes.
