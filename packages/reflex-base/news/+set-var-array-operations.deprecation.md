Array operations on a `set` or `frozenset` var (indexing, `map`, `filter`, `join`, `reverse`, `+`, `*`, ...) are deprecated now that such vars are a `SetVar` rather than an `ArrayVar`. Call `.to_array()` first:

```python
State.tags[0]  # deprecated
State.tags.to_array()[0]
```
