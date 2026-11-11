# Registry and fixtures summary (prerelease-testing)

Sources read: `prerelease-testing/REGISTRY.md` (baseline: reflex 0.10.0, rxe 0.9.7), `fixtures/README.md` and the four area READMEs
(hydration, class_state, enterprise, upgrade), `runs/2026-10-26-v0.10.1a2/NOTES.md`, and `runs/2026-10-23-v0.10.1a1/FINDINGS.md`
(executive summary and index). Read-only; nothing under `/home/user/reflex` was modified.

"Positive control" = a version where the defect reproduced (usually first-seen). Where a fixture README names a control, it is used.
"Re-run" paths are relative to `prerelease-testing/fixtures/` unless absolute. `$SB` = scratch root, `$NEW`/`$PREV` = venv names.

## 1. Re-verify on every pass (REGISTRY.md, "Re-verify on every pass", priority order 1-17)

| # | IDs (verbatim) | What to check | Rerun (fixture + command) | Positive control |
|---|---|---|---|---|
| 1 | HYD-01, HYD-02 | Fresh profile writes nothing on first load; computed-var storage rewrite reaches browser | `hydration/`: `scripts/run_f002.sh $NEW prod new-prod 3140 3140` (dev: `... dev new-dev 3142 8142`); HYD-02: `scripts/run_cv.sh $NEW dev new-dev-s4 3142 8142 all PYTHONHASHSEED=4` (diff vs `expected/cvstore_dev.summary.txt`) | 0.10.0a1 (`CTRL_F002=alpha`) |
| 2 | HYD-08, HYD-09 | `sync=True` LocalStorage, 3+ tabs: 0 storms, convergence | `hydration/`: `scripts/run_storm.sh $NEW dev 3 3142 8142 S 6` then `scripts/summ_s.py`; `scripts/run_stamp2.sh $NEW dev 3142 8142 3 1 6` | 0.10.0a3 (`CTRL_STORM=a3`; 2/2 storms) |
| 3 | ENT-30 | OIDC cross-tab logout; core `get_delta` sees boot-time values | `enterprise/`: `auth/bin/seq_ent_auth.sh $ENT_NEW <L> 1` (dev+Redis, vdrv stale/away/xtab); `auth/scripts/xtab_matrix.sh 5 $ENT_NEW:<L>` (infra up); prod `auth/bin/seq_n032_prod.sh $ENT_NEW <L>` | 0.10.0a2 + rxe 0.9.8 (per 0.10.1a1 FINDINGS) |
| 4 | ENT-29 | Prod prerendered AG Grid with state-valued `column_defs` renders on load and reload | `enterprise/`: `grid/bin/run.sh $ENT_NEW aggrid_min prod 3601 aggrid_min_<x>_prod` (expect 4/4); `grid/bin/seq_grid.sh $ENT_NEW <L> 1` | rxe 0.9.6 with reflex 0.10.0 (first seen 0.10.0a1) |
| 5 | ENT-16, DOC-14 | No `client_token`/`session_id` in REST/MCP; no cookie/credential in frames, HTML, DOM | `enterprise/`: `auth/bin/seq_deeplink.sh $ENT_NEW <L> dev,prod` (check G: no cookie in `rx_router_headers`); `hydration/`: `scripts/run_rtr.sh $NEW dev <L> 3142 8142 8143` (expect 0 secrets). REST redaction probe (`verify_leak_http.py`) is archive-only | ENT-16: 0.10.0a4 (10 secrets, per fixture README); DOC-14: 0.10.0a5 |
| 6 | EVT-06 | `cache=False` var withheld by `get_delta` is delivered once released | No fixture in this set. Archive repro `[912] event_loop/scripts/s_filtered.py` (app `elapp`, `/filtered`) on branch `claude/reflex-prerelease-testing-t0sd90` | 0.9.12a1 (first seen) |
| 7 | STATE-05 | `type(rx.State) is BaseStateMeta`; BaseStateMeta-derived metaclass constructs; rxe modules import | No fixture in this set. Archive `[912] orch_probes/metaclass_probe.py`, `ent_import_probe.py` | 0.9.12a1 (rxe 0.9.5 apps died) |
| 8 | STATE-11, STATE-12, STATE-13, STATE-14, STATE-15, STATE-16, STATE-17, STATE-18, STATE-19 | Class assignment/patching raises documented TypeError; field patching round-trips; dev guard rejects `_x__y` | `class_state/`: `bin/run_python_suite.sh $NEW` (pytest: `pytest/test_moot.py`, `test_converted.py`, `test_n039_fields.py`); `probes/probe_storage_setdefault.py`, `probes/adv7495.py` (STATE-18), `probes/probe_v8_storage.py` (STATE-17), `probes/guard7495.py` (STATE-19/N-008); run as `cd <dir> && EXPECT_VENV=$NEW $SB/envs/$NEW/bin/python -I <file>` | STATE-11 0.10.0a1; STATE-12/14/15/19 0.10.0a2; STATE-16/17/18 0.10.0a3 |
| 9 | STATE-20, STATE-21 | Schema hash identical across builds; previous-alpha pickles load; 0.9 to 0.10 sessions survive | `class_state/`: `bin/n004_matrix.sh $W/logs/n004 $NEW $PREV`; `bin/n004_redis_chain.sh` (prod, Redis 8309). STATE-21 (Python-version-dependent hash): not in fixtures; inferred = run n004_matrix under two Python minors | STATE-20: PREV venv pair (0.9.12 / 0.10.0 era); STATE-21: not recorded |
| 10 | PKG-09, PKG-08, PKG-05 | Fresh `reflex[db]` on 3.11-3.14 (pip, uv): greenlet present, migrations apply; stock install resolves whole train | `upgrade/`: `inst/bin/n001.sh` with `SPECS="uv311:uv:3.11:db uv314:uv:3.14:db pip311:pip:3.11:db pip314:pip:3.14:db f006pip312:pip:3.12:plain"`; `inst/bin/dbcli.sh pip311`; `inst/bin/install_paths.sh`. PKG-08 (sqlmodel cap) archive-only: `upgrades_a/verification/sqlmodel-datetime/` | PKG-09: 0.10.0a2 (stock 0.9.x still broken); PKG-08: 0.10.0a1; PKG-05: 0.9.11a1 |
| 11 | CLI-16 | Dev backend refuses fast while app broken/after shutdown; stays bound across hot reload | No fixture in this set (lifecycle/ covers signals, not this). Archive `[912] dev_server_cli/verification/scripts/break_reload_probe.py`, `sigterm_port_probe.py` | 0.9.12a1 |
| 12 | EVT-04 | Prod + Redis + default workers: 6/6 backend-initiated deltas delivered | No fixture in this set. Archive `[911] bg_rehydrate/verification/` | 0.9.11a1 (pre-#7108; exact build not recorded) |
| 13 | HYD-15, CMP-05 | Backend-only/prebuilt workers serialize state referencing bundled libs; module-scope `bundle_library()` survives compile | No dedicated fixture row. Per 0.10.1a1 FINDINGS, enterprise area: `enterprise/grid/bin/demo.sh $ENT_NEW <demo> prod <L>` plus `grid/src/entr` (lazy flag: `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true`). Archive: `[911] ent_map_dnd_flow/bundlectx/` | HYD-15: 0.9.11a1 (a2 worker died at startup); CMP-05: 0.9.9a1 |
| 14 | CMP-31 | Prod with default badge: `#portal` and lower-priority wraps reach DOM; data_editor overlay opens | No fixture in this set. Archive `[912] components_bumps/gallery`, `components_bumps/verification/` | 0.9.12a1 |
| 15 | CMP-11 | Un-localed moment siblings stay English next to `locale="fr"`; `locale="en"` builds in prod | No fixture in this set. Archive `[911] components_bumps/leakapp2/`, `scripts/drive_leak.py` | 0.9.11a1 |
| 16 | ENT-01, ENT-02, CLI-03 | `dynamic.bundled_libraries`, `reflex.page.DECORATED_PAGES`, `get_config(reload=True)` still work with DeprecationWarning | `enterprise/`: `grid/bin/seq_grid.sh` (lambda renderers, ENT-01 path via entr/entv); `grid/bin/demo.sh $ENT_NEW flow dev <L>` (ENT-02 import). CLI-03 has no fixture: one-line Python check needed (inferred) | 0.9.9a1 (first seen, all three) |
| 17 | CMP-01, EVT-02 | Hostile upload filenames stay in upload dir; `client_error` with no payload ignored, no traceback | No fixture in this set. Archive `[99] components/` (raw multipart to `/_upload`); `[99] client_error/` (`noarg_unlinked.py`, `abuse2.py`) | 0.9.9a1 (both) |

Note: "Fixture" in REGISTRY.md is `—` for items 6, 7, 11, 12, 14, 15, 17 and CMP-01 / EVT-02 for this curated set; their repros live
only on the archive branch. Upgrade and class_state fixtures cover the rest.

## 2. Registry items open / filed / not-fixed (119 rows; status starts open or filed-open)

Format: ID (severity): status — one-line title (truncated). Area in parentheses is implicit from the ID prefix.
Also "unknown" (never verified, not counted above): HYD-07, HYD-14, STATE-37, ENT-06, ENT-23, ENT-41, CLI-30, CLI-33, CLI-34, CLI-36, CMP-09, CMP-24, CMP-27, CMP-42.

- HYD-03 (LOW): filed-open reflex#7484 — A computed var's state write during an ordinary event or client-side navigation is dropped depending on `PYTHONHASHSEED`
- HYD-04 (LOW): filed-open tracked by existing reflex#7253 (open; fix PR #7436 open) — Uncached computed var keeps showing its hydration-time value until a full reload (side-effectful computed var only)
- HYD-05 (MEDIUM): filed-open reflex#7486 — A client-storage value over the 1 MB socket payload causes an endless reconnect storm, no UI error
- HYD-06 (LOW): filed-open reflex#7487 — Client-side navigation before the websocket CONNECT runs the left page's `on_load` (an `rx.redirect` from it hijacks the new page)
- HYD-10 (LOW (perf)): filed-open reflex#7508 — Storage-dependent computed vars evaluated twice per page load (second boot delta from #7493; reflex-local-auth DB query runs twice)
- HYD-11 (LOW): open — by design per verifier; the suggested "last writer wins" doc note is not in the v0.10. — Two tabs writing a `sync=True` var within ~1 RTT converge on the **earlier** write (consistent last-storage-writer-wins)
- HYD-12 (LOW): open — not filed (no matching issue) — `rx.remove_local_storage` of a synced key makes other tabs sync `null` into a `str` var; a dependent computed var raises `TypeError`...
- HYD-13 (LOW): filed-open reflex#7506 — Several `sync=True` storage vars sharing one storage `name` only sync the last one
- HYD-16 (MEDIUM (911 rated HIGH)): filed-open reflex#7247 (enterprise trigger fixed separately, ENT-12) — A delta naming a substate the compiled frontend has no dispatcher for latches `backend_state_mismatch`; every later event is discard...
- STATE-06 (LOW (disputed)): open — deliberately not filed (2026-09-22) — `deps=["router"]` deprecation is silent in the redundant `auto_deps=True` + router-reading shape
- STATE-10 (LOW): filed-open reflex#7459 (message part fixed by #7496, reflex#7475 closed) — Backend-var misuse paths still silent or cryptic: `str(S._x)`, `"%s" % S._x`, `f"{S._x!s}"` embed the Field repr; `rx.box(id=S._x)` ...
- STATE-21 (unknown): filed-open reflex#7491 — Saved-state schema hash depends on the Python version, so upgrading Python with Reflex resets persisted sessions
- STATE-22 (LOW): filed-open reflex#7498 — A `str`-annotated field whose `default_factory` produces browser storage is never treated as storage
- STATE-23 (LOW): filed-open reflex#7499 — Hydrating a var annotated with a browser-storage type logs a type error from `Field.__set__`
- STATE-24 (LOW): filed-open reflex#7488 — Annotation naming an undefined class (`from __future__ import annotations`) gives a cryptic `ForwardRef` TypeError instead of `NameE...
- STATE-25 (MEDIUM): filed-open reflex#7477 — Mutating nested dict entries through `dict.values()` / `.items()` bypasses dirty tracking
- STATE-26 (LOW): filed-open reflex#7483 — Python 3.14: `state_auto_setters=True` in rxconfig generates no setters in the backend worker
- STATE-27 (LOW): open — unchanged on a5 / 0.10.0 (message text only, #7519); not filed — `State.add_var` on a substate for a name an ancestor added via `add_var` raises #7516's TypeError; `Sub.dyn = 5` for an inherited dy...
- STATE-28 (LOW): open — not filed — Deprecated `state_auto_setters=True`: parent var `set_<x>` plus child var `<x>` fails at class definition with a misleading #7516 me...
- STATE-29 (LOW (cosmetic)): open — not filed — `mock.patch.object(Substate, inherited_var, v)` surfaces mock's cleanup error with the assignment error as context (both name the va...
- STATE-31 (LOW): open — not filed; consequence of the A5-01 design — A frontend var whose default cannot be deep-copied gets an opaque `cannot pickle '_thread.lock'` instead of the `VarTypeError` namin...
- STATE-32 (LOW): open — not filed — A backend var whose default cannot be deep-copied fails at import with a message naming neither the var nor the `ClassVar` fix
- STATE-33 (LOW (perf)): open — not filed; consequence of the A5-01 design — Large mutable class-body defaults are deep-copied once more at import and the snapshot stays resident per worker
- STATE-34 (LOW): filed-open reflex#7264 — #7215 review follow-ups: dead test statement, typed root default, document the `type(rx.State) is BaseStateMeta` contract
- STATE-35 (LOW (cosmetic)): open — deliberately not filed — Declaring `get_delta` on a State subclass is rejected; the error does not name the `_override_base_method` opt-in
- STATE-36 (LOW): filed-open reflex#7258 — An app package without `__init__.py` makes frontend and backend disagree on state names; every event is dropped with only a "no disp...
- EVT-08 (LOW): filed-open reflex#7248 (fix PR #7412 open) — A cancelled foreground `supersedes=True` handler loses all its writes under the Redis manager but keeps them in memory
- EVT-09 (MEDIUM): filed-open reflex#7246 (overload still at `reflex/app.py:1822` in v0.10.0) — `app.modify_state("<bare token>")` raises `ValueError: Invalid path: ('',)` (bare 500); the `token: str` overload is still un-deprec...
- EVT-10 (LOW): filed-open reflex#7251 — An `on_load`-started self-chaining loop keeps running after the client disconnects
- EVT-11 (LOW): filed-open reflex#7253 (PR #7436 open) — #6946 dedupe polish: uncached vars re-sent once after hydrate, dict key order defeats dedupe, dead `_UNKEYABLE_VALUE` branch
- EVT-12 (LOW): filed-open reflex#7254 — Withholding an async uncached var leaves its coroutine unawaited (`RuntimeWarning`)
- EVT-13 (LOW): open — not filed (cosmetic, 2026-10-07 decision) — ty rejects a 0-arg handler as `Callable[[], Any]`; fully applied 5-arg calls fail under pyright and ty
- EVT-14 (LOW): filed-open reflex#7478 — A background task completing after session expiry sends only the root delta; substate/ComponentState values stay stale
- EVT-15 (MEDIUM): filed-open reflex#7476 — A foreground handler that mutates then raises sends no delta; the change reaches the page only with the next unrelated event (unboun...
- EVT-16 (MEDIUM): filed-open as a comment on reflex#6122 (open); related reflex#7248 / PR #7412 — Default-config Redis rolls back a failed or superseded event, including changes already delivered to the browser (client/server dive...
- EVT-17 (LOW): filed-open as a comment on reflex#6122 (open) — A superseded (cancelled) handler's changes after its last yield are committed and ride in the superseding call's delta
- ENT-07 (HIGH): filed-open rxe#262 (a3 re-check commented; unchanged on a4/a5) — `/_reflex/cookies/sync` is registered lazily per worker; with several workers a cold worker answers 404/405, so OIDC token cookies a...
- ENT-08 (LOW): open — only a Linear draft (`[99] LINEAR_DRAFTS.md` ticket 5); rxe 0.9.7 `app.py` / `utils.py — rxe error paths call reflex's deprecated `console.*` helpers (DeprecationWarning noise on the login and prod gates)
- ENT-09 (LOW): filed-open rxe#226 — MCP `reflex://state/events/<unknown state>` returns an empty list instead of an error
- ENT-10 (LOW): open — maintainer: ignore (2026-09-11); not filed — A withheld protected **field** is served to MCP as its default with no signal
- ENT-11 (MEDIUM): filed-open rxe#227 and rxe#267 — `EventHandlerAPIPlugin` `/_reflex/events/openapi.yaml` returns 500 on a clean install (PyYAML not declared); index listed as `/index`
- ENT-13 (LOW): filed-open rxe#229 — MCP `search_events` advertises a `rest_path` that 404s without `EventHandlerAPIPlugin`
- ENT-14 (LOW-MEDIUM): filed-open rxe#230 — Logout from an iframed app never reaches the IdP `end_session_endpoint`
- ENT-15 (LOW): filed-open rxe#268 — Event API: malformed JSON → 500; handler argument errors → HTTP 200 with an error body
- ENT-18 (unknown): open — deliberately not filed (2026-09-22) — rxe writes the client token into OIDC error log lines
- ENT-19 (LOW): open — deliberately not filed — rxe depends on the private reflex helper `_override_base_method`
- ENT-26 (MEDIUM (P2)): filed-open rxe#254 (deferred by the user) — Prod `POST /_reflex/mcp` (no trailing slash) returns 405 before authentication
- ENT-27 (HIGH (P1, security)): filed-open rxe#245 (the 2026-10-05 release-gate HOLD) — A failing app reset during logout leaves protected state reachable by the next account on the same client session
- ENT-31 (MEDIUM): filed-open rxe#269 — React Flow controlled edits are reverted by a prod reload (mount-time `set_nodes` from prerendered defaults)
- ENT-32 (LOW): filed-open rxe#270 — ModelWrapper SSRM/infinite text filter leaves "Loading rows…" placeholders; infinite add dialog fails on a datetime field
- ENT-33 (LOW): filed-open rxe#271 — `rxe.mantine.autocomplete` has no `on_change` trigger
- ENT-34 (MEDIUM): filed-open rxe#263 — Background-task deltas on auth-protected states are withheld (placeholders), so the page never updates live
- ENT-35 (MEDIUM): filed-open rxe#264 — IdP signing-key rotation breaks every new login until restart (JWKS cached)
- ENT-36 (MEDIUM): filed-open rxe#265 — Expired (no refresh token) or IdP-revoked access tokens keep authorizing protected events (1800 s userinfo cache)
- ENT-37 (LOW): filed-open rxe#266 — An MCP handler denied by its token-scope check returns success (`is_error=false`)
- ENT-38 (LOW): filed-open rxe#272 — `rxe.map`: `LayersControl.BaseLayer`/`Overlay` not exposed (invalid JS, 500s), `on_layeradd` never fires, `id=` sets no DOM id
- ENT-39 (LOW): filed-open rxe#275 — After the #7493 boot reconcile signs a stale tab out, the protected page stays open with blanked values instead of redirecting to login
- ENT-40 (MEDIUM): filed-open rxe#274 — Auth + Redis: client-side navigation (or a second `sync=True` tab) overwrites a signed-in user's protected LocalStorage/Cookie value...
- PKG-04 (LOW): filed-open reflex#7088 — `uv` cannot build/install the `reflex` sdist (root pyproject ships `tool.uv.sources` / workspace)
- PKG-07 (LOW): open — accepted as not practically fixable (2026-09-11); reflex-otel 0.2.0 still depends only — Installing reflex-otel next to an older reflex silently upgrades reflex-base under reflex's exact pin
- PKG-10 (MEDIUM (P2)): open — ignored at the user's direction; not filed — Unique UUID callable-default backfill of existing rows fails (`IntegrityError`: every row gets the same evaluated default)
- PKG-12 (LOW): open — not filed (installer side effect) — A fresh Bun install with a neutral `REFLEX_DIR` appends PATH setup to the user's shell profile
- PKG-14 (LOW (cosmetic)): open — deliberately not filed; still at `reflex_base/constants/installer.py:151` in v0.10.0 — Generated `package.json` pins `"mergician": "v2.0.2"` (leading `v`)
- PKG-15 (LOW): open — not filed (cosmetic) — The `rx.Model` deprecation warning location points into pydantic internals
- CLI-09 (LOW): filed-open reflex#7266 — Clean shutdown logs granian's `[ERROR] Unexpected exit from worker-1`
- CLI-11 (LOW): filed-open reflex#7092 — `reflex cloud regions/vmtypes --json` exit 0 with `[]` after a 403; `cloud config --json` reports success without PyYAML
- CLI-15 (MEDIUM): filed-open reflex#7485 (clean on macOS a1/a2) — Linux: `reflex run` under npm is still alive 30 s after SIGTERM with no TTY and orphans the node dev server
- CLI-17 (LOW): filed-open reflex#7245 (v0.10.0 still catches only `FileNotFoundError`/`JSONDecodeError`/`Permi — A non-UTF-8 stateful-pages marker permanently wedges backend startup
- CLI-18 (LOW): open — deliberately not filed; `reset_disk_state_manager()` still called at `reflex/reflex.py — `reflex run` deletes `.states/` at startup in prod too; disk-backed state never survives a restart
- CLI-19 (LOW): filed-open reflex#7252 — Dev `reflex run` prints "Backend running at …" after the app module failed to import
- CLI-21 (LOW): open — not filed (cosmetic) — #7093's "Preferring npm" notice is printed twice
- CLI-22 (LOW): filed-open — tracked by existing reflex#5534 and reflex#5394 (both open) — A stale frontend left open across an upgrade gets no user-visible version-mismatch signal
- CLI-24 (LOW): filed-open reflex#7479 (A3-05 symptom and import-first workaround added as a comment) — AppHarness: the same multi-module app cannot be restarted in one process; a second app sharing a package's states loses its handlers...
- CLI-25 (LOW): filed-open reflex#7480 — npm: source-only hot reloads still reinstall packages (`devDependencies: {}` vs absent key)
- CLI-26 (LOW): filed-open reflex#7509 — `reflex run --json` ignores SIGINT sent to its pid; under supervisord `stopsignal=INT` the app is orphaned and blocks the restart
- CLI-27 (LOW): filed-open reflex#7510 — #7428's 30 s drain cap ends the `--json` stream mid-record; a consumer that stops reading blocks shutdown forever
- CLI-28 (LOW (P3)): filed-open reflex#7432 — Hosting CLI: an initial rejected token with `--no-interactive` omits the `reflex login` hint the changelog promises
- CLI-37 (LOW): open — out of scope for #7086; not filed — reflex-otel: without `OTEL_EXPORTER_OTLP_PROTOCOL`, the SDK configuration error is logged and swallowed while otel reports enabled (...
- CMP-13 (LOW): filed-open reflex#7098 — Radix pages emit Emotion `:first-child` SSR console errors in dev
- CMP-14 (LOW): filed-open reflex#7099 — Moment locale imports log duplicate `defineLocale` deprecation warnings
- CMP-15 (LOW): filed-open reflex#7100 — Unsupported `rx.moment` props silently become CSS
- CMP-18 (LOW): filed-open reflex#7102 — Adding `rx.toast.provider` renders every toast twice
- CMP-23 (LOW): open — not filed — `frontend_path` validator still accepts Windows reserved device names (`/con`)
- CMP-26 (LOW): open — maintainer: ignore (2026-09-11); not filed — `add_custom_code` touching `window` breaks `reflex export` with an opaque prerender 500
- CMP-28 (MEDIUM): filed-open — not filed by QA; the same defect is tracked as reflex#7426 (open; PR #7442 open) — `rx._x.client_state(…, global_ref=False)` throws `ReferenceError` once memoization splits reader and writer
- CMP-29 (MEDIUM (P2)): filed-open reflex#7430 — `rx._x.code_block(use_transformers=True)` emits an empty Shiki transformer list
- CMP-30 (LOW): filed-open reflex#7250 — `on_click` on a button inside `rx.dropdown_menu.trigger` never runs (upstream Radix pointer handling)
- CMP-32 (LOW): filed-open reflex#7255 — `_app_root` nests every app wrap in the previous one; a wrap ignoring its children swallows all lower-priority wraps (general form o...
- CMP-33 (LOW): open — deliberately not filed (2026-09-22) — `rx.vars.use_id()` in an `rx.foreach` body returns one id for every item (docs gap)
- CMP-34 (MEDIUM): filed-open reflex#7244 — `rx.upload_files()` from a toast action or `call_script` callback throws `filesById is not defined` (the case #7156's changelog names)
- CMP-35 (LOW (perf)): filed-open reflex#7262 — `frontend_lazy_bundled_libraries=True` added ~65 KB of initial JS on every page of the test app
- CMP-36 (LOW): filed-open reflex#7249 — CDN fallback URL for an unbundled sub-path `@rx.dynamic` import is malformed (`…/+esm/dist/esm/icons/bug.mjs`)
- CMP-39 (LOW (cosmetic)): open — deliberately not filed — `rx.accordion.root(collapsible=True, type="multiple")` triggers a dev React warning
- CMP-40 (MEDIUM (P2)): filed-open reflex#7429 (fix PR #7441 open) — A 1,500-State app builds but renders blank (React mutation-traversal stack overflow)
- CMP-41 (MEDIUM (P2)): filed-open reflex#7431 — Primitive Progress updates visually but stays indeterminate to accessibility tools (Root lacks value)
- CMP-43 (LOW): filed-open reflex#7489 — `PageContext.get()` outside a context raises a bare `LookupError` (ContextVar repr only)
- CMP-44 (LOW): open — not filed (only seen with reflex-clerk) — React 19.3 logs an extra "script tag while rendering" console error when a route module fails to load
- CMP-45 (MEDIUM): open — not filed — DataEditor data callback escapes the `rx.foreach` scope: zero editors render, page falls into the error boundary
- CMP-46 (MEDIUM): open — not filed — Starting a DataEditor edit by typing loses the leading characters
- CMP-47 (MEDIUM): open — not filed — DataEditor with `on_delete` bound throws `TypeError: undefined.length` and never clears the cell
- CMP-48 (LOW): open — not filed — Escape right after opening a single-image preview leaves the carousel open
- CMP-49 (LOW): open — not filed — Radix form controls' synthetic clicks throw `undefined[0]` when a DataEditor is on the page
- CMP-50 (LOW): filed-open reflex#7481 — String Vars use UTF-16 code units; a split surrogate pair in prerendered HTML triggers React #418
- CMP-51 (LOW): filed-open reflex#7482 — `window.onerror` throws when the error event has no Error object (ResizeObserver loop), so nothing reaches `handle_frontend_exception`
- TP-01 (MEDIUM): filed-open chat#61; not re-tested on 0.10.0 final (see upgrade guide on shared `.default`) — reflex-chat `initial_messages` leaks messages across sessions (mutable `Field.default` shared by every instance)
- TP-02 (LOW): open — not filed (no access to those repos) — `reflex run --env prod` fails to build any app with a reflex-monaco, reflex-webcam or reflex-clerk page
- TP-03 (LOW (downstream)): open — not filed; package needs `ClassVar`; candidate for a known-incompatible list — reflex-clerk 1.0.3 on 0.10: class-level backend-var read returns `Field` (`set_clerk_session` TypeError) and its class writes raise ...
- TP-04 (LOW (P3)): filed-open examples#324 — Overkey example: Reset keeps the typed client-state input
- TP-05 (LOW): open — not filed (reflex-examples not reachable from the QA sandbox) — form-designer: `/form/<id>` places `rx.form.message` outside `rx.form.field` and crashes; no login auto-redirect
- TP-06 (LOW): open — not filed — upload example: dependency-less cached `@rx.var files()` never refreshes
- TP-07 (LOW): open — not filed — basic_crud, twitter and data_visualisation examples ship no alembic directory
- TP-08 (LOW): open — not filed (example-app logic) — reflexle example discards its "Invalid word" / "already guessed" toasts
- TP-09 (LOW): open — not filed (example-app bug) — basic_crud: `GET /products/<missing id>` returns 200 with a serialized HTTPException
- DOC-03 (LOW): open — not filed; v0.10.0 reflex-base CHANGELOG still lists them under v0.9.9.post1, v0.9.10. — reflex-base's changelog re-lists the two #6933 entries under three versions
- DOC-04 (LOW): filed-open reflex#7260 — 0.9.12 changelog: the #7132 `_get_was_touched` entry describes unreachable behaviour; #7115's `hasattr`/`getattr` change undocumente...
- DOC-05 (LOW): filed-open reflex#7261 — `frontend_path` is applied only through `rx.asset()`; a literal `src="/…"` silently 404s; undocumented
- DOC-06 (LOW): open — deliberately not filed — `rx.asession()` requires `async_db_url`; nothing in the docs says so
- DOC-08 (LOW (P3)): open — ignored at the user's direction; both links are still in reflex v0.10.0 CHANGELOG ("Da — Changelogs link wrong targets: the callable-default migration entry links issue #6706 (implementing PR is #6770); rxe's AG Grid entr...
- DOC-12 (LOW): open — not filed; sentence still at `docs/changelog/upgrading/upgrading-to-0-10.md:72` in v0. — Upgrade guide says assigning `State.__fields__["items"].default = []` "was safe" on 0.9 — false (0.9.12 shared the list across ses...

## 3. Registry items touching the areas changed in reflex 0.11.0a1

Items are registry IDs unless marked (FINDINGS) = from the 0.10.1a1 FINDINGS, not in REGISTRY.md. Verify 0.11.0a1 against these.

- **Database / alembic / migrations / rx.Model / sqlmodel:** PKG-08 (fixed, cap lifted), PKG-09 (fixed; stock 0.9.x still broken), PKG-02, PKG-13 (fixed), PKG-10 (open, MEDIUM: UUID callable-default backfill IntegrityError), PKG-15 (open, cosmetic), STATE-20 (documented: 0.9/0.10 stores), STATE-21 (filed-open reflex#7491: hash depends on Python version, resets sessions), DOC-06 (open: `rx.asession()` needs `async_db_url`), DOC-09 (fixed), TP-07 (open: example apps lack alembic dirs).
- **client_state:** CMP-28 (filed-open reflex#7426, MEDIUM: `client_state(global_ref=False)` ReferenceError once memo splits reader/writer), CMP-24 (unknown, MEDIUM: ClientStateVar work claimed to address it), TP-04 (filed examples#324).
- **Browser storage (LocalStorage / Cookie / SessionStorage):** HYD-03 (filed reflex#7484: dropped computed-var write depends on PYTHONHASHSEED), HYD-05 (filed reflex#7486, MEDIUM: >1 MB value reconnect storm), HYD-10 (filed #7508, perf: storage cvs evaluated twice), HYD-11 (open by design: earlier sync write wins), HYD-12 (open: `remove_local_storage` syncs null), HYD-13 (filed #7506), HYD-14 (unknown, MEDIUM claim), HYD-07 (unknown), STATE-22 (filed #7498), STATE-23 (filed #7499), DOC-11 (documented, per-instance storage key), ENT-39, ENT-40 (MEDIUM, auth + Redis overwrites protected storage with ""), ENT-41 (unknown), ENT-27 (HIGH security, rxe#245: protected state reachable after failed reset). (FINDINGS) R101-15 non-str storage vars log per instantiation; R101-16 background rehydrate leaves storage at defaults.
- **CORS / deploy_url:** no REGISTRY row and no fixture. Nearest (FINDINGS): R101-09 `trusted_proxy_hops` uses the XFF token verbatim (LOW); #7614 spoofed XFF ignored by default (verified fixed). R101-07 rxe REST takes leftmost XFF as `client_ip` (MEDIUM, fixed in rxe 0.9.10a1).
- **Event handlers / @rx.event:** EVT-08 (filed #7248), EVT-09 (filed #7246, MEDIUM: `modify_state("<bare token>")` 500), EVT-10 (filed #7251), EVT-11 (filed #7253), EVT-12 (filed #7254), EVT-13 (open: ty rejects 0-arg handler), EVT-14 (filed #7478), EVT-15 (filed #7476, MEDIUM: mutate-then-raise sends no delta), EVT-16 (filed comment on #6122, MEDIUM: Redis rollback diverges client/server), EVT-17 (filed #6122), EVT-18 (documented: inherited writes in background tasks), STATE-10 (filed #7459), STATE-06 (open, disputed deps=["router"]), CMP-30 (filed #7250: on_click in dropdown trigger), CMP-34 (filed #7244, MEDIUM: `rx.upload_files()` from toast). EVT-03 and EVT-07 are fixed.
- **Redis state manager / locks:** EVT-16 (MEDIUM, above), EVT-08, EVT-17, HYD-07 (unknown, Redis token reassigned after pyo3 panic), STATE-20 (mixed old/new Redis workers lose backend mutations), EVT-04 (fixed; re-verify item 12), ENT-40, ENT-39, and HYD-16 (filed #7247, HIGH rated 911: `backend_state_mismatch` latch).
- **foreach hooks:** CMP-24 (unknown, MEDIUM: hook component in `rx.foreach` throws ReferenceError and blanks page), CMP-33 (open: `use_id()` in foreach returns one id; docs gap), CMP-45 (open, MEDIUM: DataEditor callback escapes foreach scope, zero editors render), CMP-46/47 (open, MEDIUM: DataEditor edit / on_delete TypeError; adjacent).
- **Memoization / auto-memo / React compiler:** CMP-27 (unknown, MEDIUM: memo module names not reproducible), CMP-28 (above), CMP-20 (fixed), CMP-03 (fixed). (FINDINGS) R101-01 (MEDIUM regression in 0.10.1a1: AG Grid edit leaves memoized `rx.memo` consumers stale; rxe 0.9.10a1 fixes the grid, mechanism open for non-AG-Grid components that mutate state objects), R101-08 (LOW: React Compiler silently skips many generated components; docs overclaim), R101-22 (LOW-MEDIUM: recharts deep-freezes shared state).
- **Upload:** CMP-01 (fixed; re-verify 17), CMP-34 (filed, MEDIUM, above), TP-06 (open: cached `files()` var never refreshes). (FINDINGS) R101-13 empty checkbox group yields `[None]` in FormData.
- **reflex run shutdown / signals:** CLI-15 (filed #7485, MEDIUM: Linux npm `reflex run` alive 30 s after SIGTERM, orphans node), CLI-26 (filed #7509: `--json` ignores SIGINT to pid; supervisord stopsignal=INT orphans app), CLI-27 (filed #7510: 30 s drain cap truncates `--json` record), CLI-09 (filed #7266), CLI-19 (filed #7252), CLI-18 (open: `.states/` deleted at startup in prod too), CLI-36 (unknown). Fixed and re-verify-worthy: CLI-07 (#7328), CLI-08, CLI-16 (item 11). (FINDINGS) R101-02 fork preload kills import-time threads in `--backend-only` prod and on Python 3.14 (LOW, scoped regression); R101-10 deploy hides scaling-retry progress; R101-11 directory symlink crashes `reflex export`.
- **lifespan / api_transformer:** no REGISTRY row for api_transformer. Lifespan config is covered by `class_state/apps/lateapp` (A5-01 row: 0.10.0 renders `|`, `<empty>` for class-body defaults). Adjacent API-plugin rows: ENT-11 (filed rxe#227/#267, MEDIUM: openapi.yaml 500 without PyYAML), ENT-13 (filed rxe#229), ENT-15 (filed rxe#268: malformed JSON → 500, arg errors → HTTP 200).
- **Enterprise (reflex-enterprise) compatibility:** open/filed items: ENT-07 (HIGH, rxe#262: cookie sync 404/405 on cold workers, lost OIDC cookies), ENT-27 (HIGH security, rxe#245: release-gate HOLD), ENT-26 (rxe#254: prod MCP 405), ENT-31, ENT-34 (rxe#263: protected background deltas withheld), ENT-35 (rxe#264: JWKS cache breaks new logins), ENT-36 (rxe#265: revoked tokens keep authorizing), ENT-37, ENT-38, ENT-14, ENT-32, ENT-33, ENT-09, ENT-10, ENT-18, ENT-19, ENT-08, ENT-23. (FINDINGS) R101-07 rxe REST leftmost XFF (MEDIUM, fixed in rxe 0.9.10a1); R101-21 MCP OAuth consent race on Redis (LOW).

## 4. Fixture areas: contents, run commands, expected results

Conventions for all areas: run from a copy (`cp -r <area> $SB/apps/<area>/src` or the area's stage script), never from a checkout; `SB` and venv names under `$SB/envs`; drivers need `$SB/envs/driver` (Playwright; Chromium `/opt/pw-browsers/chromium`).

**hydration/** (browser storage, sync=True, router data, reconnect, prenav). Commands above in section 1 (items 1, 2, 5); full run `scripts/run_area.sh quick` (~10 min) / `full` (~2 h), with `NEW=<venv>`, optional `PREV=rel`. Expected on 0.10.0 (= a5): run_f002 prod: only `theme=system` written, boot `is_hydrated` false then true; run_storm 0/3 storms, 7 tabs one value; run_stamp2 0/3 storms, one value; run_rtr 0 secrets in frames/DOM/console, `steps A=37 B=37`; run_cv matches the expected summary line for line. Known: `/favicon.ico` 404; A4-03 earlier write wins (by design). Ports: explorer 3140-3159 / 8140-8159 (Redis 8149); race/verifier 3660-3679 / 8660-8679 (Redis 8669, CDP 8670).

**class_state/** (state class model, #7519 copy-at-definition, field API, N-004 store compatibility). Run: `bash $CS/bin/run_python_suite.sh $NEW` (≈4 min; diff against `$PREV`); `bin/n004_matrix.sh`; `bin/n004_redis_chain.sh`; e2e: `bin/start_app.sh $NEW $W/run/cse2e-dev 3300 8300 <log> --loglevel debug` then `bin/drive_cse2e.py`, `bin/hot_reload.py`; prod+Redis on 3301 with `REFLEX_REDIS_URL=redis://localhost:8309`. Expected on 0.10.0: pytest `test_moot` 25 passed, `test_converted` 25 passed, `test_n039_fields` 204 passed / 1 skipped (210 with `DOWNSTREAM=1`), `test_undo_edge` collection ERROR by design (moot); `probe_copydef` snapshot semantics (a1 `[]`, a2 `{}`); `probe_lock_tree` `cannot pickle '_thread.lock'`; `adv7495` 12000 TypeErrors, final count 0; n004 schema hash identical 0.10.0 vs a5. Ports: frontend 3300-3339, backend 8300-8339, Redis 8309.

**enterprise/** (reflex-enterprise: OIDC, MCP, AG Grid, demos, reflex-azure-auth). Venvs: `ENT_NEW` = reflex + `reflex-enterprise[mcp]` + `oidc-provider-mock`; `DRV_VENV=driver`; `ENT_DRV=ent-drv` (`auth/bin/build_ent_drv.sh`). Enterprise wheel: an offline wheel under `$SB/downloads/` installed by path, or the PyPI wheel. The PyPI wheel refuses `--env prod` / export for anonymous users even with `CI=true`; `lib.sh acct_stub` runs a loopback account stub on 127.0.0.1:8639 (set `ENT_ACCOUNT_STUB=0` for offline wheel or real login). Every start script exports `CI=true` (skips cloud login only). Demos (ag_grid, dnd, flow, mantine, map, highcharts, tickets) are NOT in the repo or the wheel: `grid/bin/fetch_demos.sh <reflex-enterprise checkout>` (default `$ENT_REPO` = `/home/user/reflex-enterprise`, tag of the release under test). Upstream auth tests: `auth/a4auth/fetch_upstream.sh <checkout>`. Full run: `auth/bin/seq_ent_auth.sh $ENT_NEW new 123`, `seq_n032_prod.sh`, `seq_deeplink.sh`, `seq_ent_extra.sh`, `seq_vea.sh`, `seq_n033.sh`, `expiry_matrix.sh` (infra on), `grid/bin/seq_grid.sh $ENT_NEW new 12`, `build_demo_venv.sh` + `ag_demo.sh`, `azure/bin/run_az.sh compact-enterprise-az new dev,prod`. Expected on 0.10.0 + rxe 0.9.7 (PyPI): N-032 stale 3/3 each, away 3/3, xtab 3/3 with 0 accepted; a4 auth matrix 36/36 + MCP; deeplink A-G 3/3; N-025 grid s1-s13 2h/6c, aggrid_min 4/4; dnd 27/27; mantine 23/23 + 1 page error (N-028, known); azure A/B/C pass dev+prod. Not re-run in the 0.10.0 curation: expiry, prod_suite, MCP entauth Redis, vauthx/vea (A3-09/10), N-033, maps, coregd/corev, flow, AG Grid demo, highcharts/tickets/rxeapp (a2 record only). Benign: AG Grid trial banner, favicon 404, OSM tile blocks.

**upgrade/** (installs, in-place upgrades of reflex-examples apps, third-party sweep, events suite, CLI lifecycle, guide, smoke). Pinned upstream: reflex-examples `ebe19ff00dfee36f9d67a9a584840c6745950b05`; third-party demos masenf/reflex-local-auth `a61d50d8`, reflex-magic-link-auth `352c675b`, reflex-google-auth `753a0298`; 22 packages in `tp/packages.txt`. Fetched and patched by `bin/stage.sh` (`EXAMPLES_SRC`/`TP_SRC` = existing clones). In-place upgrade apps: form-designer (`fd`, reflex[db] + reflex-local-auth 0.5.0; base 0.9.12 with `BASE_EXTRA='sqlalchemy<2.1'`), github-stats (`gh`), twitter-redis (`twr`, prod + Redis, includes rollback), clock (`ck`), twitter (`tw`, dev disk state), and `seq_app.sh` for counter, reflexle, lorem-stream, local-component, quiz, snakegame, nba, upload (last run at a1/a2). Driver: `up/bin/build_base_venvs.sh key:app && up/bin/seq_<x>.sh`; run in order `seq_fd`, `seq_gh`, `seq_twr`, `seq_ck`, `seq_tw`. Install paths: `inst/bin/n001.sh`, `dbcli.sh`, `prod_crud.sh`, `f014.sh`, `install_paths.sh`. Third party: `tp/bin/build_venv.sh`, `tp/probes/import_sweep.py` + `cmp_sweep.py` (22/22 SAME), `tp/bin/seq_tp.sh` (local-auth 36/38, magic-link 10/11), `tp/bin/run_google.sh` (12/13). Events: `events/bin/start.sh $NEW dev new_dev evapp`, `wait_up.sh`, `suite.sh new_dev http://localhost:3460 8460` (63 checks; a3 == a2). Lifecycle: `lifecycle/bin/json_matrix.sh new $NEW INT-group:40 TERM-pid:40 TERM-pid:6 INT-pid:40`, `lifecycle/bin/f007.sh` (npm SIGTERM, Linux). Guide/smoke: `guide/bin/probe.sh`, `seq_guide.sh`, `smoke/bin/seq_smoke.sh`. Expected on 0.10.0 (re-validated): fd 0.9.12 → 0.10.0 identical to a5 (base 18/0/2, up 12/0/1, prod 12/0/1 / 15/0/0, cold 12/0/1; no new migration revision); tp import 22/22 SAME; local-auth 36/38 (known `_validate_fields` pair); n001 pip311 `reflex[db]==0.10.0` clean; f014 F-014 pass. Pre-0.10 control (per README): events, lifecycle and twitter-redis rollback (11/1/2 is the driver's known "every session resets" expectation). F-007 (npm SIGTERM orphan) still present on Linux (last a2).

## 5. Port map (fixtures/README.md, "Ports")

| area | frontend | backend | Redis / helpers |
|---|---|---|---|
| orchestrator preflight | 3100-3119 | 8100-8119 | - |
| hydration | 3140-3159 (race/verifier 3660-3679) | 8140-8159 (8660-8679) | Redis 8149 (`REDIS_PORT`), 8669 (`VREDIS_PORT`), CDP 8670, latency proxy 8661/3663 |
| class_state | 3300-3339 | 8300-8339 | Redis 8309 |
| enterprise | 3600-3639 | 8600-8639 | Redis 8629, mock IdP 8638, account stub 8639 (127.0.0.1) |
| upgrade | 3460-3519 | 8460-8519 | Redis 8469 (events), 8499 (twitter), 8509 (lifecycle/guide); supervisord RPC 8519 |

Rules: `bin/start_app.sh` (class_state) and `srv.sh` (hydration) refuse ports outside their range; one app server set at a time; independent verifiers take a free range inside the area (e.g. 3320-3339, 3660-3679); every runner stops what it started and `bin/ports.sh` (upgrade) must print "no listeners" at the end. Granian warns about worker count with Redis (benign). Clean up `.web/` and `node_modules` in run copies.

## 6. Latest release state (from the FINDINGS and NOTES, for context)

0.10.0 is the registry baseline. 0.10.1a1 (2026-10-23) and 0.10.1a2 (2026-10-26) were checked on top: R101-04 (sibling floors) fixed in a2; R101-01 (memo staleness after AG Grid edit) fixed in rxe 0.9.10a1 but mechanism open for other components; R101-07 and R101-22 fixed via rxe 0.9.10a1. Severity 1 medium regression, 19 low, 0 high/critical.
