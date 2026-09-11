# Cluster: ent_mcp_oidc — reflex-enterprise MCP plugin and OIDC auth under reflex 0.9.11a1

Goal: the user called out `oidc/auth` and `the mcp plugin` as enterprise functionality that must
not regress. Both are backend-heavy surfaces that the enterprise demo apps cannot exercise here
(the shipped `demos/oidc` app needs live Okta and Databricks tenants), so this cluster builds its
own apps and its own OIDC provider and drives the whole flow.

Everything installed from PyPI only: `reflex==0.9.11a1` / `reflex==0.9.10.post2` plus
`reflex-enterprise[mcp]==0.9.5` (published), in two isolated uv venvs. reflex-enterprise source
was read for API discovery but never installed from a checkout.

## What was built

| Path | What it is |
| --- | --- |
| `apps/mcpapp/` | MCP exercise app: root state with cached + uncached computed vars, an arg-taking handler, a background handler, a sibling substate, a nested child substate, an `rx.memo` component and an `rx.ComponentState`. `rxe.Config(plugins=[rxe.MCPPlugin()])`. |
| `apps/authapp/` | OIDC exercise app: `rxe.Config(plugins=[rxe.AuthPlugin(), rxe.MCPPlugin()])`, a public page and an `auth=True` page, `rxe.field`/`rxe.var`/`rxe.event` tagged both ways, a protected background handler, an `rx.memo` fed an auth-derived var, and a `ComponentState`. Also carries two deliberate leak probes (below). |
| `idp/fake_idp.py` | A self-contained OIDC provider (~200 lines, Starlette + joserfc): discovery, JWKS, auto-approving `/authorize`, `/token` with **PKCE S256 verification** and a refresh grant, `/userinfo`, RP-initiated `/logout`, plus `/_log` and `/_expire` test hooks. RS256, real signature, real `at_hash`. |
| `scripts/mcp_drive.py` | Drives the MCP endpoint as an agent would: anonymous token, unauthenticated and invented-bearer rejection, `initialize`, `tools/list`, `resources/list`, `search_events`, `queue_event` (plain / arg / background / sibling substate / nested substate), every `reflex://` resource, and the error paths. |
| `scripts/mcp_probe2.py` | Resource-naming and payload-validation probe. |
| `scripts/mcp_auth_probe.py` | `MCPPlugin` + `AuthPlugin` together: OAuth 2.1 metadata, 401 + `WWW-Authenticate`, and what an anonymous MCP session may reach. |
| `scripts/drive_auth.py` | Playwright end-to-end: anonymous browse, guard redirects, login through the IdP, authenticated browse, reload, second tab, logout — capturing console, page errors, failed requests and every HTTP >= 400. |

Reproduce (ports are arbitrary; run installs from a neutral cwd, see AGENT_BRIEF.md):

```
uv venv envs/ent_mcp_a1 && VIRTUAL_ENV=envs/ent_mcp_a1 uv pip install --prerelease=allow \
    "reflex==0.9.11a1" "reflex-enterprise[mcp]==0.9.5"
python idp/fake_idp.py 9899 &
cd apps/mcpapp && reflex run --backend-only --backend-port 9801 &
python scripts/mcp_drive.py 9801
cd apps/authapp && CI=true OIDC_ISSUER_URI=http://localhost:9899 OIDC_CLIENT_ID=test-client \
    OIDC_CLIENT_SECRET=test-secret reflex run --frontend-port 5410 --backend-port 9810 &
python scripts/drive_auth.py 5410 a1
python scripts/mcp_auth_probe.py 9810
```

`CI=true` is needed only because `rxe.App` exits with "reflex-enterprise is free to use but you
must be logged in" for an anonymous tier when the frontend is served; the check is skipped under
`CI` or `REFLEX_BACKEND_ONLY` (`reflex_enterprise/app.py:110-121`). No enterprise licence is
available in this container.

## Result: no enterprise regression from reflex 0.9.11a1

Every observable behaviour matched between reflex 0.9.10.post2 and 0.9.11a1.

* `scripts/drive_auth.py`, 22 recorded steps, **`steps` arrays byte-identical** across versions
  (`logs/auth_a1.json` vs `logs/auth_0910.json`; the only diffs anywhere in the capture are
  dev-server console chatter and a 33-byte HTML length change).
* `scripts/mcp_drive.py`, `mcp_probe2.py`, `mcp_auth_probe.py`: identical apart from delta key
  ordering (FINDING-030).

What was confirmed working end to end on 0.9.11a1:

* **OIDC**: discovery → `/authorize` → callback → `/token` with **PKCE S256 verified by the IdP**
  → `/userinfo` → session. `AuthUserState.email` / `.provider_name` populate; the `rx.memo`
  component re-renders with the auth-derived var (`memo:alice@example.test`); the
  `ComponentState` instance survives the round trip; the pre-login state (`hits=3`) is *not*
  reset by logging in. Reload and a second tab in the same context stay signed in. RP-initiated
  logout sends `id_token_hint` + `post_logout_redirect_uri`, and afterwards every protected value
  is back to its default and the guarded page bounces to `/login` again.
* **Guards**: an anonymous click on an `auth=True` handler — foreground *and* background —
  redirects to `/login?redirect_to=%2F` instead of running; `/secret` bounces to
  `/login?redirect_to=%2Fsecret`; both work again once signed in.
* **Protected-value withholding**: a *public* handler was used to write `SERVER-ONLY-SECRET`
  into server-side data read by an `auth=True` uncached computed var, and `FIELD-SECRET` into an
  `auth=True` field. The anonymous browser kept showing the compiled defaults
  (`shared=default-shared`, `top-secret`) and only saw the real values after login — the delta
  filter holds. (The values the anonymous client *does* show are the compiled JS defaults; the
  server HTML contains neither string.)
* **MCP**: `initialize` (with generated instructions), `tools/list`, `resources/list`,
  `resources/templates/list`, `search_events`, `queue_event` for plain / arg-taking / background /
  sibling-substate / nested-substate handlers, and every `reflex://` resource including a
  recomputed computed var. Unauthenticated and caller-invented bearers get 401 +
  `WWW-Authenticate` with RFC 9728 `resource_metadata`. Unknown event names produce an excellent
  "Did you mean:" list.
* **MCP + AuthPlugin together**: `/.well-known/oauth-protected-resource/_reflex/mcp` and
  `/.well-known/oauth-authorization-server` both served (registration endpoint advertised as
  `/register-oidc-client`); an anonymous MCP session can call `auth=False` handlers and is
  refused `auth=True` ones with an actionable message; protected computed vars are refused on read.
* **Background events over MCP**: `slow_bump` (an `@rx.event(background=True)` that sleeps then
  mutates under `async with self`) returns the *post-sleep* delta (`count` 6 → 106), i.e.
  `queue_event` waits for the background task rather than returning an empty delta.

## Findings raised

* FINDING-030 — delta key ordering changed between 0.9.10.post2 and 0.9.11a1 (LOW, new).
* FINDING-031 — `reflex://state/events/<unknown state>` answers `{"events": []}` instead of
  erroring, and the `state` field that `search_events` returns is not the name these resources
  accept (LOW, pre-existing, enterprise-side).
* FINDING-032 — a withheld protected *field* is served to an unauthorised MCP caller as its
  default value with no indication it was withheld, while a protected *computed var* errors
  (LOW, pre-existing, enterprise-side).

## Non-findings worth writing down

* **`queue_event` does not enforce the schema it advertises.** `add(amount: int)` is published as
  `{"name": "amount", "type": "integer"}`, but `{"amount": 1.5}` is accepted and leaves the
  `int`-declared `count` var holding `1.5`, and `{"amount": "not-an-int"}` surfaces a raw
  `TypeError: unsupported operand type(s) for +=: 'int' and 'str'`. This is *not* MCP-specific:
  reflex's own `_transform_event_arg` (`reflex_base/event/processor/base_state_processor.py:92`)
  only handles unions, dataclasses/models, set/tuple, enums and string deserializers — it does
  not coerce or reject a wrong-typed scalar, so the websocket path behaves the same. Pre-existing
  framework behaviour, unchanged in this train; recorded here because the MCP surface publishes a
  JSON schema that implies validation.
* **No transitive protection.** `note_echo`, an explicitly `auth=False` computed var that reads
  the `auth=True` field `secret_note`, hands the protected value to anonymous browsers and to
  anonymous MCP sessions alike. The framework did exactly what the tag said — untagged members
  default to protected — so this is an author foot-gun, not a defect. Worth a sentence in the
  enterprise auth docs.
* `POST /_reflex/mcp` without a trailing slash 307-redirects; a client that does not follow
  redirects sees a 307 rather than the 401. Standard Starlette mounting behaviour.
* Two `net::ERR_ABORTED` on `/_reflex/cookies/sync` per browser run, on **both** versions, with
  no console error and no HTTP >= 400 — aborted by navigation, benign.
* `reflex-enterprise` 0.9.5 emits `console.debug`/`console.info`/`console.error` deprecation
  warnings (deprecated in reflex 0.9.9) on every startup under both versions. Enterprise-side
  cleanup, not a release blocker.
