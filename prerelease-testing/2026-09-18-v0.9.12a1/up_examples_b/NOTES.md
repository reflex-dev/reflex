# Cluster `up_examples_b` — upgrade regression 0.9.11.post1 -> 0.9.12a1

reflex-examples apps that depend on `reflex[db]`, `reflex-local-auth`,
`reflex-global-hotkey`, `fastapi` (mounted API) and `pandas`.

Date: 2026-09-19. All installs from PyPI only; nothing was ever installed from the
`/home/user/reflex` checkout, and no python was run with the checkout as cwd.

## Apps covered

| app | third-party surface | baseline | upgraded | cold `.web` | prod |
|---|---|---|---|---|---|
| `form-designer` | `reflex[db]`, `reflex-local-auth` 0.5.0, alembic | PASS | PASS | PASS | PASS |
| `twitter` | `reflex[db]` | PASS | PASS | not run | not run |
| `basic_crud` | `reflex[db]`, `fastapi` via `api_transformer` | PASS | PASS | not run | PASS |
| `reflexle` | `reflex-global-hotkey` 1.2.3 | PASS | PASS | not run | not run |
| `data_visualisation` | `reflex[db]`, `pandas` 3.0.6, openpyxl | PASS | PASS | not run | not run |
| `uncached_prev` (synthetic, mine) | none | PASS | PASS | PASS | PASS |

No regression was found in any of the five example apps. Everything that worked on
0.9.11.post1 still worked after the in-place upgrade, with the same DB rows, the same
rendered table contents, and no new browser console errors, page errors or 4xx/5xx
responses attributable to the upgrade.

## Environments

Baseline venv, then upgraded in place (this is the venv the numbers below come from):

```
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
cd $SB
uv venv $SB/envs/upb --python 3.11
# baseline (no --prerelease, as a user's resolve would be)
uv pip install --python $SB/envs/upb/bin/python \
    'reflex[db]==0.9.11.post1' 'reflex-local-auth>=0.5.0' 'reflex-global-hotkey>=1.2.2' pandas fastapi openpyxl
# ... run baselines ...
# upgrade in place, naming every component alpha
uv pip install --python $SB/envs/upb/bin/python --upgrade --prerelease=allow \
    'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
    'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
    'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
    'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
    'reflex-components-sonner==0.9.4a1'
```

Resolved after upgrade (`uv pip freeze --python $SB/envs/upb/bin/python | grep -iE '^reflex|^pandas|^fastapi|^sqlmodel'`),
also in `logs/freeze_upgraded.txt`:

```
fastapi==0.141.1
pandas==3.0.6
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
reflex-global-hotkey==1.2.3
reflex-hosting-cli==0.1.72
reflex-local-auth==0.5.0
sqlmodel==0.0.42
```

Baseline freeze is `logs/freeze_partial.txt` (that file is actually the *mixed* state, see below);
the pure baseline was reflex 0.9.11.post1 / reflex-base 0.9.11.post1 with the stable component
packages (code 0.9.5, core 0.9.9, dataeditor 0.9.2, gridjs 0.9.1, markdown 0.9.3, plotly 0.9.6,
radix 0.9.9, recharts 0.9.3, sonner 0.9.3).

## How to rerun

Ports used: frontend 3500-3506, backend 8500-8505 (prod uses one port for both).

```
A=$SB/apps/up_examples_b          # or this directory after copying it back out
# per-app DB bootstrap (only needed once per app dir)
cd $A/form-designer      && $SB/envs/upb/bin/reflex db migrate          # alembic already checked in
cd $A/basic_crud         && $SB/envs/upb/bin/reflex db init && ... db makemigrations && ... db migrate
cd $A/data_visualisation && (same three)     # also needs openpyxl for the .xlsx loader
cd $A/twitter            && (same three)

# start a server (waits for HTTP 200, prints the PID)
bash scripts/runapp.sh $A/form-designer $SB/envs/upb 3500 8500 $A/logs/fd.log
# prod: pass the SAME port twice plus --env prod
bash scripts/runapp.sh $A/form-designer $SB/envs/upb 3500 3500 $A/logs/fd_prod.log --env prod

# drive it (console / pageerror / requestfailed / >=400 capture + screenshots + text dumps)
cd $A && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python scripts/drive.py http://localhost:3500/ scripts/fd_full.json $A/shots/fd
```

Action files in `scripts/`: `fd_actions*.json`, `fd_full.json`, `fd_entry.json`, `fd_up.json`,
`fd_cold.json`, `fd_prod.json`, `bc_actions.json`, `bc_prod.json`, `rx_actions.json`,
`dv_actions.json`, `dv_pandas.json`, `tw_actions.json`, `tw_up.json`, `rd.json`.

`scripts/ws_probe.py <url> <outfile>` loads a page, clicks `#bump` twice and prints the raw
websocket delta frames — that is what the `@rx.var(cache=False)` check below uses.

## Per-app detail

### form-designer (`reflex[db]` + reflex-local-auth)
Baseline: registered `alice`, logged in, created form "Survey A" with two fields
(`fullname`, `age`), sqlite `reflex.db` + the checked-in alembic revision applied cleanly.
After the in-place upgrade with `.web/`, `reflex.lock/` and `reflex.db` all preserved:
login still works with the pre-upgrade bcrypt row, the existing form and its two fields load,
a third field (`city`) was added and persisted, `/responses/2` loads. Cold run after
`rm -rf .web` reproduced the same screen. Prod mode (`--env prod`, one port) served the app and
the same authenticated flow.

`.web/package.json` diff across the upgrade (`logs/pkg/form-designer.base.json` vs. post-upgrade):
```
@react-router/node      8.3.1 -> 8.4.0
@react-router/dev       8.3.1 -> 8.4.0
@react-router/fs-routes 8.3.1 -> 8.4.0
react-router            8.3.1 -> 8.4.0
+ mergician             v2.0.2   (new; framework-owned, see reflex_base/constants/installer.py)
```
The `v`-prefixed `"mergician": "v2.0.2"` is deliberate — the framework pins it that way so that
unversioned requests from `reflex-components-plotly` collapse onto the same copy.

Pre-existing app bug, NOT a regression: `/form/<id>` (the end-user form entry page) renders the
React error overlay ``Error: `FormMessage` must be used within `FormField` or specify the `name`
prop`` on **both** 0.9.11.post1 and 0.9.12a1. It comes from `form_designer/pages/form_entry.py:87`
passing `rx.form.message(...)` as a child of `field_view()`. Evidence:
`shots/fd_base/entry.txt` (0.9.11.post1) and `shots/fd_up/report.json` console entry (0.9.12a1).
Because of it the "fill out the form / see the response" half of the app could not be exercised
on either version.

### twitter (`reflex[db]`)
Baseline: signed up `bob`, posted "hello from prerelease QA", user search rendered.
After upgrade, with the same sqlite DB: logged in as `bob`, the pre-upgrade tweet is still in the
feed, posted a second tweet, `/followers` loads. No console errors beyond the browser's own
"Password field is not contained in a form" verbose hint (present on both versions).

### basic_crud (`reflex[db]` + FastAPI `api_transformer`)
The app ships no alembic dir; `reflex db init && db makemigrations && db migrate` was needed on
both versions (a 500 `no such table: product` until then — same on baseline, not a finding).
Baseline: `POST/GET/PUT /products` through the mounted FastAPI router all 200, the in-page
"Send" query returns 200 and the JSON body, and the `@rx.event(background=True)` poller picks up
out-of-band DB changes and re-renders. After the upgrade, identical: the mounted API still
answers on the backend port, `DELETE /products/1` removed the row and the running page updated
itself through the background task. Prod mode: the mounted API answers on the single prod port
(`GET /products` 200, `POST /products` 200) and the page shows both rows.

### reflexle (`reflex-global-hotkey`)
`reflex-global-hotkey` 1.2.3 imports `reflex.Fragment`, `reflex.Var`,
`reflex.event.{EventHandler,EventType,key_event,KeyInputInfo}` and `reflex.utils.imports`.
All of those still resolve on 0.9.12a1 (`scripts/probe_thirdparty.py`, which also probes the
`reflex_local_auth` surface: `reflex.event.EventSpec` plus the `rx.*` names it uses).
End-to-end: typed `CRANE` on the physical keyboard, pressed Enter, typed `SLATE`, pressed Enter —
both guesses land in the grid, identically on both versions (`shots/rx_base/*`, `shots/rx_up/*`).

### data_visualisation (`reflex[db]` + pandas)
The upstream app has no chart, so the pandas surface it exercises is the `pd.read_excel` ->
sqlite loader. That still works: 36 COVID rows load from `data_sources/covid_data.xlsx` through
pandas 3.0.6 and the table renders byte-identical before and after the upgrade
(`diff shots/dv_base/home.txt shots/dv_up/home.txt` is empty).

To actually exercise the pandas serializer and the sqlmodel relationship path from #7049 I added
a page, `data_visualisation/pandas_page.py`, mounted at `/pandas`. It renders the same
`pd.DataFrame` five ways at once — a literal, a `@rx.var`-computed frame driven by a State var,
a frame passed as a prop into an `@rx.memo` component, a frame inside an `rx.ComponentState`,
and `rx.foreach` over `list[Covid]` rows read with `rx.session()` — plus an uncached
`@rx.var(cache=False)`. Every one of them renders identically on 0.9.11.post1 and 0.9.12a1
(`shots/dv_base/pandas_after.txt` vs `shots/dv_up/pandas_after.txt`). This page is reusable for
future trains.

## Cross-cutting checks

### Upgrade resolution (the thing that bit the last campaign)
* `uv pip install --upgrade --prerelease=allow 'reflex==0.9.12a1'` (no component packages named)
  now **does** pull every component alpha — verified with `--dry-run`. That is an improvement
  over the 0.9.11 campaign.
* `uv pip install --upgrade 'reflex==0.9.12a1'` **without** `--prerelease=allow` upgrades only
  `reflex` and `reflex-base` to 0.9.12a1 and leaves every `reflex-components-*` package at its
  stable release (code 0.9.5, core 0.9.9, radix 0.9.9, ...). I ran `basic_crud` in that mixed
  state: it compiled, served and worked with no error in the log or the console
  (`logs/bc_mixed.tail.log`, `logs/freeze_partial.txt`). So the mixed state is not fatal, but it
  is what a user typing the obvious command gets, and it silently tests new core against old
  components.

### #7068 router base vars / preserved `.web/`
Every app was upgraded with its 0.9.11.post1-built `.web/` and `reflex.lock/` left in place. In
all five the first 0.9.12a1 run recompiled the frontend and the page hydrated normally — no
`client_error`, no state/schema mismatch in the server log, nothing in the browser console.
The three documented declaration errors behave exactly as the changelog says
(`scripts/probe_breaking.py`, run against both venvs):

| declaration | 0.9.11.post1 | 0.9.12a1 |
|---|---|---|
| substate var named `rx_router_page` / `rx_router_url` / `rx_router_session` | accepted | `BaseVarShadowsInheritedVarError` |
| substate var shadowing a parent state's var | silently accepted | `BaseVarShadowsInheritedVarError` |
| state var named `dict` / `set` / `reset` / `router` / `vars` | accepted | `StateValueError: ... is reserved by BaseState` |
| event handler named `reset` | already an error | same error |

`dict`, `set` and `reset` are plausible real-world var names, so #7136 has a wider blast radius
than it looks; it is documented as breaking, which is correct, but worth calling out in release
notes prominently.

### #6946 uncached vars only in the delta when they change — VERIFIED
Same synthetic app (`uncached_prev/`) run under each venv, websocket frames captured after two
`#bump` clicks (`logs/ws_prev.txt` vs `logs/ws_uc_new.txt`):

0.9.11.post1 — the never-changing `steady` is re-sent every time:
```
{"delta":{"...ucapp___s":{"changing_rx_state_":2,"tick_rx_state_":1,"steady_rx_state_":"constant"}}}
{"delta":{"...ucapp___s":{"changing_rx_state_":4,"tick_rx_state_":2,"steady_rx_state_":"constant"}}}
```
0.9.12a1 — `steady` is gone, `changing` still there:
```
{"delta":{"...ucapp___s":{"changing_rx_state_":2,"tick_rx_state_":1}}}
{"delta":{"...ucapp___s":{"changing_rx_state_":4,"tick_rx_state_":2}}}
```

## Issues found

### 1. The `deps=["router"]` deprecation never fires (low)
`CHANGELOG` for 0.9.12a1 says: *"Declaring a computed var dependency on the `router` var
(`deps=["router"]`) is deprecated"*. The warning is unreachable.

`reflex/state.py:1199-1218` only calls `console.deprecate(...)` when
`dvar_set.isdisjoint(constants.ROUTER_VARS)`, with the comment *"The Var form already carries
them, so only the legacy string form arrives here without them"*. Empirically the **string**
form carries them too:

```
$ cd $SB/apps/up_examples_b
$ EXPECT_VENV=/envs/upb/ $SB/envs/upb/bin/python scripts/probe_routerdep2.py
raw _deps: {'reflex___state____state.__main_____rd': {'rx_router_headers', 'rx_router_page',
            'rx_router_session', 'rx_router_url', 'router', 'rx_router_route_id'}}
```
`router` is present *together with* all five `rx_router_*` names, so `isdisjoint` is False and
the branch is skipped. Confirmed end-to-end too: a page whose state has
`@rx.var(deps=["router"], cache=True)` runs correctly (the var returns `/routerdep`) and the
server log for the whole run contains no deprecation line other than the unrelated
"Implicit Radix Themes enablement" one (`logs/uc_routerdep.tail.log`).

Impact: downstream apps using the legacy string form get no notice before the 1.0 removal.
Not a regression (0.9.11.post1 has no such deprecation). Behaviour is otherwise correct.

### 2. Dynamic routes return HTTP 404 in prod mode (low, pre-existing, NOT a regression)
`reflex run --env prod` answers a direct (non-client-side) request for any dynamic route with
status 404 while still serving the shell that then hydrates to the right page. On form-designer
0.9.12a1:

```
/                     200      /edit/form/           200
/edit/form/2          404      /edit/form/2/field/1  404
/form/2               404      /responses/2          404
```
The same happens on 0.9.11.post1 — verified with a minimal app that has `/item/[iid]` alongside
`/item/`: `/item/42` is 404 on **both** versions (`logs/uc_prev_prod.tail.log`,
`logs/uc_new_prod.tail.log`). Matters for crawlers, uptime checks and anything that keys on the
status code, but it is pre-existing, so it is context, not a release blocker.

## Benign noise seen (not findings)
* `net::ERR_CERT_AUTHORITY_INVALID` for the Google Fonts stylesheet — the agent proxy's CA, not
  the framework. Appears identically on both versions.
* Chromium verbose DOM hints: "Input elements should have autocomplete attributes",
  "Password field is not contained in a form".
* `Warning: reflex_base.plugins.sitemap.SitemapPlugin plugin is enabled by default ...` printed
  by `reflex db *` subcommands for apps that do not list it — both versions.
* `Received true for a non-boolean attribute collapsible` on the form-designer editor page —
  both versions.
* `reflex db init`/`makemigrations` were needed for `basic_crud`, `twitter` and
  `data_visualisation` because those examples ship no alembic directory. Same on both versions.

## Not covered / left for a follow-up
* Cold `rm -rf .web` reruns for `twitter`, `basic_crud`, `reflexle`, `data_visualisation`
  (only `form-designer` and the synthetic app got one).
* Prod mode for `twitter`, `reflexle`, `data_visualisation`.
* The `/form/<id>` end-user entry + response-collection half of form-designer, blocked by the
  pre-existing `FormMessage` app bug described above.
* Redis-backed state manager across the upgrade (no redis instance was needed by these apps).

## VERIFICATION

Independent adversarial verification (2026-09-19), working from this NOTES.md + the app
sources/scripts in this directory only. Evidence under `verification/`. Ports 4000/4001.
Venvs used read-only: `$SB/envs/shared` (0.9.12a1 train) and `$SB/envs/prev`
(0.9.11.post1); resolved versions in `verification/freeze_verify.txt`:
`reflex==0.9.12a1 / reflex-base==0.9.12a1 / reflex-components-core==0.9.10a1 /
reflex-components-radix==0.9.10a1 ...` vs `reflex==0.9.11.post1 / reflex-components-core==0.9.9`.

Working copy: `$SB/apps/verify_up_examples_b/{uc_new,uc_prev}` — a copy of `uncached_prev/`
with one extra page appended (`verification/ucapp_verify.py`):

```python
class RouterDepNoAuto(rx.State):
    @rx.var(deps=["router"], auto_deps=False, cache=True)
    def legacy_router_dep_noauto(self) -> str:
        return self.router.url.path

@rx.page(route="/routerdep2")
def routerdep2_page():
    return rx.text(RouterDepNoAuto.legacy_router_dep_noauto, id="rd2")
```

### Issue 1 — `deps=["router"]` deprecation "unreachable / never fires" — **REFUTED**

The deprecation is alive and fires. The written repro reproduces *its own output* exactly, but
that output is an artifact of the repro, not of the string form: it declares
`@rx.var(deps=["router"], cache=True)` and leaves `auto_deps` at its default `True`, with a body
that reads `self.router.url.path`. On 0.9.12a1 the auto dep scanner resolves `self.router` to all
five per-field `rx_router_*` vars and merges them into the same dep set the guard inspects, so
`dvar_set.isdisjoint(constants.ROUTER_VARS)` is False — because of the *auto* deps, not because
the string form carries them. The guard's comment is therefore imprecise, but the branch is not
dead.

Commands (from `$SB/apps/verify_up_examples_b`, neutral cwd; full output in
`verification/rdvar_variants.txt`):

```
for v in A B C D E; do EXPECT_VENV=/envs/shared/ $SB/envs/shared/bin/python scripts/rdvar.py $v; done
for v in A B C;     do EXPECT_VENV=/envs/prev/   $SB/envs/prev/bin/python   scripts/rdvar.py $v; done
```

| variant | declaration | body reads router | 0.9.12a1 resolved deps | deprecation |
|---|---|---|---|---|
| A (the written repro) | `deps=["router"], cache=True` | yes | `router` + all 5 `rx_router_*` | **no** |
| B | `deps=["router"], auto_deps=False` | no | `{router}` | **YES** |
| C | `deps=["router"]` (auto on) | no | `{router}` | **YES** |
| D | `deps=[State.router], auto_deps=False` | no | `router` + all 5 | no (correct) |
| E | `deps=["router"], auto_deps=False` | yes | `{router}` | **YES** |

Exact warning text emitted (B/C/E):

```
ComputedVar deps=["router"] on RD.p has been deprecated in version 0.9.12. the router var was
split; depend on the router Var instead (e.g. deps=[State.router.url] for one field, or
deps=[State.router] for all of them). It will be completely removed in 1.0.
```

End-to-end, not just in a script: `reflex run --env prod --frontend-port 4000 --backend-port 4000`
on `uc_new` prints the same DeprecationWarning twice during compile for
`RouterDepNoAuto.legacy_router_dep_noauto` (`verification/uc_new_prod.verify.log`), and
`/routerdep2` renders `/routerdep2/` correctly in Chromium. The 0.9.11.post1 run of the same app
prints no such line (`verification/uc_prev_prod.verify.log`, only the unrelated Radix one), and
the release source has a unit test pinning this behaviour:
`tests/units/test_state.py:4184` `test_router_var_dep_does_not_warn_for_the_var_form` asserts
exactly one deprecation for `deps=["router"], auto_deps=False` and none for `deps=[State.router]`.

Residual gap (real, but not worth a fix): variant A — the string form plus default auto deps plus
a body that touches the router — stays silent. That is also the case where the declaration is
redundant and nothing breaks at removal: auto tracking alone already registers all five
`rx_router_*` names, and an unrecognised string dep is silently accepted rather than raising
(`verification/bogusdep.py`: `deps=["no_such_var"]` is accepted on both 0.9.12a1 and
0.9.11.post1). So the users who would actually break at 1.0 (`auto_deps=False`, or a body that
never mentions the router) are precisely the ones who do get the warning today.

Side observation while probing (not a finding, not release-relevant): `ComputedVar._deps` does
`d.update(self._static_deps)` and hands `d` to `DependencyTracker`, which mutates the *same* set
objects (`packages/reflex-base/src/reflex_base/vars/base.py:2878` +
`packages/reflex-base/src/reflex_base/vars/dep_tracking.py:127,215,392`), so after the first dep
scan `_static_deps` contains auto-discovered names the user never declared — visible in variant A
above (`static_deps: {None: {'router', 'rx_router_url', ...}}` for a declared `deps=["router"]`).
Same union either way, so no behavioural impact observed.

### Issue 2 — prod returns 404 for dynamic routes — **REPRODUCED EXACTLY, pre-existing, not a release defect**

Reproduced with the minimal app rather than form-designer (same routes, no DB/auth needed):

```
bash scripts/runapp.sh $W/uc_new  $SB/envs/shared 4000 4000 logs/uc_new_prod.log  --env prod
for u in / /item/ /item/42 /item/42/ /routerdep /routerdep2 /nope /_nonexistent_deep/x; do
  curl -s --noproxy '*' -o /dev/null -w "$u %{http_code} %{size_download}\n" "http://localhost:4000$u"; done
```

0.9.12a1 (`verification/curl_new_prod.txt`) and 0.9.11.post1 on port 4001
(`verification/curl_prev_prod.txt`) are identical in status:

```
/ 200 | /item/ 200 | /item/42 404 | /item/42/ 404 | /routerdep 307 | /nope 404
```

Chromium (`verification/pwcheck.py`) on both versions: `/item/42` is served with HTTP **404** and
still renders `item page / /item/42`; `/nope` is 404 and renders `404: Page not found`
(`verification/new_prod_item_42.png`, `verification/prev_prod_item_42.png` — byte-identical
screenshots). So the explorer's description is accurate, including the browser behaviour.

Root cause (release source): prod serves the built client dir through Starlette's
`StaticFiles(..., html=True)` — `reflex/utils/exec.py:383` (`PrecompressedStaticFiles`,
directory `.web/build/client`, `reflex_base/constants/base.py:44`). In html mode Starlette answers
a miss with `404.html` at status 404. The build emits `404.html` and `__spa-fallback.html`
**byte-identical** (5374 B each here), i.e. the SPA shell is served either way; only the status
line differs, and the router-aware SPA fallback file is never used. Nothing here is 0.9.12-specific
(no `frontend_path` set; it reproduces unchanged on 0.9.11.post1), so this is a long-standing
static-serving wart, not a regression and not a release blocker. A fix would mean matching the
request against the compiled route table (dynamic segments included) and serving the fallback with
200 for a known route.

Note on the extra 307s: `/routerdep` and `/routerdep2` answer 307 to the trailing-slash form on
**both** versions (directory-style static files) — expected, mentioned only because the written
repro's route list did not include them.

### Cleanup
Both prod servers (pids 30873, 31288) killed; `python3 $SB/bin/ports.py 4000 4001` reports nothing
listening. No process left behind, nothing installed into the shared venvs, no git commands run.
