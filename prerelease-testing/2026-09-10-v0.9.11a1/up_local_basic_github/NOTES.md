# Cluster `up_local_basic_github` — upgrade testing 0.9.10.post2 -> 0.9.11a1

Three reflex-examples apps, each installed at the **previous stable** (`reflex==0.9.10.post2`),
run for real and driven in headless Chromium, then **upgraded in place to the full alpha train**
(same venv, same `.web/`, same `reflex.lock/`, same sqlite db), re-driven identically, and finally
re-run **cold** (`rm -rf .web`). `local-component` additionally got a real **prod build**.

| app | what it exercises |
| --- | --- |
| `local-component` | a local React component in `hello.jsx` shipped as `rx.asset(shared=True)` and imported via `library="/public/…"`; `React.forwardRef` prop/ref passthrough; event passthrough with `.prevent_default`; the component's own `useState`/`useMemo`; `rx.popover` + `rx.form` driving a State var live; `rx.color_mode_cond`; `rx.scroll_to`. The app whose **compiled output** the memo-hash (#6947) and context-registry (#7071) changes touch. |
| `basic_crud` | `reflex[db]` + `rx.Model`/`rx.session` + alembic, and an app-owned FastAPI router mounted with `rx.App(api_transformer=FastAPI())`. Driven **both** with `httpx` straight at the REST endpoints **and** through the UI (`rx.select`/`rx.input`/`rx.text_area`/Send), plus `@rx.event(background=True)` polling, `rx.foreach` rows and `rx.markdown` response rendering. |
| `github-stats` | `rx.recharts.bar_chart` with four `rx.recharts.bar` series over a state-driven `data=`, `x_axis`/`y_axis`/`legend`/`graphing_tooltip`; two `@rx.event(background=True)` fetchers; `rx.LocalStorage` vars restored on reload; `rx.foreach` chips with an event-arg handler; the dynamic route `/widget/[selected_user_param]` with a `?appearance=` query param. **recharts 3.8.1 -> 3.10.1** in this train. |

## Verdict

**No regressions in any of the three apps.** Every check that passes on 0.9.10.post2 passes on
0.9.11a1, in place and cold; the two anomalies per app are identical on both versions. The alpha
is a small net *improvement* here: the `reflex-components-recharts` 0.9.3a1 bump to recharts 3.10.1
removes a repeated browser console warning that 3.8.1 emits on every chart render (16 -> 0 over
four measured iterations).

The in-place migration is clean on all three: bundled Bun 1.3.11 -> 1.4.0 (downloaded into the
per-app `REFLEX_DIR`), the frontend pins bump, `reflex.lock/bun.lock` stays at
`lockfileVersion 1`, the stale `utils/context.js` is replaced by `utils/context.jsx` and the new
`utils/context-registry.js` appears (#7071), the auto-memo module names re-hash (#6947, expected
and documented), and the cold run converges to a **byte-identical** `.web/package.json`,
`web_tree` and memo-name list.

Findings (all pre-existing on 0.9.10.post2, none release-blocking):

1. **`rx.theme(appearance=…)` / `color_mode=…` is silently dropped from the compiled JSX.**
   `Theme._render()` ends with `.remove_props("appearance")` unconditionally, so a nested
   `rx.theme` can never override light/dark even though the prop is declared, typed
   (`Var[LiteralAppearance]`) and documented ("Override light or dark mode theme … It can also be
   used in a normal page to apply specified properties to all child elements as an override of the
   main theme"). This breaks `github-stats`' documented embedding URL `/widget/<user>?appearance=dark`.
   Identical on reflex-components-radix 0.9.8 and 0.9.9a1 -> **not a regression**, but a real
   dead API. See "FINDING A" below.
2. `basic_crud`'s own API returns `HTTPException(...)` instead of raising it, so "not found" and
   "invalid code" come back as **HTTP 200** with the exception serialised as the body. App bug,
   identical on both versions.
3. `github-stats` passes `rx.text_area(value=State.data_pretty)` with no `on_change`, so React
   logs `You provided a 'value' prop to a form field without an 'onChange' handler` twice per run.
   App bug, identical on both versions.
4. recharts 3.8.1 logs `The width(-1) and height(-1) of chart should be greater than 0` 4x per
   page render for the percentage-sized index chart. **Gone on 3.10.1.**
5. `basic_crud` emits `Warning: Attempting to send delta to disconnected client` after a page
   reload races the `on_load_internal` chain ("superseded by a newer invocation"). Seen on **both**
   versions (1 occurrence per 2 reload races on 0.9.10.post2, 1 per run on 0.9.11a1); the message
   exists in both versions' `reflex/app.py`, so it is timing, not a new code path.
6. Cosmetic: a shared asset compiles to a double-slash import path,
   `import {Hello} from "$/public//external/local_component/hello/hello.jsx?v=0ebba69a"`.
   Byte-identical on both versions; vite resolves it fine.
7. Cosmetic: in-place upgrade does not prune `node_modules` — the upgraded tree keeps
   `prettier@3.9.6` and twelve `@babel/*` packages that the cold tree does not have
   (222 vs 235 node packages for `local-component`). Harmless.

## Ports / envs / method

Reserved ports for this cluster: frontend 5500-5519, backend 9900-9919.

| app | FP | BP | venv |
| --- | --- | --- | --- |
| `local-component` | 5500 | 9900 (prod: 5500/5500) | `$SB/envs/ulbg_local` |
| `basic_crud` | 5501 | 9901 | `$SB/envs/ulbg_crud` |
| `github-stats` | 5502 | 9902 | `$SB/envs/ulbg_github` |
| `github-stats-b0910` (baseline A/B copy) | 5503 | 9903 | `$SB/envs/base0910` (shared, read-only) |
| `basic_crud-b0910` (baseline A/B copy) | 5504 | 9904 | `$SB/envs/ulbg_crud_b0910` |

All installs are PyPI-only into isolated uv venvs; nothing was installed or run from the checkout,
and every `uv pip install` ran with the app dir as cwd (never `/home/user/reflex`, whose
`[tool.uv] exclude-newer` filters out the alphas). `serve.sh` sets
`REFLEX_DIR=$SB/reflex_dirs/<app>` per app so the **baseline** picks up the system bun 1.3.11 from
PATH (min 1.3.0) and the **alpha** performs the real bun 1.4.0 download/migration itself rather
than reusing another agent's bun. `NO_PROXY` is only ever set on the client side (curl/Playwright),
never in the server env.

`github-stats` needs a GitHub personal access token upstream. **`github_stats/fetchers.py` in this
copy is stubbed**: `user_stats()` returns deterministic sha256-derived numbers offline (0.2 s sleep
so the "Fetching Data…" window stays observable) and treats `nosuchuser`/`doesnotexist` as
not-found so the `None` branch stays reachable. The pristine upstream module is kept beside it as
`github_stats/fetchers.py.orig`. Nothing else in the app was modified. All three apps are otherwise
unmodified copies from `/home/user/reflex-dev/reflex-examples/`.

### Rerun instructions

```sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
WD=$SB/apps/up_local_basic_github        # or a copy of THIS directory
DRIVER=$SB/envs/driver/bin/python        # playwright + httpx; chromium at /opt/pw-browsers/chromium
ALPHAS="$(cat $WD/ALPHA_TRAIN.txt)"      # reflex==0.9.11a1 + every alpha sub-package, pinned

# ---------- BASELINE (per app; local-component shown) --------------------------------
uv venv $SB/envs/ulbg_local --python 3.11
cd $WD/local-component && uv pip install --python $SB/envs/ulbg_local/bin/python \
     'reflex==0.9.10.post2' -r requirements.txt          # NO --prerelease on the baseline
cd $WD && ./serve.sh $WD/local-component $SB/envs/ulbg_local 5500 9900 $WD/logs/local_0910_dev.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_local.py http://localhost:5500 artifacts/local-component/0910 local_0910
$DRIVER record_web.py $WD/local-component $WD/artifacts/local-component/web_0910
./stop.sh $WD/local-component 5500 9900

# ---------- IN-PLACE UPGRADE (same venv, KEEP .web/ and reflex.lock/) ---------------
cd $WD/local-component && uv pip install --python $SB/envs/ulbg_local/bin/python \
     --prerelease=allow $ALPHAS
cd $WD && ./serve.sh $WD/local-component $SB/envs/ulbg_local 5500 9900 $WD/logs/local_0911_inplace_dev.log
NO_PROXY=... $DRIVER drive_local.py http://localhost:5500 artifacts/local-component/0911_inplace local_0911_inplace
$DRIVER record_web.py $WD/local-component $WD/artifacts/local-component/web_0911_inplace
./stop.sh $WD/local-component 5500 9900

# ---------- COLD ---------------------------------------------------------------------
rm -rf $WD/local-component/.web
cd $WD && ./serve.sh $WD/local-component $SB/envs/ulbg_local 5500 9900 $WD/logs/local_0911_cold_dev.log
NO_PROXY=... $DRIVER drive_local.py http://localhost:5500 artifacts/local-component/0911_cold local_0911_cold
$DRIVER record_web.py $WD/local-component $WD/artifacts/local-component/web_0911_cold
./stop.sh $WD/local-component 5500 9900

# ---------- PROD (local-component only; ONE port for both) --------------------------
cd $WD && ./serve.sh $WD/local-component $SB/envs/ulbg_local 5500 5500 $WD/logs/local_0911_cold_prod.log --env prod
NO_PROXY=... $DRIVER drive_local.py http://localhost:5500 artifacts/local-component/0911_prod local_0911_prod
./stop.sh $WD/local-component 5500
```

`basic_crud` needs its database created once, before the first run (its own README says so):

```sh
cd $WD/basic_crud && REFLEX_TELEMETRY_ENABLED=false REFLEX_DIR=$SB/reflex_dirs/basic_crud \
  $SB/envs/ulbg_crud/bin/reflex db init && \
  REFLEX_TELEMETRY_ENABLED=false REFLEX_DIR=$SB/reflex_dirs/basic_crud \
  $SB/envs/ulbg_crud/bin/reflex db migrate
# the generated alembic/ + alembic.ini are shipped in this directory; reflex.db is not (excluded)
```

Baseline install for `basic_crud` is `'reflex==0.9.10.post2' -r requirements.txt`
(`reflex[db]>=0.9.2` + `fastapi`); the alpha upgrade uses `'reflex[db]==0.9.11a1'` plus the same
sub-package pins, so sqlmodel/alembic stay in the environment.

Driver signatures:

| script | usage |
| --- | --- |
| `drive_local.py` | `<frontend_url> <artifacts_dir> <label>` — 16 checks |
| `drive_crud.py` | `<frontend_url> <backend_url> <artifacts_dir> <label>` — 27 checks (14 REST via httpx, 13 UI) |
| `drive_github.py` | `<frontend_url> <artifacts_dir> <label> [<app_dir>]` — 25 checks (`app_dir` records installed npm versions) |
| `record_web.py` | `<app_dir> <out_dir>` — no server needed; dumps `package.json`, `installed_versions.json`, `web_tree.txt`, `public_files.txt` (+sha256), `memo_modules.txt`, `memo-manifest.json`, `asset_imports.txt`, `lockfile_version.txt` |
| `probes/theme_appearance_probe.py` | `[out.json]` — no server, no browser; renders `rx.theme(...)` four ways and reports whether `appearance` survives |
| `probes/chart_bars_probe.py` | `<frontend_url> <out.json> <iterations>` — measures when each recharts bar path actually gets a non-zero bbox, and counts the chart-size console warnings |

`serve.sh <app_dir> <venv_dir> <FP> <BP> <log> [extra reflex-run args]` starts `reflex run
--loglevel debug` under `setsid`, waits for HTTP 200 (up to 450 s), writes the pgid to
`<app_dir>/logs/server.pid`. `stop.sh <app_dir> <port>…` kills the process group and verifies the
ports are free.

## Results

Legend: **B** = 0.9.10.post2 baseline, **I** = 0.9.11a1 in-place upgrade, **C** = 0.9.11a1 cold,
**P** = 0.9.11a1 prod. Counts are `pass + anomaly` from `artifacts/<app>/<run>/results.json`.

| app | run | checks | result |
| --- | --- | --- | --- |
| `local-component` | B | 16 | **16 P**, 0 anomaly, 0 console error/warning, 0 HTTP>=400 |
| `local-component` | I | 16 | **16 P** — identical |
| `local-component` | C | 16 | **16 P** — identical |
| `local-component` | P (prod build) | 16 | **16 P** — identical (vite 8.2.2, 416 modules, `built in 1.93s`) |
| `basic_crud` | B | 27 | 25 P + **2 anomaly** (finding 2) |
| `basic_crud` | I | 27 | 25 P + 2 anomaly — identical |
| `basic_crud` | C | 27 | 25 P + 2 anomaly — identical |
| `github-stats` | B | 25 | 21 P + **4 anomaly** (findings 1, 3, 4, + a flaky driver measurement) |
| `github-stats` | I | 25 | 22 P + 3 anomaly (**finding 4 resolved by recharts 3.10.1**) |
| `github-stats` | C | 25 | 22 P + 3 anomaly |

### local-component — compiled-output diffs (the point of this app)

`artifacts/local-component/*.diff`:

* `package.json` 0910 -> 0911: `@radix-ui/react-form` 0.1.14->0.1.16, `@react-router/{node,dev,fs-routes}`
  8.3.0->8.3.1, `isbot` 5.2.1->5.2.2, `react-router` 8.3.0->8.3.1, `sonner` 2.0.7->2.0.8,
  `postcss` 8.5.23->8.5.26, `postcss-import` 16.1.1->17.0.0, `vite` 8.2.0->8.2.2.
  **0 diff lines between in-place and cold.**
* `web_tree` 0910 -> 0911 (3 lines changed, exactly #7071):
  `utils/context.js` **removed**, `utils/context.jsx` **added**, `utils/context-registry.js` **added**,
  and the error-boundary memo file re-hashes
  (`Errorboundary_…_ad430eb9…` -> `…_31a7648b…`).
* `memo_modules` 0910 -> 0911: all eight memo exports in
  `app_components/local_component/local_component.jsx` re-hash (e.g.
  `Button_button_116f7592afcc10c080cf12785317ac8d_44771c95` ->
  `Button_button_6fcf696dcf8c4cdac3d51fb4d1abe1aa_44771c95`). The module-suffix `_44771c95` (the
  defining module) is unchanged; only the content hash moves. **This is the documented effect of
  #6947** ("Generated memo module names change as a result"), not a defect.
* The shared asset is byte-stable across all three runs
  (`public/external/local_component/hello/hello.jsx`, sha256 prefix `0ebba69a38fa13ac`) and its
  import line is byte-identical: `$/public//external/local_component/hello/hello.jsx?v=0ebba69a`
  (note the double slash — finding 6).
* `reflex.lock/bun.lock` and `.web/bun.lock` stay at `lockfileVersion=1` through the Bun 1.4
  migration.
* The migration log (`logs/local_0911_inplace_dev.log`) shows the expected two-step: `bun install
  --frozen-lockfile` restores the **old** pins from the retained lockfile (react-router 8.3.0,
  vite 8.2.0, …), then two `bun add` calls move them to the new pins. The two
  `warn: incorrect peer dependency "react-router@8.3.0"` lines in between are the known-benign
  one-time migration noise; the final lockfile is consistent and the cold tree matches it exactly.

### basic_crud — REST + UI

REST (httpx straight at `http://localhost:9901`, responses recorded in
`artifacts/basic_crud/<run>/api_calls.json`): `GET /products`, `POST /products`,
`GET /products/{id}`, `PUT /products/{id}`, `DELETE /products/{id}` all behave identically on both
versions; `PUT` bumps `updated` past `created`; a duplicate `code` surfaces as HTTP 500 with a
`sqlite3.IntegrityError: UNIQUE constraint failed: product.code` traceback in the server log (the
app does not catch it — same on both). `GET /openapi.json` lists exactly
`['/products', '/products/{spec_id}']`, `GET /docs` is 200, and reflex's own `GET /ping` still
answers `"pong"` next to the mounted FastAPI app, so `api_transformer` composition is intact.

UI: the Radix select + input + textarea + Send round trip drives all four methods; `Status: 200`
and the JSON body render in the `rx.markdown` pane; the `@rx.event(background=True)`
`reload_product` poller picks the change up within ~2 s and `rx.foreach` re-renders the row
(`Stock: 55` after a PUT); Clear resets the form; a 404-shaped response renders instead of
crashing the page; a reload re-hydrates the list.

Worth knowing (both versions, app design, not filed as issues): `State.load_product` yields
`State.reload_product`, an infinite `while True` background task, on **every** page load, so the
tasks accumulate for the life of the process; and the `Product.dict()` JSON key order differs from
run to run within one version (three different orders across the three runs here) — process-level
dict ordering, not a version difference.

### github-stats — recharts 3.8.1 -> 3.10.1

25 checks/run. Both the index chart (4 series x N users) and the
`/widget/[selected_user_param]` chart render correctly on both versions: correct bar count
(4 per user), correct x-axis category ticks, 4 legend items on the widget, a populated
`graphing_tooltip` on hover with **no** tooltip cursor rect (`cursor=False` respected), and bar
paths with the expected non-zero bboxes. Adding/removing users through the `rx.foreach` chips
(`State.remove_user(user)` — an event handler taking the loop item) works; an unknown user leaves
the chart untouched and raises nothing; the two `rx.LocalStorage` vars restore the whole chart
after a reload. LocalStorage keys are state-qualified, so `State.user_stats_json` and
`WidgetState.user_stats_json` do not collide:
`reflex___state____state.github_stats___github_stats____state.user_stats_json_rx_state_`.

Measured difference (`artifacts/github-stats/chart_probe_{0910,0911}.json`, 4 iterations each,
`probes/chart_bars_probe.py`):

| | recharts 3.8.1 (0.9.10.post2) | recharts 3.10.1 (0.9.11a1) |
| --- | --- | --- |
| index bars painted, fresh fetch | 4/4 iterations, 0.26 s | 4/4 iterations, 0.26 s |
| index bars painted, after reload | 4/4, 0.26 s | 4/4, 0.26 s |
| index bars painted, after resize | 4/4, 0.01 s | 4/4, 0.01 s |
| `width(-1)/height(-1)` console warnings | **16** (4 per iteration) | **0** |

Also present on both versions: a server-side
`DeprecationWarning: RouterData.page has been deprecated in version 0.8.1. Use RouterData.url
instead. It will be completely removed in 1.0. (github_stats/widget.py:18)` — the example still
uses `self.router.page.params`. The deprecation shim is still in place in 0.9.11a1, so the app
keeps working; the upstream example should be migrated before 1.0.

---

## FINDING A — `rx.theme(appearance=…)` is stripped from the compiled output (MEDIUM impact, pre-existing, not a regression)

**What breaks for a user.** `github-stats` documents its widget as embeddable with
`/widget/<user>?appearance=dark`. The page reads the query param into `WidgetState.appearance` and
passes it to `rx.theme(appearance=WidgetState.appearance)`. The embedded widget always renders
light.

**Root cause** (`reflex_components_radix/themes/base.py`, identical at 0.9.8 and 0.9.9a1):

```python
    appearance: Var[LiteralAppearance] = field(
        doc='Override light or dark mode theme: "inherit" | "light" | "dark". Defaults to "inherit".'
    )
    ...
    def _render(self, props: dict[str, Any] | None = None) -> Tag:
        tag = super()._render(props)
        return tag.add_props(
            css=Var(...)
        ).remove_props("appearance")        # <-- line 247, unconditional
```

`Theme.create()` also maps the `color_mode=` kwarg onto `appearance`, so that spelling is stripped
too. Only the *root* theme gets an appearance, and it gets it from reflex's colour-mode provider,
not from this prop — so the nested/override use the class docstring advertises ("It can also be
used in a normal page to apply specified properties to all child elements as an override of the
main theme") cannot work.

**Repro without a server or a browser** — `probes/theme_appearance_probe.py`, run from a neutral
cwd with any reflex venv:

```sh
cd $SB && $SB/envs/base0910/bin/python apps/up_local_basic_github/probes/theme_appearance_probe.py
cd $SB && $SB/envs/smoke/bin/python    apps/up_local_basic_github/probes/theme_appearance_probe.py
```

Both print `appearance present in render: False` for `appearance="dark"`, `color_mode="dark"` and
`appearance=SomeState.var`, while the control `accent_color="red"` renders as `accentColor:"red"`.
Saved output: `artifacts/theme_probe_0910.json`, `artifacts/theme_probe_0911.json`.

**Repro end to end** — `./serve.sh $WD/github-stats <venv> 5502 9902 log`, then open
`http://localhost:5502/widget/masenf?appearance=dark`. The two `.radix-themes` elements are
`radix-themes css-0 light` (root) and `radix-themes css-0` (the page's own `rx.theme`) — the nested
one carries no appearance class at all and `data-has-background="false"`. Screenshot:
`artifacts/github-stats/0911_cold/10_widget_dark.png`. Compiled proof (in-place run):
`.web/app_components/github_stats/widget.jsx` line 56 is
`jsx(RadixThemesTheme,{css:{...}},children)` — the state context for `WidgetState` is imported into
the memo body, so the compiler knew the prop was state-bound, and the prop is still absent.

**Regression:** no — byte-identical behaviour on reflex-components-radix 0.9.8 (with reflex
0.9.10.post2) and 0.9.9a1 (with reflex 0.9.11a1). **Downstream:** the code lives in
`reflex-components-radix`, a first-party reflex-dev package.

**Decision for maintainers:** either honour the prop (keep it in the rendered tag, letting Radix's
own `Theme` apply the class) or drop it from the component and the docs so it stops being a
documented no-op.

## Anomalies recorded but not filed as issues

* **`index_bars_drawn` in `drive_github.py` is a flaky measurement, not an app defect.** The
  `<g class="recharts-bar-rectangle">` groups appear a frame before their `<path>`, so reading the
  bbox the instant the group count hits 4 can see `null`. It read `0/4` on the 0910 baseline and on
  the 0911 cold run, and `4/4` on the 0911 in-place run, purely by timing. `probes/chart_bars_probe.py`
  polls properly and shows 4/4 within 0.26 s on **both** versions. The driver in this directory has
  since been fixed to poll; the `results.json` files predate the fix, which is why that row still
  says `anomaly`.
* `background_event_spinner` (was the "Fetching Data…" window observable?) is likewise racy with a
  0.2 s stubbed fetch: `True` on B and C, `False` on I. Not a defect.
* `reflex init` during the upgrade logs `Checking for the latest version of reflex… Latest version
  of reflex: 0.9.10.post2` while running 0.9.11a1 (PyPI's "latest" excludes pre-releases). Cosmetic.
* Prod mode spawns a single granian worker here, so FINDING-003 (cross-worker delta loss with
  redis) is not in play for the `local-component` prod run.

## The two baseline A/B copies (not shipped — recreate in one command each)

Both are byte-identical copies of the shipped app source, run on 0.9.10.post2 to A/B a single
observation. Recreate with:

```sh
cd $WD && for a in github-stats basic_crud; do
  mkdir -p $a-b0910
  tar -C $WD --exclude=.web --exclude=node_modules --exclude=.states --exclude=__pycache__ \
      --exclude=reflex.lock -cf - $a | tar -C /tmp -xf - && cp -r /tmp/$a/. $a-b0910/ && rm -rf /tmp/$a
done
# github-stats-b0910 runs on the shared read-only $SB/envs/base0910 (no extra deps needed):
./serve.sh $WD/github-stats-b0910 $SB/envs/base0910 5503 9903 $WD/logs/github_0910_probe_dev.log
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER probes/chart_bars_probe.py http://localhost:5503 artifacts/github-stats/chart_probe_0910.json 4
./stop.sh $WD/github-stats-b0910 5503 9903

# basic_crud needs fastapi + sqlmodel, so it needs its OWN baseline venv
# ($SB/envs/base0910 has neither and fails with ModuleNotFoundError: No module named 'fastapi'):
uv venv $SB/envs/ulbg_crud_b0910 --python 3.11
cd $WD/basic_crud-b0910 && uv pip install --python $SB/envs/ulbg_crud_b0910/bin/python \
    'reflex==0.9.10.post2' -r requirements.txt      # reflex.db is copied along, already migrated
cd $WD && ./serve.sh $WD/basic_crud-b0910 $SB/envs/ulbg_crud_b0910 5504 9904 $WD/logs/crud_0910_probe_dev.log
for i in 1 2; do NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $DRIVER drive_crud.py http://localhost:5504 http://localhost:9904 artifacts/basic_crud/0910_probe_$i crud_0910_probe_$i; done
grep -c "disconnected client" $WD/logs/crud_0910_probe_dev.log   # -> 1 across 2 drives (2 reload races)
./stop.sh $WD/basic_crud-b0910 5504 9904
```

Their run artifacts are shipped: `artifacts/github-stats/chart_probe_0910.json` (vs
`chart_probe_0911.json`) and `artifacts/basic_crud/0910_probe_{1,2}/` (27 checks each, 25 P +
the same 2 anomalies as every other basic_crud run), with server logs
`logs/github_0910_probe_dev.log` and `logs/crud_0910_probe_dev.log`.

---

## VERIFICATION: rx.theme(appearance=...) / color_mode=... is unconditionally stripped from the compiled JSX, so a nested rx.theme can never override light/dark

**Independent adversarial verifier** (separate working dir, own minimal app, own probe, own
baseline run). Verdict: **CONFIRMED — genuine framework defect, NOT a 0.9.11a1 regression,
not release-blocking.** Severity: **medium** (a declared, typed, doc-generated prop that is a
silent no-op for every non-root `rx.theme`, with real downstream breakage), pre-existing since
reflex **0.6.x (Dec 2024)**.

Working dir: `/tmp/.../scratchpad/apps/verify2_up_local_basic_github_0`
Ports used: frontend 6200 (alpha) / 6201 (baseline), backend 10600 / 10601 — both freed.
Repro copied to `verification/theme_appearance/`.

### Refutation attempts, and what each showed

| hypothesis | result |
| --- | --- |
| cwd shadowing (`/home/user/reflex` on `sys.path`) | ruled out — both probe runs assert `"/envs/" in rx.__file__`; run from `$SB` |
| proxy / ports / `NO_PROXY` | ruled out — no network needed for the probe; the browser run used `NO_PROXY` client-side only and the page loaded 200 with zero console errors |
| prop rendering itself is broken | ruled out — `accent_color="red"` renders `accentColor:"red"` and the DOM shows `data-accent-color="red"` |
| Radix wouldn't honour `appearance` anyway (so stripping is harmless) | **ruled out** — the patched-theme control (below) renders dark correctly |
| app/demo bug rather than framework bug | ruled out — reproduces in a 40-line app with no example-app code |
| regression in 0.9.11a1 | **ruled out** — identical source and identical DOM on reflex 0.9.10.post2 + radix 0.9.8 |
| documented/intended behavior | **partly true, and that is the finding** — the strip is deliberate for the *root* theme; applying it unconditionally is the bug |
| flaky | ruled out — deterministic at compile time, no timing involved |

### Minimal repro (no example app, no GitHub token, ~40 lines)

`verification/theme_appearance/theme_override/` — root app theme pinned to
`rx.theme(appearance="light")`, then five nested boxes on one page:

* **A** `rx.theme(swatch, appearance="dark")` — stock
* **B** `rx.theme(swatch, color_mode="dark")` — stock, the `create()` alias spelling
* **C** `PatchedTheme(swatch, appearance="dark")` — a 4-line subclass of
  `reflex_components_radix.themes.base.Theme` whose `_render` re-adds the prop the stock
  `_render` strips. **This is the decisive control**: it isolates the strip as the sole cause.
* **D** `rx.theme(swatch, accent_color="red")` — control for "props render at all"
* **E** `rx.theme(swatch, appearance=ThemeState.appearance_param)` — the state-Var spelling
  `github-stats/widget.py` actually uses

```sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
WD=$SB/apps/verify2_up_local_basic_github_0        # or a copy of verification/theme_appearance
cp -r <this repo>/verification/theme_appearance/theme_override $WD/

# --- no-server probe, both versions (identical output) -------------------------------
cd $SB && $SB/envs/smoke/bin/python    $WD/probes/theme_probe.py $WD/artifacts/probe_0911.json
cd $SB && $SB/envs/base0910/bin/python $WD/probes/theme_probe.py $WD/artifacts/probe_0910.json

# --- alpha, real server + real Chromium ---------------------------------------------
cd $WD && ./serve.sh $WD/theme_override $SB/envs/smoke 6200 10600 $WD/logs/theme_0911_dev.log
cd $WD && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive_theme.py http://localhost:6200 $WD/artifacts/nested_0911 /
cd $WD && ./stop.sh $WD/theme_override 6200 10600

# --- baseline 0.9.10.post2 + radix 0.9.8 (fresh copy, no .web, no reflex.lock) -------
cd $WD && ./serve.sh $WD/theme_override_b0910 $SB/envs/base0910 6201 10601 $WD/logs/theme_0910_dev.log
cd $WD && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive_theme.py http://localhost:6201 $WD/artifacts/nested_0910 /
cd $WD && ./stop.sh $WD/theme_override_b0910 6201 10601
```

### Observed — identical on 0.9.11a1 and 0.9.10.post2

`.radix-themes` elements in DOM order (`artifacts/nested_0911/dom.json`,
`artifacts/nested_0910/dom.json` — the two files differ only in whitespace/ordering, not content):

```
radix-themes css-0 light   root=true   has-background=true   accent=indigo   <- root, appearance="light" HONOURED
radix-themes css-0         root=false  has-background=false  accent=indigo   <- A  appearance="dark"  IGNORED
radix-themes css-0         root=false  has-background=false  accent=indigo   <- B  color_mode="dark"  IGNORED
radix-themes dark css-0    root=false  has-background=true   accent=indigo   <- C  PATCHED            WORKS
radix-themes css-0         root=false  has-background=false  accent=red      <- D  accent_color       WORKS
radix-themes css-0         root=false  has-background=false  accent=indigo   <- E  State Var          IGNORED
```

Computed text colour per card (same file): A/B/D/E `rgb(28, 32, 36)` (light), **C
`rgb(237, 238, 240)` (dark)**. Screenshots `artifacts/nested_0911/page.png` and
`artifacts/nested_0910/page.png` show one black card (C) among four white ones.

Compiled proof, `artifacts/compiled_index_jsx_theme_callsites_0911.txt` (from
`.web/app/routes/_index.jsx`):

```
wrap-a -> jsx(RadixThemesTheme,{css:{...theme.styles.global[':root'], ...}},...)                  # appearance gone
wrap-b -> jsx(RadixThemesTheme,{css:{...theme.styles.global[':root'], ...}},...)                  # appearance gone
wrap-c -> jsx(RadixThemesTheme,{appearance:"dark",css:{...}},...)                                 # patched: present
wrap-d -> jsx(RadixThemesTheme,{accentColor:"red",css:{...}},...)                                 # control: present
wrap-e -> jsx(Theme_theme_c8a3b51d26e8d7af641adc03cf6f5e8d_f38dd5eb,{},...)                       # auto-memo, prop gone
```

Browser console on both versions: only the three known-benign lines (HydrateFallback, vite
connecting/connected, React DevTools). No errors, no warnings.

### Mechanism (file:line, installed wheels = release branch)

1. **The strip** — `reflex_components_radix/themes/base.py:245-250` (radix **0.9.9a1** and
   **0.9.8**, byte-identical):
   ```python
   def _render(self, props: dict[str, Any] | None = None) -> Tag:
       tag = super()._render(props)
       return tag.add_props(
           css=Var(_js_expr="{...theme.styles.global[':root'], ...theme.styles.global.body}"),
       ).remove_props("appearance")          # line 247 — unconditional
   ```
   and `Theme.create` at `base.py:226` maps `color_mode=` onto `props["appearance"]`, so that
   spelling is stripped by the same line. The prop is declared and documented at `base.py:182-184`.
2. **Why the strip exists (it is deliberate, and correct for the ROOT theme).** Colour mode is
   applied imperatively by
   `reflex_base/.templates/web/components/reflex/radix_themes_color_mode_provider.js`, which does
   `document.querySelector('.radix-themes[data-is-root-theme="true"]')` and swaps the
   `light`/`dark` class on that one element. If the root `Theme` also received `appearance` as a
   React prop, Radix would re-assert it on every render and fight the toggle — the regression
   reported as reflex-dev/reflex#2992 / #4384. So the root theme's `appearance` is instead
   consumed in Python, at `reflex/compiler/compiler.py:182-203`
   (`_resolve_default_color_mode`, called from `compiler.py:216` and `:1333`), which turns a
   **literal** `"light"`/`"dark"` into the compile-time `default_color_mode`. That path is why box
   **C**'s ancestor is `light` in my run, and it is the only reason app-level `appearance` works.
3. **The defect** is that step 1 is unconditional while step 2 only ever looks at the *app* theme.
   Every non-root `rx.theme` therefore carries a typed, documented prop with no effect, and
   `data-is-root-theme="false"` means the provider's DOM patch never touches it either. A
   non-literal `Var` (case **E**, and exactly what `github-stats` passes) is also dropped at step 2.

### Provenance — long-standing, and once briefly worked

* `862d7ec80` "add test for color mode (initial and toggle) (#4467)", 2024-12-11, added the line
  with the commit note *"don't render the appearance prop of rx.theme"*, together with
  `tests/integration/tests_playwright/test_appearance.py`. That test only covers
  `rx.App(theme=rx.theme(appearance=...))` — **nothing covers a nested theme**, which is why the
  regression in the override path was never caught.
* At that time `Tag.remove_props` mutated in place (`git show 5161944e0^:reflex/components/tags/tag.py`
  lines 116-129), so the strip took effect immediately in 0.6.x.
* `5161944e0` "make tag immutable (#5641)", 2025-07-31, rewrote it to the chained
  `return tag.add_props(...).remove_props("appearance")` — same behavior, not the origin.

So: **broken since reflex 0.6.x, ~9 months before this release train.** Byte-identical at
0.9.10.post2/radix 0.9.8 and 0.9.11a1/radix 0.9.9a1.

### Impact / downstream

* Real: `reflex-examples/github-stats` documents its widget as embeddable at
  `/widget/<user>?appearance=dark`; `github_stats/widget.py:89` passes
  `appearance=WidgetState.appearance` to `rx.theme(...)` and the embed always renders light.
* `rx.theme`'s own class docstring advertises the override use ("It can also be used in a normal
  page to apply specified properties to all child elements as an override of the main theme"), and
  the prop appears in the generated props table on the docs site (`docs/library/other/theme.md`
  frontmatter `components: - rx.theme`, described as `"inherit" | "light" | "dark"`). Note the
  hand-written docs (`docs/styling/theming.md`, `docs/library/other/theme.md`,
  `docs/styling/tailwind.md`, `docs/styling/custom-stylesheets.md`) only ever *show* the
  app-level form, which does work — so nobody following the prose examples is affected.
  `docs/library/disclosure/accordion.md:362` does wrap a page in `rx.theme(...)`, but without
  `appearance`.
* No supported workaround exists short of subclassing `Theme` (case C) or hand-writing the
  `radix-themes dark` class.

### Suggested resolution (unchanged from the claimant, with the mechanism pinned down)

Make the strip conditional on being the app/root theme — the root theme is the one
`_resolve_default_color_mode` consumes and the one the colour-mode provider patches, so only that
one must not receive the React prop; nested themes should pass `appearance` straight through (case
C proves the bundled `@radix-ui/themes` then does the right thing). If per-subtree appearance is
deliberately out of scope, remove the prop from `Theme` (or accept it only on the app theme) and
drop the override sentence from the class docstring, so it stops being a typed, documented no-op.
Either way a nested-theme case belongs in `tests/integration/tests_playwright/test_appearance.py`.

Evidence paths (this repo):
`verification/theme_appearance/theme_override/` (minimal app),
`verification/theme_appearance/theme_probe.py`, `verification/theme_appearance/drive_theme.py`,
`verification/theme_appearance/artifacts/{probe_0910.json,probe_0911.json}`,
`verification/theme_appearance/artifacts/nested_0911/{dom.json,page.png,console.txt}`,
`verification/theme_appearance/artifacts/nested_0910/{dom.json,page.png,console.txt}`,
`verification/theme_appearance/artifacts/compiled_index_jsx_theme_callsites_0911.txt`.

All processes started for this verification were stopped (`stop.sh` reported "ports free"
for 6200/10600 and 6201/10601 and no leftover processes).
