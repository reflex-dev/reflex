# Cluster: telemetry_ctx — #6960, the telemetry worker no longer re-imports `rxconfig.py`

> Telemetry events are now collected under the submitting thread's registration context, so the
> background worker reuses the config the app already loaded instead of re-importing `rxconfig.py`
> (and mutating `sys.path`) off-thread.

`telapp/rxconfig.py` appends one line per import naming the importing thread, the pid and
`len(sys.path)`, so an off-thread re-import is visible without instrumenting reflex at all.
`telapp/` is otherwise a two-widget counter app.

```
cd telapp && rm -f config_imports.log && timeout 45 reflex run --backend-only --backend-port 9881
cat config_imports.log
```

## The claim holds

reflex 0.9.10.post2 (`logs/config_imports_0910.log`):

```
import thread=MainThread          pid=13352 syspath_len=6
import thread=MainThread          pid=13352 syspath_len=6
import thread=reflex-telemetry_0  pid=13352 syspath_len=6      <-- off-thread re-import
import thread=MainThread          pid=13368 syspath_len=9
```

reflex 0.9.11a1 (`logs/config_imports_a1.log`):

```
import thread=MainThread pid=13355 syspath_len=6
import thread=MainThread pid=13355 syspath_len=6
import thread=MainThread pid=13366 syspath_len=9
```

The `reflex-telemetry_0` import is gone; every remaining import is on the main thread of the CLI
process or of the reloader child. The two main-thread imports per process and the higher
`syspath_len` in the child are the same on both versions.

`sys.path` was already 6 entries at the moment of the off-thread import here, so this app does not
show the mutation half of the claim — only the re-import, which is the part that made config side
effects run on a background thread.

Outbound telemetry itself is blocked in this container (`app.posthog.com` → `connect_rejected` at
the egress proxy), which does not affect the test: the re-import happens before the network call.

## Findings raised

None.
