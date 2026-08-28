# Cluster: @rx.memo auto-memoization & component naming (reflex 0.9.9a1)

Changelog items covered: #6949 (auto-memoization of @rx.memo call sites),
#6605 (RestProp CSS classification), #6945 (displayName everywhere),
#6730 (wrapper= config, exercised via wrapper=None).

Verdict: **everything works as advertised in both dev and prod mode; no framework
bugs found.** 69/69 browser checks pass in dev, 69/69 in prod. A few
benign-but-noisy observations below.

## App

`memoapp/` — blank-template app (reflex init) with:

- `memoapp/probe.py` — render-count instrumentation. `probe(name)` is a span
  carrying a VarData hook that bumps `globalThis.__renders[name]` on every
  render of its enclosing compiled function component. It sets
  `MemoizationDisposition.NEVER` on itself so the auto-memoize pass cannot
  extract it into its own wrapper (its hook must stay in the domain being
  counted). `probe_var(name)` is the same hook attached to a plain string Var —
  passed as a memo prop at a call site, the hook lands in the **generated
  auto-memo wrapper**, so it counts wrapper renders.
- `memo_one` — state-bound prop + `rx.EventHandler[passthrough_event_spec(str)]` prop.
- `memo_two` — bound to a *different* var of the same state.
- `memo_status`, `memo_row` (under `rx.foreach`), `memo_cs`
  (receives `rx._x.client_state` value), `counter_island` (instantiates an
  `rx.ComponentState` inside the memo body), `styled_note` (RestProp),
  `unwrapped_label` (`@rx.memo(wrapper=None)`), `token_display`.
- `mod_a.py` / `mod_b.py` — two `@rx.memo def badge(...)` sharing a name across modules.
- `rx.moment(...)` for the NoSSR `ClientSide(<Tag>)` displayName.
- Page `/` plus `/about` (route displayName + second call site of `memo_two`).

## How to rerun

```
SB=<scratchpad>; VENVS with reflex==0.9.9a1 from PyPI (never the checkout)
cd memoapp
# dev
reflex run --frontend-port 3140 --backend-port 8140 --loglevel debug
BASE_URL=http://localhost:3140 OUT=out_dev MODE=dev python ../drive_memo.py
# prod (0.9.9: frontend and backend MUST share one port)
reflex run --env prod --frontend-port 8141 --backend-port 8141 --loglevel debug
BASE_URL=http://localhost:8141 OUT=out_prod MODE=prod python ../drive_memo.py
```

Driver needs playwright + Chromium (`executable_path=/opt/pw-browsers/chromium`).
Do NOT export `NO_PROXY=localhost,...` verbatim in this sandbox — it clobbers the
default NO_PROXY that exempts registry.npmjs.org, and bun then dies with
`ConnectionClosed downloading package manifest` through the agent proxy
(cost me two 500s install timeouts; environment issue, not reflex).

## Results — #6949 re-render scoping (the headline)

Counter deltas per interaction (prod numbers; dev numbers are exactly 2x from
React StrictMode double-invoke):

| action           | page | wrapper_one | wrapper_two | body_one | body_two | body_row | body_cs | body_island | body_status |
|------------------|------|-------------|-------------|----------|----------|----------|---------|-------------|-------------|
| bump a           | 0    | 1           | 1           | 1        | **0**    | 0        | 0       | 1 (title=a) | 0           |
| bump b           | 0    | 1           | 1           | 0        | 1        | 0        | 0       | 0           | 0           |
| ping (EH prop)   | 0    | 1           | 1           | **0**    | 0        | 0        | 0       | 0           | 1           |
| reverse 3 rows   | 0    | 0           | 0           | 0        | 0        | **2**    | 0       | 0           | 0           |
| append row       | 0    | 0           | 0           | 0        | 0        | **1**    | 0       | 0           | 0           |
| client_state +1  | 0    | 0           | 0           | 0        | 0        | 0        | 1       | 0           | 0           |
| ComponentState +1| 0    | 0           | 0           | 0        | 0        | 0        | 0       | 1           | 0           |

- **The page function NEVER re-renders** (page delta 0 across every state
  change) — compiled `_index.jsx` contains zero `useContext`; every stateful
  call site became a no-prop wrapper component. Confirms the #6949 claim.
- Wrappers subscribed to the same state context re-render together
  (wrapper_two +1 on `bump a`), but React memo stops propagation: body_two 0.
- Event-handler-prop changes don't defeat memoization: pinging via the
  `on_ping` EventHandler prop re-renders only the status memo (useCallback'd
  chains keep handler identity stable → body_one 0).
- `rx.foreach` + memo: reversing [red,green,blue] re-renders exactly the 2 rows
  whose label changed (green stays put); append renders exactly 1 new row.
- `rx._x.client_state` value into a memo prop: only that memo body renders.
- `rx.ComponentState` inside a memo body works; its counter updates re-render
  the memo body only (the CS state subtree is part of the memo body's domain,
  not further sub-memoized — fine, still page-stable).
- `wrapper=None` (#6730) behaves as documented: `body_unwrapped` re-renders
  whenever its wrapper does (no React memo to stop propagation), and still
  tracks its prop correctly.
- Cross-module same-name memos: compiled as `Badge_6a3335c9` / `Badge_d38f1d91`
  in `.web/app_components/memoapp/mod_{a,b}.jsx` — no collision, both render
  and update independently.

## Results — #6605 RestProp CSS classification

`styled_note(text=..., id=, class_name=, title=, font_weight="bold",
style={"padding":"10px","font_style":"italic"})` with body
`rx.el.div(span, rest)`:

- Compiled call site: `css:({padding:"10px", fontStyle:"italic", fontWeight:"bold"})`
  — the undeclared CSS prop merged with explicit `style=`, not dropped.
- Browser computed style: font-weight 700, padding 10px, font-style italic. PASS.
- `class_name` / `title` / `id` forwarded through the `...rest` spread to the DOM. PASS.
- Negative path: same props on a RestProp-less memo raise
  `TypeError: does not accept prop 'font_weight'. Only declared props may be
  passed when no rx.RestProp is present.`; `key=` still accepted with a
  console deprecation notice. PASS.

## Results — #6945 displayName

Compiled output (`grep -rn displayName .web/app .web/app_components`):

- Pages: `Component(index)`, `Component(about)`, `Component(404)`.
  Note the `/` route is labelled `index`, not `/`.
- `@rx.memo` components: named after the Python function (`MemoOne`, `Badge`
  in both modules, etc.).
- Auto-memo wrappers: `MemoComponent_<Name>_<modulehash>` (e.g.
  `MemoComponent_MemoOne_21819d56`) — hash-suffixed by design (the wrapper
  class qualname); plain-element wrappers get clean names (`Button`, `Foreach`).
- Contexts: `StateContext(<full state name>)`, `ColorModeContext`,
  `EventLoopContext`, `DispatchContext`, `UploadFilesContext`, `ThemeContext`.
- NoSSR: `ClientSide(Moment)` via `ClientSide(component, name)` helper.

Runtime (React fiber walk, `fiber_names.json` in out_dev/out_prod): all of the
above observable in dev AND in the minified prod bundle (displayName strings
survive minification; third-party components minify to `$E`, `t`, ... but every
Reflex-named node keeps its label). Gotcha for anyone repeating the fiber walk:
memo'd components mount as SimpleMemoComponent fibers, so the displayName lives
on `fiber.elementType`, not `fiber.type`.

The only unnamed contexts above the page are third-party
(`react-error-boundary`'s context and one undefined-value context) — not
Reflex-owned, so #6945 is complete on Reflex's side.

## Hygiene

- Browser console: clean in dev and prod apart from known-benign lines
  (HydrateFallback dev log, vite connect debug, React DevTools info,
  "Disconnect websocket on page navigation" on client-side nav).
  **No hydration mismatches** in either mode.
- Network: zero 4xx/5xx/failed requests in both modes.
- Server logs: no tracebacks.

## Benign-but-surprising observations (anomalies, low severity)

1. **Prod build warnings from reflex's generated vite config** (vite 8.2.0 /
   rolldown): `Warning: Invalid input options (1 issue found) - For the "jsx".
   Invalid key: Expected never but received "jsx"` and
   `WARN advancedChunks option is deprecated, please use codeSplitting instead.`
   Repro: `reflex run --env prod ...`, see `prod_server.log` lines ~142-146.
   Cosmetic today, will break when rolldown removes the deprecated options.
2. Auto-memo wrapper displayNames carry the module-hash suffix
   (`MemoComponent_MemoOne_21819d56`) while inner memos are clean (`MemoOne`).
   DevTools trees are readable but slightly noisy; arguably intended.
3. Route `/` gets displayName `Component(index)` — fine, just not literally the
   route string promised by "pages labelled with route".
4. In prod, a memo wrapper renders twice on first mount of a client-side
   navigation (`wrapper_two_about: 2` after navigating to /about) — initial
   mount + post-hydration state delivery. No user-visible effect.

## Artifacts

- `memoapp/` — app source (no .web).
- `drive_memo.py` — Playwright driver (all 69 checks; writes results.json,
  console.log, failed_requests.log, fiber_names.json, context_names.json, PNGs).
- `out_dev/`, `out_prod/` — full run outputs incl. screenshots.
- `dev_server.log`, `prod_server.log` — server logs (`--loglevel debug`) from
  the successful runs.
