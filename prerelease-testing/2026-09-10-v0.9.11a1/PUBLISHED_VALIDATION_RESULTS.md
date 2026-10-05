# Results — independent validation of the published remediation releases

Answers [PUBLISHED_VALIDATION.md](./PUBLISHED_VALIDATION.md). Review run **2026-09-11 17:20–18:20 UTC**.
Every reproduction below ran against packages installed from PyPI into throwaway `uv --no-config`
environments outside every Reflex checkout; no editable/local/VCS overrides, no `PYTHONPATH`, no
checkout code imported. Scripts, app sources, logs and JSON evidence are under
[`published_review_a2/`](./published_review_a2).

Verdict vocabulary is the handoff's: **verified fixed**, **verified documented/accepted behavior**,
**still reproduces**, **partially fixed**, **blocked**, **inconclusive**.

---

## Environment manifest

| | |
| --- | --- |
| host | Linux 6.18.44-fc-v24 x86_64, glibc 2.39, 4 CPU / 16 GB |
| Python | 3.11.15 (both environments) |
| Node | v22.22.2 · **Bun actually used by Reflex** 1.4.0 (`/root/.local/share/reflex/bun/bin/bun`) |
| browser | Chromium 141.0.7390.37 (`/opt/pw-browsers/chromium`), Playwright driver env |
| Redis | server v7.0.15 on port 8235 · `granian` 2.8.2 · `starlette` 1.6.0 · `redis` (py) 7.4.1 |
| Pyright | 1.1.411 / 1.1.412 / 1.1.414 in isolated checker envs (1.1.414 is the current PyPI release) |
| starlette-admin | 1.0.1 / 1.0.0 / 0.17.1 in separate environments |
| provenance | [`out/provenance-a1.json`](./published_review_a2/out/provenance-a1.json), [`out/provenance-a2.json`](./published_review_a2/out/provenance-a2.json) — `sys.path`, every `reflex*` distribution, each imported module's `__file__`, `all_modules_under_env: true`, `direct_url.json`: none |
| resolver output | [`out/installed-a1.txt`](./published_review_a2/out/installed-a1.txt), [`out/installed-a2.txt`](./published_review_a2/out/installed-a2.txt); `uv pip check`: "All installed packages are compatible" in both |

**Baseline (a1)**: reflex 0.9.11a1, reflex-base 0.9.11a1, reflex-components-moment 0.9.4a1,
reflex-components-radix 0.9.9a1.
**Target (a2)**: reflex 0.9.11a2, reflex-base 0.9.11a2, reflex-components-moment 0.9.4a2,
reflex-components-radix 0.9.9a2.
Both pull the unchanged siblings identically (code 0.9.5a1, core 0.9.9, plotly 0.9.6a1,
recharts 0.9.3a1, sonner 0.9.3a1, lucide 1.0.4, hosting-cli 0.1.72a1), so the four changed
packages are the only difference.

**Artifact provenance.** All ten wheel/sdist SHA-256 digests fetched from PyPI during this review
match `REVIEW_STATUS.json` exactly (10/10, no mismatch, none missing) — nothing was re-uploaded or
yanked between the handoff and this run. reflex-otel 0.1.0a2 additionally verified published
(wheel + sdist). The `.pyi` packaging audit over the five a2 packages passes: 69 stubs, identical
in wheel and sdist, no foreign stubs.

**Environment limitation, stated once.** `https://reflex.dev` is unreachable from this container
(egress proxy returns no response, `http=000`), so **every hosted-documentation check below is
`blocked`**. Published *package* metadata and GitHub release bodies were reachable and are used
instead, labelled as such.

---

## Results

| Finding / case | Versions / mode | Baseline observation | Target observation | Verdict | Evidence |
| --- | --- | --- | --- | --- | --- |
| **002** static date, `interval=0`, periodic, remount, nav, reload — **dev** | moment 0.9.4a1 → 0.9.4a2, `reflex run` | `static_count` 2 → 4 → 6, `zero_count` 2 → 4 → 6, `tick_count` 4 → 8 → 12 across load → reload → client nav | **identical**: 2 → 4 → 6, 2 → 4 → 6, 4 → 8 → 12 | verified documented/accepted behavior | `out/moment_onchange_a{1,2}_dev.json` |
| **002** same — **prod** | `reflex run --env prod` | `static_count` 1 → 2 → 3, `zero_count` 1 → 2 → 3, `tick_count` 3 → 6 → 9 | **identical**: 1 → 2 → 3, 1 → 2 → 3, 3 → 6 → 9 | verified documented/accepted behavior | `out/moment_onchange_a{1,2}_prod.json` |
| **002** published documentation | GitHub release `reflex-components-moment-v0.9.4a2` | — | Release body carries the Breaking Change verbatim: mount **and remount**, "including for static dates and `interval=0`", and "React Strict Mode invoking it twice **in development**". The dev-vs-prod split is exactly what the two rows above measure. | verified documented/accepted behavior | release body quoted below |
| **002** hosted docs page | `https://reflex.dev/docs/library/data-display/moment/` | — | unreachable from this container | **blocked** | proxy returns `http=000`; moment's PyPI description is 54 chars and carries no prose, so release notes are the only reachable published surface |
| **003** worker identity | reflex 0.9.11a1 → a2, prod + Redis, 9 forked Granian workers | 9 distinct PIDs, **1 shared `instance_id`** (`RedisTokenManager`) | 9 distinct PIDs, **9 distinct `instance_id`s** | verified fixed | `out/whoami_a1.txt`, `out/whoami_a2.txt` |
| **003** six backend-initiated events, 9 workers | same | **1/6** iterations delivered a delta; UI `pings=3` of 6 before any click; it only reached 6 **after a click** | **6/6** delivered live; UI `pings=6` before any click | verified fixed | `out/xw_a1_9w/results.json`, `out/xw_a2_9w/results.json` |
| **003** one-worker control | a2, `GRANIAN_WORKERS=1` | — | 1 PID / 1 `instance_id`; **6/6** delivered — multi-worker now matches single-worker | verified fixed | `out/whoami_a2_1w.txt`, `out/xw_a2_1w/results.json` |
| **003** rehydrate / eviction path | a2 | — | not established: the probe assumes a freshly started server (its `runs` counters are per-process and were already non-zero from earlier runs), and under 9 workers those counters are answered by a different worker than the one that ran the handler | **inconclusive** | `logs/rehydrate_a2_1w.tail.log` — 28 PASS / 9 FAIL, every FAIL on a per-process counter, none on a UI value |
| **005** class access, current checker | reflex-base 0.9.11a1 → a2, pyright **1.1.414** | `Base.full/doubled/positive/tags/maybe/greeting` and every `Child.*` → **`Any`** | `StringVar[str]`, `NumberVar[int]`, `BooleanVar`, `ArrayVar[list[str]]`, `StringVar[str] \| None`, `StringVar[str]`; inherited `Child.*` the same | verified fixed | `out/pyright-ext-a1-414.json`, `out/pyright-ext-a2-414.json` |
| **005** 1.1.412 and 1.1.411 control | same | 1.1.411 already correct on a1 | correct on 1.1.411 **and** 1.1.412 | verified fixed | `out/pyright-ext-a2-41{1,2}.json` |
| **005** instance access | same | `str` / `int` / `list[str]` | unchanged | verified fixed | same files; probe `scripts/hp_types_ext.py` |
| **014** invalid prefixes | reflex-base 0.9.11a1 → a2 | `/trail.`, `/trail `, `/a/b.`, `/a//b`, `//lead` all **accepted** | all five **rejected** with `ConfigError` naming the offending segment | verified fixed | full case table `out/frontend_path_cases.txt` |
| **014** valid controls | same | accepted | `/ok`, `/a/b`, `/ok/`, `/`, `""` still accepted; `/..`, `/a/../b` still rejected | verified fixed | same |
| **014** build/export of a valid prefixed app | a2, `frontend_path="/myapp"` | — | `reflex export --frontend-only --no-zip --no-ssr` rc=0 **and** the same with SSR enabled rc=0, emitting `build/client/myapp/{index,404}.html` | verified fixed | `logs/fp_a2_nossr.tail.log`, `logs/fp_a2_ssr.tail.log`, app `apps/fpapp/` |
| **022** handoff app, **dev** | reflex 0.9.11a1 → a2 | initial load renders **no icon at all**; `window.__reflex` has **no lucide keys**; the browser tries `https://cdn.jsdelivr.net/npm/lucide-react@1.26.0/+esm/dist/esm/icons/{tag,apple}.mjs` and those requests fail; Activate never renders the counter | Tag on initial load; Activate → Apple + count 0; +/+ → 2; − → 1; deactivate → Tag; reactivate → Apple; reload keeps 1; click → 2. `window.__reflex` holds exactly `lucide-react/dist/esm/icons/apple.mjs` and `…/tag.mjs`; **no** `lucide-react` root; **zero** failed requests and zero CDN fetches | verified fixed | `out/bundle_a1_dev.json`, `out/bundle_a2_dev.json` |
| **022** emitted `root.jsx` | same | no lucide reference | exactly the two subpath strings, nothing broader | verified fixed | grep transcript; `.web/app/root.jsx` |
| **022** **prod** | a2 `reflex run --env prod` | — | identical to dev, same two subpaths | verified fixed | `out/bundle_a2_prod.json` |
| **022** prebuilt frontend + **fresh non-compiling backend** | a2: `reflex export --frontend-only`, static `http.server` on 5503, separate `reflex run --backend-only` on 9902 | — | backend log contains **zero** "Creating Production Build"; initial-state Tag discovered, Activate renders Apple, increments, deactivate/reactivate, reload and post-reload increment all work | verified fixed | `out/bundle_a2_static_backend.json`, `logs/bundle_backend_only.tail.log` |
| **022** invalid `bundle_library()` inputs | same | class-not-instance / int / None / list → bare `AttributeError: 'int' object has no attribute 'library'` | all four → `TypeError: Pass a library name as a str or a prototype Component instance to bundle_library(), for example bundle_library(rx.icon('apple')).` | verified fixed | `out/bundle_api_a1.json`, `out/bundle_api_a2.json` |
| **022** duplicate explicit registration | same | registering `"d3-format"` three times leaves **three** entries | leaves **one** | verified fixed | same |
| **022** exact subpath string registration | same | accepted | accepted | verified fixed | same |
| **025** `/admin/`, model list, create | reflex[db] 0.9.11a1 → a2, starlette-admin **1.0.1** | **500** on `/admin`, `/admin/`, `/admin/widget/list`, `/admin/widget/create`, `/admin/login`; log shows `NoMatchFound: No route exists for name` ×4 | **200 / 200 / 200**; no `NoMatchFound` anywhere in any body | verified fixed | `out/admin_a1-sa101.json`, `out/admin_a2-sa101.json` |
| **025** starlette-admin 1.0.0 and 0.17.1 | a2 | — | both **200** on `/admin/`, model list and create | verified fixed | `out/admin_a2-sa100.json`, `out/admin_a2-sa017.json` |
| **025** referenced static assets | a2 + 1.0.1 | — | every `/admin/static/...` href on the rendered index fetched: all **200** (e.g. `vendor/fontawesome.min.css` 75 767 B, `vendor/tabler.min.css`, `select2-tabler.css`, `panel_widget.css`) | verified fixed | `out/admin_a2-sa101.json` (`assets`) |
| **025** login route with no login configured | a2 | 500 | **404** with starlette-admin's own page (11 874 B) — not a 500, and not demanded to be 200 | verified fixed | same |
| **025** API transformer wrapping the API | a2 + 1.0.1, `api_transformer=Starlette(...)` | — | `/admin/` and the model views still **200**, and the transformer's own `/extra` route returns `{"transformer":"ok"}` | verified fixed | `out/admin_a2-tx.json` |
| **025** event / request-context control | a2 | — | app state handler reading `self.router.page.path` present in the same app (`apps/adminapp`); backends answered `/ping` 200 throughout | verified fixed | `apps/adminapp/adminapp/adminapp.py` |
| **027** published recipe text | reflex-otel 0.1.0a2 | a1 recipe omitted the protocol variable | **PyPI description** (the page a user reads) carries `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` plus "Without the protocol setting, `otlp` defaults to gRPC and requires the separate gRPC exporter package"; the in-repo `docs/api-reference/observability.md` on the release branch matches | verified fixed | PyPI JSON `info.description`; quoted below |
| **027** executing that recipe against a real collector | a2 + `opentelemetry-exporter-otlp-proto-http` **only** (no gRPC exporter installed) | a1: configuration error swallowed, `ProxyTracerProvider`, nothing exported | local OTLP/HTTP receiver on 127.0.0.1:10291 received **5 × `POST /v1/traces`** and **3 × `POST /v1/metrics`**, `Content-Type: application/x-protobuf`, `User-Agent: OTel-OTLP-Exporter-Python/1.44.0`, after loading the app and clicking five times | verified fixed | `out/otlp_records_a2.json`, receiver `scripts/otlp_receiver.py`, app `apps/otelapp/` |
| **027** hosted observability guide | `https://reflex.dev/docs/api-reference/observability/` | — | unreachable | **blocked** | proxy `http=000` |
| **030** same event, parsed-JSON comparison | reflex 0.9.11a1 → a2 | key order `count, marker, doubled, label, flags, history`; sibling `seen, note_upper, note` | key order `doubled, count, label, flags, history, marker`; sibling `note, note_upper, seen` | verified documented/accepted behavior | `out/delta_multi_a1.json`, `out/delta_multi_a2.json` |
| **030** values unchanged | same | — | **normalised parsed JSON compares equal** (`NORMALISED PARSED JSON EQUAL: True`); only ordering differs | verified documented/accepted behavior | same; `out/delta_order_comparison.txt`, capture `scripts/capture_delta.py` |
| **030** published note | reflex 0.9.11a2 changelog | — | Breaking Changes entry says values are unchanged and tells readers to "compare parsed JSON objects or normalize key order instead" | verified documented/accepted behavior | release branch `CHANGELOG.md` |
| **033** French **before** the un-localed set — dev | moment 0.9.4a1 → a2 | un-localed render English on this order | English | verified fixed | `out/locale_a{1,2}_dev.json` step 1 |
| **033** French **after** the un-localed set — dev | same | **`jeudi 14 mars 2024`, `il y a 7 ans`, `dans 7 ans`, title `jeudi`, title attribute `jeudi 14 mars 2024`** | all English; explicit French one still French | verified fixed | same, step 2 |
| **033** same — **prod** | same, `--env prod` | leak reproduces identically | all English | verified fixed | `out/locale_a{1,2}_prod.json` |
| **033** route with only default-English moments, nav away/back, reload | same, dev + prod | English | English | verified fixed | steps 3, 5, 6 |
| **033** explicit `locale="en"` | same | **dev**: route module 500s, page blank, `TypeError: Failed to fetch dynamically imported module`; **prod**: the whole build fails — `Rolldown failed to resolve import "moment/locale/en"` | renders English, **zero** failed requests, no missing-module fetch; prod builds and serves | verified fixed | `logs/locale_a1_dev.tail.log`, `logs/locale_a1_prod.tail.log`, `out/locale_a2_{dev,prod}.json` step 4 |
| **033** reactive locale fr → en → "" → fr | same | — | the Var-driven moment follows the Var; **siblings stay English throughout**, and a later English-only route is still English | verified fixed | steps 7–11 |
| **033** duration-format control | same | `4 years, 2 months, 13 days` | identical | verified fixed | every step's `*-duration` |
| **033** `defineLocale` warnings (034 / #7099) | same | 0 observed in this app | 0 observed in this app | **not assessed here** — counted separately as the handoff requires; absence in this app is not evidence that #7099 is resolved | `defineLocale_warnings` in each locale JSON |

---

## 018 — separately labelled adjacent check

Procedure from the handoff: the minimized `ent_aggrid/verification/issue2_hydrate_delta/app` (a state
var holding a Python callable returning a Radix component, serialized by reflex-enterprise's
`LiteralLambdaVar`), published **reflex-enterprise 0.9.5**, fresh dev; click the counter to 3,
reload with the same session token, click once more.

| Stack | Observation | Verdict |
| --- | --- | --- |
| reflex 0.9.11a1 + rxe 0.9.5 | counter reaches 3; **reload shows 0** with `on_load-ran` and `hydrated`; the next click shows **4** | **still reproduces** — exactly the failure signature the handoff describes |
| **reflex 0.9.11a2 + rxe 0.9.5** | **the app never starts**: worker-1 exits during startup and the backend never binds, so the page cannot hydrate at all | **still reproduces, with the failure moved to compile time** |

The a2 crash is deterministic (reproduced twice, the second time after `rm -rf .web`):

```
File ".../reflex/compiler/utils.py", line …            return serializers.serialize(value)
File ".../reflex_base/utils/serializers.py", line …    serialized = serializer(value)
File ".../reflex_enterprise/vars.py", line …           return serialize_lambda_var(LiteralLambdaVar.create(func))
File ".../reflex_enterprise/vars.py", line 166         raise ValueError(
ValueError: Library @radix-ui/themes is not bundled. Use `from reflex.components.dynamic import
bundle_library; bundle_library('@radix-ui/themes') to enable it it.
[ERROR] Unexpected exit from worker-1
```

On a1 the **same** `ValueError` appears twice in the log but the worker survives and the backend
serves (the error is swallowed per-delta — the original 018 mechanism). On a2 it is raised while the
worker is loading the app and kills it. Frontend still serves (`5512` → 200); backend `9922` → 000.

Maintainer's read, which this review agrees with: **raising at compile time is the better failure
mode**, so this is a step in the right direction rather than something to revert — the silent packet
loss is gone and the problem is loud and immediate. What remains is that the app still cannot run,
and the error's advice cannot be followed from where it is raised (the value is a state field's
default, and the exception happens while the worker is importing the app module). Root cause and a
suggested direction are recorded on [#7096](https://github.com/reflex-dev/reflex/issues/7096):
the `serialize_initial_value` hook #7109 added in `reflex/compiler/utils.py::_compile_initial_state`
bundles only when `isinstance(value, Component)`, so a callable that reflex-enterprise turns into a
`LiteralLambdaVar` — whose component is reachable only through the Var's `_get_all_var_data()` —
is never seen.

The other half is reflex-enterprise's: `LiteralLambdaVar._validate_and_extend_return_expr`
(`reflex_enterprise/vars.py:121` in 0.9.5) already has that var data in hand and raises on the first
unbundled package rather than registering it, so a caller cannot bundle first. Either enterprise
registers what it finds / exposes a non-validating construction, or the mechanism goes away in
favour of function-style `rx.memo` for ag-grid-style callback props — which would also remove the
bespoke `__reflex['<pkg>']?.<tag>` runtime lookup. Note the ordering constraint either way: in
`compile_app` the non-compiling branches call `_compile_initial_state` *before*
`_reset_bundled_libraries_for_compile()` and plugin dependency registration
(`reflex/compiler/compiler.py:1234`/`:1254` vs `:1264-1271`), so registering at that point cannot
repair a frontend that was already built.

Evidence: `out/f018_a1_dev.json`, `out/f018_a2_dev.json`, `logs/minrx_a1_dev.tail.log`,
`logs/minrx_a2_clean.tail.log`, driver `scripts/drive_018.py`.

Not run, and therefore not claimed: the production-build / separately-started non-compiling backend
variant of this check — the a2 app cannot start at all, so that configuration has no meaning until
the startup crash is fixed. #7096 is **not** closed by this review, and no general
serializer-error isolation is claimed.

---

## Claimed fixes that fail, with the smallest reproduction

**One.** Nothing in the nine claimed fixes fails. The remaining failure is the adjacent 018 check:
still open, with its failure moved from a silently dropped delta to a compile-time raise that stops
the app from starting.

Smallest reproduction — three files, published packages only, no checkout:

```python
# minrx/minrx.py
import reflex as rx
import reflex_enterprise as rxe


def cell_renderer(params: rx.Var) -> rx.Component:
    return rx.text("cell")          # any component from a bundled library


class MinState(rx.State):
    col_defs: list[dict] = [{"field": "name", "cell_renderer": cell_renderer}]


def index() -> rx.Component:
    return rx.text("hi")


app = rxe.App()
app.add_page(index)
```

```sh
uv --no-config venv env && uv --no-config pip install --python env/bin/python --prerelease=allow \
  'reflex[db]==0.9.11a2' 'reflex-base==0.9.11a2' 'reflex-enterprise==0.9.5'
CI=true env/bin/reflex run --frontend-port 5512 --backend-port 9922
# a2: "ValueError: Library @radix-ui/themes is not bundled" -> "Unexpected exit from worker-1";
#     curl localhost:9922/ping -> connection refused
# a1 (same command with ==0.9.11a1): backend starts and answers /ping
```

The app never calls `bundle_library()`, and the message's advice cannot be followed from inside a
state var's default value: the error is raised while the worker is loading the app module.

---

## Quoted published documentation

`reflex-components-moment` 0.9.4a2 — GitHub release body (the only reachable published prose, since
the PyPI description is empty):

> ### Breaking Changes
> - `rx.moment` now fires `on_change` on mount and remount, including for static dates and
>   `interval=0`. Handlers with side effects should account for the initial call and for React
>   Strict Mode invoking it twice in development. ([#7085])
>
> ### Bug Fixes
> - Keep `rx.moment` locales independent: components without a `locale` render in English even when
>   another component or route imports a different locale. Explicit `locale="en"` also works without
>   importing a nonexistent locale module. ([#7110])

`reflex-otel` 0.1.0a2 — PyPI description:

> ```bash
> OTEL_SERVICE_NAME=myapp OTEL_TRACES_EXPORTER=otlp OTEL_METRICS_EXPORTER=otlp \
>   OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
>   OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318 reflex run
> ```
> Install `opentelemetry-exporter-otlp-proto-http` for this HTTP/protobuf configuration. Without the
> protocol setting, `otlp` defaults to gRPC and requires the separate gRPC exporter package.

---

## Reported separately, as the handoff directs

- **Fail-fast SDK configuration (out of scope for the 027 documentation fix).** With the old
  recipe — no `OTEL_EXPORTER_OTLP_PROTOCOL` — a2 behaves exactly as a1: the SDK raises
  `RuntimeError: Requested component 'otlp_proto_grpc' not found`, reflex-otel logs and swallows it,
  then reports `enabled=True` while the provider is still `ProxyTracerProvider`, spans are
  `NonRecordingSpan` and nothing is exported. Anyone who omits the variable still gets a silently
  non-exporting app. `scripts/min_repro_a2.py --noproto`.
- **`frontend_path` and Windows reserved device names.** `/con` is still accepted by the validator.
  Outside the original 014 scope (trailing dot/space and empty segments), recorded so it is not lost.
- **`reflex-components-radix` 0.9.9a2's stale-registration fix** could not be exercised: a
  cross-process recompile of the same `.web` from a Radix page to a Radix-free page leaves no
  `@radix-ui` dependency on **either** version, so this probe shows no difference. The registration
  it targets is in-process. **inconclusive**, not a failure; the sibling `bundle_library` behaviour
  from the same PR is verified fixed above.
- **009 (double-stripped `frontend_path`)** was not exercised and is not claimed either way; no
  routing observation here was used as evidence for or against 014.
