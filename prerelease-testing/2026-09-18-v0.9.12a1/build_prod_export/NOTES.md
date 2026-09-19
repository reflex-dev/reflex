# build_prod_export — reflex 0.9.12a1 pre-release QA

Cluster: **build_prod_export** (prerender/asset collisions, compression, preload, lazy bundled
libraries, sitemap #7078; `frontend_path` prefix routes #7153; backend-only bundled-library
metadata #7096; json5 removal #7165; atomic stateful-page markers #7142; sentry ASGI wrap #7139;
vite memory / urllib telemetry #7112).

Tested 2026-09-19 with **PyPI packages only**. Nothing was installed from `/home/user/reflex`;
every app run has `assert "/envs/" in rx.__file__` at the top of its app module.

## Versions actually used

`uv pip freeze | grep reflex` — new train (`$SB/envs/shared`, read-only shared venv):

```
reflex==0.9.12a1
reflex-base==0.9.12a1
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
```

Baseline (`$SB/envs/prev`): `reflex==0.9.11.post1`, `reflex-base==0.9.11.post1`,
`reflex-components-core==0.9.9`, `-radix==0.9.9`, `-code==0.9.5`, `-markdown==0.9.3`,
`-recharts==0.9.3`, `-sonner==0.9.3`, `-plotly==0.9.6`, `-gridjs==0.9.1`, `-dataeditor==0.9.2`,
`-lucide==1.0.4`, `-moment==0.9.4`, `-react-player==0.9.2`.

Sentry run only: venv `$SB/envs/bpe` (same alpha train) plus `sentry-sdk==2.69.2`.

## The test app

`bpapp/` (new train) and `prev/bpapp/` (identical source, baseline import assertion) — a single
app configured with `frontend_path="/app"`:

* routes `/`, `/apple`, `/app`, `/about`, `/components`, `/assets`, `/items/[id]`, `/dyn`
* asset directories deliberately colliding with route names: `assets/components/logo.svg`,
  `assets/apple/note.txt`
* `/about` uses `rx.markdown` + `rx.code_block` (shiki), `/components` uses `@rx.memo` cards, an
  `rx.ComponentState`, `rx.cond`, and `rx.icon(tag=State.icon_name)` (dynamic icon name)
* `/assets` uses `rx.upload` whose handler sets `float("inf")`, `float("-inf")`, `float("nan")`
  and a normal float (#7165)
* `/dyn` renders a `@rx.dynamic` component-valued state var whose tree references a bundled
  library (`lucide-react/dist/esm/icons/rocket.mjs`) — the #7096 shape
* index page has a counter, a `@rx.event(background=True)` task, an `rx._x.client_state` input,
  and a "probe" button rendering `sorted(m for m in ("httpx","json5","sqlalchemy","pandas",
  "h11","granian") if m in sys.modules)` (#7112)

Env switches read by `rxconfig.py` / the app module:
`BP_LAZY=1` (frontend_lazy_bundled_libraries), `BP_API_URL`, `BP_BUNDLE=0` (skip the
module-scope `bundle_library(rx.icon("rocket"))`), `BP_SENTRY=1` (sentry init).

## Exact rerun commands

```bash
SB=/tmp/.../scratchpad                      # any scratch root
D=$SB/apps/build_prod_export                # copy bpapp/ and prev/bpapp/ from this dir here

# --- venvs (NEVER create them with /home/user/reflex as cwd) ---
cd $SB && uv venv $SB/envs/mine --python 3.11
uv pip install --python $SB/envs/mine/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-lucide==1.0.4'
# sentry test only (use a PINNED stable; see the sentry-sdk note below):
uv pip install --python $SB/envs/mine/bin/python 'sentry-sdk<3'

# --- 1. export + artifact inspection (#7078, #7165) ---
cd $D/bpapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/mine/bin/reflex export --frontend-only
python3 - <<'PY'
import zipfile; z=zipfile.ZipFile('frontend.zip'); n=set(z.namelist())
print(sorted(x for x in n if x.endswith('.html')))
print(z.read('app/sitemap.xml').decode())
print([l for l in z.read('app/index.html').decode().split('<') if 'preload' in l][:3])
print('gz missing for js:', len([x for x in n if x.endswith('.js') and x+'.gz' not in n]))
PY
unzip -o frontend.zip -d /tmp/exp >/dev/null && grep -rl "core-js" /tmp/exp | head    # must be empty

# --- 2. prod route matrix (#7153) — ONE port for both flags ---
cd $D/bpapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/mine/bin/reflex run --env prod \
   --frontend-port 3260 --backend-port 3260 > prod.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $D/scripts/routes_probe.py \
   http://localhost:3260 $D/out/routes.json prod-0.9.12a1
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $D/scripts/interact.py \
   http://localhost:3260 $D/out/interact.json prod-new $D/shots/prod-new
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $D/scripts/slash_probe.py \
   http://localhost:3260 prod-new $D/out/slash_new.json
# baseline: same commands with $SB/envs/prev and prev/bpapp on port 3261

# --- 3. lazy bundled libraries (#7078) ---
BP_LAZY=1 REFLEX_TELEMETRY_ENABLED=false $SB/envs/mine/bin/reflex run --env prod \
   --frontend-port 3260 --backend-port 3260 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $D/scripts/measure_bytes.py \
   http://localhost:3260 $D/out/bytes_lazy1.json lazy1        # BP_LAZY unset -> bytes_lazy0.json

# --- 4. backend-only + static export (#7096) ---
cd $D/bpapp && REFLEX_TELEMETRY_ENABLED=false $SB/envs/mine/bin/reflex run --env prod \
   --backend-only --backend-port 8260 > be.log 2>&1 &
(cd $D/bpapp/.web/build/client && $SB/envs/mine/bin/python -m http.server 3262 &)
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $D/scripts/backend_only_probe.py \
   http://localhost:3262 backend-only $D/out/backend_only.json

# --- 5. marker scenarios (#7142) — W=$D/bpapp/.web/backend ---
printf '["comp'          > $W/stateful_pages.json   # truncated  -> restart backend-only
rm -f                      $W/stateful_pages.json   # missing    -> restart backend-only
head -c 64 /dev/urandom  > $W/stateful_pages.json   # non-UTF-8  -> restart backend-only (CRASHES)
GRANIAN_WORKERS=4 ... reflex run --env prod --backend-only --backend-port 8260   # 4 workers
md5sum $W/*.json && reflex compile --dry && md5sum $W/*.json                      # dry run

# --- 6. sentry (#7139) ---
cd $D/bpapp && BP_SENTRY=1 REFLEX_TELEMETRY_ENABLED=false $SB/envs/mine/bin/reflex run \
   --frontend-port 3265 --backend-port 8265

# --- 7. rxconfig isolation (#7078) ---
mkdir -p $D/emptydir && cd $D/emptydir && PYTHONPATH=$D/bpapp $SB/envs/mine/bin/reflex compile --dry
```

Kill servers by port (do **not** `pkill -f "reflex run …"` — the pattern matches your own shell
and kills it; that is what `killport.sh` in the scratch dir works around).

## Results

### Verified working (new behavior of this train)

| what | result |
|---|---|
| **#7153 prefix routes** | `/app/apple` (a route whose name starts with the `frontend_path` text) returns **HTTP 200 with the prerendered page** on 0.9.12a1; on 0.9.11.post1 the same URL returns **404** (the SPA shell then client-renders it). Same improvement for `/app/components` and `/app/assets` (route names colliding with build directories). `out/routes_prod_0912a1.json` vs `out/routes_prod_prev.json`. |
| **#7078 prerender + asset collision** | export contains `app/components/index.html` (12 487 B, real page text) **and** `app/components/logo.svg` (172 B); `app/apple/index.html` **and** `app/apple/note.txt`. Both served. |
| **#7078 compression** | `.gz` sidecars exist for every html (12/12), css (2/2) and js file ≥ 256 B; the 283 js files without a `.gz` are all < 256 B, which matches `MIN_SIZE = 256` in `.web/compress-static.js`. No `.br`/`.zst` — correct, `frontend_compression_formats` defaults to `["gzip"]` (reflex-base `config.py:240`). |
| **#7078 preload** | `app/index.html` head has `<link as="style" href="/app/assets/__reflex_global_styles-*.css" rel="preload"/>` before the modulepreloads. |
| **#7078 sitemap** | `xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"`, all six `<loc>` entries carry the `/app` prefix. |
| **#7165 json5 removal** | `grep -r core-js` over the extracted export: **no hits**. Upload handler setting `inf/-inf/nan` renders `inf=Infinity`, `ninf=-Infinity`, `nan=NaN`, `normal=10` with **zero console errors** (`out/interact_prod_0912a1.json` step `upload`, `shots/prod-new-upload.png`). |
| **#7112 no httpx in the worker** | the in-page module probe reports `modules: granian` only — `httpx`, `json5`, `sqlalchemy`, `pandas` are absent from `sys.modules` of the backend worker, in prod, prod+lazy and backend-only. |
| **#7096 backend-only hydration** | `reflex run --env prod --backend-only` + statically served export: `/app/dyn` hydrates, the component-valued state var renders its lucide rocket SVG, ws delta arrives, no `ValueError`, no dropped hydrate. `.web/backend/bundled_libraries.json` is written by the full compile and contains the explicitly bundled `lucide-react/dist/esm/icons/rocket.mjs`; the file does **not** exist at all on 0.9.11.post1. |
| **#7142 markers** | truncated (`["comp`), missing, and 4-granian-worker-cold-start cases all rebuild the marker to `["components"]` with no traceback and no leftover `stateful_pages.json.*.tmp` files. `reflex compile --dry` leaves both markers byte-identical **and** mtime-identical. |
| **#7139 sentry** | with `sentry_sdk.init(dsn=..., integrations=[StarletteIntegration(), StarletteIntegration()])` in the app module, `reflex run` starts, pages render, events work; **no** `AttributeError: 'method' object attribute '__call__' is read-only`, no traceback in the server log after browsing. `logs/dev_sentry.log`. |
| **#7078 rxconfig isolation** | from an empty directory with the app package on `PYTHONPATH`, `reflex compile` does not adopt the other project's config — it treats the cwd as an uninitialized project and offers the template prompt (`logs/rxconfig_isolation.log`). |

### Issues found

**ISSUE 1 (medium, gap in the #7142 fix, NOT a regression) — a stateful-pages marker containing
non-UTF-8 bytes crashes backend startup.**
`reflex/compiler/compiler.py::_read_stateful_pages_marker()` catches `FileNotFoundError` and
`json.JSONDecodeError`, but `Path.read_text()` raises `UnicodeDecodeError` first for a marker
that is not valid UTF-8, so the exception escapes and the granian worker dies before binding:

```
File ".../reflex/compiler/compiler.py", line 1220, in _read_stateful_pages_marker
  return json.loads(marker.read_text())
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b in position 0: invalid start byte
[ERROR] Unexpected exit from worker-1
```

Repro: `head -c 64 /dev/urandom > .web/backend/stateful_pages.json`, then
`reflex run --env prod --backend-only --backend-port 8260`. Evidence `logs/be_s3_garbage.log`
(full traceback at line 24), `logs/markers.log` scenario S3. The marker is left corrupt, so every
subsequent start fails too — it is a permanent wedge until someone deletes the file by hand.
Baseline: 0.9.11.post1 reads the marker with a bare `json.load(file)` and no `try` at all
(`envs/prev/.../reflex/compiler/compiler.py:1227-1229`), so it crashes on this input as well —
0.9.12a1 is strictly better, this is just an un-covered corruption shape for a changelog line that
says markers "are rebuilt when missing or corrupt".

**ISSUE 2 (medium, PRE-EXISTING, reproduced on 0.9.11.post1) — a `@rx.dynamic` component never
re-renders when the state it reads changes.**
`/app/dyn` renders `widget()` built from `@rx.dynamic def widget(state: DynState)` reading
`state.tag`. Clicking `#dyn-flip` updates `#dyn-tag` to `tag: bug` (the ws delta carries
`{"...dyn_state": {"tag_rx_state_": "bug"}}`) but `#dyn-widget` keeps showing `dyn:rocket` with
`class="lucide lucide-rocket"` — the dynamic component's value is never recomputed or sent.
Reproduced identically in dev (`dev-0912a1`), backend-only prod (all marker scenarios) **and on
0.9.11.post1 dev** (`logs/dev_prev.log`, label `dev-0911post1`). Only a full page reload picks up
the new tag. Evidence: `out/backend_only_0912a1.json` (steps `dyn_loaded` / `after_flip`),
`logs/markers.log`.

**ISSUE 3 (low, PRE-EXISTING) — asset URLs are not rewritten for `frontend_path`.**
`rx.image(src="/components/logo.svg")` on a `frontend_path="/app"` app requests
`http://host/components/logo.svg` → 404, and the image renders with `naturalWidth == 0`, while the
same file is served correctly at `/app/components/logo.svg`. Appears in every browser run on both
versions (`out/routes_prod_0912a1.json` `/app/components` → `bad_responses`, and the same entry in
`out/routes_prod_prev.json`). Since #7078 is specifically about assets under `frontend_path`, the
missing prefix on literal `src` strings is worth a docs line or a rewrite.

### Anomalies (surprising but not broken)

**A1 — `frontend_lazy_bundled_libraries=True` made a plain page load MORE JavaScript, not less.**
Prod build, decoded response-body bytes (Playwright `response.body()`, so uncompressed sizes; all
responses were gzip on the wire):

| page | default | `BP_LAZY=1` | delta |
|---|---|---|---|
| `/app/` | 17 js files, 1 177 996 B | 14 js files, 1 243 249 B | **+65 253 B (+5.5 %)**, −3 requests |
| `/app/about` | 20 files, 1 786 894 B | 17 files, 1 852 144 B | +65 250 B (+3.7 %) |
| `/app/components` | 23 files, 1 211 673 B | 20 files, 1 276 926 B | +65 253 B (+5.4 %) |

The setting does what it says structurally — with it on, the index page no longer pulls the shiki
`code-*.js` chunk and the per-icon chunks, and a single `esm-*.js` module appears instead — but
that module is ~65 KB bigger than everything it replaced, on every page, including the pages that
do use the lazy libraries. The changelog line "reducing JavaScript loaded by ordinary pages" does
not hold for this app. Data: `out/bytes_lazy0.json`, `out/bytes_lazy1.json`. Functionally fine: the
dynamic icon, `@rx.memo` cards, `rx.ComponentState` and the shiki-highlighted code block all still
render with the flag on (`out/interact_prod_lazy1.json`, `shots/prod-lazy1-components.png`).

**A2 — every prod start logs `Page X is being redefined with the same component` once per route.**
7 warnings for 7 routes, on a plain `@rx.page`-only app that never calls `app.add_page()`. Dev logs
none. Identical on 0.9.11.post1 (`logs/prod_prev.log`, `logs/prod_prev2.log`) → pre-existing.
This settles handover lead #2 from the `router_vars` cluster.

**A3 — handover lead #1 settled: pre-existing, both versions.** In `--env prod`, a direct load of a
dynamic route (`GET /app/items/7?x=1`) returns **HTTP 404** (the SPA shell) before client-rendering
the correct page, and a query-string URL is rewritten with a trailing slash
(`/app/about?q=hello` → `/app/about/?q=hello`). Both reproduce byte-for-byte on 0.9.11.post1 prod:
`out/routes_prod_prev.json`, `out/slash_prev.json`. It is static-export behavior (no prerendered
file exists for a parameterized route), not a change in this train.

**A4 — `.web/backend/bundled_libraries.json` is never rebuilt by a backend-only start.** Deleting it
and starting `reflex run --env prod --backend-only` leaves it absent; the app still worked here,
because the one stateful page that is re-evaluated (`components`, from the marker) re-registers
lucide by itself. A deployment that ships a `.web/` without that file therefore silently falls back
to whatever page evaluation happens to register. I could **not** construct the negative control
(library registered *only* by a non-stateful page) inside the timebox, so the #7096 fix is verified
in the positive direction only (`logs/markers.log` S4/S7/S8).

**A5 — not a reflex bug, but a trap for testers:** installing sentry with `--prerelease=allow`
resolves `sentry-sdk==3.0.0a7`, whose OpenTelemetry scope setup is incompatible with the
`opentelemetry-api==1.44.0` reflex brings in, and `sentry_sdk.init()` itself raises `ValueError`
from `opentelemetry/context/context.py:21` before reflex is involved. Pin `sentry-sdk<3`.
First traceback kept in `logs/dev_sentry.log`'s predecessor run (re-run overwrote it; the failing
call chain is `sentry_sdk.init → setup_scope_context_management → attach → context.pop`).

**A6 — a `json5-*.js` chunk survives in the export, and it is fine.** `grep json5` over the
exported bundle still hits `app/assets/json5-BkFQEBcI.js` (518 B) and six references in
`bpapp-*.js`. It is the *syntax-highlighting language definition* for JSON5 shipped with the code
block's language list (`import e from "./json-*.js"; t.displayName = \`json5\``), not the `json5`
npm parser, it is lazily chunked (never requested by any page load recorded here), and it contains
no core-js. `grep -r core-js` over the whole export is empty, so #7165 holds.

### Not covered

* vite/react-router RSS comparison with `MIMALLOC_ARENA_EAGER_COMMIT=1` vs default (#7112) — only
  the "no httpx in the backend worker" half of that changelog line was checked.
* `frontend_compression_formats=["brotli","zstd"]` was read from the source but not exercised.
* `rx.dynamic` component whose library fails to load once and then succeeds (Playwright `route`
  blocking) — not run.
* A baseline of the sentry double-`StarletteIntegration` crash on 0.9.11.post1 (would need
  sentry-sdk in a fourth venv).

## Layout of this directory

```
bpapp/            the test app (new train). bpapp/bpapp/bpapp.py is the whole app.
prev/bpapp/       identical source for the 0.9.11.post1 baseline
scripts/          routes_probe.py, interact.py, measure_bytes.py, slash_probe.py,
                  backend_only_probe.py, dyn_check.py   (run with the playwright driver venv)
out/              JSON results of every probe (new + baseline)
logs/             server logs, marker scenarios, export logs, compile --dry, rxconfig isolation
shots/            screenshots: prod pages, lazy-mode components page, backend-only dyn page
```
