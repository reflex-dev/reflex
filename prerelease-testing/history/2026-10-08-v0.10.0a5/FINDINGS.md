# Findings — final pre-release pass on reflex 0.10.0a5 / reflex-base 0.10.0a5 (+ reflex-enterprise 0.9.7a5), 2026-10-08

**Status: FINAL.** Previous passes: [../2026-10-08-a4/](../2026-10-08-a4/FINDINGS.md),
[../2026-10-07-a3/](../2026-10-07-a3/FINDINGS.md), [../2026-10-07/](../2026-10-07/FINDINGS.md). Context:
[CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md).

## Versions under test
- reflex 0.10.0a5 + reflex-base 0.10.0a5 (tag `v0.10.0a5` = `57aee8ccf`); a4 → a5 is exactly #7519, #7360 and #7504
  (#7504 touches only the unpublished `reflex-components-internal`).
- reflex-enterprise 0.9.7a5 (offline wheel; still the newest on PyPI).
- Baselines run back to back on the same machine: 0.10.0a4 (previous alpha), 0.9.12 (stable), and the version each
  re-verified regression was broken on (0.10.0a1 / a3) as the positive control.

## Pre-flight (`preflight/`)
20/20 packages published with wheel + sdist; reflex pins `reflex-base==0.10.0a5`; the a5 source files are byte-identical
in the installed wheels; `.pyi` audit PASS (122 stubs); blank app clean in dev and prod. Changelogs carry #7360
(deprecation + bug fix) and #7519 (feature); the a4 #7516 entry now reads `set_default(10)`.

## Re-verification table — every identified-and-fixed regression of the 0.10 train, on a5
| id (pass found) | what | positive control | a5 result | evidence |
|---|---|---|---|---|
| F-002 (a1) | first load writes client-storage defaults | a1 prod writes 8 LS/SS/cookie keys | **fixed**: fresh profile writes nothing (dev, prod, prod + Redis); returning visitor gets new defaults | `a5_hydration_router/results/p2/` |
| F-003 (a1) | computed var rewriting storage at hydration lost | a1 cvstore a/b/g `[l='bad']` | **fixed**: cvstore a–j = the fixed a3 baselines (dev seeds 0/4, prod); google-auth bogus token cleared (0.9.12 keeps it) | `a5_hydration_router/` |
| F-004 / N-039 / A3-01 (a1–a3) | class assignment / patch of a var | a3 test_undo_edge 4F/4P, test_v7_undo 4F/16P | **fixed**: assignment and class patching raise the actionable TypeError (now naming the declaring state); field patching 204/204 (210 with downstream) on 3.11/3.12/3.14 | `a5_class_state/` |
| N-005 / A3-02 (a2–a3) | storage default dropped | a3 None/int drop storage | **fixed**: `set_default(rx.LocalStorage(..., name=...))` keeps storage, name, options; e2e dev + prod/Redis 9 workers 28/28 | `a5_class_state/apps/c5e2e` |
| A3-04 (a3) | thread-stress assign/restore | a3 count 10589 | **fixed**: 12000 TypeErrors, count 0; `set_default` stress ends on the declared defaults | `a5_class_state/` |
| N-008 (a2) | dev guard accepts `_x__y` | — | **fixed** (output identical to a4, dev and prod) | `a5_class_state/` |
| N-004 (a2) | state-store compatibility | — | **as documented**: schema hash a5 == a4 == a3; a5 ↔ a4 ↔ a3 pickle / disk / Redis interchange; 0.9.12 → a5 loads | `a5_class_state/` |
| A3-11 (a3) | `sync=True` boot-echo storm | a3 3/4 dev, 3/3 prod storms | **fixed**: a5 0/5 dev, 0/4 prod; all tabs + localStorage on the last value | `a5_hydration_router/` |
| A3-12 (a3) | on_load stamp loop | a3 2/2 dev, 2/2 prod | **fixed**: a5 0/3 dev, 0/3 prod, one value | `a5_hydration_router/` |
| A4-01 / A4-02 (a4, not fixed) | substate `add_var` / auto-setter collisions | — | **unchanged** (message text changed by #7519 only) | `a5_class_state/` |
| N-032 (a2) | OIDC cross-tab logout | a2 + ent a4 (earlier passes) | **fixed**: vdrv stale P1–P4 / away / xtab 3/3 each, 0 accepted after logout, dev + Redis and prod 1 worker; entauth suites ALL_PASSED; = a4 back to back | `a5_upgrade_ent/ent/auth/` |
| N-025 (a2) | prod AG Grid Var `column_defs` | ent a4 (earlier passes) | **fixed**: entv prod s1–s13 byte-identical to the a4 pass; aggrid_min 4/4 | `a5_upgrade_ent/ent/grid/` |
| N-001 (a2) | `reflex[db]` without greenlet | a2 | **fixed**: fresh `reflex[db]==0.10.0a5` on 3.11 and 3.14, pip (no `--pre`) and uv, nothing added: greenlet 3.5.6 via the extra; `reflex db init/makemigrations/migrate` rc 0; prod CRUD | `a5_upgrade_ent/inst/` |
| F-005 (a1) | sqlmodel cap | a1 | **fixed**: sqlmodel 0.0.48 + SQLAlchemy 2.1.4; migrations apply on a fresh db | `a5_upgrade_ent/inst/` |
| F-006 (a1) | component floors | a1 | **fixed**: `pip install reflex==0.10.0a5` without `--pre` resolves the full train (uv still needs `--prerelease=allow`, as on every alpha) | `a5_upgrade_ent/inst/` |
| F-014 (a1) | `reflex component` message | a2 | **fixed**: every form exits 1 with the wrapping-docs + component-template pointer; hidden from `--help` | `a5_upgrade_ent/inst/` |

## Spot check of the a5 changes
- **#7360 (router data, security)** — works as claimed, no functional regression (`a5_hydration_router`). The backend's
  `self.router` view in every on_load flavour (single, list, other-state handler, yield chain, returned event, background
  task, redirect + 2-hop chain, `/post/[slug]`, `[[...splat]]`, frontend events in on_load, reload, client nav,
  back/forward, two tabs, `update_vars_internal`, hot-reload reconnect) is field-for-field identical a4 vs a5 in dev (37
  steps), prod (35) and prod + Redis with 9 workers (35, full loads on 8 different pids); the server still sees the plain
  and HttpOnly cookies and the credential headers, also after a Redis round trip on another worker. Security: a4 leaks all
  10 test secrets (cookie, HttpOnly cookie, Authorization, Proxy-Authorization, Cf-Access-Jwt-Assertion,
  X-Forwarded-Access-Token, X-Auth-Request-Access-Token, X-Amzn-Oidc-Accesstoken / -Data, X-Goog-Iap-Jwt-Assertion) into
  websocket frames and the DOM; a5 has 0 occurrences in frames, prerendered HTML, DOM and console (dev, prod, prod +
  Redis). `State.router.headers.cookie` / `["cookie"]` render "" with a compile-log deprecation per call site;
  `raw_headers` lose exactly the 9 filtered names. reflex-local-auth 36/38 (known) + 14/14 storage; google-auth guard
  path unchanged. Enterprise (`a5_upgrade_ent`): auth matrix 36/36 + MCP OAuth + anonymous MCP (api-token /
  `persist_router_data` path), expiry / proactive refresh / revoke, a new deep-link probe (`/vault?x=1&y=two%20words` →
  login → back on the same URL; dynamic routes; anonymous client nav keeps `redirect_to`; every on_load sees its own url /
  query / params / host / client_token / session_id; logout re-protects) and audit page_load routes all equal a4 and
  0.9.12; the only difference is the intended one — the HttpOnly `_oidc_*` id/refresh token cookies reach the browser in
  `rx_router_headers` on a4 / 0.9.12 and never on a5, while server-side cookie reads still work. reflex-azure-auth 0.1.2
  (on_load callback reading `router.url.query_parameters`) against the mock IdP passes on a5 and a4. No component-side use
  of `router.headers.cookie` / `raw_headers` in 38 downstream wheels, the auth packages or reflex-examples.
- **#7519 (`Field.set_default`, copy at definition, error owner)** — `set_default` and every docs sample work as
  documented; the TypeError names the declaring state (substates, grandchildren, mixins, ComponentState) and its
  suggested fix works e2e; hot reload, AppHarness, 22-package sweep = a4; all 112 enterprise modules import. One medium
  and four low findings: A5-01 … A5-05.

## New findings on 0.10.0a5

### A5-01: A mutable class-body default populated after the `class` statement is snapshotted at class definition; later additions are silently lost (MEDIUM, regression vs a4 and 0.9.12; CONFIRMED and narrowed by independent verifier)
- Item `a5_class_state`. `OPTIONS = []`; `class S(rx.State): options: list[str] = OPTIONS`; `OPTIONS.append("late")` →
  new sessions get `['late']` on 0.9.12 and a4, `[]` on a5. Same for a backend dict filled by a decorator / a later
  module import (registry pattern), a config object filled in a lifespan task, `default_value()` at UI build,
  `reset()`, substates, ComponentState, `add_var`, and the compiled initial state. E2E (`apps/lateapp`, Chromium):
  0.9.12 / a4 render `red,green|`, `plugin_a`, the config; a5 renders `|`, `<empty>`, `<empty>` — no error, no log line.
  Tests that `mock.patch.dict(MODULE_DEFAULTS, ...)` a module-level default are silently ignored on a5 (the remaining
  patch route now that 0.10 blocks class `setattr`). `rx.field(OPTIONS)` stays live on a5, so the two spellings differ.
- Cause: #7519 changed `_default_arguments` (`reflex_base/vars/base.py` ~4706) to
  `partial(copy.deepcopy, copy.deepcopy(value))`, so the class-body default is copied once when the class is created.
  The PR body mentions it in one sentence; no review thread or test covers it; not in either a5 changelog, base_vars.md or
  the upgrade guide.
- **Verification (`verify_class_state5`): CONFIRMED, NARROWED.** Only in-place mutation of the exact default object after
  the class statement is affected (rebinding the name never worked; data filled before the class is unaffected).
  0.9.12 was not uniformly live: it already snapshotted backend `rx.field(...)` defaults, and called a backend
  `default_factory` once — a4 was the first uniformly live version. No real-world hit found (6 GitHub code searches,
  reflex-examples, 37 downstream wheels, enterprise), so reach is low, but the failure is silent. Pydantic 2.13 keeps the
  live behaviour.
- Suggested fix (small): keep live semantics for class-declared defaults and copy up front only in `set_default` /
  `add_var` (a flag on `_default_arguments`) — this also resolves A5-02 and A5-04. Alternative: a breaking-change line +
  upgrade-guide note.
- Repro: `a5_class_state/probes/probe_copydef.py` (rows a1–a10, e14); `verify_class_state5/v1/probe_v1.py`,
  `v1/probe_patchdict.py`; e2e `a5_class_state/apps/lateapp` + `bin/drive_late.py`.

### A5-02: A frontend var whose default cannot be deep-copied gets an opaque `TypeError: cannot pickle '_thread.lock' object` instead of the clear `VarTypeError` naming the var (LOW, message regression vs a4 and 0.9.12; CONFIRMED)
- `class FeState(rx.State): holder: Holder = Holder()` (Holder holds a `threading.Lock`): every version fails at the class
  statement, but a5's deepcopy in the metaclass `__new__` runs before the `__init_subclass__` serializability check, so
  the user sees a copy.py traceback with no var name. Repro `a5_class_state/run/lockmod/fevar.py`. Fixed by A5-01's fix.

### A5-03: A backend var whose default cannot be deep-copied fails at import with a message naming neither the var nor the `ClassVar` fix (LOW, message only; RECLASSIFIED: not a regression vs 0.9.12)
- `_lock: threading.Lock = threading.Lock()`: 0.9.12 `reflex compile` exits 1 inside `compile_state` (the app could never
  start); a4 compiles and fails only on access to `_lock`; a5 exits 1 at import pointing at the user's class line.
  Failing fast is better; the message should name `Class._lock` and suggest `ClassVar` (the documented fix). Repro
  `verify_class_state5/apps/lockapp`, `a5_class_state/run/lockmod/mystate.py`.

### A5-04: Large mutable class-body defaults are deep-copied once more at import and the snapshot stays resident (LOW, performance, regression vs a4 only; CONFIRMED, narrowed)
- Class definition +0.26–1.1 s for 8–60 MB defaults (a4 / 0.9.12 ~1 ms); the snapshot lives in
  `Field.default_factory.args[0]` for the process lifetime: +1× the default's size while the user's module keeps its own
  reference (+36.7 MB for 200k rows, +50 MB for a 50 MiB array; 0 if the module drops it); paid per prod worker (2×CPU+1
  with Redis). With ≥ 1 in-memory session a5 uses no more memory than 0.9.12 (which copies a backend default twice per
  instance). Fixed by A5-01's fix. Repro `a5_class_state/probes/probe_large.py`, `verify_class_state5/logs/{time,mem}.txt`.

### A5-05: The upgrade guide says assigning `State.__fields__["items"].default = []` "was safe" on 0.9 — false (LOW, docs; CONFIRMED, refined)
- `docs/changelog/upgrading/upgrading-to-0-10.md`, "Assigning a state var through its class", last paragraph: "On 0.9,
  assigning `State.__fields__["items"].default = []` was safe, because each instance got a copy of the default." On
  0.9.12 a frontend list var's assigned default was the same object in every new session (leaked across sessions and into
  the caller's list; `reset()` restored the declared default), and a backend var's `.default` assignment was ignored
  entirely. The 0.10 half of the paragraph is accurate. Suggested rewording in `verify_class_state5/NOTES.md`.

### Pre-existing / informational (not caused by a5)
- An app package without `__init__.py` breaks every state update with a misleading "no dispatch function for
  substate(s)" console error (state names drop the module segment); identical on 0.9.12, a4, a5; `reflex init` always
  creates the file. Repro `a5_hydration_router/src_noinit`.
- #7360's frontend cookie deprecation warns only in the compile/server log, once per call site per compile, never in the
  browser; `raw_headers["cookie"]` / `["authorization"]` silently become undefined (documented in router_attributes.md);
  an event arg `State.router.headers.cookie` now delivers "". The deprecation names `deprecation_version="0.9.13"` inside
  a 0.10 alpha (fine if #7360 is also released in 0.9.13).
- Unchanged and filed earlier: A3-07, A3-08, A3-09, A3-10, A3-13, A4-01, A4-02, A4-03, N-026, N-028, N-033, reflex#7506.

## Install, upgrade and third-party (`a5_upgrade_ent`)
In place: form-designer (reflex[db] + local-auth), github-stats and twitter prod + Redis 0.9.12 → a5, and twitter a4 → a5
(only reflex + reflex-base move; `.web/package.json` unchanged; 0.9.12- and a4-pickled Redis sessions load) give exactly
the a4 pass's per-check results; cold rebuilds equal. 22-package import sweep = a4; reflex-local-auth 36/38 dev / prod /
prod + Redis, magic-link 10/11, google-auth 12/13 (known failures only). Demo smoke: dnd 27/27, flow 20/22 (N-026),
mantine 23/23 (+ N-028), map 4/4.

## Cluster summaries
- `preflight` — publish, wheel contents, `.pyi` audit, changelog, blank-app smoke: clean (`preflight/NOTES.md`).
- `a5_hydration_router` — #7360 verified (no regression; security claim holds with a4 as the leaking control); F-002,
  F-003, A3-11, A3-12 fixed with positive controls (`a5_hydration_router/NOTES.md`).
- `a5_class_state` — #7519 hunt: A5-01 … A5-05; every class-state regression fixed with positive controls; A4-01 / A4-02
  unchanged (`a5_class_state/NOTES.md`; verification `verify_class_state5/NOTES.md`).
- `a5_upgrade_ent` — enterprise, installs, upgrades, third-party: no new issue; N-032, N-025, N-001, F-005, F-006, F-014
  fixed (`a5_upgrade_ent/NOTES.md`).
