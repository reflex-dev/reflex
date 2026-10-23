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

### Hot reload with a NEW substate (dev): 0.10.1a1 vs 0.10.0

`drive_hmr.py` opens `/hooks`, appends `HmrState` + a page using it to the app source, waits, then reverts.
- 0.10.1a1: new element renders ~5 s after the edit, events on the new substate work, old substates and the
  two `ComponentState` instances keep working, no page errors. Console: 2 transient "built for another version"
  warnings (one per backend restart, dev warns only) + 1 "Skipping state update for unknown substate" from the
  reconnect that happened before Vite served the rebuilt bundle. After the revert the page keeps working.
- 0.10.0: the new element appears, but the first delta naming the new substate hits the old fatal path
  (`Cannot process state update: no dispatch function for substate(s) ...hmr_state`), `#hydrated` stays
  `false`, the websocket closes and the session is dead until a manual reload (also after the revert).
  → #7435/#7441 improve this; not a regression.
- Both versions: the uncontrolled `<input>` loses its value across the reload (Vite "Could not Fast Refresh
  /utils/context.jsx", the tree remounts) — same on 0.10.0 (`hmr_prev_dev`), not a regression. A default-only
  change of the new state's var does not show for the existing session (dev state persists across backend
  restarts) — expected.

### Schema hash probe (`probe_schema.py`, backend only, schema_app)

Stable across `PYTHONHASHSEED` and across page-evaluation order; default-only change keeps the hash;
renamed handler / extra substate change it. Evaluating a page twice in one process (ComponentState
instance counter → extra `Tally_nN` classes) changes it, and so does evaluating a subset of the
ComponentState pages — see the schema_app section for whether real process layouts hit this.

### React Compiler (#7234) — `REFLEX_REACT_COMPILER=1`, fs_app, dev 3224/8224 and prod 3225

- Wiring: `.web/package.json` gains `@babel/core 7.29.7` + `babel-plugin-react-compiler 1.0.0` (devDependencies),
  `vite.config.js` imports `./vite-plugin-react-compiler.js` and lists `reactCompiler()` first; `utils/state.js` is
  not transformed (correct).
- dev: `drive_share` 48/48 (hydrate 1.9 s vs 0.6 s off), `drive_js` all pass, `drive_hooks` 23/23, `drive_hmr` pass
  (ComponentState keeps working after the hot reload).
- **Coverage observation**: served `app/routes/*.jsx` modules contain **no** `_c(` / `react/compiler-runtime`
  (index, hooks, js routes: 0), `app_components/fs_app/fs_app.jsx` has 60 `_c(` calls, `root.jsx` 1.
  `rc_probe.mjs` (babel + the plugin, run inside `.web/`) shows why: the compiler bails out with
  `CompileError: This value cannot be modified` on `refs["ref_a"] = ref_a` and `Cannot access refs during render`
  on a `useRef` passed as `ref` — reflex hoists `const ref_x = useRef(null); refs["ref_x"] = ref_x;` into every
  component that renders an element with an `id`, so page components are silently skipped
  (`panicThreshold: "none"`). The docs say the compiler covers `app/`, `app_components/`, `utils/components/`.

### Stale `postcss.config.js` after removing the tailwind plugin (found by accident, compiler run)

Sequence on 0.10.1a1 in one `.web`: run with `plugins=[TailwindV4Plugin(...)]` → run again **without** the
plugin → `[vite] Internal server error: Failed to load PostCSS config ... Loading PostCSS Plugin failed:
Cannot find module '@tailwindcss/postcss'` (vite error overlay on every page; CSS 500). `.web/package.json`
no longer lists `@tailwindcss/postcss` / `tailwindcss` (plugin dev deps pruned, node_modules pruned by bun) but
`.web/postcss.config.js` still says `plugins: { "@tailwindcss/postcss": {} }` (the plugin's modify task ran once
and the base template is only written when `.web` is created). Baseline on 0.10.0: see below.

React Compiler, continued:
- prod (3225): `drive_share` 48/48 (hydrate 242 ms), `drive_js` pass, `drive_hooks` 23/23; the client bundle imports
  `react/compiler-runtime` (`useMemoCache`) in `components-*.js`, `context-*.js`, `entry.client-*.js`.
- toggling OFF again (dev run without the env var): `.web/package.json` and `vite.config.js` lose the babel /
  compiler entries, `node_modules/babel-plugin-react-compiler` is removed (`@babel/core` stays as a transitive dep).
- compiler-off `vite.config.js` on 0.10.1a1 is byte-identical to 0.10.0's (`compiled_snapshots/{prev_dev,new_dev}`).

Stale `postcss.config.js` baseline on 0.10.0 (`fs_app_prev`, plugin on → off): identical breakage
(`vite-error-overlay` on `/js`, 3× "Failed to load PostCSS config" in the log) → pre-existing, **not a regression**.
Same run also gives the #7573 baseline: with `TailwindV4Plugin(config={"important": True})` 0.10.0 renders
`#styled` blue (`importants:` ignored), 0.10.1a1 red; `tailwind_config_js_template(important=True)` prints
`importants: true,` on prev and `important: true,` on new.

### bigstate (#7441 / reflex#7429): BIG_N=1500 dormant substates, 50 read on the page

```
cd $W/bigstate && BIG_N=1500 BIG_READ=50 ../serve.sh start new $W/bigstate dev 3226 8226 big_new_dev
$PW ../drive_big.py --url http://localhost:3226/ --read 50 --out ../logs/big_new_dev_1500.json
```
0.10.1a1 dev: load 1.3 s, hydrated 2.1 s, 50 values correct, 3-substate event 97 ms and correct, single-substate
event 50 ms, reload+hydrate 322 ms, no page errors, no stack overflow.
0.10.0 dev, same app (`bigstate_prev`, `EXPECT_VENV=prev`): page never hydrates, 0 values rendered,
`pageerror: Maximum call stack size exceeded` (`[vite] (client) [Unhandled error] RangeError: Maximum call stack`)
→ reflex#7429 reproduced on 0.10.0 and **fixed** on 0.10.1a1.
0.10.1a1 prod (`BIG_N=1500 BIG_READ=50 ../serve.sh start new $W/bigstate prod 3226 3226 big_new_prod`): prerender ok,
load 144 ms, hydrated 392 ms, events 99 / 64 ms, reload+hydrate 213 ms, 50/50 values, no errors.

Third-party use of the removed `StateContexts` export: GitHub code search (`StateContexts org:reflex-dev`,
`"useContext(StateContexts"` across GitHub) finds only compiled `.web` outputs, the nextpy fork and
reflex's own old templates — no published component package hand-writes it. reflex-enterprise 0.9.8 imports only
`ColorModeContext` from `$/utils/context` (still exported) and passes `VarData(position=...)` in dnd.py /
combobox.py (now a deprecation warning, see the enterprise item).
