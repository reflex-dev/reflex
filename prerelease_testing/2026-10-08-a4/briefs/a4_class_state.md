# Brief: a4_class_state — re-verify A3-01/02/04 (now moot) on 0.10.0a4 and hunt #7516 regressions

Read first: `/home/user/reflex/prerelease_testing/2026-10-08-a4/AGENT_BRIEF.md` (hard rules), then
`/home/user/reflex/prerelease_testing/2026-10-08-a4/CAMPAIGN_STATE.md` (what a4 changed). Your artifacts go to
`/home/user/reflex/prerelease_testing/2026-10-08-a4/a4_class_state/`; scratch under `$SB/apps/a4_class_state/`.
Ports: frontend 3300-3319 / backend 8300-8319. Redis, if needed: a port from your backend range.
Build your own venvs with pytest / pytest-mock (e.g. `$SB/envs/a4_class_state-a4` with `reflex[db]==0.10.0a4`
`reflex-base==0.10.0a4` `pydantic<2.14` pytest pytest-mock pytest-asyncio; same for a3 and 0.9.12 baselines; Python 3.11
and 3.14 once each for the core probes).

#7516 is an intentional BREAKING change: on 0.10.0a4, assigning over a state var through its class
(`S.x = v`, `setattr(S, "x", v)`, `monkeypatch.setattr(S, "x", v)`, `mock.patch.object(S, "x", v)`) raises
`TypeError`; defaults are set with `S.__fields__["x"].default = v` (or `.default_factory`), tests patch the field. Read the
PR (reflex-dev/reflex#7516, GitHub MCP `pull_request_read`) and the merged source (`git show v0.10.0a4:packages/reflex-base/src/reflex_base/vars/base.py`, `BaseStateMeta.__setattr__` / `__delattr__` /
`_state_var_assignment_error`) before testing. Judge a4 against what #7516 and its docs promise, and against 0.9.12 for
anything users relied on.

## Part 1 — re-run the ORIGINAL repros of A3-01, A3-02, A3-04 (positive control on a3 first)
Assets under `/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_class_state/` (COPY them out): `NOTES.md`,
`probes/undo_edge/test_undo_edge.py`, `verification/probes/test_v7_undo.py`, `verification/probes/probe_v8_storage.py`,
`probes/adv7495.py` (case `thread_stress_assign_restore`), e2e app `apps/clse2e`. On a3 they must fail as recorded; on a4
each assignment must raise the documented `TypeError` at the assignment line and leave the var fully working (field
unchanged, instances get the declared default, `reset()`, pickling, the compiled page). Then convert each repro to the
supported a4 API (`__fields__[...]` defaults; `mock.patch.object(S.__fields__["x"], "default", v)`; monkeypatch on the
field; `monkeypatch.delattr(S, "x")` + `monkeypatch.setattr(S, "x", v, raising=False)` on the declaring class) and show the
original intent now works or is cleanly unsupported: no leaked default, no lost configuration, threads patching field
defaults concurrently (A3-04's stress, adapted) end on the declared default.
Also re-check under the new semantics: N-005 (storage default via `__fields__` with a storage value keeps storage, name
and options — e2e dev + prod/Redis, `str`-annotated and storage-annotated vars, LocalStorage/Cookie/SessionStorage), N-039
(field patching round-trips; downstream packages' own State vars patched through their fields), N-008 (the dev guard
against `self._sneaky__name = 1` still raises; own/base/mixin mangled names still fine), N-004 (a3 ↔ a4 interchangeable:
same schema hash, a3-written Redis/disk sessions load on a4 and vice versa).

## Part 2 — #7516 regression hunt (real apps, dev AND prod)
Anything that sets an attribute named like a state var on a state CLASS now raises. Hunt for legitimate paths that hit it:
- framework internals: dynamic routes (`/post/[slug]` adds a route-arg var), `setvar` and auto setters, `rx.ComponentState`
  `.create` many times (per-component defaults via `cls.__fields__[...]` inside `get_component`, incl. `default_factory`
  and a storage value with a per-instance `name`), mixins (`mixin=True`) and substates inheriting vars, `rx._x.client_state`,
  `rx.SharedState` (link/unlink), computed vars, backend vars, `rx.field(...)`/`rx.Field[...]` annotations, `rx.Model`
  vars, upload handlers, `reset()`, `get_state`, background tasks;
- **dev hot reload**: `reflex run` dev, edit the file that declares a state (add/rename/remove a var, change a default)
  several times — must reload cleanly with no TypeError (`_reload_state_module` / re-registration);
- AppHarness (copy a small integration-test-style app) running two apps in one pytest process;
- import-time configuration that used to "work": `State.x = 5` at module level in an app → TypeError at import: is the
  message clear and actionable, is it raised at import (not on first request), and does `reflex run` show it well?
  0.9.12 silently accepted it — confirm that's the documented breaking change, not a crash elsewhere;
- ClassVar (incl. one redeclaring an inherited var on a substate) and new attributes stay assignable; `del S.x` + re-set
  on the declaring class works; deleting an inherited var through a substate raises the same TypeError;
- Python 3.11 and 3.14 for the core probes.
- Downstream: grep the published wheels/sdists of reflex-local-auth, reflex-google-auth, reflex-magic-link-auth
  (`$SB/downloads/`), the enterprise a5 wheel (`$SB/downloads/enterprise_wheel_a5/x/`) and the a3 third-party sweep's
  packages (`/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_events_tp/NOTES.md` lists them) for class-level writes
  to state vars (`<State>.<var> = `, `setattr(<state class>, ...)`, `patch.object(<State>, ...)`), and import + exercise
  each package's states on a4 (their own test suites if they ship any).
- Docs: every code sample in `git show v0.10.0a4:docs/vars/base_vars.md` ("Changing Defaults", backend vars, ClassVar),
  `docs/state_structure/component_state.md` (EditableText `initial_value`, ThemeToggle per-component storage key) and
  `docs/changelog/upgrading/upgrading-to-0-10.md` ("Assigning a state var through its class", plus the #7513 background-task
  inherited-var text) runs as written on a4 and every statement is true (e.g. "a mutable default needs a default_factory",
  "a str-annotated var with a plain default becomes an ordinary var", "a storage-typed var stays storage but loses name/
  options", "each backend worker holds its own ClassVar value"). Check the a4 `CHANGELOG.md` entries for #7516/#7513 too.

Anything that differs from what the docs/PR promise → check a3 and 0.9.12 to classify. Report in the structured format of
AGENT_BRIEF.md with `REVERIFIED:` lines for A3-01, A3-02, A3-04 (expected: "moot — assignment raises TypeError") and
N-005, N-039, N-008, N-004 under the new semantics.
