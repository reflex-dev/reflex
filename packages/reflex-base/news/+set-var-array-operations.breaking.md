A `set` or `frozenset` state var is now a `SetVar` rather than an `ArrayVar`, so it no longer type-checks as a sequence in frontend code: indexing, slicing, `map`, `filter`, `join`, `reverse`, `+` and `*` on it are deprecated. They still compile for now with a deprecation warning and will be removed in 1.0. Call `.to_array()` first:

```python
State.tags[0]  # deprecated
State.tags.to_array()[0]
```
