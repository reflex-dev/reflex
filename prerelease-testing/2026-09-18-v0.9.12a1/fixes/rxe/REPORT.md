# rxe — FINDING-011 (reflex-dev/reflex#7214) and the reflex-enterprise half of FINDING-001 (reflex-dev/reflex#7211)

Status: **both defects fixed**, both verified end to end against the published reflex 0.9.12a1.

| | |
|---|---|
| Repository | `reflex-dev/reflex-enterprise` (internal) |
| Worktree | `/home/user/wt/rxe` (worktree of `/home/user/reflex-enterprise`) |
| Branch | `fix/reflex-0.9.12-compat`, 2 commits on top of `origin/main` (`592d5cc`) |
| Commits | `038c613` fix(auth): derive the OIDC cookie metaclass from the installed State metaclass (`Refs reflex-dev/reflex#7211`)<br>`c0e6b5d` fix(api): redact the session token after the router var split (`Fixes reflex-dev/reflex#7214`) |
| Patches | `patches/0001-*.patch`, `patches/0002-*.patch` (`git format-patch origin/main`) |
| Evidence | `evidence/` (before/after test runs, HTTP bodies with tokens masked, server logs, pyright output) |
| Ports used | 3980-3982 / 8980-8982, all released |
| Not done | never pushed, no PR opened, `reflex[db] >=0.9.6` pin left alone (see "Pins") |

---

## Defect 1 — `OIDCCookieMeta(BaseStateMeta)` conflicts with reflex 0.9.12's State metaclass

### Root cause

`reflex_enterprise/auth/oidc/state.py:26` imported `BaseStateMeta` and `:347` declared
`class OIDCCookieMeta(BaseStateMeta)`, used at `:381` by
`class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta)`.

reflex 0.9.12 (reflex-dev/reflex#7136) changed `rx.State`'s metaclass:

```
reflex 0.9.11.post1  type(rx.State) = reflex_base.vars.base.BaseStateMeta
reflex 0.9.12a1      type(rx.State) = reflex.istate.validation._StateMeta   (a sibling subclass of BaseStateMeta)
```

Two sibling subclasses of `BaseStateMeta` cannot both be the metaclass of one class, so the
`OIDCAuthState` statement raises `TypeError: metaclass conflict` at import. Every
`AuthPlugin` / `MCPPlugin` / `EventHandlerAPIPlugin` app reaches that import from `post_compile`,
so the backend worker dies at startup while vite keeps serving the page.

### Fix

`reflex_enterprise/auth/oidc/state.py` — read the metaclass off the installed reflex:

```python
if TYPE_CHECKING:
    from reflex.vars import BaseStateMeta

    _StateMetaclass = BaseStateMeta      # keeps the __new__ override type-checked
else:
    _StateMetaclass = type(rx.State)     # BaseStateMeta <= 0.9.11, _StateMeta >= 0.9.12

class OIDCCookieMeta(_StateMetaclass):
```

One declaration that is correct on every reflex version, past and future — the metaclass
identity is never hard-coded. `BaseStateMeta` is the only such use in the package
(`grep -rn BaseStateMeta` returns exactly those two lines).

### Alternatives considered and rejected

* `class OIDCCookieMeta(type(rx.State))` directly — same runtime behaviour, but pyright cannot
  resolve a call expression as a base class, so the `__new__` override would stop being checked.
* Waiting for reflex-dev/reflex#7211 to be fixed upstream — reflex-enterprise 0.9.5 is already
  published with `reflex[db] >=0.9.6` and **no upper bound**, so rxe must be self-sufficient here.
  If reflex also fixes its side, this change stays correct (`type(rx.State)` would simply be
  `BaseStateMeta` again).
* Rebinding `reflex.vars.BaseStateMeta` (what the campaign's `oidc_meta_shim.py` does) — a global
  monkeypatch of the framework; fine for a QA probe, not a fix.

---

## Defect 2 — the REST/MCP session-token redaction was a silent no-op

### Root cause

`reflex_enterprise/plugins/event_handler_api.py:733 redact_router_session()` looked the session up
by var name:

```python
router_key = "router" + FIELD_MARKER
for sub in state_dict.values():
    if isinstance(sub, dict) and router_key in sub:
        sub[router_key] = _redact_router_value(sub[router_key])
```

reflex 0.9.12 (reflex-dev/reflex#7068) made `router` a property with **no backing field** and split
the data into five base vars. The root state dict on 0.9.12a1 is exactly
`is_hydrated`, `rx_router_session`, `rx_router_headers`, `rx_router_page`, `rx_router_url`,
`rx_router_route_id` — no `router` key at all, so the loop matched nothing and returned the dict
untouched. Everything downstream inherited the hole:

* `resolve_state_dict()` (`:901`) → `POST /_reflex/retrieve_state` and the MCP `reflex://state`
  resources (`mcp_builtin_resources.py:199`)
* `sanitize_agent_delta()` (`:852`) → the ndjson stream of `POST /_reflex/event/<state>/<handler>`,
  `queue_event()`'s merged delta, and the buffered MCP follow-up updates
  (`mcp_auth/tools.py:580`)
* `mcp_builtin_resources.py:374` single-var read — additionally special-cased the var **named**
  `router`, which does not exist on 0.9.12, while `rx_router_session` was readable by name and
  returned raw.

The leaked `client_token` is the server-generated session identifier the caller never presented
(it is not the bearer), and rxe's own comment at `_ROUTER_SESSION_SECRETS` calls handing it back a
session-takeover vector.

### Fix

`reflex_enterprise/plugins/event_handler_api.py`:

* new `_redact_session_value()` blanks `client_token` / `session_id` on session data in any of the
  three shapes it arrives in — the `SessionData` dataclass, reflex's mutable proxy around it, or the
  already-serialized dict (the `queue_event` path JSON-round-trips before sanitizing).
  `_redact_router_value()` now delegates to it instead of repeating the blanking logic.
* `redact_router_session()` walks each state's vars once and redacts on **either** signal:
  * the var name — `router` (reflex < 0.9.12) or `rx_router_session`, taken from
    `reflex_base.constants.route.ROUTER_SESSION` when the installed reflex has it (it does from
    0.9.12) and falling back to the literal otherwise;
  * the value's type — `RouterData` / `SessionData`. `isinstance` sees through reflex's mutable
    proxy (verified on both versions), so no unwrapping is needed in the loop.

  The type match is the part that matters for the next release: the defect being fixed is not
  "the name changed" but "a rename turned a security control into a no-op with no signal". A
  value carrying a `SessionData` is now redacted whatever var it sits under.
* the docstrings that described the redaction as keying on `router` were corrected
  (`strip_field_markers`, `sanitize_agent_delta`, `resolve_state_dict`).

`reflex_enterprise/plugins/mcp_builtin_resources.py` — the single-var read routes every value
through `redact_router_session()` instead of special-casing `var_name == "router"`. The function is
inert for anything that is not router data, so no var name is hard-coded on that path any more.

Public signature of `redact_router_session(state_dict) -> state_dict` (mutated in place) is unchanged,
as the brief required.

### Alternatives considered and rejected

* **Name-keyed only** (add `rx_router_session` beside `router`): the minimal change, and it fixes the
  reported leak. Rejected as the whole fix because it reproduces the exact failure mode — the next
  framework rename silently disables the redaction again. The name keys are kept (they are the only
  thing that can match an already-serialized dict) and the type match backs them up.
* **Type-keyed only**: cannot match the JSON-round-tripped dict on the `queue_event` path, where the
  session is a plain `{"client_token": ...}` dict by the time `sanitize_agent_delta` sees it.
* **Value scanning** (search the dict for the session token string): explicitly ruled out by the
  brief, and wrong — it would blank legitimate app data that happens to equal the token and would
  need the token in hand at redaction time.
* **Dropping the `rx_router_*` vars from API responses entirely**: a bigger behaviour change than the
  defect warrants; handlers and agents legitimately read the URL, page params, headers and client IP.

---

## Regression tests

`tests/units/plugins/test_event_handler_api.py` (7 new tests, + a `_secret_paths` walker modelled on
the campaign's `probe_router_redact.py` `find_token`):

| test | what it pins |
|---|---|
| `test_redact_router_session_blanks_split_session_var` | `rx_router_session` carrying a `SessionData` |
| `test_redact_router_session_blanks_serialized_split_session_var` | the same after JSON round-trip (dict) |
| `test_redact_router_session_blanks_legacy_router_var` | the legacy `router` var still redacts |
| `test_redact_router_session_blanks_serialized_legacy_router_var` | legacy var, serialized |
| `test_redact_router_session_blanks_real_root_state_dict` | **layout-agnostic**: builds the router the way `EventHandlerAPIPlugin` does, redacts a real `State(...).dict()`, asserts the sentinel appears nowhere — this is the campaign probe as a unit test, and it passes on whichever layout the installed reflex uses |
| `test_sanitize_agent_delta_blanks_session_and_strips_markers` | the delta surface, redaction before marker-stripping |
| `test_redact_router_session_blanks_proxied_session_under_any_var_name` | proxy transparency + the type match under a var name nobody hard-coded |

`tests/units/auth/test_oidc_state.py` (3 new, one parametrized over two provider states):

| test | what it pins |
|---|---|
| `test_oidc_cookie_meta_composes_with_installed_state_metaclass` | `issubclass(OIDCCookieMeta, type(rx.State))` and `isinstance(OIDCAuthState, OIDCCookieMeta)` |
| `test_oidc_cookie_meta_assigns_partitioned_cookie_descriptors[…]` | the metaclass still stamps `_oidc_<provider>_<attr>_partitioned` cookies — the behaviour that must not change with the base class |

### Before the fix (`evidence/before_fix.txt`, source stashed, new tests in place)

```
### unfixed SOURCE + new tests, v12 (reflex 0.9.12a1)
FAILED …::test_redact_router_session_blanks_split_session_var
FAILED …::test_redact_router_session_blanks_serialized_split_session_var
FAILED …::test_redact_router_session_blanks_real_root_state_dict
FAILED …::test_sanitize_agent_delta_blanks_session_and_strips_markers
FAILED …::test_redact_router_session_blanks_proxied_session_under_any_var_name
5 failed, 2 passed, 47 deselected

### unfixed SOURCE + new tests, v11 (reflex 0.9.11.post1)        4 failed, 3 passed
### unfixed SOURCE + new tests, repo .venv (reflex 0.9.6)        4 failed, 3 passed

### unfixed SOURCE, v12 — metaclass test module cannot even be collected
E   TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass …
ERROR tests/units/auth/test_oidc_state.py
```

The two legacy-`router` tests pass before the fix by design: they are the guard that the fix does not
regress reflex < 0.9.12.

### After the fix (`evidence/after_fix.txt`)

```
v12 (0.9.12a1)   new tests: 10 passed    touched modules: 159 passed    tests/units: 26 failed, 890 passed, 113 errors
v11 (0.9.11.p1)  new tests: 10 passed    touched modules: 159 passed    tests/units: 26 failed, 890 passed, 113 errors
.venv (0.9.6)    new tests: 10 passed    touched modules: 159 passed    tests/units:  9 failed, 1015 passed,  5 errors
```

The pre-existing failures are unchanged by this diff — measured directly: `tests/units` on the
**unfixed** tree is `26 failed, 880 passed, 113 errors` on v11 and `9 failed, 1005 passed, 5 errors`
in the repo `.venv`, i.e. exactly `+10 passed` and nothing else moves. See "Open questions" for what
those pre-existing failures are.

---

## End-to-end verification

All three servers were the **unmodified `demos/tickets`** app (`EventHandlerAPIPlugin`, no auth
configured), started with `CI=true REFLEX_TELEMETRY_ENABLED=false … reflex run` in dev mode.

### 1. In-process probe — the campaign's own `scripts/probe_router_redact.py`, unedited

```
fixed worktree + reflex 0.9.12a1      VERDICT OK
fixed worktree + reflex 0.9.11.post1  VERDICT OK
published rxe 0.9.5 + reflex 0.9.12a1 (envs/ent, untouched)   VERDICT LEAK
    -> ['.reflex___state____state.rx_router_session_rx_state_.client_token']
```

### 2. Import, without any shim

```
fixed worktree, v12:  import reflex_enterprise.auth.oidc.state  -> OK
fixed worktree, v11:  import reflex_enterprise.auth.oidc.state  -> OK
published rxe 0.9.5 + 0.9.12a1:                                 -> TypeError: metaclass conflict
```

### 3. HTTP — `evidence/e2e_http_912.txt`, bodies in `evidence/*_912_*.{json,ndjson}` (tokens masked)

`v_leak_http.py` (the campaign's verifier script, with the port and state name from argv and the
saved bodies masked) issues an anonymous app bearer at `POST /_reflex/auth/token`, then reads
`POST /_reflex/retrieve_state` and `POST /_reflex/event/tickets___tickets____ticket_state/seed`.

| | control: published rxe 0.9.5 + reflex 0.9.12a1 (port 8981, rxconfig metaclass shim — the published package cannot start without it) | fixed worktree + reflex 0.9.12a1 (port 8980, **no shim**) |
|---|---|---|
| backend starts | only with the shim | yes, unmodified demo |
| `retrieve_state` | `rx_router_session.client_token = <live UUID>` | **NONE (redacted)** |
| event delta (ndjson) | same live token | **NONE (redacted)** |
| leaked token == caller's bearer? | no — a server-side identifier the caller never had | — |
| verdict | `LEAK` | `OK` |

The fixed response keeps the var and blanks only the secrets, which is the point:

```json
"rx_router_session": {"client_token": "", "client_ip": "0.0.0.0", "session_id": ""}
```

### 4. HTTP on the previous framework — `evidence/e2e_http_911.txt`

Fixed worktree + reflex 0.9.11.post1 (port 8982): root state keys are `is_hydrated`, `router`;
`router.session.client_token` is `""`; both surfaces `NONE (redacted)`; verdict `OK`. The fix is
genuinely dual-compatible at the HTTP level, not only in unit tests.

---

## Checks run

| check | result |
|---|---|
| `ruff check .` | All checks passed! |
| `ruff format .` | 284 files already formatted (one test file was reformatted while writing) |
| `pyright reflex_enterprise tests` | 220 errors, 9 warnings — **byte-identical to the pre-change run**; `diff` of the two diagnostic lists is empty (`evidence/pyright_before.txt`, `evidence/pyright_after.txt`). The 220 are pre-existing. |
| `pytest tests/units` | see the table above; +10 passed, no other change, on all three reflex versions |
| `.pyi` stubs | not applicable — no component `create` signature or prop changed |

Ruff/format/pyright were run with the worktree's own `.venv` (reflex 0.9.6), the version CI uses.

---

## Pins

**`reflex[db] >=0.9.6` should stay as it is** — left unchanged, as the brief instructed, and I
recommend keeping it:

* Both fixes are dual-compatible by construction and are proven on reflex 0.9.6 (the floor),
  0.9.11.post1 and 0.9.12a1 — unit tests on all three, HTTP on the last two. Raising the floor to
  `>=0.9.12` would strand users on 0.9.6-0.9.11 for no benefit, and reflex-dev/reflex#7214's
  "ideally with a `reflex>=0.9.12` lower bound" suggestion assumes a 0.9.12-only fix, which this is
  not.
* No upper bound is needed either: neither fix names a reflex version, and neither reads a private
  reflex API. `type(rx.State)` and `reflex.istate.data.{RouterData,SessionData}` are stable public
  surface.
* **The already-published reflex-enterprise 0.9.5 has no upper bound on reflex**, so the moment
  reflex 0.9.12 ships to PyPI, `pip install -U reflex` on a deployed enterprise app takes it down
  (metaclass) and, if reflex fixes the metaclass on its side without rxe, silently starts leaking
  session tokens (redaction). That is a release-sequencing problem this branch cannot solve:
  **reflex-enterprise 0.9.6 carrying these two commits has to be on PyPI before, or at the same
  time as, reflex 0.9.12.** If it cannot be, reflex 0.9.12 should consider yanking-by-metadata the
  combination (e.g. rxe 0.9.5 + reflex >= 0.9.12) rather than leaving it to resolve.

---

## Risks and behaviour changes

* **A var whose value is a `RouterData`/`SessionData` is now redacted whatever it is called.** If an
  app deliberately exposed its own `SessionData`-typed var over the REST/MCP surface, its
  `client_token`/`session_id` will now come back blank. I judged this correct (it is the same secret,
  by the same type), but it is a behaviour change worth a maintainer's eye.
* **`redact_router_session()` now iterates every var of every state** instead of doing one dict
  lookup per state. `strip_field_markers()`, which runs on the same dicts on every one of these
  paths, already does exactly that, so the cost is a constant factor on an existing pass — two
  `isinstance` checks and a string compare per var, no allocation, no unwrapping.
* **The MCP single-var read now always calls `redact_router_session()`.** For a non-router var this
  builds one two-level dict and iterates one entry; the value is returned unchanged.
* **`reflex_enterprise.plugins.event_handler_api` now imports `reflex_base.constants.route` at module
  import** (inside a `try`). `reflex_base` is a hard dependency of reflex and the module is tiny.
* `reflex.vars.BaseStateMeta` is no longer imported at runtime by `auth/oidc/state.py` — it remains a
  public reflex export, nothing else in rxe used it, and it is still imported for type checking.

---

## Open questions for the maintainers

1. **Release sequencing** (the important one): see "Pins". reflex-enterprise 0.9.6 with these commits
   must not land after reflex 0.9.12.
2. **`tests/units` does not pass against reflex >= 0.9.11 in a single-process run.** Independent of
   this diff and identical before and after it: `26 failed, 113 errors` on both 0.9.11.post1 and
   0.9.12a1, versus `9 failed, 5 errors` on 0.9.6. Nearly all of them are
   `ReflexRuntimeError: A RegistrationContext can only be associated with a single App instance`
   from test fixtures that build several `App`s. That is a test-harness incompatibility with newer
   reflex, not a product defect, but it means CI on this repo will go red as soon as it moves off
   0.9.6 — worth its own issue before the 0.9.6 release.
3. **No regression test covers the MCP `_resolve_single_var` router path.** A meaningful one cannot
   be written today: on reflex ≤ 0.9.11 reading `router` was already redacted (it would pass before
   and after), and on 0.9.12a1 the surrounding `test_mcp.py` tests cannot run at all for reason (2).
   The path is covered indirectly — it now calls the unit-tested `redact_router_session()` with no
   var-name condition.
4. **Server logs still carry the client token.** `auth/oidc/state.py:1072` prefixes OIDC error log
   lines with `self.router.session.client_token`. Unchanged by this train (the `router` property read
   works fine on 0.9.12a1) and it is a server-side log, not an API response — flagging it only
   because it is the one remaining place the token is written out in full.
5. **Should reflex offer a redaction hook?** reflex-dev/reflex#7214 raises this. This fix does not
   need one, but a framework-declared "these vars are session secrets" list would let downstream code
   stop guessing at names entirely.

---

## Deviations from the brief

* The brief's commit trailer specified `Co-Authored-By: Claude Fable 5.1`. The session's own
  attribution instruction (which post-dates and explicitly replaces earlier attribution guidance)
  specifies `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`; the commits carry
  that line, with the same `Claude-Session:` trailer. Rewrite the trailer on cherry-pick if the
  other spelling is wanted.
* The `[mcp]` extra resolved fine in both scratch venvs (`mcp 1.30.0`), so nothing was dropped there.
  `oidc-provider-mock`, `pytest-mock` and `pytest-retry` had to be added to both venvs for
  `tests/units` to collect.
* A third venv was added beyond the two the brief asked for: `v12pub`
  (reflex 0.9.12a1 + the published rxe 0.9.5 wheel + `aiosqlite`) to run the HTTP **control**. The
  read-only `envs/ent` has no `aiosqlite`, so the `tickets` demo's `/seed` handler errors there and
  the event-delta surface could not be compared.

## Reproducing this

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/fixes/rxe
# venvs: $SB/v12 (0.9.12a1 + editable worktree), $SB/v11 (0.9.11.post1 + editable worktree),
#        $SB/v12pub (0.9.12a1 + published rxe 0.9.5 wheel)
cd /home/user/wt/rxe
$SB/v12/bin/python -m pytest tests/units/plugins/test_event_handler_api.py tests/units/auth/test_oidc_state.py -q
$SB/v11/bin/python -m pytest tests/units/plugins/test_event_handler_api.py tests/units/auth/test_oidc_state.py -q
cd $SB && ./v12/bin/python probe_router_redact.py /fixes/rxe/v12     # VERDICT OK

# HTTP (ports 3980/8980 fixed, 3981/8981 control)
cd $SB/apps/tickets_fixed     && CI=true REFLEX_TELEMETRY_ENABLED=false $SB/v12/bin/reflex    run --frontend-port 3980 --backend-port 8980
cd $SB/apps/tickets_published && CI=true REFLEX_TELEMETRY_ENABLED=false $SB/v12pub/bin/reflex run --frontend-port 3981 --backend-port 8981
cd $SB && NO_PROXY=localhost,127.0.0.1 ./v12/bin/python v_leak_http.py http://localhost:8980 /tmp/rs.json /tmp/ev.ndjson
```

`apps/tickets_published/rxconfig.py` carries the QA-only metaclass shim (clearly marked, not a fix)
so the published package can start at all; `apps/tickets_fixed` is the demo unmodified.
