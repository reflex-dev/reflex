# Findings — re-verification on reflex 0.10.0a3 / reflex-base 0.10.0a3 + reflex-enterprise 0.9.7a5, 2026-10-07 (second pass)

**Status: IN PROGRESS.** Board: [board/](./board/). Protocol: [COORDINATION.md](./COORDINATION.md). Context: [CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md).
Previous pass (a2 train): [../2026-10-07/FINDINGS.md](../2026-10-07/FINDINGS.md), plan [../2026-10-07/RELEASE_PLAN.md](../2026-10-07/RELEASE_PLAN.md).

## Versions under test
- reflex 0.10.0a3, reflex-base 0.10.0a3 (`r/pre-2026.10.06-37579583012` @ `555b667c1`); all other train packages unchanged from a2.
- reflex-enterprise 0.9.7a5 (offline wheel `reflex_enterprise-0.9.7a5-0offline-py3-none-any.whl`, sha256 aad70d1a…; PyPI wheel 5e394ddb…).
- Baselines: reflex 0.10.0a2 (+ enterprise 0.9.7a4), reflex 0.9.12 (+ enterprise 0.9.7a5 / a4).

## Pre-flight (orchestrator)
- 19:25 UTC: `Release from changelog` run 37673748075 built reflex-base 0.10.0a3; its `publish` job waits for environment
  approval, so reflex / reflex-base 0.10.0a3 are not on PyPI yet (discovery script: 18/20 OK, the two a3 packages
  "NOT ON PYPI"). Agents started with positive controls on a2 / 0.9.12 meanwhile. After the maintainer approved the
  publish jobs, reflex-base 0.10.0a3 and reflex 0.10.0a3 (uploaded 19:51:42 UTC) resolved on PyPI at 19:52 UTC.
- 19:52 UTC: all 20 train packages published with wheel + sdist; `.pyi` audit PASS (122 stubs, wheel == sdist, counts match
  `pyi_hashes.json`, no foreign stubs). Published reflex 0.10.0a3 pins `reflex-base==0.10.0a3` exactly, so any install
  or upgrade of reflex a3 brings the reflex-base fixes with it. `db` extra: alembic, `greenlet>=3.3`, pydantic, sqlmodel.
- Blank-app smoke on a3 (`reflex init --template blank`, dev and prod): clean in Chromium.
- reflex-enterprise 0.9.7a5: the offline wheel and the PyPI wheel differ only in `constants.py` (`IS_OFFLINE = True`).
  a4 → a5 changes only `formatColumnDefs` in `components/ag_grid/aggrid.py` (the `typeof __reflex === 'undefined'` early
  return and the unused `jsx`/`Fragment` lookups are gone) plus the CHANGELOG entry (enterprise#260). Metadata unchanged:
  `reflex[db]>=0.9.6`, `Requires-Python >=3.10,<4.0`.

## Re-verification table (must-fix findings of the a2 pass)
| id | a2-pass status | a3 result | evidence | item |
|---|---|---|---|---|
| F-002 / F-003 (a2-pass fixed; #7493 risk) | fixed in a2 | **still fixed**: positive controls catch 0.10.0a1's 8-key write-back and F-003 cases; a3 fresh profiles write nothing (dev, prod, prod/Redis; LS, SS, cookie options, `sync=True`, substates, ComponentState, local-auth, google-auth); cvstore a–j identical to a2 on seeds 0/4 | `a3_hydration/NOTES.md` | a3_hydration |
| N-001 greenlet missing from `reflex[db]` | HIGH, all fresh installs | **fixed**: fresh `reflex[db]==0.10.0a3` with uv and pip on 3.11–3.14 resolves greenlet 3.5.6 + SQLAlchemy 2.1.4 through the extra (8/8); `rx.Model`, `reflex db init/makemigrations/migrate` and prod CRUD work | `a3_preflight/logs/03-*`, `04-*`, `dbcli-prod.*` | a3_preflight |
| N-025 prod AG Grid Var `column_defs` empty | HIGH regression | **fixed with reflex a3 + enterprise 0.9.7a5** (enterprise-side fix): verifier fixture entv s1–s13 render in prod and dev (state grid 2h/6c, memo grids, `/onload`, second context, detail grid Count/Value), aggrid_min 4/4, demo `probe_state_coldefs` 7/7 (a2 3/7). **Still broken with enterprise 0.9.7a4 on a3** (state grid 0h/0c, memo grids empty, detail headers []): users must upgrade reflex-enterprise together with reflex. a5 also fixes reflex a2 and keeps 0.9.12 working. Positive control on a2 + a4 still reproduced first | `a3_ent_grid/NOTES.md`, `out/` | a3_ent_grid |
| N-032 OIDC cross-tab logout | HIGH regression | **fixed with reflex a3** (reflex-side #7493; a5 alone does not fix a2: 0/3): `away` (Back-button) signed out 3/3 in dev Redis, prod Redis (1 worker) and dev memory (a2 0/3); stale-hash probes 3/3/3 (a2 0/0/0); two-tab `xtab` 6/6, 6/6, 4/4 with every race healed; explorer probes 3/3/3 and 5/5 (a2 3/7); core `get_delta` override sees the boot value once in dev and prod, like 0.9.12. Positive control on a2 + a4 reproduced first. Side effect A3-09 | `a3_ent_auth/NOTES.md`, `logs/` | a3_ent_auth |
| N-004 0.10 state unreadable by 0.9 | MEDIUM, decided: document | **behaves as documented** (#7494): 0.9.12 → a3 keeps sessions; a3 → 0.9.12 resets cleanly (fresh state, nothing logged) on Redis and disk; a2 ↔ a3 interchangeable (schema hash identical); a3 pickles hold only field values (no `_PREVIOUS_RELEASE_PICKLE_KEYS`, no undo stack) | `a3_class_state` pickle matrix, disk store, fleet e2e | a3_class_state |
| N-005 plain default drops storage | MEDIUM | **fixed** for `str` values: 3 storage types × str/storage annotation × 6 assignment kinds keep storage, name and options; e2e dev + prod/Redis (9 workers) writes `ls_plain_key`, `lscs_key`, `ck_key`, n005 8/8 (a2 4/8). Gap: `None` / non-str values still drop storage (A3-02) | `a3_class_state/out/e2e/`, `logs/` | a3_class_state |
| N-039 patch/restore of a var default | MEDIUM | **fixed**: monkeypatch / mock.patch.object / pytest-mock / substate / delattr round trips, 15 var kinds, 0 errors and 0 leaks on Python 3.11–3.14 (a2: 15/15 fail); edge cases in A3-01 | `a3_class_state/logs/` | a3_class_state |
| N-008 `_x__y` accepted by the dev guard | LOW regression | **fixed**: `self._sneaky__name = 1` raises in dev; own/base/mixin/`_Under`/ComponentState mangled names still accepted | `a3_class_state` | a3_class_state |
| N-006 `BackendVarFormatError` message | LOW docs | **changed**: message names `default_value()` / `ClassVar` / a state var; `str(S._x)`, `"%s" % S._x`, `f"{S._x!s}"` still embed the `Field` repr silently (as the guide now states) and `rx.box(id=S._label)` is still a cryptic TypeError | `a3_class_state` | a3_class_state |
| N-002/N-007/N-009/N-024/N-040 docs | LOW docs | **fixed (documented)**: the a3 CHANGELOG carries the #7462 entry; the "Upgrading to Reflex 0.10" guide's samples run as written on a3 (dev and prod/Redis, 9 workers) and on 0.9.12 where it says so; 50+ statements checked (Field class read, `ChildrenTypeError`, `BackendVarFormatError` hint, `get_fields()[...]` recipe portable to 0.9.12, class-default scope incl. per-worker runtime assignment, callable factories, lock-pickling error text, `ClassVar`, background-task inherited handlers, state-store note). N-040 behavior itself unchanged (179/255 raise) and now documented. Gaps: A3-06 (inherited-var writes in background tasks), the `id=`/`href=` prop errors differ from the quoted text (N-006) | `a3_upgrade/NOTES.md` | a3_upgrade, a3_class_state |
| F-014 `reflex component` message | LOW | **fixed**: every `reflex component …` form exits 1 with the wrapping-React docs + component-template pointer on stderr (a2: "No such command", rc 2); hidden from `reflex --help` | `a3_upgrade/NOTES.md` | a3_upgrade |

## New findings on 0.10.0a3
Numbered A3-xx. "Pending verification" until a `verify_*` item reports.

### A3-01: #7495's undo stack restores the latest entry, not what the patch saved: a rejected `mock.patch.object` / `pytest-mock` patch, `monkeypatch.delattr`, or an assignment inside a patch window loses a configured default or leaks the patched one (LOW, regression vs a2 in 3 of 4 cases; CONFIRMED and narrowed by independent verifier)
- Item `a3_class_state` (inbox 7). With `Svc.limit = 10` configured at import: (a) `mock.patch.object(Svc, "limit", Other.y)` raises
  TypeError but mock's exit still restores, popping the configuration → later tests see 0; (b) same for `mocker.patch.object(Svc, "_quota",
  rx.field(5))`; (c) `monkeypatch.setattr(Svc, "limit", 99)` then code under test assigns `Svc.limit = 50` → teardown undoes the 50 and
  leaves 99 for later tests; (d) `monkeypatch.delattr(Svc, "_quota")` pops the configuration and teardown pops again → 0 for good.
  a3: 4 failed / 4 passed; a2: (c) only, loudly. Also: `S.x = S.x` after a configuration silently reverts it; a `str` var with a
  non-storage declared `default_factory` now has that factory called when a plain str is assigned.
- Cause (published reflex-base 0.10.0a3 `vars/base.py`): `_keep_client_storage` / `_accepts_default` raise before `_keep_default`
  pushes the "failed assignment" entry (4895–4903, 4918); `__delattr__` pops (4926–4939); identity restore pops whatever is on top (4888).
- Repro: `a3_class_state/probes/undo_edge/test_undo_edge.py` (needs reflex[db]==0.10.0a3, pytest, pytest-mock).
- **Verification (`verify_class_state`, own repro `a3_class_state/verification/probes/test_v7_undo.py` first): CONFIRMED, narrowed.**
  a3 4 failed / 16 passed (controls — plain monkeypatch/mock round trips, nested patches, a rejected wrong-type value — pass).
  Only Var/Field values skip the undo entry (wrong types, raising factories, Literal/dict/dataclass/tuple mismatches round-trip);
  `monkeypatch.setattr` with a Var/Field does NOT lose the default (pytest records the undo only after a successful setattr) —
  `unittest.mock` / pytest-mock restore the saved Field even when their own setattr failed, which pops one entry. Regression vs a2
  for (a), (b), (d); (c) leaked on a2 too (loudly, N-039) and now leaks silently. Impact: pytest suites only; (a)/(b) only after a
  patch that already raised; (c) needs code under test reconfiguring a patched class default; (d) needs `monkeypatch.delattr` on a
  declared var. Docs: base_vars.md says a restore "undoes the most recent default assignment" ((c)/(d) match that literally) but
  also promises monkeypatch and `mock.patch.object` round trips, and the `__setattr__` docstring says a failed assignment "leaves the
  default as it was". Code: `__setattr__` 4861-4924 (identity restore 4888-4890; `_keep_client_storage` 4895 and `_accepts_default`
  4896 run before `_keep_default` 4903/4918; Var 4738-4743, Field 4744-4749), `Field._restore_default` 4130-4133 pops the newest entry,
  `__delattr__` 4926-4939. Also confirmed: a frontend `str` var with a non-storage declared `default_factory` has that factory called on a
  plain str assignment (a raising factory surfaces its raw exception; a2 accepted).

### A3-02: The N-005 fix covers only `str` values: assigning `None` to an `Optional[str]` storage var (or a non-str to a Union var) still silently drops browser storage (LOW, regression vs 0.9.12, same as a2; CONFIRMED by independent verifier)
- Item `a3_class_state` (inbox 8). `opt: Optional[str] = rx.LocalStorage("d", name="k_opt")`; `St.opt = None` → no client-storage entry;
  e2e `apps/clse2e`: `k_opt` never written, a new tab shows "". 0.9.12 ignored the assignment and kept storage.
- **Verification: CONFIRMED** (`verification/probes/probe_v8_storage.py`, e2e a3 dev): `None` → `Optional[str]` LocalStorage, `5` →
  `Union[str, int]`, `None` → `Optional[str]` Cookie are accepted silently and the var leaves storage; a later str assignment does not
  bring it back; `_is_client_storage` is lru-cached, so it can stay True for a var looked up before the assignment while the compiled
  frontend omits it. Rare in practice (GitHub search: 2 repos declare Optional storage vars, none assign None through the class; the
  docs only promise the plain-string case). Code: `reflex/istate/storage.py` 24-37 (`_with_value` wraps only str, line 34),
  `reflex_base/vars/base.py` `_keep_client_storage` 4753-4780, `_accepts_default` 4725-4750, `reflex/state.py` 1635-1656.

### A3-03: ComponentState + named storage var + `cls.x = initial` (the a3 changelog's example) makes every instance share one browser key (LOW, docs; NARROWED by independent verifier to a documentation caveat)
- Item `a3_class_state` (inbox 9). csbox on a3 dev and prod/Redis: one `box_pref` key for all instances; after a reload one instance
  shows another's choice. 0.9.12 shares the key too; a2 hid it only because N-005 dropped storage.
- **Verification: NARROWED to docs.** A named key is shared by definition (instances that assign nothing collide identically on
  0.9.12); a per-instance `name=` or an unnamed storage var gets its own key. a3 keeps the name exactly as #7495 promises, but the
  a3 changelog example (`cls.theme = initial` in `get_component` on `rx.LocalStorage("light", name="theme")`) and base_vars.md
  ("independently for each component") do not say that a named key is shared by every instance.

### A3-04: Concurrent class-default assign/restore from several threads leaves a stale patched default (LOW, pre-existing on a2)
- Item `a3_class_state` (inbox 10). 8 threads × 1500 assign/restore: final default corrupted on 3.11/3.12/3.14 (a2 too, plus TypeErrors).

### A3-05: AppHarness: a second app in one pytest process rendering a state from a shared module crashes on first render (`useContext` of a missing StateContext) (LOW, pre-existing — REFUTED as a regression by independent verifier; same root cause as reflex#7479)
- Item `a3_class_state` (inbox 11). `a3_class_state/harness/test_shared_state_harness.py`: 2 failed, 1 passed on a3 and a2.
- **Verification: REFUTED as a regression.** 0.9.12 crashes identically when the shared module is first imported inside app one
  (the explorer's 0.9.12 pass used `H_ASSIGN=1`, which on 0.9.12 replaces the class attribute with a plain value, so the pages never
  referenced the shared state). Importing the shared module before the first harness makes both apps work on a3 and 0.9.12. Cause:
  `reflex/testing.py` 296-304 forks the registration context per app; a state registers into the context active at first import
  (`reflex/state.py:807`, `reflex_base/registry.py` 192-221); `_reload_state_module` (322-331) reloads only the app package. Add the
  render-crash symptom and the import-first workaround to reflex#7479; no new issue.

### A3-06: The upgrade guide misses that writing an INHERITED var outside `async with self` in a background task now raises `ImmutableStateError` (0.9.12 wrote it without the lock) (LOW, docs)
- Item `a3_upgrade` (inbox 5). App `a3_upgrade/apps/guide`, `bin/seq_guide2.sh`: a Child background task doing `self.count += 100`
  (count declared on Parent) outside the lock: 0.9.12 14 → 114 with no error; a3 raises. A handler declared on the same state that
  writes the inherited var splits the same way. The guide covers only calling inherited handlers (N-024). The new behaviour is the
  safe one; the gap is documentation. 0.9.12 cause: `istate/proxy.py:322-329` skip-vars bypass + `state.py:1455`.

### A3-07: `reflex run --json` ignores SIGINT sent to its pid only; the server keeps running (LOW, pre-existing on 0.9.12 and a2)
- Item `a3_upgrade` (inbox 4). `kill -INT <pid>` of `reflex run --json`: still running after 60–210 s; plain `reflex run` exits in
  0.25 s; `--json` + SIGTERM exits in 2 s; Ctrl-C in a terminal (process-group SIGINT) works. `reflex_base/utils/log.py:519` forwards
  only SIGTERM, `:524` `except KeyboardInterrupt: continue`. Repro `a3_upgrade/bin/json_matrix.sh a3fast a3 INT-pid:100000`.

### A3-08: #7428's 30 s drain cap ends `reflex run --json` mid-record: a very slow consumer gets a truncated last JSON line (LOW, new in a3 but strictly better than a2)
- Item `a3_upgrade` (inbox 3). #7428 itself works: Ctrl-C/SIGTERM with a 40 lines/s consumer exits in 6.5–6.7 s, rc 0, 0 lines lost,
  0 invalid JSON (a2 lost 49–63 lines plus a truncated record). With a 6 lines/s consumer the cap fires at 30.4 s (as designed) and the
  stream ends in `{"timestamp": "...", "level"` with no newline (82 lines undelivered). A consumer parsing line by line sees one
  invalid record. Repro `a3_upgrade/bin/json_matrix.sh a3 a3 TERM-pid:6`.

### A3-09: After the #7493 boot reconcile signs a stale tab out, the tab stays on the protected page with blanked values instead of being redirected to /login (LOW, behaviour change vs 0.9.12; pending verification)
- Item `a3_ent_auth` (inbox 4). vauth on a3-ent, `vdrv.py stale … 3`: P3 ends on `('/vault', '')` 3/3 dev Redis, 2/3 prod, 3/3 memory;
  0.9.12 + a5 `('/login', None)` 3/3 (and 2/3 in `away`). a2 never signed the tab out at all (N-032). `hydrate_and_load` runs the page
  guard during the boot chain, before the frontend's cookie sync and `reconcile_tokens_after_sync` reset the session; the reset does not
  re-run the guard. Nothing protected is exposed (values blanked; the next protected event redirects to /login).

### A3-10: Enterprise auth + Redis: client-side navigation erases a signed-in user's protected `rx.LocalStorage` / `rx.Cookie` values (MEDIUM, pre-existing on a2 + a4 and 0.9.12 + a5, enterprise; pending verification)
- Item `a3_ent_auth` (inbox 3). App `a3_ent_auth/apps/vauthx` (default-protected state with `draft = rx.LocalStorage(name="vx_draft",
  sync=True)`, `ck = rx.Cookie(name="vx_ck")`): sign in, "set draft", click the "vault2" link → localStorage `vx_draft` and cookie
  `vx_ck` become "" (2/2 on a3, a2 and 0.9.12 with Redis); the next boot sends "" so the backend loses the value too. With the memory
  manager the values survive. Suspected cause: `enforcement.filter_protected_delta` looks the user up via
  `_get_state_from_cache(AuthUserState)`, which returns None for `update_vars_internal` under Redis, so the filter fails closed and the
  frontend persists the "" placeholders. Repro: `bin/infra.sh start; bin/run_storx.sh a3-ent:vauthx_a3e:a3e-dev-redis-v2;
  drivers/storx_table.py a3e-dev-redis-v2`.
- Filed: [reflex-enterprise#274](https://github.com/reflex-dev/reflex-enterprise/issues/274) (2026-10-07). N-033's a3 re-check added to
  [reflex-enterprise#262](https://github.com/reflex-dev/reflex-enterprise/issues/262#issuecomment-6047554210).

### A3-11: `sync=True` LocalStorage: the #7493 boot echo writes back the stale value a tab read at connect time, so a change made in another tab while tabs are booting starts an endless cross-tab storage ping-pong (MEDIUM, regression vs a2, not vs 0.9.12; pending verification)
- Item `a3_hydration` (inbox 1). `src/bootecho`, `scripts/run_storm.sh a3 dev 8 3142 8142 S 6`: tab 0 sets the synced `be_theme` 5× 250 ms
  apart while 6 more tabs load in the same browser context. a3: endless ping-pong dev 6/9 (+3/3 long runs), prod 2/5; a2 0/15; 0.9.12
  9/10. Long runs: 8k–39k websocket frames per 5 s for 60 s, tabs stuck on mixed s2–s4 (the user's last value s5 is lost), backend
  ~50–70 % CPU. Two-tab form with inbound messages held: transient revert 1/2 (a2 0/2). Cause: `reflex/state.py:2401` + `2420-2422`
  re-mark the applied browser values dirty after the snapshot → the boot delta carries the value read at CONNECT → `state.js:896/1076`
  `localStorage.setItem` of the stale value → `storage` event in the other tabs (`state.js:1267`) → `update_vars_internal` → deltas write
  back again. #7493 restored 0.9.12's boot echo, and with it 0.9.12's storm; a2 was immune because it echoed nothing.

### A3-12: `sync=True` LocalStorage written concurrently by several tabs (an on_load that stamps a synced var, a browser session restore) loops forever between the tabs (MEDIUM, pre-existing on 0.9.12, a2 and a3; pending verification)
- Item `a3_hydration` (inbox 2). `src/syncstamp` (`Stamp.last = rx.LocalStorage("", name="ss_last", sync=True)` set to a per-tab value in
  `/stamp`'s on_load), `scripts/run_stamp.sh a3 dev 4 3142 8142 /stamp 6`: 3–6 tabs → a3 41k–234k, a2 118k–137k, 0.9.12 40k–64k frames
  per 5 s; the control `/same` (same value from every tab) stays quiet. The volume crashed the Playwright driver in 4/12 runs.

## Cluster summaries

### `a3_hydration` — done (positive controls catch a1's F-002/F-003 and 0.9.12's storm first)
F-002 and F-003 stay fixed; the whole reverify_hydration suite (f1combo, mini, cvstore a–j, hydapp s1–s13, reconnect, Redis restart,
token leak, prenav, preconnect, csbox) matches a2 field by field in dev, prod and prod/Redis. #7493 works as designed and restores
0.9.12's boot semantics: `get_delta` overrides see the browser's storage values once (a2: never), a sanitising override now reaches
localStorage, a fresh browser gets nothing written, computed vars over storage vars are right at first hydration, on_load values win;
returning-user boot = 4 frames / 2 deltas (= a2; 0.9.12 6/4). By design (as on 0.9.12, not a2): every storage value is sent twice at
boot (+826 B / +24 % for the bootecho page), every returning visit rewrites every storage value, so a cookie's `max_age` expiry slides and
raw cookie values set outside reflex come back URL-encoded. reflex-local-auth 0.5.0 36/38 (known demo pitfall) + 14/14 storage checks,
reflex-google-auth bogus-token clearing: identical on a3, a2 and 0.9.12. Unchanged: F-008 (>1 MB storage storm), F-010 (prenav
on_load), N-015, N-016; F-017 not reproduced. New: A3-11 (medium, regression vs a2), A3-12 (medium, pre-existing).
Notes: `a3_hydration/NOTES.md`.

### `a3_ent_auth` — done (positive controls on a2 + a4 / a5 reproduced first)
N-032 fixed on a3 (+ a5) in dev Redis, prod Redis and dev memory; the boot now sends `hydrate_and_load`, then
`reconcile_tokens_after_sync` when the hash differs. #7493 regression hunt clean in the auth flows: a fresh anonymous browser gets nothing
written (a3, a2, 0.9.12); each signed-in boot writes the stored hash back once with the same value (as 0.9.12; a2 wrote nothing), 0
cookie syncs, three idle tabs 0 events in 10 s; relogin alice → bob on the same tab clean in dev and prod; protected fields still withheld
at boot; proactive refresh works; hydration-token probe flags equal 0.9.12. a4 auth matrix 36/36; MCP OAuth + anonymous identical to a2
(N-037 unchanged); maps 16/17 dev and prod (on_layeradd, pre-existing). N-033 unchanged (fresh 9-worker prod: 27/27 cookie-sync POSTs
405, 3/6 logins keep their token cookies). New: A3-09 (low), A3-10 (medium, pre-existing enterprise). Notes: `a3_ent_auth/NOTES.md`.

### `a3_upgrade` — done
No upgrade regression 0.9.12 → a3 or a2 → a3: form-designer, github-stats, clock, twitter dev and twitter prod/Redis give exactly the
a2-pass results in place and cold; 0.9.12- and a2-pickled Redis sessions load on a3; `.web/package.json` identical to a2; a3 → 0.9.12
rollback on the same Redis discards a3-written substates silently (no crash; substates a3 only read stay loadable — per-substate reset),
as the state-store note says. Install paths: pip and uv upgrades from a2 move only reflex + reflex-base; fresh `--pre` and exact-pin
installs give only train packages; a pip upgrade without `[db]` keeps an old greenlet-less venv broken (installer semantics; naming
`reflex[db]` fixes it). Stock `pip install 'reflex[db]'` (no pre) still gives 0.9.12 with SQLAlchemy 2.1.4 and no greenlet, so
`import reflex.model` fails on the stable line today — N-001 for 0.9.x users; a 0.9.13 with #7466 would fix it. `reflex component`
fixed (F-014); #7428 works (A3-08 at the cap); Python 3.11.17 and 3.14.6 init + dev + prod clean. Upgrade guide accurate (gap A3-06).
New: A3-06, A3-07, A3-08. Notes: `a3_upgrade/NOTES.md`.

### `a3_ent_grid` — done (positive control on a2 + a4 reproduced first)
N-025 fixed on a3 + a5 (prod and dev), and on a2 + a5; 0.9.12 + a5 unaffected; a3 + a4 still broken (the reflex side did not change:
`corev` probes on a3 prod are identical to a2, render-before-`window.__reflex` ordering unchanged). enterprise#273 regression hunt
(new `entr` fixture: literal and State column defs with lambda `rx.badge` / formatter / getter / tooltip / `@rx.memo` cells,
`cell_class_rules`, pinned rows, grouping, `rx.cond`, computed-var defs, master/detail with lambda renderers, memo grids; prod
load/reload/client nav and dev; a3, a2, 0.9.12): all render, 0 page errors, no ReferenceError, 0 of 583 traced renderer calls ran
before `window.__reflex`. AG Grid demo a3 + a5: prod smoke 20/20, features 46/47, model 24/29 (same failures as a2 and 0.9.12);
F-001 enterprise half still holds; dev numbers equal a2 after re-running load-induced timeouts (load average 23–30). dnd 27/27 prod and
dev (kanban first load writes no LocalStorage default, so #7493 did not bring F-002 back), flow 20/22 prod (same as a2 and 0.9.12),
mantine 23/23, maps route smoke 4/4. `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` still crashes lambda→Radix renderers with React #130
(unchanged from a2; the flag is no longer needed as a workaround). Pre-existing on 0.9.12 + a5: `rx.badge(params.value)` shows a
JSON-quoted value, AG Grid warning #306 for `tooltip_field`. Notes: `a3_ent_grid/NOTES.md`.

### `a3_class_state` — done (positive controls on a2 all reproduced first)
N-005, N-039 and N-008 fixed; N-006 changed (message fixed, silent `str()` paths remain); N-004 behaves exactly as the #7494 note says
(Redis, disk and pickle level; a2 ↔ a3 interchangeable); N-040 unchanged and now documented. #7495 adversarial hunt: `del State.x`
with nothing assigned is a no-op, parent/child/mixin/ComponentState patches restore, `reset()` after assignment and restore, storage
factories called exactly once, storage options kept, pickles carry no undo stack, schema unchanged by assignment, bounded stack across
20 module reloads. New: A3-01 (regression vs a2, low), A3-02, A3-03, A3-04, A3-05. Notes: `a3_class_state/NOTES.md`.
