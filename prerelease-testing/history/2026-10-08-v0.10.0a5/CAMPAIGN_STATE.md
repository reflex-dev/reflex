# Campaign state (compact context) — final pre-release pass on the 0.10.0a5 train (2026-10-08)

## What is under test
- **reflex 0.10.0a5 + reflex-base 0.10.0a5**, released from `origin/r/pre-2026.10.06-37579583012` at `57aee8ccf`
  (tag `v0.10.0a5`). Only these two packages were re-released; every other train package stays on its a2-train
  version. All 20 packages are on PyPI with wheel + sdist; reflex 0.10.0a5 pins `reflex-base==0.10.0a5`; every source
  file a5 changed is byte-identical in the installed wheels (`preflight/`).
- **reflex-enterprise 0.9.7a5** (unchanged, newest on PyPI). Offline wheel at `$SB/downloads/enterprise_wheel_a5/`.

## What a5 changed (a4 → a5: exactly three PRs; `git diff v0.10.0a4 v0.10.0a5`)
| PR | Change | Risk |
|---|---|---|
| #7360 (security, ENG-12909) | `reflex/istate/data.py`: the frontend serialization of `router.headers` drops `cookie`, and `raw_headers` drops `cookie`, `authorization`, `proxy-authorization`, `cf-access-jwt-assertion`, `x-auth-request-access-token`, `x-forwarded-access-token`, `x-amzn-oidc-accesstoken`, `x-amzn-oidc-data`, `x-goog-iap-jwt-assertion`. In components, `State.router.headers.cookie` / `State.router.headers["cookie"]` are DEPRECATED (deprecation_version "0.9.13") and render `""`. Server-side (`self.router.headers...` in handlers) is meant to be unchanged. `reflex/state.py` `_load_events_for_page`: on_load events are no longer created with `router_data=state.router_data` (backend chains inherit the originating view through `EventContext`). Changelog: Deprecations + Bug Fixes entries in reflex 0.10.0a5. | every `on_load` handler that reads `self.router` (page path/params/url/query, headers, session client_token/session_id/client_ip) on first load, reload, client nav, dynamic routes, redirects, chains, background tasks started from on_load, prod + Redis multi-worker; enterprise auth (page guards build `login_url_for(str(state.router.url))`, cookie auth reads `instance.router.headers.cookie` server-side, `_event_client_token` falls back to `event.router_data`, api_tokens `persist_router_data`); apps that render `State.router.headers.cookie` / `raw_headers`; the security claim itself (no cookie / auth header in any websocket frame, dev and prod) |
| #7519 | `reflex_base/vars/base.py`: new public `Field.set_default(default=MISSING, *, default_factory=None)` (exactly one; a mutable default becomes a deep-copying factory); `_default_arguments` now deep-copies a mutable class-body default ONCE at class definition (`partial(deepcopy, deepcopy(value))`) instead of copying the live object per instance; the #7516 TypeError now names the DECLARING state (`Owner.__fields__[name].set_default(...)`, "inherited by Sub" wording). Docs/upgrade guide use `set_default`. | a mutable default that is mutated after the class is defined (module-level list/dict populated later — registries, plugins, lazily loaded config) is now snapshotted at definition (instances no longer see later additions — compare 0.9.12 and a4); a default that cannot be deep-copied now fails at class definition / import instead of at first instance; large defaults copied once more; the error message's owner for substates, mixins, ComponentState, dynamic vars (A4-01); `set_default` semantics vs `.default =` |
| #7504 | `reflex-components-internal` demo form only (not a published train package) | none for users |

## Identified-and-fixed regressions to re-verify on a5 (run the ORIGINAL repro; positive control on the broken version first)
| id (pass) | what | broken on | repro assets | item |
|---|---|---|---|---|
| F-002 (a1 pass) | first page load writes client-storage defaults into the browser | a1 (`$SB/envs/alpha` if present) | `2026-10-06/` + `2026-10-07/reverify_hydration/`, `2026-10-07-a3/a3_hydration/scripts/run_f002.sh` | a5_hydration_router |
| F-003 (a1) | computed var rewriting a storage var at hydration never reaches the browser (google-auth bogus token) | a1 | `2026-10-07-a3/a3_hydration/scripts/run_gauth.sh`, cvstore a–j | a5_hydration_router |
| A3-11 / A3-12 (a3) | `sync=True` cross-tab storms | a3 | `2026-10-08-a4/a4_hydration/` (storm, stamp, verifier scenarios) | a5_hydration_router |
| N-032 (a2) | OIDC cross-tab logout (reflex side #7493) | a2 + ent a4/a5 | `2026-10-08-a4/a4_upgrade_ent/ent/auth/`, `2026-10-07-a3/a3_ent_auth/verification/drivers/vdrv.py` | a5_upgrade_ent |
| N-025 (a2) | prod AG Grid Var `column_defs` empty | ent a4 | `2026-10-08-a4/a4_upgrade_ent/ent/grid/` (entv) | a5_upgrade_ent |
| N-001 (a2) | `reflex[db]` without greenlet | a2 | fresh `reflex[db]==0.10.0a5` venv on 3.11–3.14, `reflex db init/makemigrations/migrate` | a5_upgrade_ent |
| F-005 / F-006 (a1) | sqlmodel cap / component floors | a1 | fresh `pip install reflex==0.10.0a5` (no `--pre`), fresh-db migrations | a5_upgrade_ent |
| F-014 (a1) | `reflex component` message | a2 | `reflex component init` | a5_upgrade_ent |
| F-004 / N-005 / N-039 / A3-01 / A3-02 / A3-04 (a1–a3) | class-level assignment / patch / storage defaults → now: assignment raises, defaults via `__fields__[...].set_default` | a1–a3 | `2026-10-08-a4/a4_class_state/` (test_a4_moot, test_a4_converted, probe_storage_fields, apps/c4e2e) | a5_class_state |
| N-008 (a2) | dev guard accepts `_x__y` | a2 | `2026-10-08-a4/a4_class_state/` guard7495 | a5_class_state |
| N-004 (a2) | state-store compatibility (documented) | — | schema hash a4 == a5; a4 ↔ a5 interchange | a5_class_state |
| A4-01 / A4-02 (a4, NOT fixed — status check) | substate `add_var` / auto-setter collisions | a4 | `2026-10-08-a4/verify_class_state/` | a5_class_state |

Known and filed (do NOT re-report unless changed): A3-07, A3-08, A3-09, A3-10, A3-13, A4-03 (last-writer-wins), the
`rx.remove_local_storage` null sync, N-026, N-028, N-033, F-007, F-008, F-009, F-010, F-011–F-013, F-015–F-020,
reflex#7506, reflex-clerk 1.0.3.

## Environment
- SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad. Venvs: `a5` (under test), `a4`
  (previous alpha), `a3` (positive control for a4 fixes), `stable` (0.9.12), `driver`, `a5-ent` / `a4-ent` / `a3-ent`,
  `s912-ent-a5`; `alpha` and `alpha2` (0.10.0a1 / a2) from earlier passes if present — check `bin/python -m pip show reflex`.
- Disk is tight (~12 GB free): delete each app's `.web/` and `node_modules/` when done with it.
- Chromium: `/opt/pw-browsers/chromium`. Artifacts: `prerelease_testing/2026-10-08-a5/<item>/` on branch
  `claude/reflex-prerelease-testing-t0sd90` (the orchestrator commits; agents never run git write commands).
