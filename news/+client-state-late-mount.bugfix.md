Fix a global `rx._x.client_state` reader that mounts after the value was set, such as one behind an `rx.cond`, keeping the stale value when the value is later set back to its default.
