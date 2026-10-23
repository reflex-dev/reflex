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

### fs_app on 0.10.1a1 — dev (3220/8220) and prod (single port 3221, `FS_TW_IMPORTANT=1`)

```
cd $W/fs_app
FS_TRUTH=$W/truth/t.json ../serve.sh start new $W/fs_app dev 3220 8220 new_dev        # ../serve.sh wait http://localhost:3220/
$PW ../drive_share.py --url http://localhost:3220/ --truth $W/truth/t.json --out ../logs/share_new_dev.json
$PW ../drive_js.py    --url http://localhost:3220 --out ../logs/js_new_dev.json
$PW ../drive_hooks.py --url http://localhost:3220 --out ../logs/hooks_new_dev.json     # after drive_share (both write the truth file)
$PW ../drive_hmr.py   --url http://localhost:3220 --app fs_app/fs_app.py --out ../logs/hmr_new_dev.json
FS_TRUTH=$W/truth/t.json FS_TW_IMPORTANT=1 ../serve.sh start new $W/fs_app prod 3221 3221 new_prod   # same drivers on :3221
```

| check | dev | prod |
|---|---|---|
| `drive_share`: 48 ops, DOM == `State.dict()` after every op (lists append/pop/pop0/insert/sort/reverse/clear/reset, equal-but-new element, nested dict add/update/**delete key**/reorder, dict→None→dict, list↔dict var, list of lists, nested dataclass in list, pydantic in list, datetime, set, tuple, 5000-int list fill/mutate/append/pop0, same value twice, no-op, 6 ops in one handler, two substates + 4-deep inheritance chain in one event, background task 5 deltas) | pass (0 diffs, 0 console, 0 pageerrors, hydrate 615 ms) | pass (0 diffs; only console noise is the favicon 404) |
| memo card render counters (`data-renders`): unchanged cards keep identity and do NOT re-render (e.g. `replace_equal` → 0 cards re-render; `bump0` → only the mutated card; nested/matrix/blob ops → 0 cards) | pass (sharing works) | pass |
| `drive_js`: Unicode `len/[i]/[-1]/[a:b]/[-3:]/[::2]` on `"héllo 👋🏽 wörld é 𝔘𝔫𝔦"` (emoji + skin tone, combining mark, surrogate pairs) and on `"ab"` (out-of-range index renders ""), `None` string length → 0 then 2, `(-x)**2`, `-(x**2)`, `(x-5)**2`, `(-x)**3`, `Var(-2)**x` | pass (31/31) | pass |
| dict props: `style={"padding": x.to_string()+"px"}` → 4px; `custom_attrs` dict → JSON attr (#7587) | pass | pass |
| #7544 error events without an Error object: `ErrorEvent` without `error`, `window.onerror(msg,url,1,2)` and a real thrown Error all reach `handle_frontend_exception` (`[Reflex Frontend Exception]` ×3 in the backend log), no secondary TypeError | pass | pass |
| #7573 tailwind `important`: `.web/tailwind.config.js` has `important: true`; `.text-red-500` beats inline `color: blue` (computed oklch red) | n/a | pass |
| `drive_hooks`: hooks in declaration order (`useStateContext` → `hr_doubled` → `hr_plain` → `hr_pos` → `hr_pos_pre`, see `compiled/new_dev/app/routes/[hooks]._index.jsx`), `VarData(position=)` compiles + works + logs `DeprecationWarning: VarData(position=...) has been deprecated in version 0.10.1`, `add_custom_code` ran once, `window_event_listener` resize/keydown, `clipboard` paste, `call_script` callback, two `ComponentState` instances independent, global `client_state` set / late reader behind cond / set back to default / `push()` → late reader, memo with object prop + internal state read (0 re-renders on unrelated var; updates on prop rename and on state), `/dyn/[pid]` reads router + other substates, client-side nav back to `/` | pass (23/23) | pass |
| `drive_hmr` (dev): append a NEW substate used by `/hooks` → element renders after the reload, events on the new and old substates work, no page errors; the default-only change propagates; revert works | pass; 2 transient `state schema` console warnings (dev warns only, by design) + 1 `Skipping state update for unknown substate` while the backend restarted before Vite served the rebuilt bundle | — |
| uncontrolled input across the hot reload | value reset (Vite "Could not Fast Refresh /utils/context.jsx" → tree remount). Compare prev. | — |
| local (`global_ref=False`) `rx._x.client_state` whose reader span and writer input land in different auto-memoized components: reader never updates | 'loc' (compare prev) | same |

Notes: my first prod build failed in prerender with `ReferenceError: window is not defined` — that was my own
`add_custom_code` writing `window` at module scope (SSR evaluates it); guarded with `typeof window`.
`ssr_probe.mjs` (run with node inside `.web/`) renders the built server bundle for a route and prints the
real exception, which the react-router prerender log hides behind "Received a 500".

#7405 (`probe_cdn.py`, backend only): `ImportVar(tag, package_path="/fa")` on an unbundled lib →
new `https://cdn.jsdelivr.net/npm/react-icons/fa/+esm`, prev `https://cdn.jsdelivr.net/npm/react-icons/+esm/fa` → fixed.

### Baseline: the same app on 0.10.0 (`fs_app_prev/`, dev 3222/8222)

```
cp -r $W/fs_app/fs_app $W/fs_app/rxconfig.py $W/fs_app_prev/
EXPECT_VENV=prev FS_NEGSQ=0 FS_NONELEN=0 FS_POSITIONED=0 FS_TRUTH=$W/truth/t.json ../serve.sh start prev $W/fs_app_prev dev 3222 8222 prev_dev
$PW ../drive_share.py --url http://localhost:3222/ --truth $W/truth/t.json --out ../logs/share_prev_dev.json
$PW ../drive_js.py --url http://localhost:3222 --negsq 0 --nonelen 0 --out ../logs/js_prev_dev.json
$PW ../drive_hooks.py --url http://localhost:3222 --positioned 0 --out ../logs/hooks_prev_dev.json
```

The three `FS_*=0` gates exist because on 0.10.0 each of these breaks a whole page (positive controls, all fixed on 0.10.1a1):
- `rx.Var.create(-2) ** x` → `[PARSE_ERROR] A unary expression with the '-' operator cannot be used as the left operand of an exponentiation` in the shared `app_components/fs_app/fs_app.jsx` → **every page** of the app fails to load in dev (`Failed to fetch dynamically imported module`) (#7565).
- `JsState.n.length()` with `n: str | None = None` → `TypeError: Cannot read properties of null (reading 'split')` → `/js` crashes (#7518).
- a hook with `VarData(position=PRE_TRIGGER)` reading one with `POST_TRIGGER` → `ReferenceError: Cannot access 'hr_pos' before initialization` → `/hooks` crashes (#7586 bucket ordering; compiled order was `hr_pos_pre` before `hr_pos`).

| check | 0.10.0 result |
|---|---|
| `drive_share` 48 ops | pass (0 diffs) — same correctness as new |
| memo card render counters | **every** card re-renders on every ShareState update (e.g. `replace_equal`, `bump0`, `rename_last` → all 3 cards); on new only the changed card. Identity sharing is new behaviour, correctness unchanged. |
| `drive_js` Unicode | 7 FAILs: `len`=26 (UTF-16 units), `[6]`/`[7]`/`[-1]` = lone surrogates (`�`), slices cut surrogate pairs → #7518 fixed on new |
| `drive_js` error events | `window.onerror` without an Error object throws `TypeError: Cannot read properties of undefined (reading 'name')` inside `state.js` (`_call_script TypeError...`) → #7544 fixed on new (the real `Error` still reached the backend) |
| `drive_hooks` | 1 FAIL: global `client_state` late reader keeps `2` after `set_value(0)` → #7407 fixed on new. Local (`global_ref=False`) client_state reader also stays `'loc'` on 0.10.0 → not a regression. Memo unrelated-var re-renders = 0 on both. |
