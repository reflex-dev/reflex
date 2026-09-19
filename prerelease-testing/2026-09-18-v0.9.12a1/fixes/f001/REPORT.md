<!-- Written by the orchestrator from the fix agent's final response: the harness does not let subagents write
report files. Structured result and evidence: fixes/f001/evidence/, workflow wf_d7e6ae4d-a6e. -->

# f001 — FINDING-001 / reflex-dev/reflex#7211: State metaclass conflict

Branch `fix/finding-001-state-metaclass` in `/home/user/wt/f001`, 2 commits, **not pushed**. Base `origin/main` @ `4cba00435`.

| Commit | Subject |
| --- | --- |
| `6ab3edbc9` | `fix: keep BaseStateMeta as the metaclass of State` |
| `4290548fe` | `docs: note the router state-dict shape change from #7068` |

Evidence: `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/fixes/f001/evidence/` (`01`–`09`, incl. `09-branch.diff`).

## 1. Root cause (confirmed independently)

- `reflex/istate/validation.py:90` (pre-fix) — `class _StateMeta(BaseStateMeta)`
- `reflex/state.py:629` (pre-fix) — `class BaseState(EvenMoreBasicBaseState, metaclass=_StateMeta)`
- `packages/reflex-base/src/reflex_base/vars/base.py:4036` — `class BaseStateMeta(ABCMeta)`, exported in `reflex_base.vars.__all__`

`type(rx.State)` stopped being `BaseStateMeta` and became `_StateMeta`, a *subclass*. A downstream `class M(BaseStateMeta)` is then a **sibling** of `_StateMeta`, so `class S(rx.State, metaclass=M)` fails.

The decisive mechanical detail — and the reason only one fix shape can work: CPython's `builtin___build_class__` resolves the most derived metaclass (`_calculate_meta`) **before** it calls any metaclass. The `TypeError: metaclass conflict` is raised without executing a single line of `_StateMeta.__new__`, `BaseStateMeta.__new__`, `__init_subclass__` or `__set_name__`. **No hook on `_StateMeta` can intercept it.**

reflex-enterprise 0.9.5 does exactly this at `reflex_enterprise/auth/oidc/state.py:347` (`class OIDCCookieMeta(BaseStateMeta)`) and `:381` (`class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta)`).

## 2. The fix

Shape (a): `type(rx.State)` is `BaseStateMeta` again and the #7136 validation runs inside `BaseStateMeta.__new__`. Shape (b) was ruled out by the `__build_class__` detail above, not by taste.

`BaseStateMeta` lives in `reflex-base` and the reserved-name data is `reflex`'s `BaseState` namespace, so the check is installed as a hook rather than inlined:

1. `packages/reflex-base/src/reflex_base/vars/base.py` — module-level `_state_declaration_validator` plus `_set_state_declaration_validator()`. `BaseStateMeta.__new__` calls the validator (when installed) with `(bases, namespace)` as its first statement — before field collection, exactly where `_StateMeta.__new__` used to run.
2. `reflex/istate/validation.py` — `_StateMeta` replaced by the plain function `_validate_state_declaration(bases, namespace)` holding the identical body, plus `_install_state_validation(base_state)`. `_validate_state_name` / `_validate_inherited_members` / `_reserved_state_members` untouched.
3. `reflex/state.py` — `class BaseState(EvenMoreBasicBaseState):` and `_install_state_validation(BaseState)` immediately after the class body.

The guard changed from `isinstance(base, _StateMeta)` to `issubclass(base, BaseState)` — same set of classes, but it keeps working now that third-party metaclasses exist. `BaseState` itself is still unvalidated (the hook is installed after it exists). Non-state models on the same metaclass return early, covered by the pre-existing `test_non_state_models_keep_their_namespace`.

One incidental hardening inside the rewritten code: `base is not EvenMoreBasicBaseState and base is not object` instead of `base not in (...)`. `in` uses `==`, and the whole point is that user metaclasses (which may define `__eq__`) now reach this code; `_linearize_bases` already compares by identity for the same reason.

### Alternatives considered and rejected

- **Validate in `BaseState.__init_subclass__`** (no reflex-base change). Rejected: it runs after `BaseStateMeta.__new__` rewrote the namespace, so `__fields__`/`__own_fields__`/`__inherited_fields__` are always present and always look declared. The check would have to ignore them and would stop rejecting a state that declares `__fields__` itself — `test_reserved_state_var[__fields__]` would regress.
- **Keep `_StateMeta` and resolve the most derived metaclass from it.** Impossible, see §1.
- **Monkeypatch `BaseStateMeta.__new__` from reflex.** Same effect, no declared contract, breaks when reflex-base is imported without reflex.
- **Leave it to reflex-enterprise** (`OIDCCookieMeta(type(rx.State))`). Not sufficient: 0.9.5 is published and declares `reflex[db]>=0.9.6` with no upper bound, so shipping 0.9.12 as-is bricks every deployed enterprise auth/MCP/REST app on the next `pip install -U`. `BaseStateMeta` is public, so any third-party state metaclass breaks too.

## 3. Regression test

`tests/units/istate/test_validation.py` (the module holding the #7136 tests, mirroring the module changed):

- `test_state_metaclass_is_base_state_meta` — `type(BaseState) is BaseStateMeta` and `type(State) is BaseStateMeta`.
- `test_custom_state_metaclass[False|True]` — a `_CookieMeta(BaseStateMeta)` modelled on enterprise's `OIDCCookieMeta` (injects an annotated backend var, forwards `**kwargs`) used as `class CustomState(State, mixin=<param>, metaclass=_CookieMeta)`; asserts metaclass, `_mixin`, the injected field and a normal field.
- `test_custom_state_metaclass_validates_reserved_names` — #7136 still rejects `get_fields` through a custom metaclass.

Before the fix (`evidence/01-regression-test-before-fix.log`):

```
FAILED tests/units/istate/test_validation.py::test_state_metaclass_is_base_state_meta
FAILED tests/units/istate/test_validation.py::test_custom_state_metaclass[False]
FAILED tests/units/istate/test_validation.py::test_custom_state_metaclass[True]
FAILED tests/units/istate/test_validation.py::test_custom_state_metaclass_validates_reserved_names
4 failed, 34 passed in 0.12s
```

with `TypeError: metaclass conflict ...` on the three class statements. After the fix (`evidence/05`): `38 passed`. The 34 pre-existing #7136 tests pass on both sides.

## 4. End-to-end verification (campaign repro)

**4.1 `orch_probes/metaclass_probe.py`, copied unmodified** (`evidence/02-metaclass-probe.log`):

| interpreter | `type(rx.State)` | result |
| --- | --- | --- |
| `envs/prev` (0.9.11.post1) | `reflex_base.vars.base.BaseStateMeta` | 3 × OK |
| `envs/shared` (published 0.9.12a1) | `reflex.istate.validation._StateMeta` | **2 × FAIL** (BaseStateMeta-derived, and the `mixin=True` variant), 1 OK |
| `/home/user/wt/f001/.venv` (fixed) | `reflex_base.vars.base.BaseStateMeta` | 3 × OK |

The fixed tree matches 0.9.11.post1 line for line.

**4.2 reflex-enterprise 0.9.5 import** (`evidence/03-enterprise-import.log`). Failure side, throwaway venv, published packages only:

```
uv venv v_pub --python 3.11
uv pip install --python v_pub/bin/python --prerelease=allow 'reflex==0.9.12a1' reflex_enterprise-0.9.5-py3-none-any.whl
v_pub/bin/python -c "import reflex_enterprise.auth.oidc.state"
->   File ".../reflex_enterprise/auth/oidc/state.py", line 381, in <module>
       class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta):
     TypeError: metaclass conflict: ...
```

Pass side, wheel installed `--no-deps` into the worktree venv (plus `asgiproxy joserfc httpx psutil 'mcp>=1.14.0,<2'`), `ent_import_probe.py` with only its `/envs/ent/` guard relaxed: **23/23 modules import, 13/13 attributes resolve, `BAD = 0`**, `type(OIDCAuthState) is OIDCCookieMeta`.

**4.3 MCPPlugin-only app** (`evidence/04-mcpapp-fixed.log`). `ent_mcp_oidc/apps/mcpapp` copied to scratch, run from the fixed venv on my own port:

```
cd <scratch>/apps/mcpapp && REFLEX_TELEMETRY_ENABLED=false CI=true \
  /home/user/wt/f001/.venv/bin/reflex run --backend-only --backend-port 8900
GET http://127.0.0.1:8900/ping -> 200 "pong"
```

`metaclass conflict` occurrences in the log: 0. `Traceback`: 0. The campaign recorded `000` on published 0.9.12a1 and `200` on 0.9.11.post1. Server stopped by pid; no listeners left on 3900-3909 / 8900-8909.

## 5. Checks

| check | result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format .` | 1628 files left unchanged |
| `uv run pyright reflex tests` | 0 errors, 0 warnings |
| `uv run pyright packages/reflex-base/src/reflex_base/vars/base.py` | 0 errors, 0 warnings |
| `uv run pytest tests/units --ignore=tests/units/reflex_cli` | **9126 passed, 20 skipped** |

Two caveats, both verified pre-existing on the unmodified tree:

- `tests/units/reflex_cli/**` — **207 failures on `origin/main` with no changes applied** (environment/credential dependent). Ignored above; unaffected by this change.
- `tests/units/test_state.py::test_state_manager_lock_warning_threshold_contend` failed once, then passed 4/4 including in the full run. Timing-based with non-CI thresholds (`LOCK_EXPIRATION = 300` ms, `LOCK_WARN_SLEEP = 0.15` s), flaky under load — other fix agents are running on this box. Nothing on the fix's path runs during that test.

No `.pyi` regeneration needed (no component `create` signature or prop changed); `pyi_hashes.json` untouched.

## 6. News fragments

- `news/+state-metaclass-conflict.bugfix.md` (reflex)
- `packages/reflex-base/news/+state-metaclass-conflict.bugfix.md` (reflex-base — its source changed)
- `news/+router-split-dict-shape.breaking.md` — second deliverable, separate commit, no code change

Shape change confirmed on both versions before writing the router note:

```
0.9.11.post1  State(...).dict()['reflex___state____state'] -> [..., 'router_rx_state_']
this branch   State(...).dict()['reflex___state____state'] -> [..., 'rx_router_headers_rx_state_',
              'rx_router_page_rx_state_', 'rx_router_route_id_rx_state_', 'rx_router_session_rx_state_',
              'rx_router_url_rx_state_']
```

Same for `get_delta()`. Neither `news/7068.breaking.md` (new base vars + shadowing error), `news/7068.deprecation.md`, `news/7068.performance.md` nor `packages/reflex-base/news/7068.*` tells a downstream reader of a serialized state which keys to read now — which is what broke enterprise's REST redaction (#7214).

## 7. Risks and behaviour changes

1. **`type(rx.State)` changes identity again**, back to what 0.9.11.post1 had. Code written against the alpha as `class M(type(rx.State))` keeps working (probe case 2 passes on all three interpreters).
2. **The validator now sees namespace mutations made by a subclass metaclass.** With `metaclass=M`, `M.__new__` runs before `BaseStateMeta.__new__`, so names *injected* by `M` are validated too. Stricter than #7136 was for the (previously impossible) custom-metaclass case, and correct. Enterprise's injected names (`_access_token_data`, `_id_token`, `_refresh_token`, `_granted_scopes`) are not reserved.
3. **The hook fires for every class `BaseStateMeta` creates**, including non-state models, returning after one `any(issubclass(...))` pass. Class creation is not a hot path; same shape as the old `isinstance` guard.
4. **reflex-base gains a private, underscore-prefixed extension point.** Single global validator; a second installer would replace the first. reflex-base imported without reflex runs with no validator, as before #7136.
5. `reflex/istate/validation.py` no longer exports `_StateMeta` — private, added in this unreleased alpha, unreferenced in the repo.

## 8. Open questions for the maintainers

1. **Should reflex-enterprise still change `OIDCCookieMeta` to derive from `type(rx.State)`?** This fix makes 0.9.5 work unmodified, so it is no longer urgent, but the framework now has a reason to keep `type(rx.State) is BaseStateMeta` permanently. If that is not a contract you want, say so in the changelog and fix enterprise too; if it is, the `BaseStateMeta` docstring should say it (I did not add that — it reads as an API commitment that is yours to make).
2. **One validator slot or a list?** I used a single slot: exactly one caller, and a list costs an allocation and an iteration per state class.
3. **`REFLEX_STATE_ALLOW_RESERVED_NAMES=1`, promised in #7136's description, does not exist in the source** (also noted by the campaign). Out of scope here — I did not add it — but the PR description and shipped behaviour disagree.
4. **`news/+router-split-dict-shape.breaking.md` is filed under reflex's `news/`** though the var split is described in `packages/reflex-base/news/7068.performance.md`. The observable shape is `state.dict()` / the delta, which is reflex's API — move it if you prefer.

## 9. Deviations from the brief

- **`REPORT.md` was not written.** This session's harness refuses report files from subagents ("Subagents should return findings as text… Include this content in your final response instead"), and I did not route around that block with a shell heredoc. The full report is this message; all logs and the branch diff are under `fixes/f001/evidence/`.
- **Commit trailer.** The brief specified `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; this session's own attribution instruction names the model actually doing the work, so the commits carry `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. The `Claude-Session:` trailer is as specified. Retrailer the commits if the release tooling matches the exact string.
- The worktree venv now additionally contains `reflex-enterprise==0.9.5` (installed `--no-deps`, as directed) and its runtime deps. Venv only; the git tree is clean.
