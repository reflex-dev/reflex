# `rv_examples_upgrade` — upgrade regression 0.9.11.post1 → 0.9.12a2 (reflex-examples apps)

Phase 7 re-verification, 2026-09-21. Three reflex-examples apps taken through the full
`UPGRADE_PROTOCOL.md` cycle (baseline on the previous stable → in-place upgrade of the SAME venv
and SAME app dir → re-drive the identical flows → cold `.web` → prod), plus the deliberate
mixed-version trap.

**Result: no regressions.** Every flow that passed on 0.9.11.post1 passes on 0.9.12a2, with
byte-identical page dumps on the app that was compared dump-for-dump. Four surprises were chased
down and all four A/B'd as **pre-existing** (identical on 0.9.11.post1): the `/form/<id>`
`FormMessage` crash, a React `collapsible` non-boolean-attribute error, HTTP 404 on direct
navigation to a dynamic route in prod, and the mixed-version trap itself.

All installs PyPI-only. Nothing was installed from `/home/user/reflex`, `/home/user/wt/*` or
`/home/user/reflex-enterprise`, and no python was ever run with a checkout as its cwd. The two
probe apps print `RUNNING-REFLEX-FROM: <reflex.__file__>` at import so every run's log names the
venv it actually used (see `logs/acc_*.log`, `logs/dyn_*.log`).

Ports used: frontend 3260–3266, backend 8260–8266 (prod uses one port). No redis needed.
Every server was stopped by pid (`scripts/killtree.py`, which walks `/proc/<pid>/task/<pid>/children`);
no pattern kills. `$SB/bin/ports.py` was checked clear after each app.

---

## Pass/fail table

| # | check | prev (0.9.11.post1) | a2 (0.9.12a2) | result | evidence |
|---|---|---|---|---|---|
| 1 | `form-designer` — register + login + create form + 2 fields (reflex-local-auth 0.5.0, reflex[db], alembic) | PASS | – | pass | `shots/fd_base/two_fields.txt`, `shots/fd_base/report.json` |
| 2 | `form-designer` — in-place upgrade, preserved `.web/` + `reflex.lock/` + `reflex.db`: first-run log | – | clean recompile, no migration/mismatch line | pass | `logs/fd_a2_first.log` (10 lines, whole file) |
| 3 | `form-designer` — login with the **pre-upgrade bcrypt row**, form 1 + its 2 fields load, add a 3rd field, `/responses/1` | PASS | PASS | pass | `shots/fd_a2/three_fields.txt`, `shots/fd_a2/responses.txt`; version line reads `v0.9.12a2` |
| 4 | `form-designer` — cold run (`rm -rf .web`), same flows | – | PASS, `.web/package.json` identical to the warm upgrade | pass | `logs/fd_a2_cold.log`, `shots/fd_a2_cold/cold_form1.txt` |
| 5 | `form-designer` — prod (`--env prod`, one port 3265): home, login, `/edit/form/1`, `/responses/1` | – | PASS | pass | `shots/fd_a2_prod/prod_form1.txt`, `.../prod_responses.txt` |
| 6 | `basic_crud` — mounted FastAPI router over HTTP: POST/GET/GET-by-id/PUT | PASS (all 200) | PASS (all 200), pre-upgrade rows intact | pass | `out/bc_api_base.txt` vs `out/bc_api_a2.txt` |
| 7 | `basic_crud` — in-page "Send" query (httpx → own backend), `Status: 200` + JSON body rendered by `rx.markdown` | PASS | PASS | pass | `shots/bc_base/after_send.txt` vs `shots/bc_a2/after_send.txt` |
| 8 | `basic_crud` — radix `rx.select` → DELETE `products/2` → `@rx.event(background=True)` poller re-renders (2 products → 1) | PASS | PASS | pass | `shots/{bc_base,bc_a2}/flow_before.txt` + `flow_after_delete.txt` |
| 9 | `data_visualisation` — xlsx→sqlite loader (36 COVID rows), table render, "Add New Item" dialog | PASS | PASS | pass | `diff shots/dv_base/home.txt shots/dv_a2/home.txt` → empty |
| 10 | `data_visualisation` `/pandas` probe — 5 DataFrame renders (literal, state-computed, `@rx.memo` prop, `rx.ComponentState`, gridjs rows), uncached `@rx.var(cache=False)`, `rx.foreach` over `list[Covid]` | PASS | PASS | pass | `diff shots/dv_base/pandas_after.txt shots/dv_a2/pandas_after.txt` → empty |
| 11 | `data_visualisation` `/pandas` — recharts bar chart + plotly figure, both driven by a State var (added for this run to cover the recharts/plotly alphas) | PASS | PASS, identical eval vector | pass | evals below; `shots/dv_a2/04_pandas_after.png` |
| 12 | `data_visualisation` — prod (`--env prod`, port 3263), home + `/pandas` + bump/load/ComponentState | – | PASS | pass | `shots/dv_a2_prod/prod_pandas_after.txt` |
| 13 | `.web/package.json` diff across the upgrade, all three apps | – | react-router 8.3.1→8.4.0 (4 pkgs) + `mergician v2.0.2`; nothing else | pass | `out/pkg/*.diff.txt` |
| 14 | mixed-version trap: `uv pip install --upgrade 'reflex==0.9.12a2'` **without** `--prerelease=allow` | – | upgrades only reflex + reflex-base; every `reflex-components-*` stays stable | anomaly (unchanged from a1) | `logs/freeze_mixed_trap.txt` |
| 15 | an app actually run in that mixed state (core 0.9.12a2 + radix 0.9.9 …) | – | compiles, serves, flows work; one extra server-side DeprecationWarning | pass | `logs/acc_mixed.log`, `shots/acc_mixed/` |
| 16 | `uv pip install --upgrade --prerelease=allow 'reflex==0.9.12a2'` (components **not** named) | – | pulls all 9 component alphas | pass | `logs/dryrun_prerelease_only.txt` |
| 17 | `form-designer` `/form/<id>` end-user entry page (known pre-existing app bug) | FAIL (campaign artifact) | FAIL, identical error | pass (unchanged) | `shots/fd_a2/entry.txt` vs `up_examples_b/shots/fd_base/entry.txt` |
| 18 | React `Received true for a non-boolean attribute collapsible` on `/responses/<id>` | present | present | pass (pre-existing) | `shots/acc_prev/report.json` vs `shots/acc_a2/report.json` |
| 19 | HTTP status of a **dynamic route** on direct navigation in prod | 404 (page still renders) | 404 (page still renders) | pass (pre-existing) | `logs/dyn_prev_prod.log`, `logs/dyn_a2_prod.log` |

### The recharts/plotly/gridjs eval vector (check 11), identical on both versions

```
['36', '4', '1', 'plotly tick 0', 'tick=0', 'steady=constant',
 'tick=1', 'plotly tick 1', '45,68,90,113', 'False', 'cs 1', '19']
```

in order: COVID row count, `.recharts-bar-rectangle` count, `.js-plotly-plot` count, plotly title
before the click, tick before, uncached var, tick after `#bump`, plotly title **after** the click
(the figure re-rendered from the new state), the four bar heights, "no rows loaded" gone after
`#load`, ComponentState counter, gridjs row count. In prod the same subset reads
`['36','4','1','plotly tick 0','tick=1','plotly tick 1','False','19']`.

---

## Environments

```
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_examples_upgrade
```

One venv, `$W/venv` (Python 3.11.15), created at the previous stable and **upgraded in place** —
that is the point of the exercise.

Baseline (`logs/freeze_baseline.txt`): reflex 0.9.11.post1, reflex-base 0.9.11.post1,
components code 0.9.5 / core 0.9.9 / dataeditor 0.9.2 / gridjs 0.9.1 / markdown 0.9.3 /
plotly 0.9.6 / radix 0.9.9 / recharts 0.9.3 / sonner 0.9.3, lucide 1.0.4, moment 0.9.4,
react-player 0.9.2, hosting-cli 0.1.72; reflex-local-auth 0.5.0, sqlmodel 0.0.44, bcrypt 5.0.0,
fastapi 0.141.1, pandas 3.0.6, openpyxl 3.1.5, plotly 7.1.0.

After the upgrade (`logs/freeze_a2.txt`):

```
reflex==0.9.12a2
reflex-base==0.9.12a2
reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1
reflex-hosting-cli==0.1.72
reflex-local-auth==0.5.0
fastapi==0.141.1  openpyxl==3.1.5  pandas==3.0.6  plotly==7.1.0  sqlmodel==0.0.44
```

Read-only campaign venvs used for the A/B probes: `$SB/envs/prev` (0.9.11.post1) and
`$SB/envs/a2` (0.9.12a2). Driver: `$SB/envs/driver/bin/python` (Playwright 1.63, Chromium at
`/opt/pw-browsers/chromium`).

---

## How to re-run everything

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_examples_upgrade
mkdir -p $W/apps && cd $SB                      # NEVER cd into a checkout

# 1. apps — copied out of the campaign's own artifacts, which already carry the
#    generated alembic dirs for basic_crud / data_visualisation and the /pandas probe page
SRC=/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/up_examples_b
for d in form-designer basic_crud data_visualisation; do cp -r $SRC/$d $W/apps/$d; done
#    then overlay this dir's probes/data_visualisation_patch/pandas_page.py to get the
#    recharts + plotly additions:
cp <this dir>/probes/data_visualisation_patch/pandas_page.py \
   $W/apps/data_visualisation/data_visualisation/

# 2. BASELINE venv — no --prerelease flag, so requirements resolve the way a user's would
uv venv $W/venv --python 3.11
uv pip install --python $W/venv/bin/python \
    'reflex[db]==0.9.11.post1' 'reflex-local-auth>=0.5.0' pandas fastapi openpyxl plotly

# 3. one-time DB bootstrap per app (alembic dirs are checked in)
for a in form-designer basic_crud data_visualisation; do
  (cd $W/apps/$a && REFLEX_TELEMETRY_ENABLED=false $W/venv/bin/reflex db migrate)
done

# 4. run + drive at baseline (see per-app commands below)

# 5. IN-PLACE UPGRADE of the same venv, same app dirs, .web/ and reflex.lock/ preserved
uv pip install --python $W/venv/bin/python --upgrade --prerelease=allow \
    'reflex==0.9.12a2' 'reflex-base==0.9.12a2' \
    'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
    'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
    'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
    'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
    'reflex-components-sonner==0.9.4a1'

# 6. re-run the identical drivers and diff the dumps
```

Server launcher — `scripts/run2.sh` refuses to start if the port is already bound (a leftover
vite from an earlier run otherwise answers the readiness curl and you drive the OLD build):

```bash
bash scripts/run2.sh <appdir> <venv> <fp> <bp> <logfile> [extra reflex args]
bash scripts/run2.sh $W/apps/data_visualisation $W/venv 3263 3263 $W/logs/dv_prod.log --env prod
```

Driver (one JSON blob per run: per-action ok/FAIL, `console`, `page_errors`, `failed_requests`,
`http_errors` ≥ 400; screenshots and `dump`/`eval` results land in the shots dir):

```bash
cd $W && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python scripts/drive.py http://localhost:3260/ scripts/fd_base.json $W/shots/fd_base
```

Per-app command set:

| app | ports | baseline driver | upgrade driver | extra |
|---|---|---|---|---|
| `form-designer` | 3260 / 8260 | `scripts/fd_base.json` | `scripts/fd_up2.json` | cold: `scripts/fd_cold2.json`; prod on 3265: `scripts/fd_prod2.json` |
| `basic_crud` | 3261 / 8261 | `scripts/bc_base.json` + `scripts/bc_flow.json` | same two files | REST via `curl --noproxy '*' http://localhost:8261/products` (payload keys: `code,label,quantity,category,seller,sender`) |
| `data_visualisation` | 3262 / 8262 | `scripts/dv_flow.json` | same file | prod on 3263: `scripts/dv_prod.json` |
| `accordion_probe` | 3264 / 8264 | `scripts/acc.json` on `$SB/envs/prev` | same on `$SB/envs/a2` and on the mixed venv | `probes/accordion_probe/` |
| `dynroute_probe` | 3266 (prod) | curl the three URLs on `$SB/envs/prev` | same on `$SB/envs/a2` | `probes/dynroute_probe/` |

Stop a server: `$SB/envs/driver/bin/python scripts/killtree.py <pid> [<leftover vite pid>]`, then
confirm with `uv run --no-project python $SB/bin/ports.py <fp> <bp>`.

---

## Per-app detail

### `form-designer` — reflex-local-auth 0.5.0 + reflex[db] + alembic (full protocol)

Baseline on 0.9.11.post1: registered `alice`, logged in, created form "Survey A" (it became
`/edit/form/1`), added fields `fullname` and `age`. Home page footer read `v0.9.11.post1`.
Driver report clean — no page errors, no failed requests, no ≥400 responses; the only console
lines were the browser's own autocomplete hints and reflex's `Disconnect websocket on page
navigation` log.

`.web/`, `reflex.lock/` and `reflex.db` were then left untouched and the venv upgraded in place.
**The whole first post-upgrade run log is ten lines** (`logs/fd_a2_first.log`): web-dir init,
`Compiling 100% 33/32`, App Running. No migration notice, no lockfile complaint, no bun peer
warnings, and — the thing the #7068 router rename made worth watching — no state/schema mismatch
in the log and no `backend_state_mismatch` or `client_error` in the browser console. The frontend
was silently recompiled, exactly as intended.

After the upgrade: login succeeded against the **pre-upgrade bcrypt row**, `/edit/form/1` showed
both pre-upgrade fields, a third field `city` was added and persisted, `/responses/1` loaded, and
the footer read `v0.9.12a2`.

Cold run (`rm -rf .web`, same venv, same DB): same screen, and the regenerated
`.web/package.json` is byte-identical to the warm-upgrade one.

Prod (`--env prod`, single port 3265): home, login, `/edit/form/1` with all three fields,
`/responses/1`. See the pre-existing 404-status note below.

`.web/package.json` diff across the upgrade (`out/pkg/form-designer.diff.txt`) — identical to
what the campaign recorded for a1:

```
@react-router/node      8.3.1 -> 8.4.0
@react-router/dev       8.3.1 -> 8.4.0
@react-router/fs-routes 8.3.1 -> 8.4.0
react-router            8.3.1 -> 8.4.0
+ mergician             v2.0.2   (new; framework-owned, deliberately v-prefixed)
```

`basic_crud` shows the same five lines; `data_visualisation` shows only the four react-router
bumps because it already had `mergician` (plotly pulls it in on both versions). `gridjs 6.2.0`,
`gridjs-react 6.1.1`, `plotly.js 3.7.0`, `react-plotly.js 4.1.0`, `recharts 3.10.1`,
`@radix-ui/react-accordion 1.2.20`, `@radix-ui/themes 3.3.0`, `react 19.2.8` are unchanged.

### `basic_crud` — reflex[db] + FastAPI `api_transformer`

The mounted router answers on the backend port on both versions. Baseline created `W-001 Widget`
and `G-002 Gadget`, PUT set `quantity=42`, all 200. After the in-place upgrade the same sqlite
file still returns both rows (`out/bc_api_a2.txt`), a third POST, a GET-by-id, a PUT to 99 and a
DELETE all return 200. The only difference between the two API transcripts is JSON key ordering,
which is dict ordering, not behaviour.

In the browser: the in-page query form (radix `rx.select` → `httpx` from the backend to its own
API) returns `Status: 200` and renders the JSON through `rx.markdown`; selecting DELETE with
`products/2` removes the row and the `@rx.event(background=True)` poller re-renders the list from
2 products to 1 within its 2 s tick — identical before and after.

### `data_visualisation` — reflex[db] + pandas (+ recharts/plotly added here)

`pd.read_excel` → sqlite still loads 36 COVID rows on `on_load` and the table renders
byte-identically (`diff shots/dv_base/home.txt shots/dv_a2/home.txt` is empty), as does the
"Add New Item" dialog.

The campaign's `/pandas` probe page renders the same `pd.DataFrame` five ways (literal,
`@rx.var`-computed and driven by a State var, `@rx.memo` prop, `rx.ComponentState`, and
`rx.foreach` over `list[Covid]` rows read with `rx.session()`), plus an uncached
`@rx.var(cache=False)`. `diff shots/dv_base/pandas_after.txt shots/dv_a2/pandas_after.txt` is
empty.

Because the brief asks this app to cover recharts and plotly and the upstream app has no chart, I
added two state-driven charts to that page (`probes/data_visualisation_patch/pandas_page.py`): an
`rx.recharts.bar_chart` whose series is a `@rx.var`, and an `rx.plotly` whose `go.Figure` is a
`@rx.var`. Both render on both versions and both **re-render from a state change**: clicking
`#bump` moves the plotly title from `plotly tick 0` to `plotly tick 1` and the recharts bars keep
their four heights `45,68,90,113`. Same in prod.

Note for whoever reuses that page: `rx.plotly(..., id="plotfig")` puts no `id` on any DOM node on
**either** version (0.9.11.post1 included), so select the plot with `.js-plotly-plot` /`.gtitle`,
not by id. This train renames the plotly prop `id` → `divId` (#6977), which is the supported way
to put an id on the plot div.

---

## Cross-cutting

### Mixed-version trap (deliberate, on a throwaway venv `$W/mixed/venv`)

`uv pip install --upgrade 'reflex==0.9.12a2'` **without** `--prerelease=allow`, starting from a
clean 0.9.11.post1 install, resolves to (`logs/freeze_mixed_trap.txt`):

```
reflex==0.9.12a2                     <- upgraded
reflex-base==0.9.12a2                <- upgraded
reflex-components-code==0.9.5        \
reflex-components-core==0.9.9         |
reflex-components-dataeditor==0.9.2   |
reflex-components-gridjs==0.9.1       |  all left at their STABLE releases
reflex-components-markdown==0.9.3     |
reflex-components-plotly==0.9.6       |
reflex-components-radix==0.9.9        |
reflex-components-recharts==0.9.3     |
reflex-components-sonner==0.9.3      /
reflex-components-lucide==1.0.4, -moment==0.9.4, -react-player==0.9.2, hosting-cli==0.1.72 (unchanged anyway)
```

Unchanged from a1. reflex pins reflex-base exactly but the component packages only by floor, so
the obvious command silently tests new core against old components. I ran an app in that state
(the accordion probe, which is pure radix): it compiles, serves and behaves identically, with one
extra server-side `DeprecationWarning: Implicit Radix Themes enablement has been deprecated in
version 0.9.0 … configure rx.plugins.RadixThemesPlugin()` — the same warning the all-alpha and the
all-stable sets emit, so not a mixed-state artifact. **Not fatal, but the pre-release notes should
tell users to name the component alphas.** A final (non-prerelease) 0.9.12 makes this moot, since
`pip install -U reflex` would then resolve the whole set.

With the flag, `uv pip install --upgrade --prerelease=allow 'reflex==0.9.12a2'` alone pulls all
nine component alphas (`logs/dryrun_prerelease_only.txt`) — same improvement the campaign recorded
for a1.

### Four surprises, all A/B'd as pre-existing

1. **`/form/<id>` renders the React error overlay** — ``Error: `FormMessage` must be used within
   `FormField` or specify the `name` prop`` (`form_designer/pages/form_entry.py:87` passes
   `rx.form.message(...)` as a child of `field_view()`). `shots/fd_a2/entry.txt` on 0.9.12a2 is
   the same error as the campaign's 0.9.11.post1 artifact
   `up_examples_b/shots/fd_base/entry.txt`. Known example-app bug, explicitly pre-existing per the
   brief. It is why the "fill out the form / collect a response" half of the app cannot be driven
   on either version.

2. **React: ``Received `true` for a non-boolean attribute `collapsible``** in the console on
   `/responses/<id>`. Traced to `form_designer/pages/response.py:89-96`,
   `rx.accordion.root(collapsible=True, type="multiple")` — Radix only honours `collapsible` for
   `type="single"`, so with `type="multiple"` it falls through to the DOM. Isolated in a 30-line
   probe (`probes/accordion_probe/`) with three roots (multiple+collapsible, single+collapsible,
   multiple alone) and run on `$SB/envs/prev` and `$SB/envs/a2`: the console output and the eval
   vector `['0', '', 'True', 'False', 'True', 'False']` (no `collapsible` attribute survives into
   the DOM; the single root opens and collapses correctly on both) are **identical**. Pre-existing,
   app-side misuse; @radix-ui/react-accordion is 1.2.20 on both. Not a release item.

3. **A dynamic route direct-loaded in prod answers HTTP 404 while rendering correctly.**
   `GET /edit/form/1` and `GET /responses/1` returned 404 in the prod run even though both pages
   rendered and the authenticated flow worked. Isolated in `probes/dynroute_probe/`
   (`/item/[id]`, `reflex run --env prod`) and curled on both versions:

   ```
   0.9.11.post1:  /  200   /item/7  404   /item/abc  404
   0.9.12a2:      /  200   /item/7  404   /item/abc  404
   ```

   Identical. Pre-existing; worth a ticket of its own some day (a 404 status on a working page
   confuses CDNs, uptime checks and crawlers) but not this release's problem, and #7153/#7078's
   prerendering work in this train did not make it worse.

4. **`ERR_CERT_AUTHORITY_INVALID` for `https://fonts.googleapis.com/css?family=Inter`** in the
   `data_visualisation` console. That stylesheet is the app's own
   (`data_visualisation.py:368 stylesheets=[...]`) and the container's egress proxy breaks its TLS
   chain. Present identically on 0.9.11.post1. Environment artifact, not a finding.

### Known campaign findings observed and unchanged

- FINDING-018 (`reflex run` ignores SIGTERM to its pid alone): confirmed again on a2 — every
  teardown needed the child pids, and killing the `reflex run` pid alone repeatedly left a `node`
  vite process holding the frontend port. That is why `scripts/run2.sh` now refuses to start on a
  bound port; without the guard an earlier attempt drove the previous build for 16 s before I
  noticed. Unchanged from 0.9.11.post1 behaviour, no new severity.
- The `SitemapPlugin` "enabled by default but not explicitly added" warning and the
  `@rx.memo … without explicit annotations` deprecation both appear on 0.9.11.post1 and 0.9.12a2.

### Not covered here

- No redis: none of these three apps uses it, and the state-manager fixes are `rv_state_fixes`'s
  beat.
- `twitter` and `reflexle` (the campaign's other two `up_examples_b` apps) were not re-run; the
  brief asked for three apps spanning third-party-auth / db+API / pandas-charts and those three
  were taken deeper (prod and cold included) instead.
- Prod was run for `form-designer` and `data_visualisation`, not for `basic_crud` (the campaign
  covered `basic_crud` prod on a1 and nothing in the a2 delta touches the mounted-API path).

---

## VERIFICATION

Independent adversarial re-check of this cluster's two NEW-issue claims, 2026-09-21, by a second
agent working from the written repros alone. Ports 3760–3763 / 8760–8763 only; read-only campaign
venvs `$SB/envs/{prev,shared,a2}` (0.9.11.post1 / 0.9.12a1 / 0.9.12a2); driver
`$SB/envs/driver/bin/python`; workspace `$SB/reverify/rv_examples_upgrade-verify`;
`REFLEX_TELEMETRY_ENABLED=false` everywhere. Probes copied verbatim from `probes/` (no edits).
Every server stopped by pid (`scripts/killtree.py` + the pid holding the port per `$SB/bin/ports.py`);
no pattern kills; all eight ports verified clear at the end. Evidence under `verification/`.

**Both claims reproduce exactly as written. Both are pre-existing — identical on 0.9.11.post1,
0.9.12a1 and 0.9.12a2 — so neither is a 0.9.12 release issue. Claim 1 is additionally a duplicate
of something the campaign already recorded; claim 2's blast radius is smaller than the claim says
(dev builds only).**

| claim | prev 0.9.11.post1 | a1 0.9.12a1 | a2 0.9.12a2 | verdict |
|---|---|---|---|---|
| 1. dynamic route direct-loaded in prod answers 404 | `/`→200, `/item/7`→404, `/item/abc`→404 | identical | identical | CONFIRMED, pre-existing, **already in FINDINGS.md** |
| 2. `collapsible=True` + `type="multiple"` React console error | present | present | present | CONFIRMED, pre-existing, app-side misuse, **dev-build only** |

### Claim 1 — dynamic route 404 in prod

Reproduced from the written repro: `probes/dynroute_probe` run with `--env prod` on each venv
(ports 3760 prev / 3762 a1 / 3761 a2; logs `verification/logs/dyn_{prev,a1,a2}_prod.log`, each
carrying its `RUNNING-REFLEX-FROM` line).

```
0.9.11.post1  /→200  /item/7→404  /item/abc→404  /nope→404
0.9.12a1      /→200  /item/7→404  /item/abc→404  /nope→404
0.9.12a2      /→200  /item/7→404  /item/abc→404  /nope→404
```

Chromium on `/item/7`, all three versions byte-identical
(`verification/shots/dyn_{prev,a1,a2}/report.json`): page dump `item page / id=7`, evals
`['id=7', '/item/7 | title=Dynapp | Item']`, `page_errors: []`, `failed_requests: []`, the only
`http_errors` entry the document's own 404. So the page renders, the title is right and the state
hydrates — only the status line is wrong, exactly as claimed.

Root cause confirmed in the installed a2 wheel, and it is the same cause the campaign already
recorded: `reflex/utils/exec.py::get_frontend_mount()` mounts the build with Starlette
`PrecompressedStaticFiles(directory=…, html=True)`, and Starlette's `html=True` answers a miss with
`404.html` **at status 404**. Verified on the wire: the `/item/7` body is byte-identical to
`.web/build/client/404.html` (`cmp` clean, `verification/out/a2_item7.html`), served with
`content-length: 5436`, `server: granian`. The build also emits `__spa-fallback.html`, byte-identical
to `404.html`, which nothing ever serves. `sed -n '340,400p'` of `exec.py` on prev vs the same block
on a2 diffs **empty** — the prod static-serving path is unchanged by this train, which is the
source-level proof that a2 cannot have introduced it.

Refutation attempts, all failed to dislodge it — but they do dislodge its novelty:
- **Already recorded.** FINDINGS.md's `up_examples_b` section carries this verbatim ("prod 404s for
  dynamic routes (pre-existing on both, issue #6983 / PR #6996 …) — and roots it in
  `reflex/utils/exec.py:383` … `PrecompressedStaticFiles(html=True)`, which answers a miss with
  `404.html` at 404; the build's `__spa-fallback.html` is byte-identical to `404.html` and never
  used"). Per the re-verification rules this is a known campaign finding, not a new issue. It also
  already has an upstream ticket and an open fix: the checkout carries `31dbaa851 fix(app): return
  correct HTTP status for SPA fallback routes`, `139ba3c7b Serve SPA fallback with 200 for routable
  paths in prod static serving` and `47b9992a2 Match SPA fallback routes with URL separators on
  Windows`, all only on `origin/claude/pr-6996-review-97oxj9` / `origin/claude/investigate-reflex-
  deployment-YoZvO` — i.e. not merged, so its absence from 0.9.12a2 is expected, not a fix
  regression.
- **Not an environment quirk:** three separate app dirs, three venvs, plain `curl --noproxy '*'`,
  and Chromium all agree.
- **Not app misuse:** the 25-line probe is the documented `/item/[id]` form and the page works.
- **Prod-only, as claimed** (new control): the same app in dev on a2 answers `/item/7`→200,
  `/item/abc`→200 — and also `/nope`→200, which is ordinary vite SPA-dev behaviour
  (`verification/logs/dyn_a2_dev.log`).
- Scope note: the miss is not specific to *dynamic* routes — it is every path the prod build did not
  prerender. Static pages are prerendered to their own `index.html` and stay 200; a dynamic segment
  cannot be, so in practice dynamic routes are the whole user-visible surface. `sitemap.xml` lists
  only `/`, so crawlers are not being pointed at the 404-status URLs by reflex itself.

Severity: agree it is **not a release blocker** (identical to the previous stable, tracked upstream).
I would file it at low/medium rather than low — in a real deployment every dynamic-route URL returns
404 to crawlers, uptime checks and CDNs while looking fine in a browser — but that is a ticket-
priority argument on an existing ticket, not a 0.9.12 gate.

### Claim 2 — `rx.accordion.root(collapsible=True, type="multiple")`

Reproduced from `probes/accordion_probe` on all three venvs (dev, port 3763/8763, driver
`scripts/acc.json`). All three console arrays and all three eval vectors are identical:

```
console: ["[error] Received `%s` for a non-boolean attribute `%s`.\n\nIf you want to write it to the
          DOM, pass a string instead: … true collapsible collapsible true collapsible",
          3 × "[error] The pseudo class \":first-child\" is potentially unsafe when doing SSR …",
          "[log] Disconnect websocket on pagehide"]
evals:   ['0', '', 'True', 'False', 'True', 'False']     # prev == a1 == a2
page_errors: []   http_errors: []   failed_requests: []
```

`diff` of the rendered `acc_after.txt` across prev/a1/a2 is empty. Evidence:
`verification/shots/acc_{prev,a1,a2}/`.

Root cause named at both layers:
- Python: `reflex_components_radix/primitives/accordion.py:104` declares
  `collapsible: Var[bool]` on `AccordionRoot` unconditionally and `_exclude_props()` (lines 141-148)
  drops only `radius/duration/easing/show_dividers`, so `collapsible` is always forwarded. That file
  is **byte-identical** across `$SB/envs/{prev,shared,a2}` (`cmp` clean both ways).
- JS: `@radix-ui/react-accordion` 1.2.20 (same pin on both versions) destructures
  `collapsible = false` out of props in `AccordionImplSingle` (`dist/index.mjs:48`) but **not** in
  `AccordionImplMultiple` (`dist/index.mjs:69-98`, which hard-codes `collapsible: true` in its
  provider and spreads the rest), so the prop reaches `Primitive.div` and React warns.
- Consequence check: React drops the attribute after warning, so
  `document.querySelectorAll('[collapsible]').length === 0` on every version, and the `type="single"`
  root still opens/collapses (`True`/`False` in the eval vector). Behaviourally inert.

Refutation attempts:
- **In-app sighting confirmed:** `up_examples_b/form-designer/form_designer/pages/response.py`
  `responses_accordion()` really does pass `collapsible=True, type="multiple"`.
- **Not new, not version-sensitive:** identical console + evals + DOM on prev/a1/a2, and identical
  source on all three.
- **Narrower than claimed** (new control): in a **prod** build the warning does not exist at all —
  React's production build strips these dev warnings. `verification/shots/acc_a2_prod/report.json`
  from the same probe under `--env prod` on a2 has console `["[error] Failed to load resource: … 404
  (Not Found)"` (the template's missing `favicon.ico`, a known campaign note), "[log] Disconnect
  websocket on pagehide"]` and the same eval vector `['0','','True','False','True','False']`. The
  campaign's own prod artifact agrees: `shots/fd_a2_prod/report.json` shows no `collapsible` error.
  So "every visit to `/responses/<id>` logs the error" holds in dev only, not for deployed users.

Severity: **low, and not a release item** — pre-existing, app-side misuse, no behavioural effect, and
invisible in production builds. The residue is upstream-Reflex-side at most: either drop
`collapsible` from the rendered props when `type == "multiple"` (a one-line `_render`/`_exclude_props`
condition) or say so in the `rx.accordion.root` docstring.

### Cluster re-check byproducts (nothing new)

- FINDING-018 reproduced again on a2: `killtree.py` on the `reflex run` pid left the vite `node`
  child holding 3763, which made `run2.sh` refuse the next start (visible in the run transcript).
  Unchanged behaviour; the notes' own guard caught it.
- Benign noise seen and ignored per the agent brief: the `SitemapPlugin` "enabled by default"
  warning, the implicit-Radix-Themes `DeprecationWarning` (fires on prev too), emotion's
  `:first-child` SSR warnings, and the prod `favicon.ico` 404.
