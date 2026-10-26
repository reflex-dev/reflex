# Findings — reflex 0.10.1a1 pre-release pass (+ reflex-enterprise 0.9.8), 2026-10-23/24

Method: every package installed from PyPI into throwaway venvs (never from a checkout); eight exploration agents
(process model, frontend store, hydration/network, events/forms/state, components/typing, enterprise, upgrade/packaging,
hosting CLI/release tools) drove real apps in Chromium in dev and prod, with memory and Redis, each against reflex
0.10.0 as the baseline and older broken versions as positive controls for re-verified fixes; every claimed issue went to
an independent adversarial verifier (8 Fable verifier runs; the last three verifications — EN-1, CT-6, CT-1 — were done by the orchestrator after the Fable spend limit stopped the agents). Context: [CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md); per-item
notes in `<item>/NOTES.md`, per-item summaries in `reports/`.

## Versions under test
- reflex 0.10.1a1 + reflex-base 0.10.1a1 (tag `v0.10.1a1` = `c5f7cf3e4`, from `r/pre-2026.10.23-40018338326`),
  reflex-components-code / -core / -dataeditor / -moment / -radix 0.10.1a1, reflex-components-lucide 1.1.1a1,
  reflex-hosting-cli 0.2.1a1, reflex-release 0.2.1a1, reflex-build-sdk 0.1.1a1. Unchanged at 0.10.0: gridjs, markdown,
  plotly, react-player, recharts, sonner, docgen, hatch-reflex-pyi; reflex-otel 0.2.0. **All 20 published** (wheel +
  sdist).
- reflex-enterprise 0.9.8 (PyPI wheel, `CI=true` + local account stub for prod).
- Baseline: reflex 0.10.0 (+ hosting-cli 0.2.0, reflex-release 0.2.0, build-sdk 0.1.0). Note: the shared `prev` venv
  resolved reflex-components-code / -moment / lucide / hosting-cli / build-sdk to the a1 alphas (bootstrap uses
  `--prerelease=allow`); core / radix / base were 0.10.0, and the items that needed strict 0.10.0 siblings built their own. Positive controls: 0.10.0a1,
  a2, a3, a4, reflex-enterprise 0.9.6 / 0.9.7.
- Environment: Linux, 4 CPU / 15 GB, Python 3.12 (3.11, 3.13, 3.14, 3.15b4 for install / fork checks), Bun 1.4.4,
  Node, Chromium (Playwright), granian 2.8.5, Redis 7.

## Pre-flight (`preflight/`)
20/20 published; `.pyi` audit PASS (122 stubs, wheel == sdist, no foreign stubs); reflex pins `reflex-base==0.10.1a1`
but only `>=0.10.0` on components-core / -code / -dataeditor, `>=1.1.0` on lucide, `>=0.2.0` on hosting-cli (see
R101-03); all 77 changed source files byte-identical between the tag and the installed wheels; blank app clean in dev
and prod.

## Executive summary

**What works.** The headline changes hold up end to end, each checked against a 0.10.0 positive control that still has
the bug:
- forked prod workers (#7079): 8-worker cap, PSS 205 vs 238 MB, startup 8 vs 13 s, cross-worker deltas 6/6, clean
  SIGTERM/SIGINT; forked dev reload worker (#7113) with fast refusal while broken;
- frontend store (#7441, 1 500 substates render; 0.10.0 overflows the stack), structural sharing (#7273, 48 mutation
  kinds, DOM == backend state; memo components stop re-rendering), hook order (#7586), state-schema mismatch detection
  (#7553: no false positives across rebuilds / restarts / forked and spawned workers; real skew → one reload then a
  banner, no loop), unknown-substate skip (#7435);
- `trusted_proxy_hops` (#7614: spoofed XFF ignored by default; 0.10.0 returned it), repeated / non-UTF-8 headers,
  oversized hydrate payloads (#7551/#7605: one error + toast instead of 326 reconnects in 12 s), storage sync /
  computed-var / client_state fixes;
- new form API (`rx.form.FormData`, TypedDict coercion) with **24/25 legacy dict-handler forms byte-identical**;
  dict.values()/items() mutation tracking; event sequences; NameError on undefined annotations;
- every component fix (checkbox groups, radio_cards, auto_complete, progress ARIA, moment options + provider,
  data_editor state columns, lucide dynamic icons, shiki transformers) and the typing fixes (pyright 2 vs 12, ty 10 vs 34
  errors on a realistic module);
- installs on Python 3.11–3.15 (pip + uv), in-place upgrades of four reflex-examples apps incl. Redis sessions and
  rollback, Bun 1.4.4, npm devDependencies migration, third-party sweep 22/22;
- reflex-enterprise 0.9.8: auth matrix 36/36, OIDC cross-tab logout, MCP, AG Grid prerender, dnd / mantine / flow / map;
  rxe's deprecated `VarData(position=)` hooks still work;
- hosting CLI 0.2.1a1 (all seven fixes), reflex-release 0.2.1a1 with towncrier 26 (byte-identical output),
  build-sdk `default_transport()`.

**What needs attention before the final** (details in RELEASE_PLAN.md): one confirmed functional regression in
structural sharing (R101-01: after an AG Grid cell edit, every memoized consumer of the same state list stays stale),
one scoped behaviour regression of the fork preload that needs a changelog note (R101-02), changelog wording for the
deliberate form change (R101-05), the sibling floors of the reflex wheel (R101-04), and two small fixes in new 0.10.1
code (R101-06, R101-13).

Severity: 1 medium regression (R101-01) · 1 medium in reflex-enterprise, not a regression (R101-07) · 19 low / trivial
· 0 high / critical. Verifiers reclassified PM-1 medium → low and UP-1 medium → low, narrowed FS-2, HN-3, CC-2, ES-2,
CT-6, and broadened EN-1; no claim was fully refuted.

Index:
- R101-01: After an AG Grid cell edit, every memoized consumer of the same state list stays stale (structural sharing #7273) (MEDIUM, regression)
- R101-02: Fork preload kills import-time threads / shares module-level values in `--backend-only` prod and on Python 3.14 (LOW, scoped regression)
- R101-03: Wheels built from the 0.10.1a1 component sdists silently lose `.pyi` stubs (LOW for the release; MEDIUM robustness item)
- R101-04: Stock `pip install reflex==0.10.1a1` keeps components-code / -dataeditor 0.10.0, lucide 1.1.0, hosting-cli 0.2.0 (LOW)
- R101-05: Deliberate form-data change for repeated names with `id == name` is missing from the CHANGELOG; core deprecation entry reads as present tense (LOW, regression by design)
- R101-06: Malformed / colliding `__reflex_form_data__` envelope raises in the fallback (LOW)
- R101-07: reflex-enterprise 0.9.8 REST event API takes the leftmost X-Forwarded-For as `client_ip` (MEDIUM, rxe, not a regression)
- R101-08: React Compiler silently skips many generated components; docs overclaim coverage (LOW)
- R101-09: `trusted_proxy_hops` uses the selected XFF token verbatim (no IP validation) (LOW)
- R101-10: `reflex deploy` hides the new scaling-retry progress and its success line below `--loglevel debug` (LOW)
- R101-11: Directory symlink resolving outside the app / dangling symlink crashes `reflex export` (LOW)
- R101-12: uv cannot build the `reflex` 0.10.1a1 sdist (alpha-only) (LOW)
- R101-13: New FormData / TypedDict API yields `[None]` for an empty checkbox group that has an `id` (LOW)
- R101-14: `radio_cards(as_child=...)` silently compiled into CSS after the prop's removal (LOW)
- R101-15: Non-str browser-storage vars log a type error per instantiation and round-trip as strings (LOW, pre-existing)
- R101-16: Background-task rehydration leaves storage vars at defaults until reload (LOW, pre-existing end state)
- R101-17: Leftover "never awaited" wrapper warning when a `get_delta` filter withholds an async var without closing it (TRIVIAL)
- R101-18: Removing TailwindV4Plugin leaves a stale `postcss.config.js` (LOW, pre-existing)
- R101-19: moment: unknown props still CSS; provider `format` overrides a child's `from_now` (LOW)
- R101-20: typing gaps that pre-date 0.10.1a1 (LOW)
- R101-21: rxe MCP OAuth consent race on Redis (LOW, rxe-side, pre-existing)
- R101-22: recharts deep-freezes state objects it shares with other components, so an AG Grid edit on the same data throws (LOW–MEDIUM, pre-existing)

## Update 2026-10-26 — reflex-enterprise 0.9.10a1
With the user-supplied rxe 0.9.10a1 wheel on reflex 0.10.1a1 (`verify_ent910/`): **R101-01 fixed** (via rxe #282,
deep copies of state rows), **R101-07 fixed** (rxe #279), **R101-22 fixed** (side effect of #282). Controls with rxe
0.9.8 still reproduce all three. Residual: a rejected edit stays visible in the rejecting grid (accepted, better than
0.10.0); R101-01's mechanism remains open for non-AG-Grid components that mutate state objects.

## Re-verification table
| registry id | what | positive control | 0.10.1a1 | item |
|---|---|---|---|---|
| HYD-01 / HYD-02 | first load writes nothing; computed-var storage rewrite | 0.10.0a1 | fixed | hydration_net |
| HYD-08 / HYD-09 | sync=True storms | 0.10.0a3 (Part R mechanism; 1.1 M frames) | fixed (0 storms) | hydration_net |
| HYD-05 (F-008, reflex#7486) | oversized storage reconnect storm | 0.10.0 | **newly fixed** (#7551/#7605) | hydration_net |
| HYD-12 (C21) | `remove_local_storage` syncs null | 0.10.0 | still broken, unchanged | hydration_net |
| ENT-16 / DOC-14 (#7360) | credential exposure | 0.10.0a4 (10 secrets) | fixed (0) | hydration_net, enterprise |
| ENT-30 (N-032) | OIDC cross-tab logout | 0.10.0a2 + rxe 0.9.8 | fixed (dev + prod) | enterprise |
| ENT-29 (N-025) | prod AG Grid state column_defs | rxe 0.9.6 | fixed | enterprise |
| HYD-15 / CMP-05 | bundled libraries | — | fixed (incl. forked hot reload) | enterprise |
| ENT-01 / 02 / CLI-03 | deprecated shims | — | work with deprecation | enterprise |
| CMP-51 (N-028) | mantine page error | 0.10.0 | **newly fixed** (#7587) | enterprise |
| ENT-07 (N-033), ENT-31 (N-026) | rxe cookie sync / flow reload | — | unchanged (rxe#262, rxe#269) | enterprise |
| EVT-04 | prod + Redis backend-initiated deltas | — | fixed (6/6 cross-worker) | process_model |
| CLI-16 | dev backend refuses while broken | — | fixed | process_model |
| STATE-36 (reflex#7258) | no `__init__.py` → "no dispatch function" | 0.10.0 | **newly fixed** (#7304) | process_model, upgrade_packaging |
| CLI-26 / A3-07 | `--json` SIGINT | 0.10.0 | **newly fixed** (#7558) | process_model |
| CLI-09 | "Unexpected exit from worker" | 0.10.0 | **newly fixed** (#7538) | process_model |
| CLI-27 / A3-08, CLI-15 / F-007 | TERM truncation; npm orphan | — | unchanged (filed) | process_model |
| EVT-06, STATE-05, STATE-11…19, STATE-20/21, CMP-01, EVT-02 | class-state model, schema hash, pickles both ways, uploads, client_error | — | fixed / unchanged | events_state |
| CMP-11, CMP-31, CMP-41, CMP-13, CMP-29 | moment locale, prod portal + overlay, progress, accordion, shiki | 0.10.0 | fixed | components_typing |
| CMP-15 | moment options as CSS | 0.10.0 | changed (2.x options are props; unknown still CSS) | components_typing |
| CMP-14, CMP-39 | moment defineLocale, collapsible warning | — | unchanged | components_typing |
| PKG-09 / 08 / 13, F-006 | installs, greenlet, migrations | — | fixed | upgrade_packaging |
| PKG-05 / PKG-04 | stock pip graph; uv sdist build | — | changed (R101-04, R101-12) | upgrade_packaging |
| CLI-28 (reflex#7432), CLI-11 | token guidance; `--json` after 403 | 0.2.0 | fixed | cloud_cli |
| reflex#7429, #7247, #7407 | large trees, unknown substate, late client_state | 0.10.0 | fixed | frontend_store |

## R101-01: After an AG Grid cell edit, every memoized consumer of the same state list stays stale (MEDIUM)
- Cluster: `enterprise` | Regression vs 0.10.0: **yes** | Verifier: CONFIRMED and broadened (`verify_en1/`)
- Minimal repro: `verify_en1/gridmin/` (`./run.sh new-ent new` vs `./run.sh prev-ent prev`): `GS.rows` bound to an
  editable `rxe.ag_grid` (handler stores `int(newValue)`), a second grid, an `@rx.memo` component and an unmemoized
  text of the same var. Edit u-2 → 777: on 0.10.1a1 backend, store, the edited grid, unmemoized text and `rx.foreach`
  show 777 while **the `rx.memo` component and the second grid stay at 10**; on 0.10.0 everything shows 777. A handler
  that stores a different value (clamp to 100) updates everything on both. Explorer's original: two grids on one list
  (`enterprise/own/gridshare`, 3/3 new, 0/2 prev).
- Mechanism: AG Grid's default value setter writes the edit into the row object it received — the reflex store's own
  object. The backend echoes the same value; #7273's `replaceEqualDeep` (`reflex_base/.templates/web/utils/state.js`)
  finds prev (already mutated) deep-equal and keeps the old references, so consumers memoized on prop identity never
  re-render. Trigger: any component that mutates the objects it gets from state (AG Grid editing is the common one) +
  a memoized second consumer (rx.memo, charts, other grids, app_components memo wrappers) + a handler that stores the
  edited value as is (the normal edit handler).
- Evidence: `verify_en1/out/nochart-{new,prev}.json`; `enterprise/own/out/gridshare_*.json`.

## R101-02: Fork preload kills import-time threads and shares module-level values (LOW, scoped regression)
- Cluster: `process_model` | Regression vs 0.10.0: **yes** for `reflex run --env prod --backend-only` on Linux and any
  prod run on Python 3.14; **no** for full-stack prod on 3.12 (0.10.0 already forked from the compiling CLI) |
  Verifier: RECLASSIFIED medium → low (`verify_pm1/`)
- Repro: `process_model/NOTES.md` ISSUE-1; `scripts/probe_run.sh new new-be-fork prod-be 8201` vs prev: imported in
  worker 0/8 vs 9/9, import-time thread / Timer / QueueListener alive 0/8 vs 9/9, distinct module-level random 1 vs 9.
- Real patterns: a logging `QueueListener` started at import loses every worker record and its queue grows per worker;
  APScheduler reports running but runs only in the supervisor. Only module-level constants and user `random.Random()`
  instances are shared — the global `random` is reseeded at fork, `uuid4` / `secrets` are fresh. reflex-otel 0.2.0 is
  unaffected (OTel registers at-fork hooks). `REFLEX_BACKEND_START_METHOD=spawn` restores 0.10.0 exactly (~3× memory).
  CPython's multi-threaded-fork DeprecationWarning is hidden by default; nothing else is logged.
- Docs: `docs/hosting/self-hosting.md` names "start threads at import time" as a reason for spawn; the CHANGELOG entry
  does not name the changed cases.

## R101-03: Wheels built from the 0.10.1a1 component sdists silently lose `.pyi` stubs (LOW for release)
- Cluster: `upgrade_packaging`, `components_typing` | Regression vs 0.10.0 sdists: yes, literally (36/1/65 → 32/0/64);
  scope: alpha-vs-newest-final gap | Verifier: NARROWED (`verify_up/`)
- Repro: `pip install --no-binary reflex-components-core reflex-components-core==0.10.1a1` → 32 .pyi (wheel 36); same
  for -dataeditor (0/1) and -radix (64/65). Missing: core `base/error_boundary`, `core/banner`, `core/upload`,
  `el/elements/forms`; dataeditor `dataeditor`; radix `primitives/form`.
- Root cause: the sdists' `[tool.hatch.build.hooks.reflex-pyi].dependencies` list `reflex-base` (and
  `reflex-components-core`) unpinned → the isolated build env gets the newest FINAL base (0.10.0); hatch-reflex-pyi
  unlinks the shipped stubs and regenerates with base 0.10.0's generator, which logs import failures for new base
  symbols and exits 0 (visible only with `-v`). At the 0.10.1 final the newest base is 0.10.1, so isolated builds will
  be complete; a future base that removes a symbol would silently drop that module's stub again. uv caches the
  sdist build and reuses it for later ordinary installs of the same version (4 campaign venvs were tainted; runtime
  unaffected; pyright then rejects `rx.form.FormData[str, str]`).

## R101-04: Stock pip install does not deliver the train's component fixes (LOW)
- Cluster: `upgrade_packaging` (+ `cloud_cli`) | Regression: no (PKG-05 pattern, sibling-floor policy)
- `pip install 'reflex[db]==0.10.1a1'` (no `--pre`) and `pip install -U reflex` keep reflex-components-code /
  -dataeditor 0.10.0, lucide 1.1.0, hosting-cli 0.2.0: a state-backed `data_editor` column without `type` still crashes
  the page (#7596), shiki transformers stay off (#7430), and the compile warns "format_data_editor_column has been
  deprecated … Upgrade reflex-components-dataeditor". Evidence: `upgrade_packaging/mixed/logs/`.

## R101-05: Deliberate form change missing from the CHANGELOG; core deprecation entry reads as present tense (LOW)
- Cluster: `events_state` | Regression vs 0.10.0: yes, by design (#7386) | Verifier: CONFIRMED (`verify_es/`)
- Dict / unannotated `on_submit` handlers reading an `id == name` control whose name is submitted more than once
  (checkbox_group with 2+ checked, multi-select, repeated inputs) now get the last value: prev
  `{"cg": "c1", "topping": true}` → new `{"cg": "c3", "topping": "olives"}`. Single-submitted controls unchanged. The
  new value is the more correct one; documented in `docs/library/forms/form.md:166` and the PR, not in any CHANGELOG.
  The reflex-components-core deprecation entry's "also stops adding a field keyed by its id … submits 'on'" sentences
  describe 0.11 behaviour in present tense (verified: on 0.10.1a1 both keys are still added and the checkbox still
  gives `True`). Rare in practice (no occurrence in reflex-examples).

## R101-06: Malformed / colliding `__reflex_form_data__` envelope raises in the fallback (LOW)
- Cluster: `events_state` | Regression: no for well-formed traffic; contrived yes (below) | Verifier: CONFIRMED
- A socket message with a malformed envelope (string / int / 1- or 3-tuples / unhashable key) → `transform_form_data`
  ValueError, then the fallback `form_data_as_dict` → `dict(entries)` raises again: one double traceback + "An error
  occurred" toast per message, sender-only. Browsers never send it, but envelope detection is key-presence only: a
  control named `__reflex_form_data__` whose dict is passed on to a second dict handler works on 0.10.0 and fails on
  0.10.1a1. Fix shape: treat a dict as an envelope only when its entries are a list of 2-item lists.

## R101-07: reflex-enterprise 0.9.8 REST event API takes the leftmost X-Forwarded-For (MEDIUM, rxe)
- Cluster: `enterprise` (+ `hydration_net`) | Regression: no (same on 0.10.0) | Confirmed end to end
- `reflex_enterprise/plugins/event_handler_api.py:1353-1355` sets the session's `client_ip` from the leftmost XFF
  (even `"not an ip <script>"`) regardless of reflex's `trusted_proxy_hops`, while the same handler over the websocket
  honours #7614. No rxe security decision keys on it (rate limiters use `client_ip_from_scope` with their own hops; audit
  stores no IP; MCP sessions get 0.0.0.0); user handlers reading `router.session.client_ip` over REST get a spoofable
  value. Evidence: `enterprise/own/out/xff_new-h{0,1}.txt`, `xff_prev-h0.txt`.

## R101-08: React Compiler silently skips many generated components; docs overclaim (LOW)
- Cluster: `frontend_store` | Regression: no (new, experimental, default-off) | Verifier: NARROWED (`verify_fh/`)
- Bail-outs: `refs["ref_x"] = ref_x` (any `id=`), refs in jsx() calls, the IIFE event chain in on_mount / on_unmount /
  form on_submit (compiler invariant), optional chaining in `rx.cond(State.x == ...)` tests (incl.
  `rx.color_mode.button` in the blank template), client_state `??=`, window_event_listener, MemoizedToastProvider.
  Page route modules are static trees with nothing to memoize (not a bail-out). Coverage: blank 4/6, quiz 14/18,
  github-stats 13/16, fs_app 63/133; `panicThreshold: "none"` with no logger = silent. PR #7234's coverage assertion
  passes when any one function compiles. Docs (`docs/advanced_onboarding/configuration.md`) say it compiles generated
  JSX in `app/`, `app_components/`, `utils/components/`.

## R101-09: `trusted_proxy_hops` uses the selected XFF token verbatim (LOW)
- Cluster: `hydration_net` | Regression: no (0.10.0 worse: leftmost entry, latin-1 kills the handler) | Verifier:
  CONFIRMED / narrowed to hardening
- Client text reaches `client_ip` only when the client's own header is at position -hops (direct connection with
  hops ≥ 1, or a proxy forwarding XFF untouched — the documented misconfiguration); a trusted proxy's `ip:port` form
  (Azure App Gateway) also passes through. Rendering is safe (React text). Fix shape: `ipaddress.ip_address()` on the
  token (strip port / brackets), fall back to the peer; one docs line.

## R101-10: `reflex deploy` hides scaling-retry progress and its success line (LOW)
- Cluster: `cloud_cli` | Regression: no (mechanism since 0.8; the #7463 lines are new) | Verifier: CONFIRMED (`verify_cc/`)
- `export_for_deploy` → `export(loglevel=subprocess_level())` sets the process console level to WARNING and never
  restores it; `--loglevel info` is also hidden because `set_log_level` only writes `REFLEX_LOGLEVEL` when the level
  changes. A non-TTY deploy is silent from the upload bar until exit (up to 165 s of retries). Warnings / errors still
  shown. Workaround `REFLEX_LOGLEVEL=info`.

## R101-11: Directory symlink resolving outside the app / dangling symlink crashes `reflex export` (LOW)
- Cluster: `cloud_cli` | Regression: no | Verifier: NARROWED
- `reflex/utils/build.py` `_zip` (os.walk followlinks + resolve + relative_to): ValueError traceback and a partial
  backend.zip; `reflex deploy` reports a clean one-line error and uploads nothing. File symlinks are archived by content;
  a real `.venv` is pruned (refuted worry). A dir symlink inside the app writes duplicate zip entries.

## R101-12: uv cannot build the `reflex` 0.10.1a1 sdist (LOW, alpha-only)
- Cluster: `upgrade_packaging` | Regression: no (PKG-04 changed; 0.10.0 failed differently) | Verifier: CONFIRMED
- The custom hook's `require-runtime-dependencies = true` puts pre-release sibling floors into the build env, which uv
  will not opt into; pip works; `-b build-constraints.txt` works around it. The final sdist carries no pre-release
  specifiers.

## R101-13: New FormData / TypedDict API yields `[None]` for an empty checkbox group with an `id` (LOW)
- Cluster: `components_typing` | Regression: no for dict handlers (`null` existed on 0.10.0; `checkbox_cards` by id is
  now a form control and adds `"cards_id": null`) | Verifier: CONFIRMED / narrowed (`verify_ct/`)
- An empty `rx.checkbox_group.root(id=..., [name=...])` gives `[None]` in a `list[str]` TypedDict field and in
  `FormData.getlist()` — also for the documented `id` + `name` form; name-only groups are correctly absent. Expected `[]`
  / absent; `", ".join(...)` raises TypeError. Evidence: `verify_ct/out/ctform-{new,prev}.json`.

## R101-14: `radio_cards(as_child=...)` silently compiled into CSS (LOW)
- Cluster: `components_typing` | Regression: no (0.10.0 forwarded it and crashed the page) | Verifier: CONFIRMED
- Generic unknown-prop behaviour after the prop's removal (`as_child=True` → `css: {asChild: true}`, like `foo_bar`);
  a crash became a no-op without a warning.

## R101-15 … R101-21 (LOW / TRIVIAL, none a regression)
- **R101-15** (`hydration_net`): int / bool / dict-annotated storage vars log "Expected field … got '3' of type
  LocalStorage" per instantiation and round-trip as strings; dict stored as `[object Object]` (same on 0.10.0; docs say
  strings only).
- **R101-16** (`events_state`): after #7585 rehydrates an expired session, `rx.LocalStorage` vars show defaults until a
  full reload (0.10.0 reaches the same state after the next event).
- **R101-17** (`events_state`, verifier NARROWED to trivial): a `get_delta` filter that withholds an async
  `cache=False` var without `.close()` leaves one never-started framework wrapper "never awaited" (0.10.0: two); the
  user body never runs; filters that close (rxe, #7410's tests) get 0 warnings.
- **R101-18** (`frontend_store`): removing `TailwindV4Plugin` leaves `.web/postcss.config.js` referencing the pruned
  `@tailwindcss/postcss` → vite overlay on every page until `.web` is deleted.
- **R101-19** (`components_typing`): `rx.moment(filter=/settings=/form_at=)` still compile to CSS; a
  `moment_provider(format=...)` overrides a child's `from_now` (docs say child props win).
- **R101-20** (`components_typing`): typing gaps identical or worse on 0.10.0 (ty `rx.Field[rx.Model | None]`,
  `auto_complete=True`, `data_editor(columns=["A"])`, `VarData(position=)` deprecation invisible to checkers, ty rejects
  `rx.EventHandler[spec]`).
- **R101-21** (`enterprise`): intermittent MCP OAuth consent race on Redis (lands on /login), same on 0.10.0 + rxe 0.9.8.
- **R101-22** (`verify_en1/gridmin_chart/`, found during verification; LOW–MEDIUM, pre-existing): with
  `rx.recharts.bar_chart(data=GS.rows)` on the same page, an AG Grid edit of `GS.rows` throws `Cannot assign to read
  only property 'price' of object` and never reaches the backend, on 0.10.0 and 0.10.1a1 alike — recharts 3 keeps
  `data` in a Redux Toolkit / immer store whose auto-freeze deep-freezes the reflex store's objects.

## Context observations (not findings)
- kill -9 of one prod worker shuts the whole granian server down (granian `respawn_failed_workers=False`; same on 0.10.0).
- `rxconfig.py` edits are not hot-reloaded by the forked dev worker (same on 0.10.0).
- `reflex export --zip-dest-dir <missing dir>` → FileNotFoundError traceback (both).
- Transient #7553 / #7435 console warnings while a dev hot reload adds a page/substate (0.10.0 died with "no dispatch
  function").
- `on_submit=State.h("x_" + it)` inside `rx.foreach` → ReferenceError (both); glide-data-grid load-time TypeErrors in a
  mixed app (both).
- rxe REST responses carry the caller's own raw cookie header in `rx_router_headers` (both; same caller only).

## Cluster summaries
See `reports/<item>.md` for each item's full test list; one line each:
- `process_model` — every #7079/#7113/#7542/#7538/#7558/#7453/#7052/#7304 claim holds; R101-02.
- `frontend_store` — no regression; every targeted fix reproduces on 0.10.0; R101-08, R101-18.
- `hydration_net` — no regression; HYD-05 newly fixed; R101-09, R101-15 (+ R101-07 seen in code).
- `events_state` — legacy forms unchanged except R101-05; R101-06, R101-16, R101-17.
- `components_typing` — no behavioural regression; R101-03 (dup), R101-13, R101-14, R101-19, R101-20.
- `enterprise` — rxe 0.9.8 parity with 0.10.0 except R101-01; R101-07, R101-21.
- `upgrade_packaging` — installs / upgrades clean; R101-03, R101-04, R101-12.
- `cloud_cli` — all hosting-CLI / release-tool changes as described; R101-10, R101-11.
