Deprecate `app.event_namespace.token_to_sid`, and `token_to_sid` / `token_to_socket` on the token manager, which can only report one socket per client token. They keep working, reporting the most recently connected socket; use `token_to_sids`, which maps each token to all of its sockets:

```python
# before
if token not in app.event_namespace.token_to_sid:
    ...
# after
if token not in app.event_namespace.token_to_sids:
    ...
```
