# Candidate: nested stock changes through dict views do not update the browser

Classification: medium, pre-existing on 0.9.12. Confirmed on all three published trains, Chromium/WebKit and dev/prod. Isolated reload controls confirm backend mutation while the cached sum remains stale after reload; explicit reassignment heals it. Parent independently verified the realistic inventory workflow.

Realistic workflow: an inventory dashboard receives a bulk one-unit reservation for every stocked SKU. Initial state is `{"tea": {"stock": 10}, "mug": {"stock": 20}}`, displayed both as raw inventory and as a cached sum of 30. The backend event performs:

```python
for item in self.inventory.values():
    item["stock"] -= 1
```

Expected: tea 9, mug 19, stock total 28. Observed on alpha2 and stable Chromium: the browser still displays tea10/mug20/total30 after eight seconds. `for _, item in sorted(self.inventory.items()): item["stock"] -= 1` repeats the issue. Subsequent `self.inventory.get("tea")["stock"] -= 2` delivers the accumulated changes, yielding tea6/mug18/total24 after all three operations, so the values/items operations did mutate the underlying data in that session.

Useful independent controls:

```python
for sku in self.inventory:
    self.inventory[sku]["stock"] -= 1

self.inventory = {sku: {"stock": item["stock"]} for sku, item in self.inventory.items()}
```

The first should deliver a bulk decrement through indexed proxy access. The second makes the existing backend values explicit through field reassignment without decrementing again. For a fresh-session isolation test, execute values (or items) once, then full browser reload, then reassignment; inspect raw inventory and cached total separately at every step. Current `drive_dashboard.py` has these isolated checks and a fresh-session indexed control.

Minimal reproduction needs only one `rx.State` with the inventory dictionary, a `@rx.var(cache=True)` returning `sum(item["stock"] for item in self.inventory.values())`, the two view-iteration event handlers, and raw inventory / total text plus buttons. The full dashboard source contains the same workflow at `app/order_dashboard/order_dashboard.py`, operations `dict_values`, `dict_items`, `dict_keys`, and `inventory_assign`.

Published source hypothesis: `reflex/istate/proxy.py` wraps list iteration and dictionary `get`/`setdefault`, but `dict.values()`/`dict.items()` return views containing raw nested dictionaries. A nested mutation through those views does not mark the state field dirty. This is a hypothesis to verify, not an asserted fix.
