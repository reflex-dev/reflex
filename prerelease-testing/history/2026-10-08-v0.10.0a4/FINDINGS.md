# Findings — re-verification on reflex 0.10.0a4 / reflex-base 0.10.0a4 (+ reflex-enterprise 0.9.7a5), 2026-10-08

**Status: FINAL.** Previous pass: [../2026-10-07-a3/FINDINGS.md](../2026-10-07-a3/FINDINGS.md), plan
[../2026-10-07-a3/RELEASE_PLAN.md](../2026-10-07-a3/RELEASE_PLAN.md). Context: [CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md).

## Versions under test
- reflex 0.10.0a4 + reflex-base 0.10.0a4 (tag `v0.10.0a4` = `f6e070ef4` on `r/pre-2026.10.06-37579583012`); a3 → a4 is
  exactly #7505, #7513 and #7516. Every other train package unchanged (a2-train versions).
- reflex-enterprise 0.9.7a5 (offline wheel, sha256 aad70d1a…; still the newest on PyPI).
- Baselines, run back to back on the same machine: reflex 0.10.0a3 (positive control for every a3 finding), reflex 0.9.12.

## Pre-flight (orchestrator, `preflight/`)
- 20/20 train packages published with wheel + sdist; published reflex 0.10.0a4 pins `reflex-base==0.10.0a4`.
- Every source file a4 changed is byte-identical in the installed wheels (`state.js`, `vars/base.py`, `state.py`,
  `istate/storage.py`); the removed #7495 layer is absent.
- `.pyi` audit PASS (122 stubs, wheel == sdist, counts match `pyi_hashes.json`, no foreign stubs).
- Changelogs: reflex a4 carries the #7516 breaking entry and the #7513 wording in the #7312 entry (the a3 section's two
  #7495 class-assignment entries were removed in place); reflex-base a4 carries #7516 and the #7505 bug fix. Docs at the
  tag: upgrade guide "Assigning a state var through its class" + inherited-var background-task text, base_vars.md
  Changing Defaults via `__fields__`, ClassVar per-worker note.
- Blank-app smoke (`reflex init --template blank`, dev and prod): clean in Chromium.

## Re-verification table (findings of the a3 pass)
| id | a3-pass status | a4 result | evidence | item |
|---|---|---|---|---|
| A3-11 boot-echo cross-tab storm (`sync=True` LocalStorage) | MEDIUM, fix-before-release (#7505) | **fixed**: a3 positive control stormed first in every scenario family; a4 0 storms in 48 runs — explorer dev 5/8 → 0/8, prod 1/5 → 0/5; 100 ms RTT raw-CDP 3 background tabs + click dev 3/3 → 0/3, prod + Redis 9 workers 2/3 → 0/3, 7 restored tabs 2/2 → 0/2; race window hit in every a4 run; all tabs + localStorage end on the user's last value | `a4_hydration/NOTES.md`, `results/` | a4_hydration |
| A3-12 on_load stamp loop | MEDIUM, fixed by #7505 | **fixed**: `/stamp` 6 tabs dev 3/3 → 0/4, prod 2/2 → 0/3; 6 background `/doc` tabs dev and prod + Redis 2/2 → 0/2; 4 quiet tabs + dev backend reload 2/2 → 0/2; every run ends on ONE value with 0 frames afterwards; `/same` control quiet | `a4_hydration/` | a4_hydration |
| A3-01 undo stack loses / leaks a patched default | LOW, fix-before-release (→ #7516 back-out) | **moot as designed**: the original repros (a3 control 4F/4P and 4F/16P) stop on a4 at `Svc.limit = 10` with the documented TypeError; every patch spelling (`S.x =`, `setattr`, `mock.patch.object` with a Var or value, pytest-mock, `monkeypatch.setattr`, `patch.multiple`, by path, substate, mixin) raises and leaves the Field, default, instances, pickling, `reset()` and the class Var intact; converted to the field API all four patterns end on the configured default (21/21, 3.11/3.12/3.14) | `a4_class_state/probes/test_a4_moot.py`, `test_a4_converted.py` | a4_class_state |
| A3-02 None / non-str assignment drops storage | LOW, filed #7507 (closed not planned) | **moot as designed**: every assignment raises, storage stays declared; a field default of `None` makes the var ordinary, as documented ("keeps storage only with a storage value") | `a4_class_state/probes/probe_storage_fields.py` | a4_class_state |
| A3-04 thread-stress assign/restore | LOW, filed #7511 (closed not planned) | **moot as designed**: adv7495 stress gives 12000 TypeErrors and no state change (a3 control count=21369); field-level set/restore from 8 threads × 1500 ends on the declared default, 0 errors | `a4_class_state/probes/probe_thread_fields.py` | a4_class_state |
| A3-03 named storage key shared by every ComponentState | LOW docs | **fixed (documented)**: component_state.md documents the shared named key and the per-component `name=f"theme_{key}"` pattern; the ThemeToggle / EditableText samples run as written, e2e | `a4_class_state/` | a4_class_state |
| A3-06 inherited-var writes in background tasks | LOW docs (#7513) | **fixed (documented)**: upgrade guide and the #7312 changelog entry say the write raises `ImmutableStateError` and what 0.9 did; code unchanged since a3 | `preflight/NOTES.md` | preflight |
| N-005 (superseded) storage default | — | **works through the field API**: a storage value as field default keeps storage, name and options; e2e dev and prod + Redis 28/28 | `a4_class_state/apps/c4e2e` | a4_class_state |
| N-039 (superseded) patch round trip | — | **works through the field API**: 17 var kinds × 4 field mechanisms 170/170 on 3.11/3.12/3.14; downstream packages' states 176/176 | `a4_class_state/` | a4_class_state |
| N-008 dev guard `_x__y` | fixed in a3 | **still fixed** (output identical to a3, dev and prod) | `a4_class_state/` | a4_class_state |
| N-004 state-store compatibility | documented | **as documented**: schema hash a4 == a3; a3 ↔ a4 interchangeable (pickle, disk, Redis e2e a3→a4→a3→a4); 0.9.12 → a4 loads, a4 → 0.9.12 starts fresh | `a4_class_state/` | a4_class_state |
| N-032 OIDC cross-tab logout | fixed in a3 | **still fixed**: stale P1–P4, away, xtab 3/3 in dev + Redis and prod 1 worker; entauth suites ALL_PASSED; auth matrix 36/36 + MCP | `a4_upgrade_ent/ent/auth/` | a4_upgrade_ent |
| N-025 prod AG Grid Var `column_defs` | fixed with enterprise a5 | **still fixed**: entv s1–s13 equal to a3 prod (state grid 2h/6c, memo grids, detail headers); aggrid_min 4/4 | `a4_upgrade_ent/ent/grid/` | a4_upgrade_ent |
| F-002 / F-003 | fixed | **still fixed**: a fresh profile gets nothing written (dev, prod, prod + Redis, enterprise anonymous); sanitised boot values and google-auth bogus tokens reach storage | `a4_hydration/`, `a4_upgrade_ent/` | both |

## Spot check for new regressions
- **#7505 (state.js)** — no functional regression (`a4_hydration`, new `h4mix` app; 1–3 tabs; dev, prod, prod + Redis;
  vs a3 and 0.9.12; all four channels clean): the `sync=False` handler write found in review persists; a sanitising
  `get_delta` override's output (not the echo) reaches localStorage at boot, from handlers and after another tab's raw
  write; `sync=True` followers converge (alternating writes ≥ 40 ms apart, 10 back-to-back clicks); cookie `max_age` still
  renewed at boot; SessionStorage per tab; on_load / background task / yield chains / "" / unicode / JSON-looking / 6 KB
  values round-trip; ComponentState and substate storage behave. a4 also fixes an a3 loss: a yield chain's final value
  was overwritten by a stale echo on a3. Returning-visitor boot rewrites only `sync=False` keys (a3 / 0.9.12 rewrote all).
  reflex-local-auth 36/38 + 14/14 storage, magic-link 10/11, google-auth 12/13 (known failures only); enterprise token
  hash no longer rewritten on every boot (0 writes vs 1), events and outcomes unchanged. One low behaviour change: A4-03.
- **#7516 (metaclass guard)** — no framework, example-app, enterprise or auth-package path hits it (`a4_class_state`,
  `a4_upgrade_ent`): dynamic routes, setvar / auto setters, ComponentState (`.create` ×50, per-component defaults incl.
  storage keys), mixins, ClassVar (incl. over an inherited var), `del` + re-set, `rx._x.client_state`, `rx.SharedState`,
  computed / backend vars, `rx.Model`, upload, `reset()`, `get_state`, background tasks; dev hot reload (7 successive
  edits of a state file); AppHarness with two apps; in-place upgrades of form-designer, github-stats and twitter from
  0.9.12 and a3; 22-package third-party sweep = a3; 36 downstream wheels grepped (every enterprise class write targets a
  ClassVar). An app that assigns a var at import time now fails at startup (dev and prod, rc 1, before any server starts)
  with a traceback ending at the user's line and the actionable message — the documented breaking change. Two narrow edge
  cases: A4-01, A4-02. One downstream package hits the breaking change: reflex-clerk 1.0.3 (see below).
- **Upgrades** — 0.9.12 → a4 and a3 → a4 in place give exactly the a3 pass's per-check results; only reflex and
  reflex-base move from a3; `.web/package.json` unchanged; 0.9.12- and a3-pickled Redis sessions load.

## New findings on 0.10.0a4
Numbered A4-xx. All low severity; none is a regression against 0.9.12 that a user can reach with default settings.

### A4-01: `State.add_var` on a substate, for a name an ancestor added via `add_var`, raises the #7516 TypeError (LOW, regression vs a3 only; CONFIRMED and narrowed by independent verifier)
- Item `a4_class_state`. `class P(rx.State): a: int = 1`; `class C(P): b: int = 2`; `P.add_var("dyn", int, 7)`;
  `C.add_var("dyn", int, 9)` → `TypeError: 'dyn' is a state var of C; assigning it on the class would replace the var.
  Set its default with C.__fields__['dyn'].default = ...` (base.py:4776 via `add_field`). a3 gives C its own independent
  var (the documented 0.10 rule); 0.9.12 accepted the call but was broken (C's class Var / frontend key were C's own while
  instance reads and writes went to the parent; in Chromium the button flipped the PARENT's text).
- **Verification (`verify_class_state`): CONFIRMED, narrowed.** No framework path calls `add_var` on a substate (dynamic
  route args across 4 pages, a late substate and `[[...splat]]` make zero `add_var` calls on all three versions); no
  enterprise / third-party / auth package calls `add_var`. Realistic trigger is user code: a base state whose
  `__init_subclass__` calls `cls.add_var(...)` fails on any 3-level hierarchy (OrbitLab-OSS/OrbitLab has such a hook,
  not hit today); `if name not in S.__fields__: S.add_var(name)` still raises on a substate. In a real app `reflex run`
  exits rc 1 at import (dev and prod). Following the message's advice changes nothing, and a retry gives a misleading
  "already exist" NameError (a stray `_owner=None` field is left in `C.__fields__`, otherwise inert).
- Root cause: `add_field` updates only `cls.__fields__` and `_update_substate_vars` only `.vars`, so a substate never
  lists an inherited DYNAMIC var in `__fields__`; `add_var`'s `name in cls.__fields__` check misses it (the #7516 PR body
  assumed otherwise). Same root cause, not a regression: the guard misses inherited dynamic vars — `Sub.dyn = 5` is
  silently accepted on a4 and replaces the var on that substate, while `Sub.a = 5` for a declared inherited var raises.
- Repro: `a4_class_state/probes/probe_internals.py` (row "add_var parent/child"); `verify_class_state/probe_addvar.py`
  (rows A3–A10, D1–D3), e2e `verify_class_state/apps/dynhook`.

### A4-02: With the deprecated `state_auto_setters=True`, a parent var named `set_<x>` plus a child var `<x>` fails at class definition with a misleading #7516 message (LOW, error-message quality; CONFIRMED and reclassified by independent verifier)
- Item `a4_class_state`. Raised from `_create_setter` → `setattr(cls, setter_name, handler)` (state.py ~1400):
  "'set_color' is a state var of C; assigning it on the class would replace the var…" although the user assigned nothing.
  a3 raised a different TypeError; 0.9.12 created the class but half-broken (the inherited var became unusable through
  the child: `rx.text(C.set_color)` → ChildrenTypeError).
- **Verification: CONFIRMED, reclassified.** `state_auto_setters` defaults to False on 0.9.12, a3 and a4 and has been
  deprecated (with a warning) since 0.9.0; with the default config every version creates the classes. Only the message
  is worth improving (name the auto setter and the colliding var). Repro: `verify_class_state/probe_autoset2.py`.

### A4-03: Two tabs writing a `sync=True` LocalStorage var within ~1 round trip converge on the earlier write; the later writer's tab flips after ~1 RTT (LOW, by design: consistent last-storage-writer-wins; not a regression vs a3 or 0.9.12; RECLASSIFIED by independent verifier; not a blocker)
- Item `a4_hydration`. `drivers/b2b_probe.py … alt`: t1 and t2 alternately click #c0..#c9 with no pause → a4 ends on c8
  in both tabs and localStorage 5/5 (dev, prod, prod + Redis) and t2 visibly flips c9 → c8; a3 ends on c9 5/5 after a
  short ping-pong; 0.9.12 c9 3/4 and c5 1/4 after a long ping-pong. Gaps ≥ 40 ms and single-tab bursts end on c9. Frame
  log: t1 sends c8 at +0, t2 sends c9 at +32 ms; t2's c9 delta is written at +43, t1's slower c8 delta at +49; t1's
  storage-event sync for c9 reads the stored c8 (#7505's "send the value stored now"), so t2 syncs to c8.
- **Verification (`verify_hydration`, own app `src/h4v` + `drivers/race.py`, `drivers/bootwin.py`, 100 ms RTT proxy):
  RECLASSIFIED — consistent last-storage-writer-wins, a4 better than a3 and 0.9.12 overall.** Reproduces (c8 5/5). Gap
  sweep: localhost gap 0 → c8 4/6, ≥ 10 ms → c9; at 100 ms RTT gaps 20–80 ms → c8, ≥ 150 ms → c9 (the window is ~1 RTT of
  the earlier writer; in all 23 c8 runs the server had applied c9 last). All 136 a4 runs ended with every display,
  localStorage and every tab's backend in agreement, 0 storms, never a value nobody wrote. Two paths let the earlier
  write win: the reporter's, and a more common one at real latency (t2's click still in flight when t1's c8 lands in
  storage, so t2 sends `update_vars_internal(c8)` right after its click and its backend applies c9 then c8). Same race on
  a3 (c8 4/4 at gap 0) and 0.9.12 (3/3); at 100 ms RTT over 18 runs each a4 had 0 storms / 0 inconsistent, a3 12 / 11,
  0.9.12 13 / 11 (up to ~568 writes in 3 s). Background task in one tab + click in the other at 100 ms RTT: a4 ends
  consistently on the task's value (the click shows ~36 ms then reverts); a3 and 0.9.12 stormed 3/3. #7505's rejected
  design (a stale echo written over a newer value) stays fixed: no run wrote a recognised echo over a newer value.
- **Boot-window facet (a4-specific, follow-up to `a4_upgrade_ent` O-2):** a page whose `on_load` re-assigns the stored
  value (`/norm`) makes the booting tab write a non-echo value; if another tab stores a newer value within a few ms of
  that, the newer value is lost at localhost in 6/25 runs (a3 6/6 and 0.9.12 5/5 recover it via `e.newValue`, at the cost
  of extra writes); at 100 ms RTT 12/12 end on the newer value. Always converges, no storm. Pages without such an
  `on_load` get one echoed boot delta that is not written, so the window does not exist there.
- Repro: `verify_hydration/NOTES.md` "Setup / rerun": `srv.sh start hv-a4dev a4 dev src/h4v 3660 8660` (optionally behind
  `latency_proxy.py 8661 8660 50` with `REFLEX_API_URL=http://localhost:8661`), `race.py … 3 gap:40 bg:570`,
  `bootwin.py … /norm 0 1 2 3 4 5`. Evidence: `verify_hydration/results/race/`.
- Suggested follow-up (not for 0.10.0): document `sync=True` as last-writer-wins across tabs; the PR's own suggested
  backend echo correlation would close the in-flight path.

### Pre-existing, seen again (not caused by a4)
- `rx.remove_local_storage` of a synced key in one tab makes the other tab sync `null` into a `str` var; a computed var
  then raises `TypeError: object of type 'NoneType' has no len()` and that tab keeps the old value (a3, a4, 0.9.12 alike).
  Not filed yet (verifier searched reflex-dev/reflex: no matching issue). Repro: `a4_hydration` h4mix check C21.
- Downstream: reflex-clerk 1.0.3 `clerk_provider(secret_key=...)` / `ClerkState.set_fetch_user_on_auth()` write backend
  vars `_secret_key` / `_fetch_user` through the class and now raise the #7516 TypeError at page build; the package was
  already broken on every 0.10 alpha (class reads return `Field`, its route fails to build) and works on 0.9.12. It
  should declare these as `ClassVar`. reflex-dynoselect 0.1.0 has a similar write but fails earlier on every version.
- Cosmetic: `mock.patch.object(Substate, "inherited_var", v)` surfaces mock's cleanup error ("deleting it on the class
  would replace the var") with the "assigning" error as `__context__`; both name the same valid fix.
- Unchanged and filed earlier: A3-07, A3-08, A3-09, A3-10, A3-13, N-026, N-028, N-033, reflex#7506.

## Cluster summaries

### `preflight` — done (orchestrator)
See above. `preflight/NOTES.md`.

### `a4_hydration` — done (positive control on a3 reproduced first in every scenario family)
A3-11 and A3-12 fixed in dev, prod and prod + Redis (9 workers): 0 storms in 48 a4 runs, convergence on the user's last
value / one value every time. #7505 regression hunt clean apart from A4-03. Notes: `a4_hydration/NOTES.md`;
verification `verify_hydration/NOTES.md`.

### `a4_class_state` — done (positive controls on a3 reproduced first)
A3-01 / A3-02 / A3-04 moot as designed; N-005 / N-039 work through the field API; N-008 and N-004 unchanged; #7516
regression hunt clean apart from A4-01 / A4-02; docs samples run as written on 3.11/3.12/3.14. Notes:
`a4_class_state/NOTES.md`; verification `verify_class_state/NOTES.md`.

### `a4_upgrade_ent` — done
No new issue: upgrades, third-party sweep and enterprise a5 auth / grid / demos equal the a3 pass back to back; N-032 and
N-025 stay fixed. Notes: `a4_upgrade_ent/NOTES.md`.
