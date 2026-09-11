# testing_admin — `reflex.testing` / AppHarness, the `testing` extra, AdminDash + starlette-admin 1.0, wrapt bounds

Cluster of the 2026-09-10 reflex **0.9.11a1** pre-release campaign.
Everything here was installed from **PyPI only** into isolated `uv` venvs; nothing was
installed or imported from the `/home/user/reflex` checkout. Every script starts with
`assert "/envs/" in reflex.__file__`.

Changelog lines under test:

- reflex Bug Fixes — *"Make `reflex.testing` importable without test-only dependencies and
  provide a `testing` extra for `AppHarness`"* (#6974 / #7008)
- reflex Bug Fixes — *"`AdminDash` now works with starlette-admin 1.0, which renamed the
  SQLAlchemy `Admin(engine=...)` argument to `session_provider`. Both starlette-admin 0.x and
  1.x are supported"* (#7019)
- reflex Misc — *"Allow wrapt 2.2 and 2.3"* (#7019)
- PyPI metadata for reflex 0.9.11a1: extra `testing` = `psutil`, `selenium`, `uvicorn`

---

## 0. Environment / how to recreate

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
cd $SB          # NEVER run uv from /home/user/reflex: its exclude-newer hides the alphas

# AppHarness / testing extra
uv venv $SB/envs/ta_h311 --python 3.11
uv pip install --python $SB/envs/ta_h311/bin/python --prerelease=allow \
    'reflex[testing]==0.9.11a1' pytest pytest-asyncio playwright httpx
uv venv $SB/envs/ta_h313 --python 3.13          # same install line
# baseline that can import reflex.testing at all on the old version:
uv venv $SB/envs/ta_h_b0910 --python 3.11
uv pip install --python $SB/envs/ta_h_b0910/bin/python 'reflex==0.9.10.post2' uvicorn psutil selenium

# AdminDash matrix (the first four already existed in this campaign's shared envs)
#   envs/admin_new   reflex 0.9.11a1     + starlette-admin 1.0.1
#   envs/admin_100   reflex 0.9.11a1     + starlette-admin 1.0.0
#   envs/admin_old   reflex 0.9.11a1     + starlette-admin 0.17.1
#   envs/admin_base  reflex 0.9.10.post2 + starlette-admin 0.17.1
uv venv $SB/envs/ta_adm_b1 --python 3.11        # THE missing baseline
uv pip install --python $SB/envs/ta_adm_b1/bin/python 'reflex[db]==0.9.10.post2' 'starlette-admin==1.0.1'
uv venv $SB/envs/ta_db_nosa --python 3.11
uv pip install --python $SB/envs/ta_db_nosa/bin/python --prerelease=allow 'reflex[db]==0.9.11a1'

# wrapt bounds
uv venv $SB/envs/ta_w117 --python 3.11 && uv pip install --python $SB/envs/ta_w117/bin/python \
    --prerelease=allow 'reflex==0.9.11a1' 'wrapt==1.17.3'
uv venv $SB/envs/ta_w22  --python 3.11 && uv pip install --python $SB/envs/ta_w22/bin/python \
    --prerelease=allow 'reflex==0.9.11a1' 'wrapt==2.2.2'
uv venv $SB/envs/ta_w24  --python 3.11 && uv pip install --python $SB/envs/ta_w24/bin/python \
    --prerelease=allow 'reflex==0.9.11a1' \
  && uv pip install --python $SB/envs/ta_w24/bin/python --no-deps 'wrapt==2.4.1'   # forced past reflex's <2.4 cap
# envs/smoke already carries reflex 0.9.11a1 with the DEFAULT resolution (wrapt 2.3.0)
# envs/base0910 carries reflex 0.9.10.post2 (wrapt 2.1.2)

# extras resolution
uv venv $SB/envs/ta_pyd --python 3.11 && uv pip install --python $SB/envs/ta_pyd/bin/python \
    --prerelease=allow 'reflex[pydantic]==0.9.11a1'
uv venv $SB/envs/ta_pyd_stable --python 3.11 && uv pip install --python $SB/envs/ta_pyd_stable/bin/python \
    'reflex[pydantic]==0.9.11a1'          # no --prerelease: transitive deps stay stable
```

Reserved ports for this cluster: frontend **5580-5599**, backend **9980-9999**. Every
`reflex run` here uses `--frontend-port 5580 --backend-port 9980` (or `--backend-only
--backend-port 9980/9981`).
**Caveat:** `AppHarness` itself binds *OS-assigned ephemeral* ports — `_start_backend`
passes `port=0` and `_start_frontend` sets `PORT=0`, and there is no API to pin them. The
pytest suite below therefore cannot be confined to the reserved range; nothing else in this
cluster leaves it.

---

## 1. Results table

| # | check | result | evidence |
|---|---|---|---|
| 1 | `import reflex.testing` in a bare 0.9.11a1 install (no extra) | **pass** | `logs/bare_testing_0911a1.json` |
| 2 | same on 0.9.10.post2 → `ModuleNotFoundError: No module named 'uvicorn'` | **pass** (baseline: the fix is real) | `logs/bare_testing_0910.json` |
| 3 | `AppHarness.create(...).__enter__()` without the extra → actionable `ImportError` naming `reflex[testing]` | **pass** | `logs/bare_testing_0911a1.json` |
| 4 | `testing` extra = psutil + selenium + uvicorn, and nothing else appears in a bare install | **pass** | `logs/bare_testing_0911a1.json` |
| 5 | downstream pytest suite: module-scoped `AppHarness` fixture, Playwright-driven, py3.11 | **pass** (12 passed, 1 skipped) | `logs/pytest311.log`, `logs/harness311_results.json` |
| 6 | same suite on Python 3.13 | **pass** (12 passed, 1 skipped) | `logs/pytest313.log`, `logs/harness313_results.json` |
| 7 | `AppHarnessProd` in the SAME pytest process as a dev harness | **pass** | `logs/harness311_results.json` (`prod_*`) |
| 8 | a second **dev** harness AFTER the prod harness ran `export()` (0.9.9 `REFLEX_ENV_MODE` leak fix) | **pass** | `logs/harness311_results.json` (`dev2_env_mode`, `dev2_vite_client_status=200`) |
| 9 | `harness.poll_for_content` + server-side state read through `harness.app_instance` after real clicks | **pass** | `logs/harness311_results.json` (`dev1_state_*`) |
| 10 | 0 console errors / 0 failed requests across all three harnesses, dev and prod | **pass** | `logs/harness311_results.json` |
| 11 | `harness.frontend()` (selenium, shipped by the extra) | **skipped** — sandbox has chromedriver 147 vs chromium 141 | `logs/harness311_results.json` (`dev1_selenium_frontend`) |
| 12 | `AppHarness` app_source whose `def` line carries a trailing comment (e.g. `# noqa: N802`) | **fail** — ISSUE 1 | `logs/appharness_source_0911a1.json`, `logs/appharness_e2e_errors_0911a1.txt` |
| 13 | `AppHarness` app_source with a *string* return annotation (`-> "None"`) | **fail** — ISSUE 1 | same |
| 14 | same two shapes on 0.9.10.post2 | **fail** (identical → pre-existing) | `logs/appharness_source_0910.json` |
| 15 | AdminDash, reflex 0.9.11a1 + starlette-admin 1.0.1: app starts, `/ping` 200 | **pass** | `logs/admin_a1_sa101.status` |
| 16 | AdminDash, reflex 0.9.11a1 + starlette-admin 1.0.1: every `/admin*` page | **fail** — ISSUE 2 (all 500) | `logs/admin_a1_sa101.status`, `logs/admin_a1_sa101.trimmed.log` |
| 17 | AdminDash, reflex 0.9.11a1 + starlette-admin 0.17.1 | **fail** — HTML 500, JSON `/admin/api/widget` 200 | `logs/admin_a1_sa017.status` |
| 18 | BASELINE AdminDash, reflex 0.9.10.post2 + starlette-admin 1.0.1 | **pass** (baseline confirms the #7019 construction fix: the old version does not start at all) | `logs/admin_b0910_sa101.status`, `logs/admin_b0910_sa101.log` |
| 19 | BASELINE AdminDash, reflex 0.9.10.post2 + starlette-admin 0.17.1 | **fail** (same 500 → ISSUE 2 is pre-existing) | `logs/admin_b0910_sa017.status` |
| 20 | AdminDash CRUD (list / create / edit / delete) in Chromium | **fail** — impossible, every page is 500 | `logs/admin_browser_a1_sa101.json`, `shots/a1_sa101_admin_*.png` |
| 21 | the AdminDash app's own page works (rx.Model writes through `rx.session`) | **pass** | `shots/a1_sa101_app.png` |
| 22 | root-cause isolation of the 500 **without reflex** | **pass** (diagnostic) | `logs/admin_isolate_nesting_sa101.json` |
| 23 | reflex ASGI route tree shows the shape that breaks `url_for` | **pass** (diagnostic) | `logs/reflex_asgi_routes.json` |
| 24 | AdminDash when starlette-admin is NOT installed | **anomaly** — silent no-op, `/admin` 404, no log line — ISSUE 3 | `logs/admin_nosa.status`, `logs/admin_nosa.log` |
| 25 | starlette-admin 1.0 `No secret_key provided` warning (1.0.x only) | **anomaly** — ISSUE 4 | `logs/admin_a1_sa101.trimmed.log` |
| 26 | wrapt 2.3.0 (default resolution) — mutable list/dict/nested/dataclass vars in a browser | **pass** | `logs/drive_wrapt230.json`, `shots/wrapt_wrapt230.png` |
| 27 | wrapt 2.2.2 | **pass** | `logs/drive_wrapt222.json` |
| 28 | wrapt 1.17.3 (the floor) | **pass** | `logs/drive_wrapt1173.json` |
| 29 | wrapt 2.4.1 forced past the `<2.4` cap | **pass** — works, but is excluded by the pin — ISSUE 5 | `logs/drive_wrapt241.json` |
| 30 | BASELINE wrapt on 0.9.10.post2 (wrapt 2.1.2) | **pass** (identical → no regression) | `logs/drive_wrapt_base0910.json` |
| 31 | `reflex[pydantic]` and `reflex[db]` resolve as documented; bare install has no pydantic/sqlmodel/alembic | **pass** | `logs/bare_testing_0911a1.json`, section 6 below |
| 32 | `BaseStateToken(ident=..., cls=SubState)` silently returns the **root** State | **anomaly** — ISSUE 6 | `harness_suite/harness_app.py` comment, section 6 |

---

## 2. `reflex[testing]` / AppHarness — VERIFIED

### 2a. Bare install (no extra)

```bash
cd /tmp && $SB/envs/smoke/bin/python /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/probe_bare_testing.py      # reflex 0.9.11a1
cd /tmp && $SB/envs/base0910/bin/python /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/probe_bare_testing.py   # reflex 0.9.10.post2
```

| | `import reflex.testing` | `AppHarness.create(...).__enter__()` |
|---|---|---|
| **0.9.11a1** | OK | `ImportError: AppHarness backend support requires `uvicorn`. Install it with `pip install 'reflex[testing]'`.` |
| 0.9.10.post2 | `ModuleNotFoundError: No module named 'uvicorn'` | never reached — the import fails |

Verbatim, from `logs/bare_testing_0911a1.json`:

```
ImportError: AppHarness backend support requires `uvicorn`. Install it with `pip install 'reflex[testing]'`.
```

The message names the extra, so it is directly actionable. `psutil`, `selenium`, `uvicorn`,
`pydantic`, `sqlmodel` and `alembic` are all absent from the bare install, as intended.

One cosmetic note: `AppHarness.__enter__` runs `_initialize_app()` (a full `reflex init` +
compile, ~20 s) **before** it discovers uvicorn is missing, so the user waits through a
compile to get the ImportError. Checking for the extra first would fail in under a second.

### 2b. Downstream pytest suite (`harness_suite/`)

Three test modules run in ONE pytest process, each owning exactly one module-scoped harness,
so only one server is alive at a time but the process-global state (`REFLEX_ENV_MODE`, the
memo registry, the registration context) is shared across harnesses — which is the point:

- `test_1_dev.py` — `AppHarness` (dev). Playwright Chromium clicks `#bump` three times, the
  UI settles at `3/3/4`, and the resulting server state is read back through
  `harness.app_instance.state_manager` for the *same browser token* (rendered into the page
  as `#token`): `count=3`, `items=['i1','i2','i3']`, `meta={'k1':1,'k2':2,'k3':3}`,
  `profile.qty=4`. Also an event chain (`yield DemoState.bump` → count 11), an
  `@rx.event(background=True)` task (3 ticks) and a client-side navigation to `/second`.
- `test_2_prod.py` — `AppHarnessProd` in the same process. `/@vite/client` → 404 (a real
  static build), UI settles at `2/2/3`, state reads back correctly.
- `test_3_dev_after_prod.py` — a second **dev** harness created *after* `AppHarnessProd` ran
  `export()` (which sets `REFLEX_ENV_MODE=prod` process-wide). `REFLEX_ENV_MODE` is `Env.DEV`
  and `/@vite/client` → 200, i.e. it is a genuine dev server: the 0.9.9 leak fix holds.

```bash
cd /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/harness_suite
REFLEX_TELEMETRY_ENABLED=false TA_RESULTS=/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/logs/harness311_results.json \
  TA_SHOTS=/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/shots $SB/envs/ta_h311/bin/pytest -q -p no:randomly
# -> 12 passed, 1 skipped in ~27 s      (same with envs/ta_h313 on Python 3.13)
```

`harness.poll_for_content()` is exercised with a `PWText` shim (an object exposing `.text`
backed by a Playwright locator) — the helper only ever touches `element.text`, so it is not
actually selenium-coupled. Console messages, page errors and >=400 responses are captured on
every page: **zero errors and zero failed requests** in all three harnesses on both 3.11 and 3.13.

---

## 3. ISSUE 1 — `AppHarness` mangles `app_source` whose `def` line is not bare

**Severity: medium. Pre-existing (identical on 0.9.10.post2), but newly reachable: 0.9.11a1
is the first release where `reflex[testing]` makes `AppHarness` an installable, documented
downstream API, so this is the first release where outside users will hit it.**

`AppHarness._get_source_from_app_source` (`reflex/testing.py:245-259`) copies the *body* of
the app function into the generated module by regex-stripping the header and dedenting:

```python
source = re.sub(r"^\s*def\s+\w+\s*\(.*?\)(\s+->\s+\w+)?:", "", source, flags=re.DOTALL)
return textwrap.dedent(source)
```

Two shapes break:

1. **A trailing comment on the `def` line.** The comment survives the substitution and
   becomes the first line, so `textwrap.dedent` computes a 2-space common indent instead of
   4. This is not exotic: app factories are PascalCase, so a downstream project with ruff
   writes `def MyApp():  # noqa: N802`.
2. **A return annotation the regex does not recognise** (anything that is not a bare
   `\w+`, e.g. `-> "None"`). The optional group fails, `.*?` backtracks across newlines
   (`re.DOTALL`) to the next `):` in the body — usually the first nested `def index():` or
   `class S(rx.State):` — and **silently deletes everything up to it**.

### Repro

```bash
cd /tmp && $SB/envs/ta_h311/bin/python /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/probe_appharness_source.py      # compile-only matrix
cd /tmp && $SB/envs/ta_h311/bin/python /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/probe_appharness_e2e_errors.py  # what the user actually sees
```

`probe_appharness_source.py` output (`logs/appharness_source_0911a1.json`):

| app_source shape | generated module |
|---|---|
| `def plain():` | compiles |
| `def noqa_comment():  # noqa: N802` | **IndentationError: unexpected indent (line 2)** |
| `def annotated() -> None:` | compiles |
| `def annotated_comment() -> None:  # a comment` | **IndentationError: unexpected indent (line 2)** |
| `def annotated_str() -> "None":` | header kept verbatim → body silently re-indented |
| multi-line signature, docstring | compiles |

End-to-end (`logs/appharness_e2e_errors_0911a1.txt`), the user sees:

```
IndentationError: unexpected indent (trailingcomment.py, line 3)
  File ".../reflex/testing.py", line 317, in _initialize_app
    reflex.utils.prerequisites.get_and_validate_app(
  ...
  File "/tmp/ah_trailing_comment_h_o8blk7/trailingcomment/trailingcomment.py", line 3
    import reflex as rx
IndentationError: unexpected indent
```

with this generated module (note the 2-space indent):

```
(blank)
# noqa: N802
  import reflex as rx
(blank)
  def index():
      return rx.text("hi")
```

The traceback points at a temp file the user never wrote and never mentions `app_source`.

### Baseline

`cd /tmp && $SB/envs/ta_h_b0910/bin/python /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/probe_appharness_source.py` →
`logs/appharness_source_0910.json`: byte-for-byte the same failures, and
`reflex/testing.py:236-239` in 0.9.10.post2 has the identical regex. **regression = false.**

### Workaround

Put the `noqa` on a different line, or pass the app as a module / raw string via
`app_source=`, or let the app be a real directory (`app_source=None`).

---

## 4. ISSUE 2 — every `rx.AdminDash` page returns HTTP 500 (`NoMatchFound`)

**Severity: high (the headline #7019 changelog claim is not observable end to end).
Pre-existing — 0.9.10.post2 + starlette-admin 0.17.1 fails the same way — but #7019 fixes
only the *constructor* half, so the release note overstates what the user gets.**

### App

`admindash/` here: one `rx.Model(table=True)` (`Widget`), `rx.App(admin_dash=rx.AdminDash(models=[Widget]))`,
plus a normal page that lists and inserts widgets through `rx.session()`.

```bash
cd /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admindash
REFLEX_TELEMETRY_ENABLED=false $SB/envs/admin_new/bin/reflex db init
REFLEX_TELEMETRY_ENABLED=false $SB/envs/admin_new/bin/reflex db makemigrations --message widget
REFLEX_TELEMETRY_ENABLED=false $SB/envs/admin_new/bin/reflex db migrate
# matrix (backend-only, one env at a time):
/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admin_probe.sh $SB/envs/admin_new  a1_sa101     /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admindash 9980
/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admin_probe.sh $SB/envs/admin_old  a1_sa017     /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admindash 9980
/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admin_probe.sh $SB/envs/ta_adm_b1  b0910_sa101  /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admindash 9980
/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admin_probe.sh $SB/envs/admin_base b0910_sa017  /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admindash 9980
```

### Matrix

| reflex | starlette-admin | app starts | `/ping` | `/admin/` | `/admin/widget/list` | `/admin/api/widget` | error |
|---|---|---|---|---|---|---|---|
| **0.9.11a1** | **1.0.1** | yes | 200 | **500** | **500** | **500** | `NoMatchFound: No route exists for name "admin:list" and params "key".` |
| 0.9.11a1 | 0.17.1 | yes | 200 | **500** | **500** | 200 | `NoMatchFound: ... "admin:statics" ... / "admin:api"` |
| 0.9.10.post2 | 1.0.1 | **NO** | — | — | — | — | `TypeError: Admin.__init__() got an unexpected keyword argument 'engine'` |
| 0.9.10.post2 | 0.17.1 | yes | 200 | **500** | **500** | 200 | `NoMatchFound: ... "admin:statics"` |

So #7019 **is** a real fix — on 0.9.10.post2 the app does not even boot with starlette-admin
1.0 (granian worker dies at import, `logs/admin_b0910_sa101.log`) — but the dashboard it
unblocks still does not serve a single HTML page.

### Browser evidence

```bash
cd /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admindash && REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/admin_new/bin/reflex run --frontend-port 5580 --backend-port 9980 --loglevel debug &
cd /tmp && $SB/envs/driver/bin/python /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admin_browser.py \
  http://localhost:5580/ http://localhost:9980 a1_sa101
/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/kill_servers.sh
```

`logs/admin_browser_a1_sa101.json`: the app's own page works (two widgets created and
rendered, `shots/a1_sa101_app.png`), while `/admin/`, `/admin/widget/list` and
`/admin/widget/create` each render the plain text `Internal Server Error`
(`shots/a1_sa101_admin_index.png` etc.). **List / create / edit / delete could not be
exercised at all.**

### Root cause (isolated, no reflex involved)

```bash
cd /tmp && $SB/envs/admin_new/bin/python /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admin_isolate_nesting.py
```
`logs/admin_isolate_nesting_sa101.json` — starlette 1.6.0 + starlette-admin 1.0.1:

| shape | `/admin/` | `/admin/widget/list` |
|---|---|---|
| A. `admin.mount_to(app)` on the app that serves the request | 200 | 200 |
| B. admin mounted on an inner Starlette app, `Mount("/", app=inner)` on the outer | 200 | 200 |
| C. B + the admin Mount also registered on the outer router | 200 | 200 |
| **D. admin on an inner app reached through a bare ASGI callable: `Mount("/", app=wrapper(inner))`** | **500** | **500** |

Starlette >= 1.x resolves `request.url_for()` against `scope["router"]`, and
`Router.app()` pins that to the **outermost** router (`if "router" not in scope`). An
*unnamed* `Mount` normally makes that harmless, because `Mount.url_path_for` delegates to
`self.routes` — but `Mount.routes` is `getattr(self.app, "routes", [])`, and reflex's mount
wraps the API app in a plain function, so there are no routes to delegate to.

Reflex's actual ASGI tree confirms shape D exactly
(`cd /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admindash && $SB/envs/admin_new/bin/python /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/probe_reflex_asgi_routes.py`,
`logs/reflex_asgi_routes.json`):

```
asgi                 starlette.applications.Starlette   n_routes=1
asgi.routes[0]       starlette.routing.Mount  name=None path=''  n_routes=0   <-- no routes to delegate to
asgi.routes[0].app   builtins.function                               <-- reflex/app.py:713 context_middleware
```

while `app._api.routes` does contain `Mount('/admin', name='admin')`. The admin app is
mounted one level too deep for `url_for` to ever see it
(`reflex/app.py:1422-1453` builds it, `reflex/app.py:704-717` wraps `_api`).

**Any fix must make the admin Mount reachable from the outermost router** — e.g. mount the
admin app on the outer Starlette app, or give the outer `Mount` an `app` object that exposes
`.routes`. Passing a pre-built `admin=` to `rx.AdminDash` does not help: it is mounted the
same way.

---

## 5. ISSUE 3/4/5/6 — smaller findings

### ISSUE 3 — AdminDash is silently disabled when starlette-admin is missing (low, pre-existing)

`_setup_admin_dash` does `except ImportError: return` (`reflex/app.py:1423-1425`).
starlette-admin is not a dependency of reflex nor of the `db` extra, so:

```bash
/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admin_probe.sh $SB/envs/ta_db_nosa nosa /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/admindash 9981
```

`logs/admin_nosa.status`: `/ping` 200, **every `/admin*` path 404**, and `logs/admin_nosa.log`
contains no mention of admin, starlette-admin or the dashboard at any log level (`--loglevel
debug`). The user gets a 404 with nothing to search for. Identical code on 0.9.10.post2.

### ISSUE 4 — starlette-admin 1.0 warns about a random `secret_key` on every start (low, new in this train)

With starlette-admin 1.0.x only (0 occurrences under 0.17.1):

```
.../starlette_admin/base.py:260: UserWarning: No secret_key provided: a random one was
generated. CSRF tokens and flash messages will NOT survive server restarts. Set secret_key=
on Admin in production.
```

reflex builds `Admin(get_engine(), title=..., logo_url=...)` and never passes `secret_key`,
and `rx.AdminDash` exposes no way to set it short of constructing the whole `Admin` yourself.
In prod, reflex runs multiple granian workers, so each worker would generate a *different*
secret. Cosmetic today only because ISSUE 2 keeps anyone from reaching a form.

### ISSUE 5 — the new `wrapt <2.4` cap was already stale on release day (low)

reflex 0.9.11a1 requires `wrapt>=1.17.0,<2.4` (0.9.10.post2 had `<2.2`). PyPI upload times:
**wrapt 2.4.0 — 2026-08-30**, 2.4.1 — 2026-09-10. So the cap this train raises already
excludes a wrapt minor that had been out for 11 days when 0.9.11a1 was published, and a user
whose environment pulls wrapt 2.4 for any other reason cannot install reflex 0.9.11a1
alongside it. Forcing wrapt 2.4.1 in (`uv pip install --no-deps wrapt==2.4.1`) and running
the mutation app end to end produced **identical, correct behaviour** — see table row 29.

### ISSUE 6 — `BaseStateToken(ident=..., cls=SubState)` silently returns the ROOT state (low)

The natural downstream way to inspect state from a test:

```python
st = await app.state_manager.get_state(rx.BaseStateToken(ident=token, cls=DemoState))
st.count            # AttributeError: 'State' object has no attribute 'count'
```

`MemoryStateManager._get_or_create_state` uses `token.cls.get_root_state()` and
`BaseStateToken.cache_key` is just the ident, so `cls` only selects the *root* of the
hierarchy — the substate you named is never returned, and the failure is a bare
`AttributeError` that says nothing about tokens. The working form is:

```python
root = await app.state_manager.get_state(rx.BaseStateToken(ident=token, cls=State))
st = await root.get_state(DemoState)
```

(see the comment in `harness_suite/harness_app.py::read_state`).

---

## 6. wrapt bounds — all pass

`wraptapp/` mutates, in event handlers, a `list` (append + index assignment), a `dict`
(insert, `+=`, `pop`), a `list[dict]` (nested `+=`, append), a `@dataclasses.dataclass` var
(attribute `+=`, and appending to a list *field* of it) and the same dataclass field from an
`@rx.event(background=True)` task under `async with self`. A computed var `digest` folds all
of them into one string that the driver waits on, and `rx.foreach` re-renders the list.

```bash
/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/run_and_drive.sh $SB/envs/<env> <label> /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/wraptapp /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/wrapt_browser.py <label>
```

| env | reflex | wrapt | digest sequence | console errors | failed requests |
|---|---|---|---|---|---|
| `envs/ta_w117` | 0.9.11a1 | 1.17.3 (floor) | 1\|1\|0\|0\|1\|0 → 2\|1\|… → 2\|3\|… → 2\|3\|1\|… → …\|1\|2\|0 → 1\|1\|1\|1\|2\|0 → 1\|1\|1\|1\|5\|3 | 0 | 0 |
| `envs/ta_w22` | 0.9.11a1 | 2.2.2 | identical | 0 | 0 |
| `envs/smoke` | 0.9.11a1 | 2.3.0 (default resolution) | identical | 0 | 0 |
| `envs/ta_w24` | 0.9.11a1 | 2.4.1 (forced past the cap) | identical | 0 | 0 |
| `envs/base0910` | 0.9.10.post2 | 2.1.2 | identical | 0 | 0 |

**No regression, and the new bound is safe across its whole declared range.**

## 7. Extras resolution — as documented

| install | result |
|---|---|
| `reflex==0.9.11a1` (bare) | no psutil / selenium / uvicorn / pydantic / sqlmodel / alembic (`logs/bare_testing_0911a1.json`) |
| `reflex[testing]==0.9.11a1` | psutil 7.2.2, selenium 4.49.0, uvicorn 0.52.4 |
| `reflex[db]==0.9.11a1` | alembic 1.19.2, pydantic, sqlmodel 0.0.42 — **no starlette-admin** (see ISSUE 3) |
| `reflex[pydantic]==0.9.11a1` | reflex-base 0.9.11a1 + pydantic; nothing else |
| PyPI metadata | `provides_extra: ['db', 'pydantic', 'testing']` |

`reflex[pydantic]` resolves to `reflex-base[pydantic]` → `pydantic>=2.12.0,<3.0`, and the
three guarded call sites (`reflex_base/utils/serializers.py:278`,
`reflex_base/vars/object.py:76`, `reflex_base/event/processor/base_state_processor.py:34`)
use `find_spec("pydantic")`, so the bare install is genuinely pydantic-free.

**Watch out when reading version tables in this campaign:** installing with
`--prerelease=allow` (needed to name the reflex alpha) also lets uv pick prereleases of
*transitive* deps — several envs here ended up with `pydantic 2.14.0b2`. Installing
`'reflex[pydantic]==0.9.11a1'` **without** the flag works fine (uv still honours the explicit
alpha pin) and yields stable `pydantic 2.13.5` (`envs/ta_pyd_stable`). That is a property of
the flag, not of reflex.

---

## 8. Benign / environmental observations (not findings)

- `AppHarness` binds ephemeral ports (`port=0` / `PORT=0`) with no way to pin them; a CI that
  firewalls port ranges cannot constrain it.
- `harness.frontend()` could not be exercised: this sandbox has chromedriver 147
  (`/opt/node22/bin/chromedriver`) and Chromium 141 (`/opt/pw-browsers/chromium`), so selenium
  fails with `SessionNotCreatedException: ... only supports Chrome version 147`. That is the
  sandbox, not reflex. The test skips cleanly and records the message.
- Playwright must be launched with `--no-proxy-server` (a `proxy={"server": "direct://"}`
  argument still produced `net::ERR_PROXY_CONNECTION_FAILED` against `localhost`); never
  export `NO_PROXY` into the reflex server's environment.
- `AppHarness.poll_for_content` only reads `element.text`, so a tiny Playwright shim works
  (`harness_suite/harness_app.py::PWText`). `asyncio.run()` cannot be called inside a
  `sync_playwright()` block — do state reads after the browser block.
- `rx.Model` is deprecated (`DeprecationWarning: reflex.Model has been deprecated in version
  0.9.2`) yet it is the only documented way to feed `rx.AdminDash(models=[...])`.
- In dev, `http://localhost:<frontend>/admin/` returns 200 with an empty body — that is the
  generic client-side catch-all (`/definitely-not-a-route/` behaves the same), not an admin
  bug. The dashboard is served by the **backend** port.
- Terminating `reflex run` from a script orphans the vite/react-router child, which keeps the
  frontend port bound and makes the next run silently reuse the stale server. `kill_servers.sh`
  here sweeps `/proc/net/tcp`; note it must NOT use a plain `pkill -f "reflex run …"`, because
  that pattern also matches the calling shell's own command line and kills the test driver.

## 9. Files

```
admindash/            AdminDash sample app (rx.Model + AdminDash + a normal page)
wraptapp/             mutable-var app for the wrapt matrix
harness_suite/        downstream-style pytest suite (conftest, harness_app, 3 test modules)
probe_bare_testing.py            bare-install import + AppHarness.__enter__ probe
probe_appharness_source.py       app_source header-shape matrix (compile only)
probe_appharness_e2e_errors.py   the same two shapes, end to end
probe_reflex_asgi_routes.py      walks reflex's ASGI route tree
admin_isolate_nesting.py         reflex-free isolation of the /admin 500
admin_probe.sh                   backend-only /admin status sweep for one env
admin_browser.py                 Chromium driver for the app + /admin
wrapt_browser.py                 Chromium driver for the mutation app
run_and_drive.sh / kill_servers.sh   start `reflex run` on 5580/9980, drive, clean up
logs/ shots/ shots313/
```

---

## VERIFICATION: Every rx.AdminDash page returns HTTP 500 (NoMatchFound) — the #7019 changelog claim is not observable end to end

**Verifier:** independent adversarial re-run (cluster `verify2_testing_admin_0`), 2026-09-11.
Reproduced from the written repro only, in a fresh venv and a freshly written app; the
claimant's running processes and envs were not reused (their `admin_old`/`admin_base`/
`ta_adm_b1` venvs were used read-only for two of the four baseline rows).

**VERDICT: CONFIRMED — genuine framework defect.** Severity **high**, regression vs
0.9.10.post2 **false** (pre-existing), downstream-package impact **false**
(reflex-only; `reflex/app.py`).

Refutation attempts that all failed to explain it away:

- *Environment/proxy/port quirk* — no. The 500 is raised inside the server process
  (traceback in the server log) and reproduces with **no server and no sockets at all**
  through `starlette.testclient.TestClient` against the ASGI app `App.__call__()` returns.
- *API misuse / demo-app bug* — no. The app is the documented one-liner
  `rx.App(admin_dash=rx.AdminDash(models=[Widget]))` over a single `rx.Model(table=True)`,
  written fresh from the repro text.
- *Documented behaviour* — no. `/ping` on the same backend port is 200 and
  `app._api.routes` really does contain `Mount('/admin', name='admin')` with 13 child
  routes; the dashboard is simply unreachable through `url_for`.
- *Escape hatch exists* — no. `rx.App(..., api_transformer=Starlette())` (the supported way
  to nest a custom ASGI app) produces exactly the same `/admin/` 500, because the
  transformer output is itself re-wrapped by `_context_middleware`.
- *Flaky* — no. Deterministic on every one of ~20 requests across four env combinations.
- *Pre-existing* — **yes, and I re-ran the baseline myself**: reflex 0.9.10.post2 +
  starlette-admin 0.17.1 fails identically. That is the part of the claim that holds, so
  this is not a release regression; it is a long-standing defect the #7019 note now
  advertises as fixed.

### Reproduce (exact commands, all run from a neutral cwd, PyPI-only venv)

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
cd $SB                      # never run uv from /home/user/reflex (exclude-newer hides the alphas)
uv venv $SB/envs/verify2_testing_admin_0 --python 3.11
uv pip install --python $SB/envs/verify2_testing_admin_0/bin/python --prerelease=allow \
    'reflex[db]==0.9.11a1' 'starlette-admin==1.0.1'
#  -> reflex 0.9.11a1, starlette 1.6.0, starlette-admin 1.0.1, sqlmodel 0.0.42

mkdir -p $SB/apps/verify2_testing_admin_0
cp -r verification/verify_admindash $SB/apps/verify2_testing_admin_0/admindash
cd $SB/apps/verify2_testing_admin_0/admindash
export REFLEX_TELEMETRY_ENABLED=false
$SB/envs/verify2_testing_admin_0/bin/reflex db init      # answers: keep generated alembic.ini
$SB/envs/verify2_testing_admin_0/bin/reflex db makemigrations --message widget
$SB/envs/verify2_testing_admin_0/bin/reflex db migrate

# (a) server-free minimal repro - no ports, ~30 s, prints the ASGI tree AND the statuses
$SB/envs/verify2_testing_admin_0/bin/python minimal_admin_repro.py

# (b) the same through a real backend
$SB/envs/verify2_testing_admin_0/bin/reflex run --backend-only --backend-port 10680 --loglevel debug > run.log 2>&1 &
for p in /ping /admin/ /admin/login /admin/widget/list /admin/api/widget /admin/statics/css/main.css; do
  curl -s --noproxy '*' -o /dev/null -w "%{http_code}  $p\n" "http://localhost:10680$p"; done

# (c) reflex-free isolation of the nesting shape (+ a candidate fix shape)
cd /tmp && $SB/envs/verify2_testing_admin_0/bin/python \
  /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/verification/isolate_mount_shapes.py

# (d) browser evidence
cd /tmp && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/testing_admin/verification/browse_admin.py \
  http://localhost:10680 <outdir>
```

### Matrix I measured (independent of the claimant's numbers — they agree)

| reflex | starlette | starlette-admin | boots | `/ping` | `/admin/` | `/admin/widget/list` | `/admin/api/widget` |
|---|---|---|---|---|---|---|---|
| **0.9.11a1** | 1.6.0 | **1.0.1** | yes | 200 | **500** | **500** | **500** |
| 0.9.11a1 | 1.6.0 | 0.17.1 | yes | 200 | **500** | **500** | 200 |
| 0.9.10.post2 | 1.6.0 | 1.0.1 | **no** (`TypeError: Admin.__init__() got an unexpected keyword argument 'engine'`) | — | — | — | — |
| 0.9.10.post2 | 1.6.0 | 0.17.1 | yes | 200 | **500** | **500** | 200 |

`/admin` (no slash) is a 307 to `/admin/`. In Chromium both HTML pages render the bare text
`Internal Server Error` (`verification/shots/verify_admin_index_a1_sa101.png`,
`verify_admin_list_a1_sa101.png`).

So both halves of the claimant's framing hold: #7019's constructor change is real and
necessary (the old release does not even boot against starlette-admin 1.0), and the
dashboard it unblocks still serves no HTML page.

### Mechanism (named at file:line, release branch `origin/r/pre-2026.09.10-34457666442`, c50481a8c)

`verification/logs/verify_admin_minimal_repro_a1_sa101.json` prints reflex's real tree:

```
asgi              Starlette                      n_routes=1
asgi.routes[0]    Mount name=None path=''  app_type=builtins.function  n_child_routes=0
app._api mounts   [ Mount('/_event'), Mount('/admin', name='admin', n_child_routes=13) ]
statuses          /ping 200, /admin/ 500, /admin/widget/list 500, /admin/api/widget 500
```

1. `reflex/app.py:1453` — `admin.mount_to(self._api)` registers `Mount('/admin', name='admin')`
   on the **inner** api app.
2. `reflex/app.py:812-818` — the served app is `top_asgi_app = Starlette(...)` whose single
   route is `Mount('', app=self._context_middleware(asgi_app))`.
3. `reflex/app.py:713-717` — `_context_middleware` returns a plain `async def
   context_middleware(scope, receive, send)` **function**, which has no `.routes`.
4. starlette `routing.py:675-676` — `Router.app()` does `if "router" not in scope:
   scope["router"] = self`, pinning `scope["router"]` to the **outermost** router for the
   whole request.
5. starlette `requests.py:202` — `Request.url_for` resolves against
   `scope["router"] or scope["app"]`, i.e. the outer router.
6. starlette `routing.py:391-392` — `Mount.routes` is `getattr(self._base_app, "routes", [])`.
   For a plain function that is `[]`, so the unnamed outer `Mount` cannot delegate, and
   `Router.url_path_for` (routing.py:631-637) raises
   `NoMatchFound: No route exists for name "admin:list" and params "key"` from
   `starlette_admin/helpers.py:243`.

`verification/logs/verify_admin_isolate_mount_shapes.json` isolates this with **no reflex at
all** (starlette 1.6.0 + starlette-admin 1.0.1 + sqlmodel, `TestClient`):

| shape | `/admin/` | `/admin/widget/list` |
|---|---|---|
| A `admin.mount_to(app)` on the served app | 200 | 200 |
| B outer `Mount('', app=<Starlette object>)` | 200 | 200 |
| **C outer `Mount('', app=<plain function>)` — reflex's shape** | **500** | **500** |
| D outer `Mount('', app=<callable exposing `.routes`>)` — candidate fix | 200 | 200 |

Shape D is the cheap fix: make `_context_middleware` return a small callable **class** with a
`routes` property delegating to the wrapped app (or mount the admin app on `top_asgi_app`
instead of `self._api`). Anything that restores `Mount.routes` delegation from the outermost
router fixes every `/admin*` page at once.

Why CI did not catch it: `tests/units/test_app.py::test_initialize_with_admin_dashboard` (and
the custom-auth variant) only assert `app.admin_dash is not None` and that the models are
registered — nothing in the repo ever issues an HTTP request against `/admin`.

### Judgement

- **confirmed: true** — real defect in `reflex/app.py`, not environment, not misuse.
- **severity: high** — `rx.AdminDash` is a public, exported API (`rx.AdminDash`, `__init__.pyi:178`)
  and *every* page it serves is a 500; there is no user-side workaround, and the 0.9.11a1
  release note tells users it "now works". Not a release blocker in the regression sense
  (0.9.10.post2 is equally broken), so the minimum action is to correct/qualify the #7019
  changelog wording; the code fix is small and worth taking in this train.
- **regression: false** — re-measured on 0.9.10.post2 + starlette-admin 0.17.1: identical 500s.
  Both releases require `starlette>=1.3.1`, so there is no supported starlette version on
  either release where the old delegation behaviour would apply.
- **downstream: false** — the defect is entirely in the `reflex` package.

### Evidence produced by this verification

```
verification/verify_admindash/                      my own app (+ minimal_admin_repro.py)
verification/isolate_mount_shapes.py                reflex-free shape isolation (A/B/C/D)
verification/browse_admin.py                        Chromium driver for /admin pages
verification/logs/verify_admin_minimal_repro_a1_sa101.json   ASGI tree + statuses, server-free
verification/logs/verify_admin_isolate_mount_shapes.json     A/B/C/D results
verification/logs/verify_admin_matrix.json                   the four-row matrix + browser result
verification/logs/verify_admin_a1_sa101.trimmed.log          NoMatchFound traceback (0.9.11a1 + sa 1.0.1)
verification/logs/verify_admin_a1_sa017.trimmed.log          0.9.11a1 + sa 0.17.1
verification/logs/verify_admin_b0910_sa017.trimmed.log       BASELINE 0.9.10.post2 + sa 0.17.1 (same failure)
verification/logs/verify_admin_b0910_sa101.trimmed.log       BASELINE 0.9.10.post2 + sa 1.0.1 (worker dies)
verification/shots/verify_admin_index_a1_sa101.png           Chromium: "Internal Server Error"
verification/shots/verify_admin_list_a1_sa101.png
```

All servers started for this verification (ports 10680-10683) were stopped; no processes left running.

---

## VERIFICATION: AppHarness mangles app_source whose `def` line has a trailing comment or a non-plain return annotation

**Independent adversarial verification (agent `verify2_testing_admin_1`, 2026-09-11).**

### Verdict: CONFIRMED — genuine framework defect. Regression: NO. Downstream packages broken: NO.
### Severity: LOW (downgraded from the claimed *medium*; rationale below).

Reproduced from the written repro alone, in my own venvs and my own working dir, with my own
scripts. Nothing environmental is involved: `_get_source_from_app_source` is a pure
string transformation — no network, no ports, no cwd dependency (every script asserts
`"/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__`, so the checkout
never shadowed the wheel).

### My environment

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
cd $SB && uv venv $SB/envs/verify2_testing_admin_1 --python 3.11
cd $SB && uv pip install --python $SB/envs/verify2_testing_admin_1/bin/python \
    --prerelease=allow 'reflex[testing]==0.9.11a1' pytest
cd $SB && uv venv $SB/envs/verify2_testing_admin_1_b0910 --python 3.11
cd $SB && uv pip install --python $SB/envs/verify2_testing_admin_1_b0910/bin/python \
    'reflex==0.9.10.post2' uvicorn psutil selenium pytest      # 0.9.10 has no `testing` extra
```

### Exact commands

```bash
D=$SB/apps/verify2_testing_admin_1      # scripts also copied to verification/appharness_source/
cd $D && $SB/envs/verify2_testing_admin_1/bin/python       v_source_matrix.py   # 10-shape compile matrix, 0.9.11a1
cd $D && $SB/envs/verify2_testing_admin_1_b0910/bin/python v_source_matrix.py   # same matrix, 0.9.10.post2
cd $D && REFLEX_TELEMETRY_ENABLED=false $SB/envs/verify2_testing_admin_1/bin/python v_e2e_errors.py  # 3 real AppHarness.__enter__()
cd $D && REFLEX_TELEMETRY_ENABLED=false $SB/envs/verify2_testing_admin_1/bin/python v_e2e_silent.py  # the fully silent shape
cd $D && $SB/envs/verify2_testing_admin_1/bin/python v_silent_clean.py                               # compile-only view of the same
```

No server ever starts — every failure happens in `AppHarness._initialize_app()` before
`_start_backend()`, so no reserved port was used and no process was left running.

### Results (my run, `verification/logs/v_source_matrix_0911a1.json`)

| `app_source` header | 0.9.11a1 | 0.9.10.post2 | body intact? |
|---|---|---|---|
| `def f_plain():` | compiles | compiles | yes |
| `def f_trailing_comment():  # noqa: N802` | **IndentationError (line 2)** | **IndentationError** | yes, but re-indented 2 |
| `def f_trailing_comment_plain_words():  # a note about the app` | **IndentationError** | **IndentationError** | yes, re-indented 2 |
| `def f_annot_none() -> None:` | compiles | compiles | yes |
| `def f_annot_str() -> "None":` | **IndentationError** | **IndentationError** | **NO — body silently truncated** |
| `def f_annot_subscript() -> "tuple[int, str] \| None":` | **IndentationError** | **IndentationError** | **NO — body silently truncated** |
| `def f_annot_none_and_comment() -> None:  # noqa: N802` | **IndentationError** | **IndentationError** | yes, re-indented 2 |
| multi-line signature | compiles | compiles | yes |
| docstring first | compiles | compiles | yes |
| `@decorator` above the `def` | compiles **but wrong** | same | header kept → no module-level `app` |

Generated module for the trailing-comment shape (verbatim from my run):

```
(blank)
# noqa: N802
  import reflex as rx
(blank)
  def index():
      return rx.text("hi")
(blank)
  app = rx.App()
  app.add_page(index, route="/")
```

Generated module for `-> "None":` (note `import reflex as rx` and `def index():` are *gone*):

```
(blank)
(blank)
    return rx.text("hi")
(blank)
app = rx.App()
app.add_page(index, route="/")
```

### End-to-end, what the user sees (`verification/logs/v_e2e_errors_0911a1.json`, `v_e2e_silent_0911a1.json`)

Three distinct user-visible failures, all raised from `AppHarness.__enter__` →
`testing.py:462 start` → `testing.py:317 _initialize_app` →
`prerequisites.py:303 get_and_validate_app` → `prerequisites.py:263 get_app` → `__import__`:

1. trailing comment → `IndentationError: unexpected indent (trailingcomment.py, line 3)`
2. `-> "None"` with a nested `def index():` → `IndentationError: unexpected indent (strannot.py, line 3)`
3. **NEW, not in the original report — the fully silent shape.** `-> "None"` (or a decorator)
   on a body containing no `):` sequence at all: the regex matches *nothing*, the generated
   module is the function definition itself, the function is never called, and the user gets
   `AttributeError: module 'cleansilent.cleansilent' has no attribute 'app'`
   (`verification/logs/v_e2e_silent_0911a1.json`). This message gives no hint whatsoever that
   the `def` line was the problem.

In all three the traceback names a generated file under a temp dir the user never wrote and
never mentions `app_source`.

### Mechanism (release source, confirmed on `origin/r/pre-2026.09.10-34457666442`)

`reflex/testing.py:245-260`, the substitution at **`reflex/testing.py:257-259`**:

```python
source = re.sub(r"^\s*def\s+\w+\s*\(.*?\)(\s+->\s+\w+)?:", "", source, flags=re.DOTALL)
return textwrap.dedent(source)
```

Three independent faults in one line:
- the pattern consumes only up to the `:`, so anything after it on the header line (a comment)
  survives as the new first line at column 0 → `textwrap.dedent` computes the common prefix
  over `("", "  import reflex as rx", ...)` wrongly and re-indents the body by 2;
- the annotation group is `\s+->\s+\w+`, which rejects a quoted or subscripted annotation, and
  because of `re.DOTALL` the `.*?` then backtracks *across newlines* to the next `):` anywhere
  in the body, silently deleting everything in between;
- `^` without `re.MULTILINE` anchors at string start, so a decorated factory never matches at all.

### Baseline — pre-existing, NOT a regression

`verification/logs/v_source_matrix_0910post2.json` is behaviourally identical to the 0.9.11a1
run (same statuses, same truncation), and 0.9.10.post2 ships the byte-identical regex at
`reflex/testing.py:236-238`. `git log -L` on the release branch shows the lines untouched by
anything in this train. **regression = false, confirmed by my own baseline run.**

What *is* new in 0.9.11a1 is reachability, and I verified it: the 0.9.10.post2 wheel METADATA
declares only `Provides-Extra: db, pydantic`, the 0.9.11a1 wheel adds `Provides-Extra: testing`
(`pyproject.toml:69-73` → psutil/selenium/uvicorn). So 0.9.11a1 is the first release where
`pip install 'reflex[testing]'` is a supported way in — though a 0.9.10 user who installed
uvicorn+selenium+psutil by hand could already use `AppHarness`, so "newly reachable" is about
support status, not a hard gate.

### Refutations I tried, and why they fail

- **Environment quirk / cwd shadowing / proxy / ports** — ruled out: pure string manipulation;
  every script asserts the venv's `reflex`; no network and no socket is touched on this path.
- **API misuse / documented behaviour** — no. `AppHarness.create`'s signature types `app_source`
  as `Callable[[], None] | ModuleType | str | functools.partial | None` and its docstring says
  only "the source code from this function or module is used as the main module". Nothing
  documents a constraint on the header line. The `Callable[[], None]` hint positively invites
  `def MyApp() -> None:` — which happens to work — while an adjacent comment silently does not.
- **Contrived shape** — partly. `-> "None"` / `-> tuple[...]` on an app factory is genuinely
  exotic. The trailing comment is not: reflex's own `pyproject.toml` selects ruff `ALL`
  (pep8-naming included) and has to suppress it wholesale for its own PascalCase factories via
  `[tool.ruff.lint.per-file-ignores] "tests/*.py" = [..., "N"]` (`pyproject.toml:252-262`).
  A downstream project that instead reaches for the inline `# noqa: N802` — the obvious move if
  you don't know about the per-file ignore — lands exactly on the broken shape. `# type: ignore`
  and `# pragma: no cover` do the same.
- **Flaky** — no, deterministic; ran each shape repeatedly, identical output.
- **Reflex's own CI would catch it** — it cannot: of ~370 app factories under `tests/integration/`,
  zero carry a trailing comment or a return annotation on the `def` line. The bug is invisible
  in-repo and only bites outside users.

### Why I downgrade medium → low

- Not a regression; the code is years-stable and identical in the previous stable.
- Every observed outcome is a hard failure at harness startup — it never yields a running app
  that silently drops part of the body, so no test can silently pass against a wrong app.
- The most natural annotated form, `def MyApp() -> None:`, works; only a trailing comment or an
  exotic annotation breaks.
- Workarounds are trivial and several (move the `noqa`, module-level `# ruff: noqa`, pass a
  module or a raw `str`, or configure the per-file ignore the way reflex itself does).

It is still worth fixing — the cost is a few lines (drop `re.DOTALL`, anchor with `re.MULTILINE`,
or just take the source from `ast`/`inspect.getsourcelines` and strip the header by line and
column instead of by regex) and the payoff is that the first-run experience of a newly advertised
extra stops producing an `IndentationError` in a file the user never wrote. Not a release blocker.

### Evidence (mine)

- `verification/appharness_source/v_source_matrix.py` — 10-shape compile matrix (runs on either version)
- `verification/appharness_source/v_e2e_errors.py` — three real `AppHarness.__enter__()` calls
- `verification/appharness_source/v_e2e_silent.py`, `v_silent_clean.py` — the silent `no attribute 'app'` shape
- `verification/logs/v_source_matrix_0911a1.json`, `verification/logs/v_source_matrix_0910post2.json`
- `verification/logs/v_e2e_errors_0911a1.json`, `verification/logs/v_e2e_silent_0911a1.json`

No processes were left running (every failure precedes `_start_backend`); temp app dirs under
`/tmp/v_ah_*` were removed.
