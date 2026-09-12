`ComponentState.create()` accepts a `_state_key` naming this instance's state, instead of numbering it by creation order:

```python
Counter.create(_state_key="cart")
```

Unkeyed instances are still numbered as they are created, so adding or reordering a `create()` call renames the ones after it — which moves their entry in `minify.json` and repoints any frontend already served. A key must be a valid Python identifier and unique among the instances of that component.
