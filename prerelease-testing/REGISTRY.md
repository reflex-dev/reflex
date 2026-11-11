# Pre-release findings registry

Every finding recorded by the eight pre-release QA campaigns (reflex 0.9.9a1 → 0.10.0a5), deduplicated, with its
status as of the released **reflex 0.10.0** (tag `v0.10.0`, 2026-10-08) and **reflex-enterprise 0.9.7** (tag `v0.9.7`).
Issue and PR states were checked on GitHub on 2026-10-09 (reflex-dev/reflex, reflex-dev/reflex-enterprise,
reflex-dev/reflex-chat, plus a search of reflex-dev/reflex-examples). Fix versions come from the `v0.10.0` changelogs
(root, `packages/*/CHANGELOG.md`) and the reflex-enterprise `v0.9.7` changelog.

## Contents

1. [Reading this registry](#reading-this-registry) — ID scheme, campaign keys, status legend
2. [Summary](#summary)
3. [Hydration and browser storage](#1-hydration-and-browser-storage-hyd)
4. [State class model](#2-state-class-model-state)
5. [Events and background tasks](#3-events-and-background-tasks-evt)
6. [Enterprise](#4-enterprise-ent)
7. [Install and packaging](#5-install-and-packaging-pkg)
8. [CLI and lifecycle](#6-cli-and-lifecycle-cli)
9. [Components and compiler](#7-components-and-compiler-cmp)
10. [Third-party packages and example apps](#8-third-party-packages-and-example-apps-tp)
11. [Docs and changelogs](#9-docs-and-changelogs-doc)
12. [Refuted and reclassified claims](#refuted-and-reclassified-claims)
13. [Untriaged cluster observations](#untriaged-cluster-observations)
14. [Harness lessons](#harness-lessons-not-product-findings)
15. [Re-verify on every pass](#re-verify-on-every-pass)

## Reading this registry

**Registry ID.** `AREA-NN` (HYD, STATE, EVT, ENT, PKG, CLI, CMP, TP, DOC). One row per distinct defect; every ID a
campaign gave it is listed as an alias.

**Campaign keys** (used in the *First seen*, *Aliases* and *Repro* columns). Repro paths are relative to the archive
root (the original campaign trees, preserved on branch `claude/reflex-prerelease-testing-t0sd90` at `008ce80ef`);
the top-level documents of each campaign are also copied into `history/<dir>/`.

| key | campaign | archive path prefix | `history/` dir | baseline stable |
|---|---|---|---|---|
| `99` | reflex 0.9.9a1 (+ rxe 0.9.4), 2026-08-27 | `prerelease-testing/2026-08-27-v0.9.9a1/` | `2026-08-27-v0.9.9a1` | 0.9.8 |
| `911` | reflex 0.9.11a1 (+ rxe 0.9.5), 2026-09-10, incl. published-a2 validation | `prerelease-testing/2026-09-10-v0.9.11a1/` | `2026-09-10-v0.9.11a1` | 0.9.10.post2 |
| `912` | reflex 0.9.12a1 (+ rxe 0.9.5 / 0.9.6a1), 2026-09-18, incl. Phase 7 on a2 | `prerelease-testing/2026-09-18-v0.9.12a1/` | `2026-09-18-v0.9.12a1` | 0.9.11.post1 |
| `A1` | 0.10.0a1 exploration (+ rxe 0.9.7a2…a4), 2026-10-05 | `prerelease_testing/2026-10-05/` | `2026-10-05-v0.10.0a1` | 0.9.12 (+ rxe 0.9.6) |
| `F` | 0.10.0a1 gap validation, 2026-10-06 | `prerelease_testing/2026-10-06/` | `2026-10-06-v0.10.0a1-gaps` | 0.9.12 |
| `N` | 0.10.0a2 re-verification, 2026-10-07 | `prerelease_testing/2026-10-07/` | `2026-10-07-v0.10.0a2` | 0.9.12, 0.10.0a1 |
| `A3` | 0.10.0a3 (+ rxe 0.9.7a5), 2026-10-07 | `prerelease_testing/2026-10-07-a3/` | `2026-10-07-v0.10.0a3` | 0.9.12, 0.10.0a2 |
| `A4` | 0.10.0a4, 2026-10-08 | `prerelease_testing/2026-10-08-a4/` | `2026-10-08-v0.10.0a4` | 0.9.12, 0.10.0a3 |
| `A5` | 0.10.0a5 (final pre-release pass), 2026-10-08 | `prerelease_testing/2026-10-08-a5/` | `2026-10-08-v0.10.0a5` | 0.9.12, 0.10.0a4 |

**Alias notation.** `99/F-002` = FINDING-002 of the 0.9.9a1 campaign (likewise `911/…`, `912/…`). `A1-04` = numbered
finding 4 of the 2026-10-05 campaign. `F-0xx` (2026-10-06), `N-0xx` (2026-10-07), `A3-xx`, `A4-xx`, `A5-xx` are the IDs
those passes used. Unnumbered items are written `99/anomaly`, `911/val` (published-a2 validation), `911/preflight`,
`912/unnumbered`, `912/P7` (Phase 7 on a2), `N/obs`, `A4/obs`, `A5/obs`, `A1/obs`. Issue references are
`reflex#N`, `rxe#N` (reflex-enterprise), `chat#N` (reflex-chat), `examples#N` (reflex-examples).

**Severity** is the latest verified severity (a verifier's re-rating wins over the explorer's). The 2026-10-05 campaign
used P1/P2/P3; they are shown as HIGH (P1), MEDIUM (P2), LOW (P3).

**Fixture** names the `fixtures/` area that carries the original repro app or driver (`hydration`, `class_state`,
`enterprise`, `upgrade`), going by the fixture tree's contents on 2026-10-09; `—` means no fixture was confirmed to
carry it.

### Status legend

| tag | meaning |
|---|---|
| **fixed** | Fixed in the named release (PR #). A tracker that is still open is noted. |
| **documented** | Behaviour kept by design and documented (changelog Breaking Changes, upgrade guide, docs page). |
| **moot** | The code path no longer exists or the premise no longer holds (reason given). |
| **filed-open** | Filed upstream; the tracker is open and no fix shipped in 0.10.0 / rxe 0.9.7. |
| **open** | Still present (or last seen present) and not filed upstream, including items deliberately not filed. |
| **unknown** | Never verified, never re-tested after its first sighting, or the evidence does not settle it. |

## Summary

238 distinct findings, deduplicated from the 204 numbered campaign IDs (every one appears below as an alias or in the
refuted table) and the unnumbered items the campaigns recorded; plus 26 refuted or reclassified claims and 11
untriaged observations listed separately.

| Area | fixed | documented | moot | filed-open | open | unknown | total |
|---|---|---|---|---|---|---|---|
| HYD — hydration and browser storage | 5 | 0 | 0 | 7 | 2 | 2 | 16 |
| STATE — state class model | 6 | 3 | 10 | 9 | 8 | 1 | 37 |
| EVT — events and background tasks | 5 | 3 | 0 | 9 | 1 | 0 | 18 |
| ENT — enterprise | 16 | 0 | 0 | 18 | 4 | 3 | 41 |
| PKG — install and packaging | 8 | 0 | 1 | 1 | 5 | 0 | 15 |
| CLI — CLI and lifecycle | 16 | 0 | 3 | 11 | 3 | 4 | 37 |
| CMP — components and compiler | 20 | 1 | 0 | 16 | 10 | 4 | 51 |
| TP — third-party and example apps | 0 | 0 | 0 | 2 | 7 | 0 | 9 |
| DOC — docs and changelogs | 3 | 4 | 1 | 2 | 4 | 0 | 14 |
| **all** | **79** | **11** | **15** | **75** | **44** | **14** | **238** |

Notes on the release state:

- Regressions still open in 0.10.0, all LOW: against 0.9.12 — STATE-24 (F-011 forward-ref error message,
  reflex#7488), STATE-31 (A5-02 error message), CMP-44 (F-018 extra React 19.3 console error), TP-03 (reflex-clerk,
  downstream); against an earlier alpha only — STATE-27 (A4-01, vs a3), STATE-33 (A5-04, vs a4). Every other confirmed
  regression is fixed, documented or moot.
- The one security blocker the 2026-10-05 pass held the release on, A1-15 (ENT-27, rxe#245), is still open.
  ENT-07 (N-033, cookie sync on cold workers, HIGH) is the other high-severity enterprise item still open.
- Shipped as documented breaking changes in 0.10.0: STATE-09 (class-level backend-var read), STATE-20 (0.9/0.10
  state stores), STATE-30 (A5-01 mutable defaults), EVT-18 (inherited writes in background tasks); the class-assignment
  layer behind STATE-11…STATE-18 was removed by #7516.
- The upgrade guide's "was safe on 0.9" sentence (DOC-12, A5-05) is still at
  `docs/changelog/upgrading/upgrading-to-0-10.md:72`.
- **unknown** (14): HYD-07, HYD-14, STATE-37, ENT-06, ENT-23, ENT-41, CLI-30, CLI-33, CLI-34, CLI-36, CMP-09, CMP-24,
  CMP-27, CMP-42.

## 1. Hydration and browser storage (HYD)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| HYD-01 | F-002 | First page load writes client-storage **defaults** into localStorage/sessionStorage/cookies (diffed boot delta drops root `is_hydrated`); returning visitors keep stale defaults | HIGH | F (0.10.0a1) | yes vs 0.9.12 (since a1) | **fixed** in 0.10.0 (#7460); re-verified a2, a3, a4, a5 | `[F] hydration/verification/f1-client-storage-defaults/` (app `f1combo`, `drivers/f1_check.py`); `[A3] a3_hydration/scripts/run_f002.sh` | hydration |
| HYD-02 | F-003 | Client-storage var rewritten by a computed var during hydration never reaches the browser (reflex-google-auth bogus-token cleanup) | MEDIUM | F (0.10.0a1) | partial (0.9.12 seed-dependent, a1 always) | **fixed** in 0.10.0 (#7460) | `[F] thirdparty/verification/clientstorage-hydrate/` (app `cvstore`, `drivers/drive_cvstore.py`), `thirdparty/apps/google_auth_demo` | hydration |
| HYD-03 | N-015 | A computed var's state write during an ordinary event or client-side navigation is dropped depending on `PYTHONHASHSEED` | LOW | N (0.10.0a2) | no | **filed-open** reflex#7484 | `[N] reverify_hydration/cv/drivers/drive_cvnav.py` (cvstore, `PYTHONHASHSEED=0`) | hydration |
| HYD-04 | N-016 | Uncached computed var keeps showing its hydration-time value until a full reload (side-effectful computed var only) | LOW | N (0.10.0a2) | unknown | **filed-open** tracked by existing reflex#7253 (open; fix PR #7436 open) | `[N] reverify_hydration/results/f003/` (cvstore variant b) | hydration |
| HYD-05 | F-008 | A client-storage value over the 1 MB socket payload causes an endless reconnect storm, no UI error | MEDIUM | F (0.10.0a1) | no | **filed-open** reflex#7486 | `[F] hydration/hydapp` + `drivers/hyd_driver.py --only s5` | hydration |
| HYD-06 | F-010 | Client-side navigation before the websocket CONNECT runs the left page's `on_load` (an `rx.redirect` from it hijacks the new page) | LOW | F (0.10.0a1) | no (redirect-hijack variant alpha-only) | **filed-open** reflex#7487 | `[F] hydration/drivers/prenav_test.py`, `verification/f6-prenav-onload/` | hydration |
| HYD-07 | F-017 | Redis prod restart once reassigned a new client token after a granian/pyo3 shutdown panic (1/9 stops) | LOW | F (0.10.0a1) | unknown | **unknown** — not reproduced on a2 (0/9) or a3; not filed | `[F] hydration/drivers/reconnect_driver.py --manager redis` | hydration |
| HYD-08 | A3-11 | `sync=True` LocalStorage: #7493's boot echo writes back a stale value; a change during other tabs' boot starts an endless cross-tab ping-pong (~72 % backend CPU) | MEDIUM | A3 (0.10.0a3) | no vs 0.9.12 (also storms); yes vs a2 | **fixed** in 0.10.0 (#7505); 0 storms in 48 a4 runs and on a5 | `[A3] a3_hydration/src/bootecho`, `scripts/run_storm.sh`; verifier scenarios in `a3_hydration/verification/` | hydration |
| HYD-09 | A3-12 | `sync=True` LocalStorage written concurrently by several tabs (on_load stamp, session restore, dev reload) loops forever | MEDIUM | A3 (0.10.0a3) | no (0.9.12, a2, a3 all loop) | **fixed** in 0.10.0 (#7505) | `[A3] a3_hydration/src/syncstamp`, `scripts/run_stamp.sh` | hydration |
| HYD-10 | A3-13 | Storage-dependent computed vars evaluated twice per page load (second boot delta from #7493; reflex-local-auth DB query runs twice) | LOW (perf) | A3 (0.10.0a3) | no (same as 0.9.12; a2 ran once) | **filed-open** reflex#7508 | `[A3] a3_events_tp/events/src/bootdup` | — |
| HYD-11 | A4-03 | Two tabs writing a `sync=True` var within ~1 RTT converge on the **earlier** write (consistent last-storage-writer-wins) | LOW | A4 (0.10.0a4) | no (a3 and 0.9.12 storm instead) | **open** — by design per verifier; the suggested "last writer wins" doc note is not in the v0.10.0 docs; not filed | `[A4] verify_hydration/` (`src/h4v`, `drivers/race.py`, `drivers/bootwin.py`) | hydration |
| HYD-12 | A4/obs | `rx.remove_local_storage` of a synced key makes other tabs sync `null` into a `str` var; a dependent computed var raises `TypeError` and the tab keeps the old value | LOW | A4 (0.10.0a4) | no (same on 0.9.12) | **open** — not filed (no matching issue) | `[A4] a4_hydration` app `h4mix`, check C21 | hydration |
| HYD-13 | reflex#7506 | Several `sync=True` storage vars sharing one storage `name` only sync the last one | LOW | A3 (review of #7505) | no | **filed-open** reflex#7506 | `[A3] a3_hydration/pr7505/NOTES.md` | — |
| HYD-14 | 911/F-004 | Client-storage vars show their defaults after a backend rehydrate until a full reload | MEDIUM (claimed) | 911 (0.9.11a1) | no (claimed) | **unknown** — claim never verified, triaged or filed | `[911] bg_rehydrate/NOTES.md` | — |
| HYD-15 | 911/F-018, 911/val "018" | One unserializable state var drops the **whole** hydrate delta in dev (non-compiling workers lack bundled-library metadata); on 0.9.11a2 the worker died at startup instead | HIGH | 911 (0.9.11a1) | no | **fixed** in 0.9.12 (#7096; reflex#7096 closed) | `[911] ent_aggrid/verification/issue2_hydrate_delta/app`, `scripts/drive_hydrate2.py`; minimal repro in `PUBLISHED_VALIDATION_RESULTS.md` | — |
| HYD-16 | 911/F-036 (reflex half), 912/F-023 | A delta naming a substate the compiled frontend has no dispatcher for latches `backend_state_mismatch`; every later event is discarded for the session | MEDIUM (911 rated HIGH) | 911 (0.9.11a1) | no (deliberate latch since 0.9.9) | **filed-open** reflex#7247 (enterprise trigger fixed separately, ENT-12) | `[912] render_ctx_statemgr` (`renderapp`, `RENDERAPP_EXTRA_STATE=1`); `[911] ent_mantine_highcharts_tickets/scripts/probe_tickets_hydrate.py` | — |

## 2. State class model (STATE)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| STATE-01 | 99/F-002, 99/F-006 | PEP 695 alias-annotated vars compile but cannot be assigned (`_isinstance` TypeError); an uncalled alias-annotated handler crashes page compile | HIGH | 99 (0.9.9a1) | no (0.9.8 failed earlier) | **fixed** in 0.9.9 (#6986, completing #6944) | `[99] typing_python/repro_alias_setattr.py`, `repro_alias_event_arg.py`, app `pep695app` | — |
| STATE-02 | 911/F-005 | `hybrid_property` class-level typing degrades to `Any` on pyright ≥ 1.1.412 | MEDIUM | 911 (0.9.11a1) | no | **fixed** in 0.9.11 (#7106) | `[911] orch_probes/hp_types.py` | — |
| STATE-03 | 911/F-010 | A backend var named `_get_was_touched` silently breaks disk/Redis persistence | MEDIUM | 911 (0.9.11a1) | no | **fixed** in 0.9.12 (#7132; #7136 now rejects the name; reflex#7091 closed). Changelog wording: DOC-04 | `[911] event_hotpath/logs/gwt_disk_*.log`; `[912] orch_probes/reserved_names_probe.py` | — |
| STATE-04 | 911/F-011 | State attribute names colliding with BaseState internals are unvalidated (`'int' object is not callable` in `get_delta`) | LOW | 911 (0.9.11a1) | no | **fixed** in 0.9.12 (#7136 reserved-name validation) | `[911] event_hotpath/scripts/probe_names.py` | — |
| STATE-05 | 912/F-001 | `rx.State`'s new `_StateMeta` (#7136) makes any `BaseStateMeta`-derived metaclass conflict; every rxe 0.9.5 AuthPlugin/MCPPlugin/EventHandlerAPIPlugin app dies at startup | CRITICAL | 912 (0.9.12a1) | yes vs 0.9.11.post1 | **fixed** in 0.9.12 (#7215; reflex#7211 closed) and rxe 0.9.6 (#232) | `[912] orch_probes/metaclass_probe.py`, `orch_probes/ent_import_probe.py` | — |
| STATE-06 | 912/F-004 | `deps=["router"]` deprecation is silent in the redundant `auto_deps=True` + router-reading shape | LOW (disputed) | 912 (0.9.12a1) | n/a (new in #7068) | **open** — deliberately not filed (2026-09-22) | `[912] router_vars/scripts/deps_legacy.py`, `router_vars/verification/scripts/v_deps_legacy_matrix.py` | — |
| STATE-07 | 912/F-006 | A substate redeclaring a parent's backend (`_`) var is silently ignored; writes go to the parent | LOW | 912 (0.9.12a1) | no | **moot** — 0.10.0 (#7312) gives a substate its own independent var; reflex#7265 closed ("backend-only vars can be shadowed on 0.10.0+") | `[912] router_vars/verification/scripts/v_backend_shadow_tree.py` | — |
| STATE-08 | 912/unnumbered (reflex#7263) | Decision: `BaseVarShadowsInheritedVarError` (#7077) is a hard error with no opt-out | LOW (decision) | 912 (0.9.12a1) | n/a | **moot** — 0.10.0 (#7312) lets a substate redeclare an inherited var; reflex#7263 still open | `[912] RELEASE_PLAN.md` ("Decisions") | — |
| STATE-09 | F-001 (core half) | Reading a backend var on the state **class** returns its `Field` descriptor; silently rendered as `Field(...)` text | HIGH | F (0.10.0a1) | yes vs 0.9.12 | **documented** — 0.10.0 Breaking Changes (#7312), `BackendVarFormatError` (#7456) with a `default_value()`/`ClassVar` hint (#7496), upgrade guide "Reading a backend var on a state class" | `[F] thirdparty/probes/quick_classattr.py`, `thirdparty/verification/classattr/` (`scripts/derive_a.py`, `e2e_app`) | class_state |
| STATE-10 | N-006 | Backend-var misuse paths still silent or cryptic: `str(S._x)`, `"%s" % S._x`, `f"{S._x!s}"` embed the Field repr; `rx.box(id=S._x)` raises a cryptic TypeError | LOW | N (0.10.0a2) | n/a | **filed-open** reflex#7459 (message part fixed by #7496, reflex#7475 closed) | `[N] reverify_core/scripts/derive_e_format.py` | class_state |
| STATE-11 | F-004 | Class-level assignment to a declared backend var replaces its descriptor (pickling, `reset()`, Redis lose it) | MEDIUM | F (0.10.0a1) | yes vs 0.9.12 | **moot** — fixed in a2 (#7461), then class assignment removed in 0.10.0: `State.x = …` raises `TypeError` (#7516, documented breaking change; use `State.__fields__[name].set_default`, #7519) | `[F] thirdparty/probes/classassign_pickle_probe.py`, `verification/classattr/scripts/derive_b.py`, `derive_b_reset.py` | class_state |
| STATE-12 | N-005 | Assigning a plain default to a LocalStorage/Cookie var (incl. the ComponentState `cls.value = initial` pattern) silently drops browser persistence | MEDIUM | N (0.10.0a2) | no (new #7461 behaviour) | **moot** — fixed in a3 (#7495), layer removed by #7516; `set_default(rx.LocalStorage(…))` keeps storage (a4/a5 e2e 28/28); reflex#7471 closed | `[N] reverify_core/verification/n005-storage-assign/` | class_state |
| STATE-13 | N-039 | `monkeypatch.setattr` / `mock.patch.object` of a var default cannot be undone; the patch leaks into later tests | MEDIUM | N (0.10.0a2) | yes vs a1 and 0.9.12 | **moot** — #7516: class patching raises; patching the field round-trips (170/170 a4, 204/204 a5); reflex#7472 closed | `[N] thirdparty_a2/pytest_probe/min/test_min.py`, `thirdparty_a2/verification/probes/test_min_t1.py` | class_state |
| STATE-14 | N-040 | Class assignment to an unannotated placeholder raises `TypeError`; an assigned zero-arg callable is executed as a factory check | LOW | N (0.10.0a2) | yes vs a1 and 0.9.12 | **moot** — assignment layer removed (#7516); `ClassVar` guidance in the upgrade guide | `[N] thirdparty_a2/probes/` (`none_slot_probe`, `callable_assign_probe`), `verification/probes/min_t2.py` | — |
| STATE-15 | N-009 | Class-default assignment scope surprises (mixin assignment affects only later states; runtime assignment is per worker) | LOW | N (0.10.0a2) | n/a | **moot** — assignment layer removed (#7516) | `[N] reverify_core/scripts/derive_g_assign.py` | — |
| STATE-16 | A3-01 | #7495's undo stack restores the newest entry, not the patch's: a rejected patch, `monkeypatch.delattr` or an assignment inside a patch window loses or leaks a default | LOW | A3 (0.10.0a3) | yes vs a2 (3 of 4 cases) | **moot** — #7516 (PR #7512 closed); class patching now raises | `[A3] a3_class_state/probes/undo_edge/test_undo_edge.py`, `verification/probes/test_v7_undo.py` | class_state |
| STATE-17 | A3-02 | `None` or non-str assigned to a storage var silently drops browser storage | LOW | A3 (0.10.0a3) | yes vs 0.9.12 | **moot** — #7516; reflex#7507 closed not planned | `[A3] a3_class_state/verification/probes/probe_v8_storage.py`, app `clse2e` | class_state |
| STATE-18 | A3-04 | Concurrent class-default assign/restore from threads corrupts the default | LOW | A3 (0.10.0a3) | yes vs 0.9.12 | **moot** — #7516; reflex#7511 closed not planned | `[A3] a3_class_state/probes/adv7495.py` (`thread_stress_assign_restore`) | class_state |
| STATE-19 | N-008 | Dev `SetUndefinedStateVarError` guard accepts any undeclared `_x__y` name (fallout of #7465) | LOW | N (0.10.0a2) | yes vs 0.9.12 and a1 | **fixed** in 0.10.0 (#7495, kept by #7516; reflex#7473 closed) | `[N] reverify_core/scripts/derive_f_dunder.py` | class_state |
| STATE-20 | N-004, A1-16 | 0.9 workers discard state saved by 0.10 (and mixed old/new Redis workers lose backend mutations): rolling deploy or rollback resets sessions | MEDIUM | A1 (0.10.0a1, A1-16) / N (N-004) | yes vs a1 (a1 pickles still loaded on 0.9.12) | **documented** — 0.10.0 Breaking Changes (#7494), Self Hosting note, upgrade guide; reflex#7470 closed not planned; A1-16 withdrawn as an unsupported configuration (forward-only upgrades) | `[N] reverify_core/verification/n004-schema-rollback/` (`fleet_app`, `bin/phase.sh`, `drivers/drive_fleet.py`); `[A1] enterprise/a4/rolling/REPORT.md` | class_state |
| STATE-21 | reflex#7491 | Saved-state schema hash depends on the Python version, so upgrading Python with Reflex resets persisted sessions | unknown | N (found fixing N-004) | unknown | **filed-open** reflex#7491 | reflex#7491 | — |
| STATE-22 | reflex#7498 | A `str`-annotated field whose `default_factory` produces browser storage is never treated as storage | LOW | N (#7495 review) | n/a | **filed-open** reflex#7498 | reflex#7498 | — |
| STATE-23 | reflex#7499 | Hydrating a var annotated with a browser-storage type logs a type error from `Field.__set__` | LOW | N (#7495 review) | n/a | **filed-open** reflex#7499 | reflex#7499 | — |
| STATE-24 | F-011 | Annotation naming an undefined class (`from __future__ import annotations`) gives a cryptic `ForwardRef` TypeError instead of `NameError` | LOW | F (0.10.0a1) | yes vs 0.9.12 | **filed-open** reflex#7488 | `[F] pymatrix_install/apps/fwdref_app`, `scripts/fwdref_tb.py` | — |
| STATE-25 | N-017 | Mutating nested dict entries through `dict.values()` / `.items()` bypasses dirty tracking | MEDIUM | N (0.10.0a2) | no | **filed-open** reflex#7477 | `[N] browser_cache_bundle/verify_inventory/` | — |
| STATE-26 | N-043 | Python 3.14: `state_auto_setters=True` in rxconfig generates no setters in the backend worker | LOW | N (0.10.0a2) | no | **filed-open** reflex#7483 | `[N] thirdparty_a2/apps/cfgprobe`, `drivers/drive_cfgprobe.py` | — |
| STATE-27 | A4-01 | `State.add_var` on a substate for a name an ancestor added via `add_var` raises #7516's TypeError; `Sub.dyn = 5` for an inherited dynamic var slips past the guard | LOW | A4 (0.10.0a4) | yes vs a3 only | **open** — unchanged on a5 / 0.10.0 (message text only, #7519); not filed | `[A4] a4_class_state/probes/probe_internals.py`, `verify_class_state/probe_addvar.py`, app `dynhook` | class_state |
| STATE-28 | A4-02 | Deprecated `state_auto_setters=True`: parent var `set_<x>` plus child var `<x>` fails at class definition with a misleading #7516 message | LOW | A4 (0.10.0a4) | n/a (message quality) | **open** — not filed | `[A4] verify_class_state/probe_autoset2.py` | class_state |
| STATE-29 | A4/obs | `mock.patch.object(Substate, inherited_var, v)` surfaces mock's cleanup error with the assignment error as context (both name the valid fix) | LOW (cosmetic) | A4 (0.10.0a4) | n/a | **open** — not filed | `[A4] FINDINGS.md` "Pre-existing, seen again" | class_state |
| STATE-30 | A5-01 | A mutable class-body default populated after the `class` statement is snapshotted at definition (#7519); later additions silently lost; `rx.field(OPTIONS)` stays live | MEDIUM | A5 (0.10.0a5) | yes vs 0.9.12 and a4 | **documented** — shipped as a 0.10.0 breaking change: CHANGELOG Breaking Changes #7519 entry (commit 80d36782a) and upgrade-guide section "Mutable defaults filled in after the class is defined" (f74469d54) | `[A5] a5_class_state/probes/probe_copydef.py`, app `lateapp` + `bin/drive_late.py`; `verify_class_state5/v1/` | class_state |
| STATE-31 | A5-02 | A frontend var whose default cannot be deep-copied gets an opaque `cannot pickle '_thread.lock'` instead of the `VarTypeError` naming the var | LOW | A5 (0.10.0a5) | yes (message) vs a4 and 0.9.12 | **open** — not filed; consequence of the A5-01 design | `[A5] a5_class_state/run/lockmod/fevar.py` | class_state |
| STATE-32 | A5-03 | A backend var whose default cannot be deep-copied fails at import with a message naming neither the var nor the `ClassVar` fix | LOW | A5 (0.10.0a5) | no (0.9.12 failed in compile) | **open** — not filed | `[A5] verify_class_state5/apps/lockapp`, `a5_class_state/run/lockmod/mystate.py` | class_state |
| STATE-33 | A5-04 | Large mutable class-body defaults are deep-copied once more at import and the snapshot stays resident per worker | LOW (perf) | A5 (0.10.0a5) | yes vs a4 | **open** — not filed; consequence of the A5-01 design | `[A5] a5_class_state/probes/probe_large.py` | class_state |
| STATE-34 | 912/unnumbered (reflex#7264) | #7215 review follow-ups: dead test statement, typed root default, document the `type(rx.State) is BaseStateMeta` contract | LOW | 912 (0.9.12a2) | n/a | **filed-open** reflex#7264 | reflex#7264 | — |
| STATE-35 | 912/P7 | Declaring `get_delta` on a State subclass is rejected; the error does not name the `_override_base_method` opt-in | LOW (cosmetic) | 912 (0.9.12a2) | no | **open** — deliberately not filed | `[912] FINDINGS.md` Phase 7 | — |
| STATE-36 | 912/unnumbered (reflex#7258), A5/obs | An app package without `__init__.py` makes frontend and backend disagree on state names; every event is dropped with only a "no dispatch function" console error | LOW | 912 (0.9.12a1) | no | **filed-open** reflex#7258 | `[912] vars_typing/NOTES.md`; `[A5] a5_hydration_router/src_noinit` | hydration |
| STATE-37 | 911/F-041 | Two same-named `rx.ComponentState` subclasses in different modules crash the compile | MEDIUM | 911 (0.9.11a1) | no | **unknown** — never triaged or re-tested; not filed | `[911] memo_hash/verification/componentstate_name_collision/` | — |

## 3. Events and background tasks (EVT)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| EVT-01 | 99/F-003 | A background-task `on_load` is cancelled on navigation (on_load chain supersession #6593) | MEDIUM | 99 (0.9.9a1) | yes vs 0.9.8 | **documented** — 0.9.9 changelog (#6593 entry names background `on_load` cancellation); a "detached events" API is open as reflex#7239 | `[99] routing/drive_routing.py <base> shots bg` (apps `routing_app`, `routing098`) | — |
| EVT-02 | 99/F-004 | `client_error` emitted with no payload raises an unhandled TypeError before every anti-abuse guard (unauthenticated log spam) | MEDIUM (security) | 99 (0.9.9a1) | n/a (new handler) | **fixed** in 0.9.9 (#6984) | `[99] client_error/` (`noarg_unlinked.py`, `abuse2.py`) | — |
| EVT-03 | 99/anomaly (reflex#6982) | A background handler that raises before entering `async with self` gets no compatibility delta flush | LOW | 99 (0.9.9a1) | no | **fixed** in 0.9.11 (#6995; reflex#6982 closed) | `[99] state_concurrency/` (`/noctx` page) | — |
| EVT-04 | 911/F-003 | Prod multi-worker + Redis: forked workers share one `RedisTokenManager.instance_id`, so backend-initiated deltas for another worker's client are dropped | HIGH | 911 (0.9.11a1) | no (baseline worse) | **fixed** in 0.9.11 (#7108) | `[911] bg_rehydrate/verification/` | — |
| EVT-05 | 911/F-030 | State-delta key ordering changed (breaks text snapshots of deltas) | LOW | 911 (0.9.11a1) | behaviour change | **documented** — 0.9.11 Breaking Changes (#7087) | `[911] ent_mcp_oidc/scripts/mcp_drive.py` | — |
| EVT-06 | 912/F-003 | A `@rx.var(cache=False)` withheld from a delivered delta by a `get_delta` override is never re-sent (#6946 recorded "sent" while building) | HIGH | 912 (0.9.12a1) | yes vs 0.9.11.post1 | **fixed** in 0.9.12 (#7216; reflex#7212 closed) | `[912] event_loop/scripts/s_filtered.py` (app `elapp` `/filtered`); `ent_mcp_oidc/verification/2026-09-19-adversarial/pure_delta_memo.py` | — |
| EVT-07 | 912/P7 (reflex#7229) | Writes through `self.router` bypassed background-task locks and read-only proxies (0.9.12a1 regression, not found by QA; QA verified the fix) | unknown | 912 (0.9.12a2 re-verify) | yes vs 0.9.11.post1 | **fixed** in 0.9.12 (#7230) | `[912] FINDINGS.md` Phase 7 table | — |
| EVT-08 | 912/F-016, N-021(b) | A cancelled foreground `supersedes=True` handler loses all its writes under the Redis manager but keeps them in memory | LOW | 912 (0.9.12a1) | no | **filed-open** reflex#7248 (fix PR #7412 open) | `[912] event_loop/elapp` `/supersede`; dev + `REFLEX_REDIS_URL` | — |
| EVT-09 | 912/F-024 | `app.modify_state("<bare token>")` raises `ValueError: Invalid path: ('',)` (bare 500); the `token: str` overload is still un-deprecated | MEDIUM | 912 (0.9.12a1) | no | **filed-open** reflex#7246 (overload still at `reflex/app.py:1822` in v0.10.0) | `[912] render_ctx_statemgr` (`evidence/modify_state_legacy_token_traceback.txt`, `verification/legacy_token_check.py`) | — |
| EVT-10 | 912/unnumbered (reflex#7251) | An `on_load`-started self-chaining loop keeps running after the client disconnects | LOW | 912 (0.9.12a1) | no | **filed-open** reflex#7251 | `[912] event_loop/NOTES.md` | — |
| EVT-11 | 912/unnumbered (reflex#7253) | #6946 dedupe polish: uncached vars re-sent once after hydrate, dict key order defeats dedupe, dead `_UNKEYABLE_VALUE` branch | LOW | 912 (0.9.12a1) | n/a | **filed-open** reflex#7253 (PR #7436 open) | `[912] event_loop/NOTES.md` | — |
| EVT-12 | 912/unnumbered (reflex#7254) | Withholding an async uncached var leaves its coroutine unawaited (`RuntimeWarning`) | LOW | 912 (0.9.12a1) | n/a | **filed-open** reflex#7254 | `[912] ent_mcp_oidc/NOTES.md` | — |
| EVT-13 | F-016 | ty rejects a 0-arg handler as `Callable[[], Any]`; fully applied 5-arg calls fail under pyright and ty | LOW | F (0.10.0a1) | no | **open** — not filed (cosmetic, 2026-10-07 decision) | `[F] pymatrix_install/apps/typing_fixture/handlers_0_5.py` | — |
| EVT-14 | N-019 | A background task completing after session expiry sends only the root delta; substate/ComponentState values stay stale | LOW | N (0.10.0a2) | no | **filed-open** reflex#7478 | `[N] statemgr_perf/verify_expiry/` | — |
| EVT-15 | N-020 | A foreground handler that mutates then raises sends no delta; the change reaches the page only with the next unrelated event (unbounded) | MEDIUM | N (0.10.0a2) | no (since 0.9.0) | **filed-open** reflex#7476 | `[N] events/src/mini` (`bin/start.sh alpha2 dev mini_a2_dev mini`), `driver/drive_mini.py`; verifier `events/verification/` | — |
| EVT-16 | N-021 | Default-config Redis rolls back a failed or superseded event, including changes already delivered to the browser (client/server divergence) | MEDIUM | N (0.10.0a2) | no | **filed-open** as a comment on reflex#6122 (open); related reflex#7248 / PR #7412 | `[N] events/` cases `gen_yield_then_raise`, `sup_split`, `bg_raise_inside` (redis on 8479) | — |
| EVT-17 | N-022 | A superseded (cancelled) handler's changes after its last yield are committed and ride in the superseding call's delta | LOW | N (0.10.0a2; 10-06 lead) | no | **filed-open** as a comment on reflex#6122 (open) | `[N] events/out/mini_*` (`sup.split_cancelled_mutation_surfaces`) | — |
| EVT-18 | N-024, A3-06 | Background task: calling an inherited handler, or writing an inherited var, outside `async with self` now raises `ImmutableStateError` (0.9 wrote without the lock, or lost the write on Redis) | LOW (docs) | N (0.10.0a2) | behaviour change (safer) | **documented** — 0.10.0 Breaking Changes (#7312 entry) and upgrade guide "Calling inherited handlers from background tasks" (#7496, #7513) | `[N] events` evapp `/bind`; `[A3] a3_upgrade/apps/guide`, `a3_events_tp/events/src/n024doc` | class_state |

## 4. Enterprise (ENT)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| ENT-01 | 99/F-001, 99/F-021, 99/F-022, 99/F-008 (half) | reflex removed `dynamic.bundled_libraries`; rxe 0.9.4's LambdaVar path (ag-grid python-callable renderers/formatters, non-static dnd lambdas) crashes, masked as `VarAttributeError` | CRITICAL | 99 (0.9.9a1) | yes vs 0.9.8 | **fixed** in 0.9.9 (deprecated shim #6967, removal in 1.0) and rxe 0.9.5 (#219 reads the RegistrationContext) | `[99] ent_aggrid/` (`REPRO_LAMBDA=1`), `ent_map_dnd/repro_finding001_dnd_can_drop.py`, `reverify_a2/` | — |
| ENT-02 | 99/F-023, 99/F-009 (half) | `reflex.page.DECORATED_PAGES` removed without shim; rxe flow demo fails at import with a confusing error | HIGH | 99 (0.9.9a1) | yes vs 0.9.8 | **fixed** in 0.9.9 (deprecated shim #6985, removal in 1.0) | `[99] ent_misc/drive_flow.py` | — |
| ENT-03 | 99/F-025, 911/F-019 (1), 912/unnumbered | Shipped `demos/ag_grid` bundles the stale `$/utils/components` memo path and cannot start | MEDIUM | 99 (0.9.9a1) | no | **fixed** in the rxe 0.9.7 tree (changelog "Fix AgGrid formatter demo exports by bundling memoized cell renderers from their generated module"; the demo's routes load on 0.10.0a1 + rxe 0.9.7a4 in F and N); rxe#225 still open | `[99] ent_aggrid/NOTES.md`; `[911] ent_aggrid/NOTES.md` ISSUE 1 | enterprise |
| ENT-04 | 99/anomaly, 911/F-019 (2), 912/unnumbered | `ModelWrapper` datasource URL percent-encodes `?`; `/model*` fetches 404 with an empty grid | MEDIUM | 99 (0.9.9a1) | no | **fixed** in rxe 0.9.7 ("datasource URL query parameters" fix in the AG Grid 36.2 change); part of rxe#225 (open) | `[911] ent_aggrid/NOTES.md` ISSUE 5 | enterprise |
| ENT-05 | 911/F-019 (3) | rxe pins ag-grid 34.3.1 against ag-charts-enterprise 11.2.4 (integrated charts unusable) | MEDIUM | 911 (0.9.11a1) | no | **fixed** in rxe 0.9.7 (AG Grid 36.2.0 / AG Charts 14.2.0; integrated charts pass in A1) | `[911] ent_aggrid/NOTES.md` ISSUE 4 | enterprise |
| ENT-06 | 911/F-019 (4), 912/unnumbered | `ag_grid.column_def()` silently drops unknown kwargs (`checkbox_selection` in `ag_grid_finance`) | LOW | 911 (0.9.11a1) | no | **unknown** — deliberately not filed (2026-09-22); not re-tested after 0.9.12a1 | `[911] ent_aggrid/NOTES.md` ISSUE 7 | — |
| ENT-07 | 99/F-026, 912/unnumbered (`cookies/sync` 405), N-033 | `/_reflex/cookies/sync` is registered lazily per worker; with several workers a cold worker answers 404/405, so OIDC token cookies are lost after every start/deploy (plus a cross-tab 405 storm) | HIGH | 99 (0.9.9a1) | no | **filed-open** rxe#262 (a3 re-check commented; unchanged on a4/a5) | `[N] ent_auth/scripts/prod_sync_probe.py`, `ent_auth/verification/` (`bin/post_sync.sh`, `drivers/vdrv.py logins/storm`); `[99] ent_misc/NOTES.md` | enterprise |
| ENT-08 | 99/F-029 | rxe error paths call reflex's deprecated `console.*` helpers (DeprecationWarning noise on the login and prod gates) | LOW | 99 (0.9.9a1) | no | **open** — only a Linear draft (`[99] LINEAR_DRAFTS.md` ticket 5); rxe 0.9.7 `app.py` / `utils.py` still call `console.error` (GitHub code search) | `[99] ent_map_dnd/NOTES.md` | — |
| ENT-09 | 911/F-031 | MCP `reflex://state/events/<unknown state>` returns an empty list instead of an error | LOW | 911 (0.9.11a1) | no | **filed-open** rxe#226 | `[911] ent_mcp_oidc/scripts/mcp_drive.py` | — |
| ENT-10 | 911/F-032 | A withheld protected **field** is served to MCP as its default with no signal | LOW | 911 (0.9.11a1) | no | **open** — maintainer: ignore (2026-09-11); not filed | `[911] ent_mcp_oidc/scripts/mcp_auth_probe.py` | — |
| ENT-11 | 911/F-035, 912/P7, N-027 | `EventHandlerAPIPlugin` `/_reflex/events/openapi.yaml` returns 500 on a clean install (PyYAML not declared); index listed as `/index` | MEDIUM | 911 (0.9.11a1) | no | **filed-open** rxe#227 and rxe#267 | `[911] ent_mantine_highcharts_tickets/runpair.sh`; `[N] ent_grid/scripts/api_tickets.py` | enterprise |
| ENT-12 | 911/F-036 (enterprise half) | Importing the rxe auth enforcement module registers unused OIDC substates, so the tickets demo UI never dispatches an event | HIGH | 911 (0.9.11a1) | no | **fixed** in rxe 0.9.6 (#231; tickets UI hydrates on 0.9.12a2 + 0.9.6a1); rxe#228 still open. Reflex-side latch: HYD-16 | `[911] ent_mantine_highcharts_tickets/scripts/probe_tickets_hydrate.py` | — |
| ENT-13 | 911/F-038 | MCP `search_events` advertises a `rest_path` that 404s without `EventHandlerAPIPlugin` | LOW | 911 (0.9.11a1) | no | **filed-open** rxe#229 | `[911] ent_mcp_oidc/scripts/mcp_extra_probe.py` | — |
| ENT-14 | 911/F-039 | Logout from an iframed app never reaches the IdP `end_session_endpoint` | LOW-MEDIUM | 911 (0.9.11a1) | no | **filed-open** rxe#230 | `[911] ent_mcp_oidc/scripts/drive_popup_logout.py` + `idp/fake_idp2.py` | — |
| ENT-15 | 911/F-048, N-029 | Event API: malformed JSON → 500; handler argument errors → HTTP 200 with an error body | LOW | 911 (0.9.11a1) | no | **filed-open** rxe#268 | `[911] ent_mantine_highcharts_tickets/out/tickets_api_a1.json`; `[N] ent_grid/scripts/api_tickets.py` | enterprise |
| ENT-16 | 912/F-011 | After the router split, rxe's REST/MCP `redact_router_session()` silently no-ops: `client_token`/`session_id` disclosed over HTTP | HIGH (security) | 912 (0.9.12a1) | yes vs 0.9.11.post1 | **fixed** in rxe 0.9.6 (#232: redacts both layouts, matches by type); reflex breaking note in #7215; reflex#7214 closed | `[912] ent_map_dnd_flow_mantine/scripts/probe_router_redact.py`, `verification/v_leak_http.py` | — |
| ENT-17 | 912/P7 | rxe 0.9.6a1 imports the removed `reflex.istate.validation._StateMeta` under `TYPE_CHECKING` | LOW | 912 (0.9.12a2) | n/a | **fixed** in rxe 0.9.6 (rxe #235) | `[912] FINDINGS.md` Phase 7 | — |
| ENT-18 | 912/unnumbered | rxe writes the client token into OIDC error log lines | unknown | 912 (0.9.12a1) | unknown | **open** — deliberately not filed (2026-09-22) | `[912] ent_mcp_oidc/NOTES.md` | — |
| ENT-19 | 912/unnumbered | rxe depends on the private reflex helper `_override_base_method` | LOW | 912 (0.9.12a1) | n/a | **open** — deliberately not filed | `[912] RELEASE_PLAN.md` (enterprise list) | — |
| ENT-20 | A1-01 | `rxe.field(…)` no longer becomes a State Var on reflex 0.10 (`ChildrenTypeError`; the auth demo cannot compile) | HIGH (P1) | A1 (0.10.0a1 + rxe 0.9.7a2) | yes vs 0.9.12 | **fixed** in rxe 0.9.7 (0.9.7a3; changelog "auth-field-set-name") | `[A1] enterprise/repro_auth_field.py` | enterprise |
| ENT-21 | A1-02 | `AuthPlugin(extra_scopes=…)` reads the removed `backend_vars`; the app cannot start | HIGH (P1) | A1 (0.10.0a1 + rxe 0.9.7a2) | yes vs 0.9.12 | **fixed** in rxe 0.9.7 ("backend-vars-compat") | `[A1] enterprise/apps/auth_min` (`AUTH_TEST_EXTRA_SCOPES=1`), `repro_oidc_scopes.py` | enterprise |
| ENT-22 | A1-03 | Default OIDC logout raises after partially clearing the session (name/email stay visible) | HIGH (P1) | A1 (0.10.0a1 + rxe 0.9.7a2) | yes vs 0.9.12 | **fixed** in rxe 0.9.7 ("backend-vars-compat") | `[A1] enterprise/repro_logout.py` | enterprise |
| ENT-23 | A1-11 | Rejected Free-tier production/export credentials print a login error but exit 0 | MEDIUM (P2) | A1 (rxe 0.9.7a2) | no (same guard in 0.9.7a1) | **unknown** — not filed; not re-tested after a3; rxe 0.9.7 reworked Free-tier gating (#241) | `[A1] enterprise/free_tier/REPORT.md`, `results.json` | — |
| ENT-24 | A1-12 | A protected async computed var stays a placeholder on a public page reload with reflex 0.10 | HIGH (P1) | A1 (rxe 0.9.7a3) | yes vs 0.9.12 | **fixed** in rxe 0.9.7 (rxe#252 closed; 22/22 on a4) | `[A1] enterprise/a3/auth-stable/README.md`, `a3/auth-alpha/REPORT.md` | enterprise |
| ENT-25 | A1-13 | Combined iframe popup login + pending protected-event replay stalls on `/login` | MEDIUM (P2) | A1 (rxe 0.9.7a3) | no (stable fails too) | **fixed** in rxe 0.9.7 (rxe#253 closed) | `[A1] enterprise/a3/auth-alpha/REPORT.md` | enterprise |
| ENT-26 | A1-14 | Prod `POST /_reflex/mcp` (no trailing slash) returns 405 before authentication | MEDIUM (P2) | A1 (rxe 0.9.7a2) | no (stable too) | **filed-open** rxe#254 (deferred by the user) | `[A1] enterprise/a3/components/REPORT.md` | — |
| ENT-27 | A1-15 | A failing app reset during logout leaves protected state reachable by the next account on the same client session | HIGH (P1, security) | A1 (rxe 0.9.7a4) | unknown | **filed-open** rxe#245 (the 2026-10-05 release-gate HOLD) | `[A1] enterprise/a4/logout-recheck/REPORT.md`, `enterprise/a4/security/REPORT.md` | — |
| ENT-28 | F-001 (enterprise half) | AG Grid `ModelWrapper` reads `__data_source_params_class__` through the class and gets a `Field`; every data request fails | HIGH | F (0.10.0a1 + rxe 0.9.7a4) | yes vs 0.9.12 | **fixed** in 0.10.0 (#7465: double-underscore names are plain attributes; verified a2–a5) | `[F] FINDINGS.md` "Partial clusters" (`ent_demos`, demo `/model`); `[N] ent_grid/scripts/drive_ag_model.py` | enterprise |
| ENT-29 | N-025 | Prod, prerendered route: AG Grid with Var-valued `column_defs` / `detail_cell_renderer_params` renders no columns (boot delta carries only changed substates; `window.__reflex` is set in an effect) | HIGH | N (since 0.10.0a1) | yes vs 0.9.12 | **fixed** in rxe 0.9.7 (0.9.7a5, rxe#260 closed); reflex keeps the boot change (reflex#7468 closed not planned, PR #7492 closed). Needs rxe ≥ 0.9.7 with reflex 0.10 | `[N] ent_grid/apps/aggrid_min` + `scripts/probe_aggrid_min.py`; verifier `ent_grid/verification/` (`entv`, `corev`) | enterprise |
| ENT-30 | N-032 | OIDC: logging out in one tab leaves other tabs signed in (`hydrate_and_load` skipped the `get_delta` token-hash reconciliation) | HIGH (security) | N (since 0.10.0a1) | yes vs 0.9.12 | **fixed** in 0.10.0 (#7493; reflex#7469 closed); rxe#261 still open | `[N] ent_auth/scripts/stale_hash_probe.py`, `xtab_probe.py`; `ent_auth/verification/drivers/vdrv.py away/stale/xtab`, `coregd_app` | enterprise |
| ENT-31 | N-026 | React Flow controlled edits are reverted by a prod reload (mount-time `set_nodes` from prerendered defaults) | MEDIUM | N (0.10.0a2) | no | **filed-open** rxe#269 | `[N] ent_grid/scripts/probe_flow_reload.py` | enterprise |
| ENT-32 | N-030 | ModelWrapper SSRM/infinite text filter leaves "Loading rows…" placeholders; infinite add dialog fails on a datetime field | LOW | N (0.10.0a2; 10-06 lead) | no | **filed-open** rxe#270 | `[N] ent_grid/out/ag_prod_a2/` | enterprise |
| ENT-33 | N-031 | `rxe.mantine.autocomplete` has no `on_change` trigger | LOW | N (0.10.0a2) | no | **filed-open** rxe#271 | `[N] ent_grid/apps/mantine/mantine/qa_mantine.py` | enterprise |
| ENT-34 | N-034 | Background-task deltas on auth-protected states are withheld (placeholders), so the page never updates live | MEDIUM | N (0.10.0a2) | no | **filed-open** rxe#263 | `[N] ent_auth/scripts/bglive_probe.py` | enterprise |
| ENT-35 | N-035 | IdP signing-key rotation breaks every new login until restart (JWKS cached) | MEDIUM | N (0.10.0a2) | no | **filed-open** rxe#264 | `[N] ent_auth/scripts/expiry_matrix.sh` | enterprise |
| ENT-36 | N-036 | Expired (no refresh token) or IdP-revoked access tokens keep authorizing protected events (1800 s userinfo cache) | MEDIUM | N (0.10.0a2) | no | **filed-open** rxe#265 | `[N] ent_auth/logs/expiry-*` (`expiry_matrix.sh`) | enterprise |
| ENT-37 | N-037 | An MCP handler denied by its token-scope check returns success (`is_error=false`) | LOW | N (0.10.0a2) | no | **filed-open** rxe#266 | `[N] ent_auth/scripts/check_mcp_oauth_redis.py` | enterprise |
| ENT-38 | N-038 | `rxe.map`: `LayersControl.BaseLayer`/`Overlay` not exposed (invalid JS, 500s), `on_layeradd` never fires, `id=` sets no DOM id | LOW | N (0.10.0a2) | no | **filed-open** rxe#272 | `[N] ent_auth/scripts/layers_dynimport_check.py`, `layeradd_debug.py` | enterprise |
| ENT-39 | A3-09 | After the #7493 boot reconcile signs a stale tab out, the protected page stays open with blanked values instead of redirecting to login | LOW | A3 (0.10.0a3) | no (0.9.12 redirects only when a race goes its way) | **filed-open** rxe#275 | `[A3] a3_ent_auth` (`vdrv.py stale … 3`), verifier app `vea` | enterprise |
| ENT-40 | A3-10 | Auth + Redis: client-side navigation (or a second `sync=True` tab) overwrites a signed-in user's protected LocalStorage/Cookie values with "" | MEDIUM | A3 (0.10.0a3) | no (0.9.12 + a5 too) | **filed-open** rxe#274 | `[A3] a3_ent_auth/apps/vauthx`, `bin/run_storx.sh`, `drivers/storx_table.py` | enterprise |
| ENT-41 | N/obs (ent_auth) | Garbage token cookies are ignored at boot (read only on cookie sync) | LOW | N (0.10.0a2) | no | **unknown** — recorded as a pre-existing anomaly; never triaged or filed | `[N] ent_auth/NOTES.md` | — |

## 5. Install and packaging (PKG)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| PKG-01 | 99/F-016 | `reflex.testing` (AppHarness) needs uvicorn and psutil that the wheel does not declare | LOW | 99 (0.9.9a1) | no | **fixed** in 0.9.11 (`reflex[testing]` extra, #7008; reflex#6974 closed) | `[99] registration_context/NOTES.md`; `[911] orch_probes/` | — |
| PKG-02 | 99/F-014, 911/F-012 | `rx.Model(table=True)` without sqlmodel raises a bare TypeError instead of `reflex[db]` guidance | LOW | 99 (0.9.9a1) | no | **fixed** in 0.9.12 (#7083; reflex#6973 closed) | `[911] orch_probes/logs/probe_smoke.json` | — |
| PKG-03 | 911/F-001 | reflex-otel 0.1.0a1 not published by the release run (no PyPI pending trusted publisher) | PROCESS | 911 (0.9.11a1) | n/a | **moot** — published manually the same day; checklist item for new packages | `[911] packaging/NOTES.md` | — |
| PKG-04 | 911/F-006, 912/unnumbered | `uv` cannot build/install the `reflex` sdist (root pyproject ships `tool.uv.sources` / workspace) | LOW | 911 (0.9.11a1) | no | **filed-open** reflex#7088 | `[911] packaging/logs/sdist_install*.log` | — |
| PKG-05 | 911/F-007, 911/preflight §1, 912/P7 (mixed-version trap), F-006 | reflex floors its component packages at old versions, so upgrades (and `pip install -U reflex`) never pull the component fixes reflex's changelog advertises | MEDIUM | 911 (0.9.11a1) | no | **fixed** in 0.10.0 (#7464 sibling floors; a stock `pip install reflex==0.10.0a5` resolves the whole train) | `[F] pymatrix_install/freeze/`, `apps/formapp` + `scripts/drive_form.py` | upgrade |
| PKG-06 | 911/preflight §2 | reflex-otel 0.1.0a2 published with a prerelease floor `reflex-base>=0.9.11a1` | LOW | 911 (0.9.11a2) | n/a | **fixed** — reflex-otel 0.2.0 requires `reflex-base >= 0.10.0` (v0.10.0 pyproject) | `[911] FINAL_RELEASE_PREFLIGHT.md` | — |
| PKG-07 | 911/F-029 | Installing reflex-otel next to an older reflex silently upgrades reflex-base under reflex's exact pin | LOW | 911 (0.9.11a1) | n/a | **open** — accepted as not practically fixable (2026-09-11); reflex-otel 0.2.0 still depends only on reflex-base | `[911] otel/evidence/mixed-env-0910-plus-otel.txt` | — |
| PKG-08 | F-005 | `sqlmodel<0.0.45` cap downgrades fresh-0.9.12 environments; their `UTCDateTime()` migrations fail on a fresh database | MEDIUM | F (0.10.0a1) | yes vs fresh 0.9.12 installs | **fixed** in 0.10.0 (#7462 lifts the cap; Breaking Changes entry on UTC datetimes) | `[F] upgrades_a/verification/sqlmodel-datetime/` (`dt_matrix_probe.py`, `dtapp`), `pymatrix_install/apps/dbmig` | upgrade |
| PKG-09 | N-001 | Fresh `reflex[db]` resolves SQLAlchemy 2.1 without greenlet; `rx.Model` and every `reflex db` command crash | HIGH | N (0.10.0a2) | no (fresh 0.9.12 fails too); yes vs a1 | **fixed** in 0.10.0 (#7466 adds greenlet to the `db` extra). Still broken for stock 0.9.x installs (no 0.9.13; Linear ENG-13207). Related reflex#7421 (lazy import, open; PR #7440 open) | `[N] reverify_db_install/scripts/greenlet_probe.py` | upgrade |
| PKG-10 | A1-10 | Unique UUID callable-default backfill of existing rows fails (`IntegrityError`: every row gets the same evaluated default) | MEDIUM (P2) | A1 (0.10.0a1) | no (0.9.12 fails earlier with CompileError) | **open** — ignored at the user's direction; not filed | `[A1] services/migrations.py --unique`, `services/migrations-unique-*.json` | — |
| PKG-11 | A1/obs | reflex-components-dataeditor 0.9.3 yanked for an incorrect minimum reflex-base requirement | LOW | A1 (0.10.0a1) | n/a | **fixed** — 0.9.3.post1 published 2026-10-06 (dataeditor 0.10.0 in the final train) | `[A1] FINDINGS.md` "Triage and rerun guidance" | — |
| PKG-12 | A1/obs | A fresh Bun install with a neutral `REFLEX_DIR` appends PATH setup to the user's shell profile | LOW | A1 (0.10.0a1) | unknown | **open** — not filed (installer side effect) | `[A1] FINDINGS.md` | — |
| PKG-13 | 912/unnumbered (reflex#7259) | `reflex db init` without the db extra prints a raw click traceback | LOW | 912 (0.9.12a1) | no | **fixed** in 0.10.0 (#7275, #7322; reflex#7259 closed) | `[912] db_optional_imports/bareapp` | — |
| PKG-14 | 912/unnumbered | Generated `package.json` pins `"mergician": "v2.0.2"` (leading `v`) | LOW (cosmetic) | 912 (0.9.12a1) | n/a (new in #6850) | **open** — deliberately not filed; still at `reflex_base/constants/installer.py:151` in v0.10.0 | `[912] up_examples_a/NOTES.md` | — |
| PKG-15 | F-013 | The `rx.Model` deprecation warning location points into pydantic internals | LOW | F (0.10.0a1) | no | **open** — not filed (cosmetic) | `[F] thirdparty/verification/classattr/scripts/derive_d/derive_d.py` | — |

## 6. CLI and lifecycle (CLI)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| CLI-01 | 99/F-005 | `REFLEX_ENABLE_FULL_LOGGING`: granian worker's file handler is closed; worker records vanish and plain text leaks into `--json` stdout | MEDIUM | 99 (0.9.9a1) | no | **fixed** in 0.9.9 (#6992) | `[99] logging_cli/` | — |
| CLI-02 | 99/F-011 | `reflex run` hangs forever after a fatal node-version error (npm path) | MEDIUM | 99 (0.9.9a1) | no | **fixed** in 0.9.9 (#6990, #6994) | `[99] prod_export/` (fake node on PATH + `REFLEX_USE_NPM=1`) | — |
| CLI-03 | 99/F-008 (half) | `get_config(reload=True)` raises a bare TypeError after the RegistrationContext move | MEDIUM | 99 (0.9.9a1) | yes vs 0.9.8 | **fixed** in 0.9.9 (#6985 deprecated shim delegating to `reload_config()`, removal in 1.0) | `[99] registration_context/NOTES.md` | — |
| CLI-04 | 99/F-013, 911/F-016 | `reflex run --json`: granian's lifecycle lines are plain text on stdout | LOW | 99 (0.9.9a1) | no | **fixed** in 0.9.12 (#7193; reflex#6972 closed) | `[911] orch_probes/logs/json_backend_*.out` | — |
| CLI-05 | 99/F-018 | A failed `REFLEX_USE_NPM` run persists an inconsistent `reflex.lock` (next bun run fails) | LOW | 99 (0.9.9a1) | no | **fixed** — 0.9.12 (#7129) and 0.10.0 (#7210; reflex#6976 closed); did not reproduce on 0.9.11a1 | `[99] prod_export/` (`oldnode_bun.log`) | — |
| CLI-06 | 99/F-027 | Console warnings print backslash-escaped brackets (`dict\[str, …]`) | LOW | 99 (0.9.9a1) | yes vs 0.9.8 | **fixed** in 0.9.9 (#6989) | `[99] up_counter_todo/` | — |
| CLI-07 | 99/anomaly (reflex#6980), 912/F-018 | `reflex run` without a TTY ignores SIGTERM/SIGINT sent to its pid; only SIGKILL of the group stops it | MEDIUM | 99 (0.9.9a1) | no | **fixed** in 0.10.0 (#7328; reflex#6980 closed). npm path on Linux: CLI-15 | `[912] dev_server_cli/scripts/signal_test.py` | — |
| CLI-08 | 99/anomaly (reflex#6981 part) | A normal SIGTERM shutdown logs "Starting frontend failed with exit code 143" | LOW | 99 (0.9.9a1) | no | **fixed** in 0.9.12 (#6981 entry; reflex#6981 closed) | `[99] state_concurrency/`, `logging_cli/` | — |
| CLI-09 | 99/anomaly (reflex#6981 part), 912/unnumbered, N/obs | Clean shutdown logs granian's `[ERROR] Unexpected exit from worker-1` | LOW | 99 (0.9.9a1) | no | **filed-open** reflex#7266 | `[912] dev_server_cli/` | — |
| CLI-10 | 911/F-008 | `reflex run --backend-only` leaks `.web/nocompile`; the next full run serves a stale frontend | MEDIUM | 911 (0.9.11a1) | no | **fixed** in 0.9.12 (#7089; reflex#7089 closed) | `[911] event_hotpath/logs/repro_nocompile_*.out` | — |
| CLI-11 | 911/F-015 | `reflex cloud regions/vmtypes --json` exit 0 with `[]` after a 403; `cloud config --json` reports success without PyYAML | LOW | 911 (0.9.11a1) | no | **filed-open** reflex#7092 | `[911] orch_probes/logs/cloud_sweep_0911.json` | — |
| CLI-12 | 911/F-021 | One `REFLEX_USE_NPM=1` run silently keeps the project on npm | LOW | 911 (0.9.11a1) | no | **fixed** in 0.10.0 (#7305 logs why and how to switch back with `REFLEX_USE_NPM=0`; reflex#7093 closed) | `[911] orch_probes/logs/{npm_run,bun_after_npm,bun_after_rmlock}.trimmed.log` | — |
| CLI-13 | 911/F-025 | `rx.AdminDash` returns 500 on every `/admin` route (`NoMatchFound`) | MEDIUM-HIGH | 911 (0.9.11a1) | no | **fixed** in 0.9.11 (#7107) | `[911] orch_probes/adminapp/`, `admin_isolate.py` | — |
| CLI-14 | 911/F-028 | The initial dev `reflex.compile` span tree is never exported (worker exits via `os._exit`) | LOW | 911 (0.9.11a1) | n/a (new feature) | **fixed** in 0.9.12 (#7155; reflex#7095 closed) | `[911] otel/evidence/compile-span-loss.txt` | — |
| CLI-15 | F-007 | Linux: `reflex run` under npm is still alive 30 s after SIGTERM with no TTY and orphans the node dev server | MEDIUM | F (0.10.0a1) | no | **filed-open** reflex#7485 (clean on macOS a1/a2) | `[F] pymatrix_install/scripts/npm_sigterm_repro.sh` | — |
| CLI-16 | 912/F-017 | Dev backend port stays bound and swallows connections while no worker can serve (#7114) | MEDIUM | 912 (0.9.12a1) | yes vs 0.9.11.post1 | **fixed** in 0.9.12 (#7217; reflex#7213 closed) | `[912] dev_server_cli/verification/scripts/break_reload_probe.py`, `scripts/sigterm_port_probe.py` | — |
| CLI-17 | 912/F-019 | A non-UTF-8 stateful-pages marker permanently wedges backend startup | LOW | 912 (0.9.12a1) | no (0.9.12a1 strictly better than 0.9.11) | **filed-open** reflex#7245 (v0.10.0 still catches only `FileNotFoundError`/`JSONDecodeError`/`PermissionError`) | `[912] build_prod_export/` (`head -c 64 /dev/urandom > .web/backend/stateful_pages.json`) | — |
| CLI-18 | 912/F-025 | `reflex run` deletes `.states/` at startup in prod too; disk-backed state never survives a restart | LOW | 912 (0.9.12a1) | no | **open** — deliberately not filed; `reset_disk_state_manager()` still called at `reflex/reflex.py:642` in v0.10.0 | `[912] render_ctx_statemgr/logs/disk_verify.log` | — |
| CLI-19 | 912/unnumbered (reflex#7252) | Dev `reflex run` prints "Backend running at …" after the app module failed to import | LOW | 912 (0.9.12a1) | no | **filed-open** reflex#7252 | `[912] ent_mcp_oidc/NOTES.md` ISSUE-1 | — |
| CLI-20 | F-014 | `reflex component …` after its removal prints only "No such command 'component'" with no pointer | LOW | F (0.10.0a1) | n/a | **fixed** in 0.10.0 (#7497; reflex#7490 closed) | `reflex component --help` | upgrade |
| CLI-21 | F-015 | #7093's "Preferring npm" notice is printed twice | LOW | F (0.10.0a1) | no | **open** — not filed (cosmetic) | `[F] pymatrix_install/logs/3a-npm-run2-plain.log` | — |
| CLI-22 | F-019 | A stale frontend left open across an upgrade gets no user-visible version-mismatch signal | LOW | F (0.10.0a1) | no | **filed-open** — tracked by existing reflex#5534 and reflex#5394 (both open) | `[F] upgrades_a/logs/ckprod-up.server.log` | upgrade |
| CLI-23 | F-020 | Upgrading reflex under a running dev server crashes later hot reloads until restart | LOW | F (0.10.0a1) | no | **moot** — not actionable (worker forked from the old process); a restart fixes it | `[F] upgrades_a/` | — |
| CLI-24 | N-003, N-041, A3-05 | AppHarness: the same multi-module app cannot be restarted in one process; a second app sharing a package's states loses its handlers or crashes on first render | LOW | N (0.10.0a2) | no | **filed-open** reflex#7479 (A3-05 symptom and import-first workaround added as a comment) | `[N] reverify_db_install/logs/26-harness-*.log`, `thirdparty_a2/harness/test_two_apps.py`; `[A3] a3_class_state/harness/test_shared_state_harness.py` | class_state |
| CLI-25 | N-018 | npm: source-only hot reloads still reinstall packages (`devDependencies: {}` vs absent key) | LOW | N (0.10.0a2) | no | **filed-open** reflex#7480 | `[N] browser_cache_bundle/reload_cache/minimal_results/` | — |
| CLI-26 | A3-07 | `reflex run --json` ignores SIGINT sent to its pid; under supervisord `stopsignal=INT` the app is orphaned and blocks the restart | LOW | A3 (0.10.0a3) | no | **filed-open** reflex#7509 | `[A3] a3_upgrade/bin/json_matrix.sh a3fast a3 INT-pid:100000` | — |
| CLI-27 | A3-08 | #7428's 30 s drain cap ends the `--json` stream mid-record; a consumer that stops reading blocks shutdown forever | LOW | A3 (0.10.0a3) | no (better than a2) | **filed-open** reflex#7510 | `[A3] a3_upgrade/bin/json_matrix.sh a3 a3 TERM-pid:6` | — |
| CLI-28 | A1-08 | Hosting CLI: an initial rejected token with `--no-interactive` omits the `reflex login` hint the changelog promises | LOW (P3) | A1 (hosting-cli 0.1.73a1) | n/a | **filed-open** reflex#7432 | `[A1] tooling/probe.py`, `tooling/results.json` | — |
| CLI-29 | 911/F-043 | Frontend packages are reinstalled on every run / compile (package.json compared as text), so #7050's claim is not observable | MEDIUM | 911 (0.9.11a1) | no | **fixed** in 0.10.0 (#7236; reflex#7235 closed). npm residual: CLI-25 | `[911] config_assets_cli/NOTES.md` ISSUE-1 | — |
| CLI-30 | 911/F-044 | Multi-process compile of one app directory still aborts one step past the fixed asset link (#7039) | MEDIUM | 911 (0.9.11a1) | no | **unknown** — never triaged or re-tested; not filed | `[911] config_assets_cli/NOTES.md` ISSUE-2 | — |
| CLI-31 | 911/F-045 | `reflex component init` dies with "No module named pip" in a uv venv | LOW | 911 (0.9.11a1) | no | **moot** — `reflex component` removed in 0.10.0 (#6425, #7497) | `[911] config_assets_cli/NOTES.md` ISSUE-3 | — |
| CLI-32 | 911/F-046 | `reflex component build` prints five tracebacks, then reports success | LOW | 911 (0.9.11a1) | no | **moot** — `reflex component` removed in 0.10.0 | `[911] config_assets_cli/NOTES.md` ISSUE-6 | — |
| CLI-33 | 911/F-049 (a) | `reflex run --env prod` logs "Page <name> is being redefined" once per `@rx.page` | LOW | 911 (0.9.11a1) | no | **unknown** — never triaged; not filed | `[911] ent_mantine_highcharts_tickets/NOTES.md` ISSUE-3 | — |
| CLI-34 | 911/F-049 (c) | An unknown route renders the 404 page with HTTP 200 in dev and 404 in prod | LOW | 911 (0.9.11a1) | no | **unknown** — never triaged; not filed | `[911] ent_mantine_highcharts_tickets/NOTES.md` ISSUE-7 | — |
| CLI-35 | 99/anomaly (reflex#6983), 911/F-037, 912/unnumbered (router_vars), 912/P7 | Self-hosted prod serves HTTP 404 (with the SPA body) for valid dynamic-route URLs, and for every route but `/` with `REFLEX_SSR=false` | LOW | 99 (0.9.9a1) | no | **fixed** in 0.10.0 (#6996; reflex#6983 closed). The `REFLEX_SSR=false` variant was not re-tested after the fix | `[99] routing/`; `[911] frontend_path_ssr/probe_routes.sh` | — |
| CLI-36 | N/obs (ent_auth) | `reflex run --backend-only` refuses to start when rxconfig sets `frontend_port` | LOW | N (0.10.0a2) | no | **unknown** — recorded as a pre-existing anomaly; never triaged or filed | `[N] ent_auth/NOTES.md` | — |
| CLI-37 | 911/val | reflex-otel: without `OTEL_EXPORTER_OTLP_PROTOCOL`, the SDK configuration error is logged and swallowed while otel reports enabled (nothing exported) | LOW | 911 (0.9.11a2) | n/a | **open** — out of scope for #7086; not filed | `[911] PUBLISHED_VALIDATION_RESULTS.md` ("Reported separately"; `scripts/min_repro_a2.py --noproto`) | — |

## 7. Components and compiler (CMP)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| CMP-01 | 99/F-007 | Upload filename sanitizer returns `..` for all-dots names, escaping the upload dir (500) | MEDIUM (security) | 99 (0.9.9a1) | no | **fixed** in reflex-components-core 0.9.9 (#6971) | `[99] components/` (raw multipart to `/_upload`) | — |
| CMP-02 | 99/F-010 | `library="react-router-dom"` silently installs unpinned RR7 in dev and breaks prod cryptically | MEDIUM | 99 (0.9.9a1) | yes vs 0.9.8 | **fixed** in 0.9.9 (#6991: actionable error) | `[99] prod_export/` | — |
| CMP-03 | 99/F-012, 99/F-015, 99/F-019 | Generated `vite.config.js` passes a rejected `jsx` option and deprecated `advancedChunks` to vite 8.2 (warnings every build) | LOW | 99 (0.9.9a1) | yes vs 0.9.8 | **fixed** in 0.9.9 (#6987) | `[99] memo/`, `prod_export/` (`reflex export` log) | — |
| CMP-04 | 99/F-028 | Template `vite.config.js` imports `vite-plugin-safari-cachebust` without an extension (`configLoader: 'native'` warning) | LOW | 99 (0.9.9a1) | yes vs 0.9.8 | **fixed** in 0.9.9 (#6959) | `[99] up_counter_todo/` | — |
| CMP-05 | 99/F-017, 911/F-022, 911/F-019 (verifier half) | `compile_app()` discards module-scope `bundle_library()` registrations (the error tells you to do what you did); subpath imports never rewritten | MEDIUM | 99 (0.9.9a1) | no (since 0.9.2) | **fixed** in 0.9.11 (#7109; reflex#6975 closed) | `[911] ent_map_dnd_flow/bundlectx/`; `PUBLISHED_VALIDATION_RESULTS.md` rows "022" | — |
| CMP-06 | 99/F-020, 911/F-017 | `rx.plotly` drops `id` (react-plotly.js forwards only `divId`) | LOW | 99 (0.9.9a1) | no | **fixed** in reflex-components-plotly 0.9.7 (reflex#6977 closed) | `[911] orch_probes/NOTES.md` (compile-only check) | — |
| CMP-07 | 99/F-024, 911/F-013, 912/refuted | `CachedVarOperation` masks any `AttributeError` as an unchained `VarAttributeError: … _cached_get_all_var_data` | MEDIUM | 99 (0.9.9a1) | no | **fixed** in 0.9.12 (#7115; reflex#6978 closed) | `[911] orch_probes/probe_reverify.py` | — |
| CMP-08 | 99/anomaly (reflex#6979) | `rx.script(id=…)` inside `App(head_components=…)` crashes compile | LOW | 99 (0.9.9a1) | no | **fixed** in 0.9.10 (#7005) | `[99] components/` | — |
| CMP-09 | 99/anomaly | react-helmet `UNSAFE_componentWillMount` console error on pages with `rx.script` | LOW | 99 (0.9.9a1) | unknown | **unknown** — listed as "worth its own issue"; never filed or re-tested | `[99] components/NOTES.md` | — |
| CMP-10 | 911/F-002 | `rx.moment` `on_change` fires at mount and remount (react-moment 2.0.2) | LOW | 911 (0.9.11a1) | yes vs 0.9.10.post2 | **documented** — reflex-components-moment 0.9.4 Breaking Changes (#7085) and the Moment guide | `[911] up_counter_todo_clock/verification/drive_moment.py` | — |
| CMP-11 | 911/F-033 | One `rx.moment(locale=…)` changes the language of every other moment on the page | MEDIUM | 911 (0.9.11a1) | yes vs 0.9.10.post2 | **fixed** in reflex-components-moment 0.9.4 (#7110) | `[911] components_bumps/leakapp2/`, `scripts/drive_leak.py` | — |
| CMP-12 | 911/F-034 ISSUE-2 | `rx.form.message(force_match=…)` without `match` is always visible and leaks `forceMatch` to the DOM | LOW | 911 (0.9.11a1) | no | **fixed** in reflex-components-radix 0.9.10 (#7133; reflex#7097 closed) | `[911] components_bumps/NOTES.md` | — |
| CMP-13 | 911/F-034 ISSUE-3 | Radix pages emit Emotion `:first-child` SSR console errors in dev | LOW | 911 (0.9.11a1) | no | **filed-open** reflex#7098 | `[911] components_bumps/NOTES.md` | — |
| CMP-14 | 911/F-034 ISSUE-4 | Moment locale imports log duplicate `defineLocale` deprecation warnings | LOW | 911 (0.9.11a1) | no | **filed-open** reflex#7099 | `[911] components_bumps/NOTES.md` | — |
| CMP-15 | 911/F-034 ISSUE-5 | Unsupported `rx.moment` props silently become CSS | LOW | 911 (0.9.11a1) | no | **filed-open** reflex#7100 | `[911] components_bumps/NOTES.md` | — |
| CMP-16 | 911/F-034 ISSUE-6 | Plotly `layout={"title": "…"}` as a plain string renders no title | LOW | 911 (0.9.11a1) | no | **fixed** in reflex-components-plotly 0.10.0 (#7226; reflex#7101 closed) | `[911] components_bumps/results/out_dev/plotly.json` | — |
| CMP-17 | 911/F-034 ISSUE-7 | Recharts props (`tick_formatter`, `stroke_dasharray`) routed into `wrapperStyle` | LOW | 911 (0.9.11a1) | no | **fixed** in reflex-components-recharts 0.9.4 (#6833; reflex#6575 closed) | `[911] components_bumps/NOTES.md` | — |
| CMP-18 | 911/F-034 ISSUE-8 | Adding `rx.toast.provider` renders every toast twice | LOW | 911 (0.9.11a1) | no | **filed-open** reflex#7102 | `[911] components_bumps/NOTES.md` | — |
| CMP-19 | 911/F-034 ISSUE-9 | Toast docs reference `ToastAction` without a usable public import | LOW | 911 (0.9.11a1) | no | **fixed** in 0.10.0 docs (#7327; reflex#7103 closed) | `[911] components_bumps/NOTES.md` | — |
| CMP-20 | 911/F-034 ISSUE-10, 912/F-010 | Form `on_submit` data includes `null` entries for every `id=` on non-input children | LOW | 911 (0.9.11a1) | no | **fixed** in 0.10.0 (#7227; reflex#7104 closed) | `[911] components_bumps/NOTES.md`; `[912] memo_aschild/` | — |
| CMP-21 | 911/F-009 | `frontend_path` is stripped twice for routes beginning with the prefix text (`/app/apple` → 404) | MEDIUM | 911 (0.9.11a1) | no | **fixed** in 0.9.12 (#7153; reflex#7090 closed) | `[911] event_hotpath/logs/pw_routes_*_fp/results.json` | — |
| CMP-22 | 911/F-014 | `frontend_path` validation accepts Win32-trimmed (trailing dot/space) and empty segments | LOW | 911 (0.9.11a1) | no (gap in new #7044 guard) | **fixed** in 0.9.11 (#7105) | `[911] orch_probes/logs/probe_smoke.json` | — |
| CMP-23 | 911/val | `frontend_path` validator still accepts Windows reserved device names (`/con`) | LOW | 911 (0.9.11a2) | no | **open** — not filed | `[911] PUBLISHED_VALIDATION_RESULTS.md` ("Reported separately") | — |
| CMP-24 | 911/F-023 | A hook-bearing component used directly in `rx.foreach` compiles, then throws `ReferenceError` and blanks the page | MEDIUM | 911 (0.9.11a1) | no | **unknown** — maintainer said new ClientStateVar work addresses it; never verified; not filed | `[911] ent_map_dnd_flow/foreachhook/` | — |
| CMP-25 | 911/F-024 | The error boundary fallback logs three invalid-DOM-property errors above the real exception | LOW | 911 (0.9.11a1) | no | **fixed** in reflex-components-core 0.9.10 (#7130; reflex#7094 closed) | `[911] ent_map_dnd_flow/NOTES.md` | — |
| CMP-26 | 911/F-026 | `add_custom_code` touching `window` breaks `reflex export` with an opaque prerender 500 | LOW | 911 (0.9.11a1) | no | **open** — maintainer: ignore (2026-09-11); not filed | `[911] orch_probes/memoapp/` | — |
| CMP-27 | 911/F-040 | Generated memo module names and bodies are not reproducible across identical compiles | MEDIUM | 911 (0.9.11a1) | no | **unknown** — never triaged or re-tested; not filed | `[911] memo_hash/NOTES.md` ISSUE-1 | — |
| CMP-28 | 911/F-042 | `rx._x.client_state(…, global_ref=False)` throws `ReferenceError` once memoization splits reader and writer | MEDIUM | 911 (0.9.11a1) | no | **filed-open** — not filed by QA; the same defect is tracked as reflex#7426 (open; PR #7442 open), related reflex#7309 (open) | `[911] memo_hash/verification/clientstate_global_ref_split/` | — |
| CMP-29 | A1-05, 911/anomaly (up_upload_traversal_quiz) | `rx._x.code_block(use_transformers=True)` emits an empty Shiki transformer list | MEDIUM (P2) | 911 (0.9.11a1) | no | **filed-open** reflex#7430 | `[A1] components/component_probe.py`, `components/evidence/probe-*.json` | — |
| CMP-30 | 912/F-008 | `on_click` on a button inside `rx.dropdown_menu.trigger` never runs (upstream Radix pointer handling) | LOW | 912 (0.9.12a1) | no | **filed-open** reflex#7250 | `[912] memo_aschild/` `/triggers` | — |
| CMP-31 | 912/F-012 | `rx.data_editor` overlay (image-preview carousel) cannot open in prod: the badge app-wrap swallows `#portal` | HIGH (impact) | 912 (0.9.12a1) | no | **fixed** in 0.9.12 (#7218; existing reflex#6143 closed) | `[912] components_bumps/gallery`, `components_bumps/verification/` | — |
| CMP-32 | 912/unnumbered (reflex#7255) | `_app_root` nests every app wrap in the previous one; a wrap ignoring its children swallows all lower-priority wraps (general form of CMP-31) | LOW | 912 (0.9.12a1) | no | **filed-open** reflex#7255 | reflex#7255 | — |
| CMP-33 | 912/F-013 | `rx.vars.use_id()` in an `rx.foreach` body returns one id for every item (docs gap) | LOW | 912 (0.9.12a1) | n/a (new API) | **open** — deliberately not filed (2026-09-22) | `[912] components_bumps/NOTES.md` | — |
| CMP-34 | 912/F-015 | `rx.upload_files()` from a toast action or `call_script` callback throws `filesById is not defined` (the case #7156's changelog names) | MEDIUM | 912 (0.9.12a1) | no | **filed-open** reflex#7244 | `[912] event_loop/elapp` `/callback`; verifier `/upbtn` control | — |
| CMP-35 | 912/F-022 | `frontend_lazy_bundled_libraries=True` added ~65 KB of initial JS on every page of the test app | LOW (perf) | 912 (0.9.12a1) | n/a | **filed-open** reflex#7262 | `[912] build_prod_export/NOTES.md` | — |
| CMP-36 | 912/F-027 | CDN fallback URL for an unbundled sub-path `@rx.dynamic` import is malformed (`…/+esm/dist/esm/icons/bug.mjs`) | LOW | 912 (0.9.12a1) | no | **filed-open** reflex#7249 | `[912] build_prod_export/verification/out/vcheck_prod_new.json` | — |
| CMP-37 | 912/unnumbered (reflex#7256) | `rx.Var.create(x)._replace(_var_data=…)` raises `TypeError` | LOW | 912 (0.9.12a1) | no | **fixed** in 0.10.0 (#7306; reflex#7256 closed) | `[912] vars_typing/NOTES.md` O5 | — |
| CMP-38 | 912/unnumbered (reflex#7257) | Recharts `Axis.tick_formatter` accepts only a literal string; function vars raise | LOW | 912 (0.9.12a1) | no | **fixed** in reflex-components-recharts 0.10.0 (#7366; reflex#7257 closed) | `[912] components_bumps/NOTES.md` | — |
| CMP-39 | 912/P7 | `rx.accordion.root(collapsible=True, type="multiple")` triggers a dev React warning | LOW (cosmetic) | 912 (0.9.12a2) | no | **open** — deliberately not filed | `[912] FINDINGS.md` Phase 7 | — |
| CMP-40 | A1-04 | A 1,500-State app builds but renders blank (React mutation-traversal stack overflow) | MEDIUM (P2) | A1 (0.10.0a1) | unresolved (stable fails at 1,300) | **filed-open** reflex#7429 (fix PR #7441 open) | `[A1] enterprise/many_states/REPORT.md`, `QA_EXTRA_STATES=1500`; `[A1] enterprise/a4/scale/REPORT.md` | — |
| CMP-41 | A1-06 | Primitive Progress updates visually but stays indeterminate to accessibility tools (Root lacks value) | MEDIUM (P2) | A1 (0.10.0a1) | no | **filed-open** reflex#7431 | `[A1] components/component_probe.py` | — |
| CMP-42 | A1/obs | Two Grid.js `TypeError`s logged in an initial dashboard run | LOW | A1 (0.10.0a1) | unknown | **unknown** — not reproduced in narrowed or final reruns | `[A1] components/REPORT.md` | — |
| CMP-43 | F-012 | `PageContext.get()` outside a context raises a bare `LookupError` (ContextVar repr only) | LOW | F (0.10.0a1) | no (type change documented in #6553) | **filed-open** reflex#7489 | `[F] thirdparty/verification/classattr/scripts/derive_c.py` | — |
| CMP-44 | F-018 | React 19.3 logs an extra "script tag while rendering" console error when a route module fails to load | LOW | F (0.10.0a1) | yes (React 19.2.8 → 19.3.0) | **open** — not filed (only seen with reflex-clerk) | `[F] thirdparty/apps/tp_components` `/clerk`, `drivers/debug_page.py` | — |
| CMP-45 | N-010 | DataEditor data callback escapes the `rx.foreach` scope: zero editors render, page falls into the error boundary | MEDIUM | N (0.10.0a2; 10-06 lead) | no | **open** — not filed | `[N] board/findings-inbox/dataeditor-1.md` (`/de-foreach`, `focused_driver.py --groups de_foreach`) | — |
| CMP-46 | N-011 | Starting a DataEditor edit by typing loses the leading characters | MEDIUM | N (0.10.0a2; 10-06 lead) | no | **open** — not filed | `[N] board/findings-inbox/dataeditor-2.md` (`typing_driver.py`) | — |
| CMP-47 | N-012 | DataEditor with `on_delete` bound throws `TypeError: undefined.length` and never clears the cell | MEDIUM | N (0.10.0a2; 10-06 lead) | no | **open** — not filed | `[N] board/findings-inbox/dataeditor-3.md` | — |
| CMP-48 | N-013 | Escape right after opening a single-image preview leaves the carousel open | LOW | N (0.10.0a2) | no | **open** — not filed | `[N] board/findings-inbox/dataeditor-4.md` (`--groups de_overlay`) | — |
| CMP-49 | N-014 | Radix form controls' synthetic clicks throw `undefined[0]` when a DataEditor is on the page | LOW | N (0.10.0a2) | no | **open** — not filed | `[N] board/findings-inbox/dataeditor-5.md` | — |
| CMP-50 | N-023 | String Vars use UTF-16 code units; a split surrogate pair in prerendered HTML triggers React #418 | LOW | N (0.10.0a2) | no | **filed-open** reflex#7481 | `[N] events/` evapp `/emoji-rev` | — |
| CMP-51 | N-028 | `window.onerror` throws when the error event has no Error object (ResizeObserver loop), so nothing reaches `handle_frontend_exception` | LOW | N (0.10.0a2) | no | **filed-open** reflex#7482 | `[N] ent_grid/scripts/probe_mantine_pageerror.py` | — |

## 8. Third-party packages and example apps (TP)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| TP-01 | F-009 | reflex-chat `initial_messages` leaks messages across sessions (mutable `Field.default` shared by every instance) | MEDIUM | F (0.10.0a1) | no | **filed-open** chat#61; not re-tested on 0.10.0 final (see upgrade guide on shared `.default`) | `[F] thirdparty/apps/tp_components` `/chat-initial`, `drivers/drive_chat_leak.py` | — |
| TP-02 | N-042 | `reflex run --env prod` fails to build any app with a reflex-monaco, reflex-webcam or reflex-clerk page | LOW | N (0.10.0a2) | no | **open** — not filed (no access to those repos) | `[N] thirdparty_a2/bin/prod_probe.sh`, `logs/tp_components-prod-build-matrix.txt` | — |
| TP-03 | N/obs, A4/obs | reflex-clerk 1.0.3 on 0.10: class-level backend-var read returns `Field` (`set_clerk_session` TypeError) and its class writes raise #7516's TypeError (reflex-dynoselect similar) | LOW (downstream) | N (0.10.0a2) | yes vs 0.9.12 | **open** — not filed; package needs `ClassVar`; candidate for a known-incompatible list | `[N] thirdparty_a2/NOTES.md`; `[A4] a4_class_state/NOTES.md` | — |
| TP-04 | A1-07 | Overkey example: Reset keeps the typed client-state input | LOW (P3) | A1 (0.10.0a1) | no | **filed-open** examples#324 | `[A1] components/upgrades/REPORT.md` | — |
| TP-05 | 99/refuted, 912/unnumbered | form-designer: `/form/<id>` places `rx.form.message` outside `rx.form.field` and crashes; no login auto-redirect | LOW | 99 (0.9.9a1) | no | **open** — not filed (reflex-examples not reachable from the QA sandbox) | `[99] up_lorem_form/NOTES.md`; `[912] up_examples_b/` | — |
| TP-06 | 99/refuted, 912/unnumbered | upload example: dependency-less cached `@rx.var files()` never refreshes | LOW | 99 (0.9.9a1) | no | **open** — not filed | `[99] up_upload_clock/NOTES.md` | — |
| TP-07 | 912/unnumbered | basic_crud, twitter and data_visualisation examples ship no alembic directory | LOW | 912 (0.9.12a1) | no | **open** — not filed | `[912] up_examples_a/`, `up_examples_b/` | — |
| TP-08 | 99/refuted | reflexle example discards its "Invalid word" / "already guessed" toasts | LOW | 99 (0.9.9a1) | no | **open** — not filed (example-app logic) | `[99] up_reflexle_snake/NOTES.md` | — |
| TP-09 | 99/refuted | basic_crud: `GET /products/<missing id>` returns 200 with a serialized HTTPException | LOW | 99 (0.9.9a1) | no | **open** — not filed (example-app bug) | `[99] up_local_basic/NOTES.md` | — |

## 9. Docs and changelogs (DOC)

| ID | Aliases | Title | Sev | First seen | Regression | Status @ 0.10.0 / rxe 0.9.7 | Repro | Fixture |
|---|---|---|---|---|---|---|---|---|
| DOC-01 | 99/F-009 (half) | A second bare `rx.App()` in one process now raises `ReflexRuntimeError`, undocumented | MEDIUM | 99 (0.9.9a1) | yes vs 0.9.8 | **documented** — 0.9.9 Breaking Changes (#6382) | `[99] registration_context/NOTES.md` | — |
| DOC-02 | 911/F-027 | reflex-otel's documented env-var recipe exports nothing (`otlp` resolves to gRPC, recipe installs the HTTP exporter) | MEDIUM | 911 (0.9.11a1) | n/a (new package) | **fixed** in reflex-otel 0.1.0 (#7086 sets `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`) | `[911] otel/evidence/run9-readme-env-traceback.txt` | — |
| DOC-03 | 911/F-047 | reflex-base's changelog re-lists the two #6933 entries under three versions | LOW | 911 (0.9.11a1) | n/a | **open** — not filed; v0.10.0 reflex-base CHANGELOG still lists them under v0.9.9.post1, v0.9.10.post1 and v0.9.11 | `git show v0.10.0:packages/reflex-base/CHANGELOG.md` (grep 6933) | — |
| DOC-04 | 912/F-002, 912/unnumbered (#7115 `hasattr`, #7131 wording) | 0.9.12 changelog: the #7132 `_get_was_touched` entry describes unreachable behaviour; #7115's `hasattr`/`getattr` change undocumented; #7131 wording | LOW | 912 (0.9.12a1) | n/a | **filed-open** reflex#7260 | `[912] orch_probes/reserved_names_probe.py` | — |
| DOC-05 | 912/F-021 | `frontend_path` is applied only through `rx.asset()`; a literal `src="/…"` silently 404s; undocumented | LOW | 912 (0.9.12a1) | no | **filed-open** reflex#7261 | `[912] build_prod_export/NOTES.md` | — |
| DOC-06 | 912/unnumbered | `rx.asession()` requires `async_db_url`; nothing in the docs says so | LOW | 912 (0.9.12a1) | no | **open** — deliberately not filed | `[912] db_optional_imports/NOTES.md` | — |
| DOC-07 | 911/anomaly (otel) | PR descriptions of #6899/#6901 describe behaviour the shipped otel code lacks (span kind, endpoint fallback) | LOW | 911 (0.9.11a1) | n/a | **moot** — README and docs are correct; only PR text is wrong | `[911] FINDINGS.md` cluster `otel` | — |
| DOC-08 | A1-09 | Changelogs link wrong targets: the callable-default migration entry links issue #6706 (implementing PR is #6770); rxe's AG Grid entry links a 404 `issues/ag-grid-36` | LOW (P3) | A1 (0.10.0a1) | n/a | **open** — ignored at the user's direction; both links are still in reflex v0.10.0 CHANGELOG ("Database" section) and rxe v0.9.7 CHANGELOG | `[A1] tooling/reference/`, `enterprise/reference/` | — |
| DOC-09 | N-002 | No changelog entry for #7462 (sqlmodel cap removal changes naive-datetime semantics on `uv pip install -U`) | LOW | N (0.10.0a2) | n/a | **fixed** in 0.10.0 (#7496; Breaking Changes entry for #7462) | `[N] reverify_db_install/logs/19-naive-uvU-run.log` | upgrade |
| DOC-10 | N-007 | The documented `State._x.default_value()` is not portable to 0.9.x | LOW | N (0.10.0a2) | n/a | **documented** — upgrade guide gives the portable `get_fields()[name].default_value()` (#7496; reflex#7474 closed) | `[N] reverify_core/` | — |
| DOC-11 | A3-03 | A named storage var's key is shared by every ComponentState instance; the a3 changelog example implied per-instance persistence | LOW | A3 (0.10.0a3) | no (0.9.12 shares too) | **documented** — `docs/state_structure/component_state.md` per-component `name=f"theme_{key}"` (via #7516; PR #7514 closed) | `[A3] a3_class_state` (`csbox`) | hydration |
| DOC-12 | A5-05 | Upgrade guide says assigning `State.__fields__["items"].default = []` "was safe" on 0.9 — false (0.9.12 shared the list across sessions; backend `.default` assignment was ignored) | LOW | A5 (0.10.0a5) | n/a | **open** — not filed; sentence still at `docs/changelog/upgrading/upgrading-to-0-10.md:72` in v0.10.0 (suggested rewording in `[A5] verify_class_state5/NOTES.md`) | `[A5] verify_class_state5/NOTES.md` | class_state |
| DOC-13 | A5/obs | #7360's `State.router.headers.cookie` deprecation named `deprecation_version="0.9.13"` inside 0.10 | LOW | A5 (0.10.0a5) | n/a | **fixed** in 0.10.0 (#7523: `deprecation_version="0.10.0"`, `reflex/istate/data.py:173`) | `[A5] FINDINGS.md` "Pre-existing / informational" | — |
| DOC-14 | A5/obs | #7360's cookie deprecation warns only in the compile/server log; `raw_headers["cookie"]` / `["authorization"]` silently become undefined | LOW | A5 (0.10.0a5) | n/a | **documented** — `docs/utility_methods/router_attributes.md` and 0.10.0 Deprecations/Bug Fixes (#7360) | `[A5] a5_hydration_router/NOTES.md` | — |

## Refuted and reclassified claims

Claims a verifier refuted or reclassified as not-a-defect. Kept so the next pass does not re-file them; not counted in
the summary. Where a refuted claim exposed a real defect, the defect has its own row.

| Campaign claim | Verdict | Where |
|---|---|---|
| 99: PR #6863 "`import reflex` bootstraps the loggers" is not literal | wording in a PR description only | `[99] FINDINGS.md` "Refuted" |
| 99: transient "incorrect peer dependency react-router@7.18.2" bun warnings during the 0.9.8 → 0.9.9 migration | benign by design | `[99] up_counter_todo/`, `up_local_basic/` |
| 99: fresh prerelease-enabled `reflex[db]` pulls pydantic 2.14.0b1 | same on 0.9.8; resolver flag semantics | `[99] up_lorem_form/` |
| 99: enterprise prod untestable without a paid subscription | licensing behaviour, not a defect | `[99] ent_map_dnd/` |
| 99: MCP plugin `IncompleteFieldDefinitionWarning` (pydantic-settings) | upstream warning | `[99] ent_misc/` |
| 99: form-designer / upload / reflexle / basic_crud example quirks | example-app bugs, not reflex (rows TP-05…TP-09) | `[99] FINDINGS.md` Phase 2 refuted |
| 912/F-005: a narrow `deps=` cannot narrow router dependencies | `deps=[State.router.url], auto_deps=False` narrows; additive by design | `[912] router_vars/verification/scripts/v_narrow_deps.py` |
| 912/F-007: #7136's `REFLEX_STATE_ALLOW_RESERVED_NAMES` escape hatch missing | promised only in the PR description | `[912] FINDINGS.md` |
| 912/F-009: `rx.cond` evaluates both branches eagerly | only raw `rx.Var("<js>")` literals are inlined (JS semantics) | `[912] memo_aschild/verification/app_boomy` |
| 912/F-014: #7124's import path fails | module path works; `from … import code` never did | `[912] components_bumps/` |
| 912/F-020: `@rx.dynamic` never re-renders | delta carries the component; CDN blocked in sandbox (exposed CMP-36) | `[912] build_prod_export/verification/` |
| 912/F-021: literal asset `src` not prefixed with `frontend_path` | by design (`rx.asset()`); docs gap DOC-05 | `[912] build_prod_export/` |
| 912/F-026: #7083 changelog understates the `rx.Model` change | wording covers every subclass | `[912] db_optional_imports/` |
| 912: masked cached-var `AttributeError` still present | fixed by #7115 on 0.9.12a1 (CMP-07) | `[912] ent_aggrid/scripts/probe_masked_attrerror.py` |
| 912: a failing `rx.asession()` in a background task is invisible | an error toast is shown (DOC-06 remains) | `[912] db_optional_imports/verification/shots/` |
| 912: npm stickiness has no way back | `REFLEX_USE_NPM=0` restores bun | `[912] dev_server_cli/verification/scripts/lock_probe.sh` |
| 912: "#6181 halves the on_load render count" | measurement noise (bimodal on every version) | `[912] FINDINGS.md` Phase 7 |
| 912/P7: declaring `get_delta` is rejected | blanket reserved-member guard with a working opt-in (cosmetic message row STATE-35) | `[912] FINDINGS.md` Phase 7 |
| F: "0.9.12 passes the computed-var storage test deterministically" | 0.9.12 is hash-seed dependent (HYD-02 kept, MEDIUM) | `[F] FINDINGS.md` |
| F: pre-connect navigation is a MEDIUM regression | same race on 0.9.12 (HYD-06, LOW) | `[F] FINDINGS.md` |
| F: class-level backend attr change breaks published packages broadly | only reflex-clerk / reflex-dynoselect, both already broken | `[F] FINDINGS.md` |
| F: `uv pip install 'reflex==0.10.0a1'` without `--prerelease=allow` fails | uv prerelease semantics, same on every alpha | `[F] FINDINGS.md` |
| F: `instance._backend_vars` still exists and returns None | reserved `ClassVar[None]` for pickle compatibility | `[F] FINDINGS.md` |
| F partial leads closed by N: `rx.select` id-only payload; nested-dialog form submit propagation; nested event list `TypeError`; `temporal.offline_disconnect`; `api.*` sibling/dataclass checks; failing substate `__init__`; recharts tick-formatter checks; prod master-detail / memo-grid failures | usage, pre-existing by design, passing on rerun, or explained by N-025 (ENT-29) | `[N] FINDINGS.md` "events", "dataeditor", "ent_grid" |
| A3-05 reported as a regression | pre-existing; folded into CLI-24 | `[A3] FINDINGS.md` |
| A4-03 reported as a race defect | consistent last-writer-wins (HYD-11) | `[A4] verify_hydration/NOTES.md` |

## Untriaged cluster observations

Mentioned in cluster summaries but never numbered, verified or filed. Status for all: **unknown**. Not counted in the
summary.

| Campaign | Observation | Where |
|---|---|---|
| 99 | 0.9.9a1 enterprise prod newly required `frontend-port == backend-port` | `[99] ent_map_dnd/NOTES.md` |
| 911 | Stale `__pycache__` after a same-second double save | `[911] hmr_runtime/NOTES.md` |
| 911 | Vite "Could not Fast Refresh" for `context.jsx` | `[911] hmr_runtime/NOTES.md` |
| 911 | Duplicate HMR frames | `[911] hmr_runtime/NOTES.md` |
| 911 | A background task is killed by a dev worker restart | `[911] hmr_runtime/NOTES.md` |
| 911 | One extra reload when toggling `REFLEX_DEV_PROD_REACT` | `[911] hmr_runtime/NOTES.md` |
| 911 | `hybrid_property` error quality: a `None` var function renders nothing / bakes "None" into f-strings; list/dict getters yield plain containers at class level; a `TYPE_CHECKING`-only dataclass annotation hides its attributes; `len(var)` raw TypeError | `[911] hybrid_property/NOTES.md` |
| 911 | First click on a Highcharts point after a fresh load sends no websocket frame | `[911] ent_mantine_highcharts_tickets/NOTES.md` ISSUE-6 (911/F-049 b) |
| N | `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` crashes lambda `cell_renderer` → Radix component with React #130 | `[N] ent_grid/NOTES.md`; `[A3] a3_ent_grid/NOTES.md` |
| A3 | `rx.badge(params.value)` in an AG Grid renderer shows a JSON-quoted value; AG Grid warning #306 for `tooltip_field` (0.9.12 + rxe a5 too) | `[A3] a3_ent_grid/NOTES.md` |
| A3 | Every returning visit rewrites every storage value at boot (cookie `max_age` slides; raw cookies set outside reflex come back URL-encoded) — by design as on 0.9.12; a4 limits it to `sync=False` keys | `[A3] a3_hydration/NOTES.md` |

## Harness lessons (not product findings)

Recorded by the campaigns about their own tooling; relevant to anyone reusing the fixtures.

- `[A1] REVIEW.md` 1–4: the runtime browser driver's pass flag ignores console errors and HTTP failures; the ORM
  subprocess does not itself drop `PYTHONPATH`; unexpected failures can discard partial evidence before it is
  written; the Free-tier credential helper checks a lexical path prefix (`..` escapes it).
- Never `pkill -f "reflex run"` (it matches the invoking shell); kill by pid or listening port. Terminating
  `reflex run` can orphan the vite / react-router process that keeps the frontend port bound (`[911] README.md`,
  `[912] README.md`).
- Create venvs from a neutral cwd: inside the reflex checkout uv's `exclude-newer` hides fresh alphas, and the
  checkout's `reflex/` shadows the install. `uv pip install reflex==<alpha>` without `--upgrade` (or without naming the
  component alphas) leaves stable component packages in place.
- Pin `pydantic<2.14` and `sentry-sdk<3` under `--prerelease=allow`; add `greenlet` to any 0.9.x `reflex[db]` venv.
- Enterprise dev needs `CI=true` (or the offline wheel); enterprise prod is behind the paid-tier gate.
- Explorer "regression" claims need a same-machine baseline run on the previous stable; several were refuted because
  that baseline was skipped (912/F-016, F-003's 5/5 claim, A3-05).

## Re-verify on every pass

The fixed regressions most likely to come back, in priority order. Run the original repro with the last broken version
as a positive control first.

| # | Registry ID | What to check | Why it can regress | Fixture |
|---|---|---|---|---|
| 1 | HYD-01, HYD-02 | A fresh browser profile gets **nothing** written to localStorage/sessionStorage/cookies on first load; a computed var's hydration-time storage rewrite reaches the browser | Any change to `hydrate_and_load` / the boot delta / `applyClientStorageDelta` (#7460, #7493, #7505 all touched it) | hydration |
| 2 | HYD-08, HYD-09 | `sync=True` LocalStorage with 3+ tabs at ~100 ms RTT, session restore, on_load stamps: 0 storms, all tabs and storage converge | Boot-echo and storage-event handling in `state.js` (#7505) | hydration |
| 3 | ENT-30 | OIDC cross-tab logout (`vdrv.py away/stale/xtab`); a core `get_delta` override sees boot-time storage values | Boot sequence must keep routing client storage through `get_delta` (#7493) | enterprise |
| 4 | ENT-29 | Prod, prerendered route: AG Grid with state-valued `column_defs` and `detail_cell_renderer_params` renders on full load and reload | Depends on rxe ≥ 0.9.7 and on render-before-`window.__reflex` ordering | enterprise |
| 5 | ENT-16, DOC-14 (#7360) | No `client_token`/`session_id` in REST/MCP responses; no cookie or credential header in any websocket frame, prerendered HTML or DOM | Any router-data or serialization rename silently defeats redaction | enterprise |
| 6 | EVT-06 | A `cache=False` var withheld by a `get_delta` override is delivered once the override releases it | Delta dedupe bookkeeping (#6946, #7216) | — |
| 7 | STATE-05 | `type(rx.State) is BaseStateMeta`; a `BaseStateMeta`-derived metaclass on a State subclass constructs; all rxe modules import | Any metaclass/validation refactor | — |
| 8 | STATE-11…19 | `State.x = …` / `mock.patch.object(State, "x", …)` raise the documented TypeError naming the declaring state; patching the field round-trips; dev guard rejects `_x__y` | #7516 / #7519 guard paths | class_state |
| 9 | STATE-20, STATE-21 | Schema hash identical across consecutive builds; previous-alpha pickles load; 0.9 → 0.10 sessions survive | Field/default changes alter the saved-state schema | class_state |
| 10 | PKG-09, PKG-08, PKG-05 | Fresh `reflex[db]` on 3.11–3.14 with pip and uv: greenlet present, migrations apply on a fresh DB; a stock install resolves the whole train | Upstream dependency releases (SQLAlchemy, sqlmodel) and floor changes | upgrade |
| 11 | CLI-16 | Dev backend refuses fast while the app module is broken and after shutdown; stays bound across hot reload | Granian supervisor socket handling (#7114, #7217) | — |
| 12 | EVT-04 | Prod + Redis + default workers: 6/6 backend-initiated deltas delivered | Worker identity assignment at fork (#7108) | — |
| 13 | HYD-15, CMP-05 | Backend-only / prebuilt-frontend workers serialize state referencing bundled libraries; module-scope `bundle_library()` survives compile | Bundled-library registry lifecycle (#7096, #7109) | enterprise |
| 14 | CMP-31 | Prod with the default badge: `#portal` and every lower-priority app wrap reach the DOM; data_editor overlay opens | App-wrap nesting (#7218; general form still open as CMP-32) | — |
| 15 | CMP-11 | Moment pages: un-localed siblings stay English next to a `locale="fr"` moment; `locale="en"` builds in prod | Component bumps (react-moment) | — |
| 16 | ENT-01, ENT-02, CLI-03 | `dynamic.bundled_libraries`, `reflex.page.DECORATED_PAGES`, `get_config(reload=True)` still work with a DeprecationWarning | Deprecated shims are scheduled for removal in 1.0; rxe still reading them would break | enterprise |
| 17 | CMP-01, EVT-02 | Hostile upload filenames stay inside the upload dir; `client_error` with no payload is ignored without a traceback | Security fixes in network-facing handlers | — |
