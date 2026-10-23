# frontend_store — reflex 0.10.1a1 (2026-10-23)

Covers #7273 (structural sharing), #7441 (single shared store), #7586 (hook order), #7234
(React Compiler), #7553 / #7435 (state-schema hash, unknown substates), #7645 (React / Vite
bumps) and the compiled-JS fixes #7565 #7518 #7573 #7405 #7544 #7587.

Venvs: `$SB/envs/new` = 0.10.1a1 (under test), `$SB/envs/prev` = 0.10.0 (baseline), `$SB/envs/driver`
(Playwright). Ports 3220-3239 / 8220-8239. Everything runs from `$SB/apps/frontend_store/` (copies of
the files in this directory); never from a checkout.

```
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
W=$SB/apps/frontend_store            # cp -r <this dir>/{fs_app,bigstate,schema_app,*.py,*.sh} $W/
PW="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
```

## Apps

- `fs_app/` — pages `/` (structural-sharing lab: 45 mutation ops on lists / nested dicts /
  dataclasses / pydantic / sets / tuples / datetimes / a 5000-element list, foreach with index
  and `key=`, `rx.memo` cards with a render counter, computed var returning nested data, conds on
  nested values, two substates + a 4-deep inheritance chain updated in one event, a background task),
  `/hooks` (custom components with `add_hooks` reading state as Var and as plain string, deprecated
  `VarData(position=...)`, `add_custom_code`, `rx.window_event_listener`, `rx.clipboard`,
  `rx.call_script` callback, two `rx.ComponentState` instances, global + local
  `rx._x.client_state`, memo with object prop reading state), `/js` (compiled-JS fixes),
  `/dyn/[pid]`. Every mutating handler writes the backend truth (`self.dict()`) to `$FS_TRUTH`;
  `drive_share.py` compares the DOM with it after every op.
- `bigstate/` — `BIG_N` dynamically created substates, all read on one page (#7441 / reflex#7429).
- `schema_app/` — state-schema hash app; `SCHEMA_EXTRA=1` / `SCHEMA_RENAME=1` / `SCHEMA_DEFAULT=1`
  produce "another backend version".

## Log

(filled in as the run proceeds)
