`auth.tokens.create` returns a `CreatedToken` and `auth.tokens.refresh` a `RotatedToken`, rather than the bare token value. Read the value from `.token`:

```python
token = client.auth.tokens.create("ci").token
```

If a refresh returns `previous_revoked=False`, the old token is still live; revoke it with `auth.tokens.revoke`.
