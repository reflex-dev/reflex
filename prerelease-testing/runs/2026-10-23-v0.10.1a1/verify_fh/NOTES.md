# verify_fh — independent verification of FS-2 (React Compiler coverage) and HN-3 (client_ip not validated)

Verifier run, 2026-10-24. reflex **0.10.1a1** (`$SB/envs/new`) vs **0.10.0** (`$SB/envs/prev`), published PyPI packages only,
every server started from `$SB/apps/verify_fh/<app>/` (never a checkout), ports 3700-3702 / 8700-8702.
`SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`, `V=$SB/apps/verify_fh`.

Everything here is reproducible from this directory: `rc_run.sh` / `rc_audit.mjs` (FS-2), `hn_run.sh` + `probes/`
(HN-3). Raw results are under `results/`, trimmed server logs under `logs/`.

## 1. FS-2 — React Compiler silently skips generated components

### 1.1 Claim (frontend_store report)
With `react_compiler=True` the compiler skips every generated component that renders an element with `id=`
(`refs["ref_x"] = ref_x` → "This value cannot be modified"), so page route modules contain 0 `_c(` while
app_components are compiled; the docs say the compiler covers `app/`, `app_components/`, `utils/components/`.

### 1.2 Method
1. `rc_app` (this dir): 8 pages isolating shapes — static page, state read + event + cond/foreach + `on_mount` with NO
   `id`, same with one `id`, `@rx.memo` with/without id, `ComponentState`, `rx.form(on_submit)`, controlled input,
   `rx.upload`. Run on 0.10.1a1 dev with `REFLEX_REACT_COMPILER=1` (`rc_run.sh $V/rc_app rc_new_dev`): every module
   that vite serves is fetched (`curl -g http://localhost:3700/<module>`) and its `_c(` / `react/compiler-runtime`
   counted — the real transform output.
2. `rc_audit.mjs <webdir>` re-runs `babel-plugin-react-compiler 1.0.0` with reflex's exact plugin options
   (`target 19, compilationMode infer, panicThreshold none`) over `app/`, `app_components/`, `utils/components/`
   and adds the plugin's **`logger`** option, so every function the compiler considered produces a
   `CompileSuccess` / `CompileError` event with the reason. Served `_c(` counts and audit "compiled" counts agree for
   every app (e.g. rc_app 14/14, fs_app 63/63), so the offline audit is faithful.
3. Same for the `reflex init --template blank` app, four reflex-examples apps (quiz, snakegame, github-stats,
   traversal — 0 or 1 `id=` in their source) and the explorer's `fs_app` (the stress app, 4 pages, ~70 ids):
   `rc_run.sh $V/<app> <label>` each, one server at a time (ports 3700/8700).
4. `rc_probe2/3/4/5.mjs` (run with cwd = an app's `.web`): minimal sources isolating each trigger.

### 1.3 Results

| app | functions the compiler inferred as components | compiled | bailed | served `_c(` | bail reasons |
|---|---|---|---|---|---|
| rc_app (8 pages) | 20 | 14 | 6 | 14 | 4 Immutability (`refs[...] =`), 2 Invariant (IIFE) |
| blank template | 6 | 4 | 2 | 4 | 1 Todo (ternary optional), 1 Immutability (toast) |
| quiz | 18 | 14 | 4 | 14 | 3 Todo (ternary optional), 1 Immutability (toast) |
| snakegame | 19 | 17 | 2 | 17 | 1 Todo, 1 Immutability (toast) |
| github-stats | 16 | 13 | 3 | 13 | 1 Todo, 2 Immutability (toast, debounce input with id) |
| traversal | 13 | 11 | 2 | 11 | 1 Todo, 1 Immutability (toast) |
| fs_app (explorer stress app) | 133 | 63 | 70 | 63 | 64 Immutability, 3 Todo `??=`, 2 Refs, 1 UseMemo |

(`results/audit_<label>.txt` has the per-function list; `results/served_<label>.txt` the served counts.)

**Route modules.** 0 `_c(` in `app/routes/*.jsx` is mostly NOT a bail-out. In 0.10.1a1 a page's `Component()` is a
hook-free static composition of extracted `app_components` wrappers (state reads, event handlers, cond, foreach,
on_mount all live in `app_components/<app>/<app>.jsx`). The page function has no hooks and uses `jsx()` calls, not JSX
syntax, so `compilationMode: "infer"` never recognises it as a component: the compiler logs **no event at all** for
`_index.jsx`, `[noid]`, `[form]`, `[input]`, `[memo]`, `[cs]`, `[upload]`, `[404]` (`rc_probe2 plain_div`: compiled=false,
no event). There is nothing in those functions to memoize. The only route components the compiler *tries* are the
ones that carry a hook — i.e. an element with `id` at page level (`[withid]`: `const ref_count = useRef(null);
refs["ref_count"] = ref_count;` → bail). fs_app's four id-heavy routes (6/16/18/32 `refs[...]` writes) all bail; its
`[404]` route is simply not a candidate.

**The trigger is broader than `id`.** Four independent generated patterns make React Compiler 1.0.0 skip a function
(`panicThreshold: "none"` turns every one into a silent skip):

1. `refs["ref_x"] = ref_x` — module-global mutation during render → `Immutability: This value cannot be modified`.
   Every element with `id=` (page level or inside memo/ComponentState/extracted wrapper), `rx.upload`, debounced
   inputs with `id`, and reflex's own `MemoizedToastProvider` (`refs['__toast'] = toast` in
   `app_components/reflex/compiler/compiler.jsx`) — this one bails in **every** app. Independently, a `useRef` object
   passed through a `jsx("div", {ref: r})` *call* bails with `Refs: Cannot access refs during render`
   (`rc_probe2 useRef_as_ref_prop`); with JSX syntax the `ref` attribute would be allowed, so removing the global write
   alone would not rescue id-bearing elements.
2. `((...args) => (addEvents([...], args, {})))()` — reflex's immediately-invoked event chain with rest params inside
   `useEffect` (`on_mount` / `on_unmount`) and inside the form `on_submit` `useCallback` →
   `Invariant: Expected temporaries to be promoted to named identifiers in an earlier pass` (a compiler-internal
   invariant, i.e. a React Compiler bug on this shape). `rc_probe3`: the same effect calling `addEvents(...)` directly,
   or an IIFE without rest params, compiles. `on_click` handlers are fine (the arrow is passed as a prop, not invoked).
3. Optional chaining in a ternary **test** — `rx.cond` whose condition is a Var comparison, generated as
   `(a?.valueOf?.() === "x"?.valueOf?.()) ? children?.at?.(0) : children?.at?.(1)` →
   `Todo: Unexpected terminal kind \`optional\` for ternary test block` (unsupported syntax in the compiler, not a
   correctness bail). Hits `rx.color_mode.button` (in the blank template), every `rx.cond(State.x == ...)`, code
   blocks, foreach bodies with conds — one or more in every app audited. `rc_cond` on a plain bool
   (`s.flag ? ... : ...`) compiles; hoisting the test into a `const` compiles (`rc_probe4`).
4. `rx._x.client_state`: `refs['_client_state_x'] ??= ...` → `Todo: Handle ??= operators`; window event listener
   hooks `useCallback(existing_fn, deps)` → `UseMemo: Expected the first argument to be an inline function expression`.

Real apps: 11–17 of 13–19 candidate components compile (≈85 %); the explorer's stress app 63/133 (47 %, dominated by
its ~70 id-bearing buttons). Runtime behaviour is unaffected either way: a skipped function is left exactly as
generated (the explorer's 48/48, 23/23 drive results and `drive_hooks` confirm that), so the cost is "no automatic
memoization for that component", nothing else.

**Can the compiler surface this?** Yes, two knobs reflex does not use: the `logger` option (what `rc_audit.mjs`
uses — one event per function with category + reason) and `panicThreshold`. `rc_probe5`: with `"critical_errors"` the
`refs` write and the IIFE invariant make babel **throw** (the build would fail on every app because of the toast
provider), the ternary Todo still skips; with `"all_errors"` all three throw. So the current `"none"` is the only
setting under which the feature works at all with today's codegen; the useful improvement is a logger-based summary
("N of M generated components skipped by React Compiler; set REFLEX_REACT_COMPILER_LOG=1 for details") and codegen
changes for patterns 2 and 3 (call `addEvents` directly; hoist the cond test into a `const`), which are cheap and
would raise coverage to "everything except id-bearing elements and client_state".

**PR #7234** (read via GitHub): description claims 40 browser tests off/on × dev/prod and "scope limited to generated
app/, app_components/, utils/components/". Its only end-to-end coverage assertion
(`test_react_compiler_transforms_generated_components`) checks that the `app_components` module containing
`"derived-count"` imports `react/compiler-runtime` — a module-level check that passes as soon as *one* function in
the module compiled; the `derived_count` memo it names renders `rx.text(..., id="derived-count")`, i.e. it is itself
one of the skipped functions (same situation as rc_app's `MemoId`: bails, module still `runtime=1`). The unit test
`test_vite_plugin_react_compiler.py` stubs babel. No test measures per-component coverage, so the gap was invisible to
the PR's validation.

**Rating.** Not a bug in the sense of wrong behaviour (experimental opt-in, output correct, skips are the compiler's
designed bail-out semantics) — but the docs sentence "It compiles generated JavaScript and JSX in app/,
app_components/, and utils/components/" overstates what happens (a fixed share of generated components, including a
reflex-internal provider and every `rx.cond` with a comparison, is skipped, and nothing tells the user). Classify as
**docs gap + low-severity feature gap in an experimental flag**, not a regression; the explorer's "page route modules
are never compiled" headline is the wrong root cause (hook-free pages are not compile candidates; the id/refs pattern
is one of four triggers).

Side note (not a finding): `rc_run.sh` initially fetched `app/entry.client.embed.js` from the dev server, which logs
`[vite] Internal server error: Failed to resolve import "$/app/__reflex_embed_manifest"` — self-inflicted (that
module is only used by embed builds); the runner now skips it. No other errors/tracebacks in any server log.

### 1.4 Rerun
```
cd $V && ./rc_run.sh $V/rc_app rc_new_dev            # dev server 3700/8700 with REFLEX_REACT_COMPILER=1, served counts, audit, stop
cd $V/rc_app/.web && node $V/rc_audit.mjs $V/rc_app/.web --verbose   # offline audit with reasons (needs the .web generated with the flag on)
cp $V/rc_probe2.mjs $V/rc_app/.web/ && (cd $V/rc_app/.web && node rc_probe2.mjs)   # isolating cases (also rc_probe3/4/5)
```

## 2. HN-3 — `trusted_proxy_hops>=1` uses the selected X-Forwarded-For entry verbatim

### 2.1 Claim (hydration_net report §2.2)
With `trusted_proxy_hops>=1` the selected XFF entry becomes `router.session.client_ip` without being validated as an
IP (`not an ip!! <script>`, `1.2.3.4:5678`, latin-1 bytes); 0.10.0 did the same with the leftmost entry.

### 2.2 Method
`hn_run.sh`: the explorer's `hnet` app (copied, `IPState.rec` records `router.session.client_ip`, raw headers and the
ASGI peer), dev on 3701/8701, browser websocket via `probes/xff_proxy.py` on 8702 (`REFLEX_API_URL`). `ws_probe.py`
hand-rolls the websocket upgrade with raw header bytes. Three proxy behaviours were run against the SAME 0.10.1a1
server with `trusted_proxy_hops=1`: `append` (nginx `$proxy_add_x_forwarded_for`, appends the peer to the client's
XFF), `none` (forwards the client's XFF untouched — a proxy that does not manage XFF, or hops over-configured), `line`
(adds its own XFF line). Baseline: 0.10.0 behind the `append` proxy (no `trusted_proxy_hops` option there).
Browser leg: `probes/xss_probe.py` loads `/ip` in Chromium with the proxy in `none` mode injecting
`X-Forwarded-For: <img src=x onerror="window.__pwned=1">` on the upgrade, so the backend selects the payload.

### 2.3 Results (`results/hn_new_h1.txt`, `results/hn_prev.txt`, `results/xss_new_h1.json`)

0.10.1a1, hops=1:
| case | direct (client is the peer) | via `append` proxy | via `none` proxy | via `line` proxy |
|---|---|---|---|---|
| no XFF | 127.0.0.1 | 127.0.0.3 (real client) | 127.0.0.2 (the proxy) | 127.0.0.3 |
| `6.6.6.6` / `6.6.6.6, 7.7.7.7` | 6.6.6.6 / 7.7.7.7 | 127.0.0.3 | 6.6.6.6 | 127.0.0.3 |
| `not an ip!! <script>` | **verbatim** | 127.0.0.3 | **verbatim** | 127.0.0.3 |
| `1.2.3.4:5678`, `[v6]:443, 1.2.3.4:5678` | `1.2.3.4:5678` | 127.0.0.3 | `1.2.3.4:5678` | 127.0.0.3 |
| latin-1 bytes `\xe9\xe8` (#7602) | `éè` | 127.0.0.3 | `éè` | 127.0.0.3 |

0.10.0 (leftmost entry, no option): direct and **through the appending proxy** every spoof wins (`6.6.6.6`,
`not an ip!! <script>`, `[2001:db8::1]:443`, `1.2.3.4:5678` verbatim); a latin-1 XFF value makes the handler never run
(`client_ip=None`, #7602 not yet fixed). So 0.10.0 is strictly worse: client-controlled AND unvalidated.

Claim confirmed: the token reflex picks is not validated (`reflex/app.py` v0.10.1a1 L2292-2299: split on `,`, strip,
index `[-hops]`). Narrowing: with a proxy that appends (nginx, Traefik, Caddy, AWS ALB, Cloudflare all do) and hops
equal to the proxy count, the selected token is **written by the trusted proxy**, so client garbage can never be
selected (append / line columns above). Garbage reaches `client_ip` only when the client's own header is what sits at
position `-hops`: a direct connection with hops>=1, or a proxy that forwards XFF untouched — both the documented
"only enable behind the proxies you count" misconfiguration (same as uvicorn's `ProxyHeadersMiddleware`, which also
returns the chosen token without parsing it; granian / Starlette 1.9 have no XFF handling at all — uvicorn is not
even installed with reflex 0.10.1a1). The realistic non-IP form a *trusted* proxy writes is `ip:port`
(Azure Application Gateway and some IIS/ARR setups put the client port in XFF): a user there gets
`client_ip="1.2.3.4:5678"`, exactly as on 0.10.0.

Browser (`xss_probe.py`, proxy `none` + injected payload): `#f_ip` textContent == payload, innerHTML
`&lt;img src=x onerror="window.__pwned=1"&gt;`, 0 child elements, 0 `<img>` in the document, `window.__pwned` stays
0, the computed var and the handler snapshot carry the identical string. React renders `client_ip` as a text node;
no reflex code path interpolates `client_ip` into HTML, logs or scripts (`git grep client_ip v0.10.1a1`: only
`app.py` on_connect, `istate/data.py` SessionData, `state.py` router update). So the `<script>` case is inert in
reflex itself; the only consumers that can misbehave are app code treating the string as a parsed IP
(`ipaddress.ip_address(...)` raises, rate-limit keys, log lines).

**Rating.** Low, hardening/docs: not a regression (0.10.0 identical or worse), not a security issue in reflex's own
rendering, and only reachable through a misconfiguration the #7614 docs already warn about — plus the legitimate
`ip:port` form from port-writing proxies. A cheap hardening would be `ipaddress.ip_address()` on the selected token
(strip a trailing `:port` / brackets) with fallback to the connection peer, and a docs line saying `client_ip` is
the raw forwarded token.

### 2.4 Rerun
```
cd $V && ./hn_run.sh proxy append && ./hn_run.sh server new 1 hn_new_h1 && ./hn_run.sh matrix new_h1_append 0.10.1a1
./hn_run.sh proxy none && ./hn_run.sh matrix new_h1_none 0.10.1a1
./hn_run.sh proxy none --add 'X-Forwarded-For: <img src=x onerror="window.__pwned=1">' && \
  NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python probes/xss_probe.py --url http://localhost:3701/ip --payload '<img src=x onerror="window.__pwned=1">'
./hn_run.sh stop; ./hn_run.sh proxy append && ./hn_run.sh server prev "" hn_prev && ./hn_run.sh matrix prev_append 0.10.0; ./hn_run.sh stop
```

## 3. Housekeeping
Servers: rc_app / blankapp / quiz / snakegame / github-stats / traversal / fs_app (dev, compiler on, 3700/8700, one at
a time), hnet new (3701/8701, proxy 8702) and hnet prev — all stopped by PID; `.web/` trees deleted at the end;
no redis. Two foreign `bun run dev` processes (components_typing, enterprise items) were seen and left alone.
