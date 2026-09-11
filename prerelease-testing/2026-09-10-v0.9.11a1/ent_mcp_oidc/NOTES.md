# Cluster: ent_mcp_oidc — reflex-enterprise MCP plugin and OIDC auth under reflex 0.9.11a1

This cluster ran in two sessions. **Session 1** (below) built a purpose-made MCP app and
AuthPlugin app and compared 0.9.11a1 with 0.9.10.post2. **Session 2** (second half of this
file, from "session 2: the SHIPPED demos/oidc app") runs the shipped
`reflex-enterprise/demos/oidc` demo against a full fake IdP, drives the MCP OAuth 2.1 consent
flow with the real MCP SDK client, and gives verdicts on the 2026-08-27 enterprise findings.

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
* Two `net::ERR_ABORTED` on `/_reflex/cookies/sync` per browser run, on **both** versions. Session 2
  pins this down: the endpoint really is **404** (the abort is just how this driver saw it), which
  is the previous campaign's FINDING-026 still open in reflex-enterprise 0.9.5 — see §3 of the
  session-2 notes below. Not benign, and not a regression.
* `reflex-enterprise` 0.9.5 emits `console.debug`/`console.info`/`console.error` deprecation
  warnings (deprecated in reflex 0.9.9) on every startup under both versions. Enterprise-side
  cleanup, not a release blocker.

---

# ent_mcp_oidc — session 2: the SHIPPED demos/oidc app + the MCP OAuth 2.1 consent path

Session 1 of this cluster (see `NOTES.md`) built its own MCP app and its own AuthPlugin app and
compared reflex 0.9.11a1 against 0.9.10.post2 (findings 030–032). It did **not** run the
shipped `reflex-enterprise/demos/oidc` demo, and it stopped short of the MCP OAuth 2.1 /
consent flow with a real MCP client. This session covers exactly those gaps, plus explicit
verdicts on the previous campaign's enterprise findings.

Everything from PyPI: `reflex==0.9.11a1` (venv `$SB/envs/ent_mcp_a1`) and
`reflex==0.9.10.post2` (venv `$SB/envs/ent_mcp_0910`), both with `reflex-enterprise[mcp]==0.9.5`
and `mcp==1.30.0`. Demo sources copied unmodified from the read-only clone
`/home/user/reflex-enterprise/demos/oidc` (repo HEAD 2026-09-03). Nothing installed from a
checkout. Ports used: frontend 5260–5264, backend 9660–9663, fake IdP 9670, OAuth client
callback 9671/9672 — all released, no processes left running.

## TL;DR

| Area | 0.9.11a1 | 0.9.10.post2 baseline | Verdict |
| --- | --- | --- | --- |
| shipped `demos/oidc`, full OIDC login/logout in Chromium | 12/12 driver steps pass | 12/12 pass | works, no regression |
| proactive access-token refresh (`offline_access`, 70 s tokens) | 3 refresh grants in 210 s, `_on_access_token_change(refresh=True)`, toast, session survives | not needed (a1 passed) | works |
| iframed popup login + popup logout | both popups close, opener signed in / out | identical | works (see ISSUE B for the IdP half of logout) |
| `HTTPCookie.sync()` → `/_reflex/cookies/sync` | **404** | **404** | 2026-08-27 FINDING-026 still open (pre-existing, rxe-side) |
| MCP OAuth 2.1 + human consent with the real `mcp` SDK client | full flow passes, agent acts as the user | identical | works, no regression |
| anonymous MCP session vs `auth=True` surface | refused, actionable message | identical | works |
| `search_events` `rest_path` with MCPPlugin alone | 404 | 404 | ISSUE A (low, pre-existing, rxe-side) |
| enterprise `--env prod` | paid-subscription gate | same | untestable here (expected) |

No reflex 0.9.11a1 regression was found in either the OIDC/auth or the MCP surface.

## 1. Shipped `demos/oidc` against a real (fake) IdP

`idp/fake_idp2.py` extends session 1's `idp/fake_idp.py` with multiple registered clients (the
demo drives an Okta *and* a Databricks provider at once), `aud` taken from the authorizing
client, `iat`/`exp` in `/userinfo` (the demo renders `rx.moment(userinfo["iat"], unix=True)`),
and a configurable `IDP_EXPIRES_IN` so the proactive refresh fires inside a test run. It signs
RS256 with a real key, verifies PKCE S256, supports the refresh grant, RP-initiated logout and
`/_log` + `/_expire` test hooks.

```bash
SB=<scratchpad>; W=$SB/apps/ent_mcp_oidc            # working dir
cp -r /home/user/reflex-enterprise/demos/oidc $W/oidcdemo    # unmodified; drop its reflex pin
$SB/envs/ent_mcp_a1/bin/python $W/idp/fake_idp2.py 9670 > $W/logs/idp2.log 2>&1 &

cd $W/oidcdemo && CI=true REFLEX_TELEMETRY_ENABLED=false \
  OKTA_ISSUER_URI=http://localhost:9670 OKTA_CLIENT_ID=okta-client OKTA_CLIENT_SECRET=okta-secret \
  DATABRICKS_ISSUER_URI=http://localhost:9670 DATABRICKS_CLIENT_ID=databricks-client \
  DATABRICKS_CLIENT_SECRET=databricks-secret \
  $SB/envs/ent_mcp_a1/bin/reflex run --frontend-port 5260 --backend-port 9660 --loglevel debug \
  > $W/logs/demo_a1_run.log 2>&1 &

NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  scripts/drive_oidc_demo.py 5260 9660 9670 a1 $W/shots/demo_a1
```

Baseline: same commands with `$SB/envs/ent_mcp_0910/bin/reflex`, app dir `oidcdemo_0910`,
ports 5261/9661, label `0910`.

**Result (`shots/demo_a1/results_a1.json`, `shots/demo_0910/results_0910.json`): identical on
both versions.** Anonymous index renders both provider cards; `Do Nothing` round-trips;
"Login with Okta" → discovery → `/authorize` (PKCE S256, `response_mode=query`, correct
per-provider `redirect_uri`) → callback → `/token` (**PKCE verified by the IdP**) → `/userinfo`
→ the card shows `sub/email/name/preferred_username`; `Log AT` logs the tokens server-side;
reload keeps the session; a second tab in the same context is signed in; Databricks logs in
independently with its own scopes `all-apis offline_access openid email profile` and renders the
`last_access_token_hash` / `latest_access_token_hash_ls` badges; "Logout" on the Okta card sends
`GET /logout` to the IdP with `id_token_hint` + `post_logout_redirect_uri`, clears only that
provider's session (the Databricks card stays signed in — correct), and the Okta card is back to
its login button; `/iframe` renders the app inside an iframe.

Server logs (`logs/demo_a1_run.log`, `logs/demo_0910_run.log`) contain no tracebacks; the IdP's
own request log for the run is `logs/idp2_short.log`.

### Token refresh (needs `offline_access`, so: the Databricks provider)

```bash
IDP_EXPIRES_IN=70 $SB/envs/ent_mcp_a1/bin/python $W/idp/fake_idp2.py 9670 &   # short tokens
# restart the app (it caches JWKS per IdP instance), then:
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  scripts/drive_refresh.py 5260 9670 a1 $W/shots/demo_a1 210
```

`shots/demo_a1/refresh_a1.json` + `logs/demo_a1_refresh.log`: **4 distinct access-token hashes
in 210 s, 3 `REFRESH OK` grants at the IdP**, each preceded by
`Access token change callback hit refresh=True` from the demo's `_on_access_token_change`
override, each refresh request carrying only the granted scopes; the "Access token refreshed"
toast is visible (`a1_21_refresh_toast.png`); the session never drops
(`logged_in: true` in every 5 s sample) and no console/page errors appear.

### Iframed popup login and logout (enterprise commit 592d5cc1's area)

```bash
$SB/envs/driver/bin/python scripts/drive_popup.py 5260 a1 $W/shots/demo_a1
$SB/envs/driver/bin/python scripts/drive_popup_logout.py 5260 a1 $W/shots/demo_a1
```

From `/iframe`, clicking login inside the iframe opens the popup
(`/_reflex_oidc_okta/popup-login` → IdP → `…/authorization-code/callback` → back to
`popup-login`), the **popup closes itself**, and the iframed app is signed in
(`shots/demo_a1/popup_a1.json`, `a1_12_iframe_after_login.png`). Logout from inside the iframe
opens `/_reflex_oidc_okta/popup-logout`, that popup closes too and the iframed app returns to
its login buttons (`popup_logout_a1.json`, `a1_41_iframe_logged_out.png`). Identical on
0.9.10.post2 (`shots/demo_0910/popup_logout_0910.json`).

Note for the enterprise team: **commit 592d5cc1 ("close the login popup from the callback, not
from redirect_to_url") is NOT in the published 0.9.5 wheel** — diffing
`reflex_enterprise/auth/oidc/state.py` from the wheel against the checkout HEAD shows the wheel
still lacks `post_auth_message(fallback_url)` and the `from_popup` branch in `auth_callback`.
The published wheel therefore still relies on the accidental mechanism the commit message
describes (the callback redirects to `redirect_to_url`, which happens to name `/popup-login`,
whose `on_load` re-enters `redirect_to_login` and posts+closes). In this environment that path
worked every time; the failure mode the commit fixes (a popup that renders the whole app at
600×600 and never closes) needs the opener's session-storage value to win the race, which it
never did here.

## ISSUE A (LOW, pre-existing, downstream: reflex-enterprise 0.9.5) — MCP `search_events` advertises a `rest_path` that 404s unless `EventHandlerAPIPlugin` is also enabled

Every `search_events` result carries
`"rest_path": "/_reflex/event/<state>/<handler>"` (built unconditionally by
`reflex_enterprise/plugins/event_handler_api.py:507 describe_event_handler`, which the MCP
plugin reuses). With `rxe.MCPPlugin()` alone — the configuration the MCP docs show — that route
is not served, so an agent that follows the advertised path gets a bare `404 Not Found` with no
hint that the REST surface is disabled.

Repro (app `apps/authapp`, `rxe.Config(plugins=[rxe.AuthPlugin(), rxe.MCPPlugin()])`):

```bash
cd $W/authapp && CI=true OIDC_ISSUER_URI=http://localhost:9670 OIDC_CLIENT_ID=test-client \
  OIDC_CLIENT_SECRET=test-secret $SB/envs/ent_mcp_a1/bin/reflex run \
  --frontend-port 5262 --backend-port 9662 &
$SB/envs/ent_mcp_drv/bin/python scripts/mcp_extra_probe.py 9662 a1 $W/logs/mcp_extra_a1.json
```

`logs/mcp_extra_a1.json`: `rest_event_path` → 404 with and without a valid bearer;
`logs/mcp_extra_0910.json` is identical on reflex 0.9.10.post2 ⇒ **not a regression**, it is a
property of the rxe 0.9.5 wheel. Suggested fix: omit `rest_path` (or mark it unavailable) when
the REST plugin is not mounted.

## ISSUE B (LOW–MEDIUM, pre-existing, downstream: reflex-enterprise 0.9.5) — logout from an iframed app never reaches the IdP's `end_session_endpoint`

In the popup (iframed) logout flow the provider session is never ended, so single sign-out does
not happen: the local session is cleared, the popup closes, but the IdP is never told. Clicking
login again silently re-authenticates from the surviving IdP session.

Mechanism (`reflex_enterprise/auth/oidc/state.py`, `redirect_to_logout`): when
`_use_popup_flow()` is true the opener yields `redirect_to_logout_popup` ("Best effort to end
provider session in popup") and then **immediately** `await self._reset_session()`. The popup's
`/popup-logout` page runs `set_from_popup(True)` + `redirect_to_logout` on load; by then the
shared cookies are gone, so `has_any_token` is false and it takes the
"Re-entry after provider logout completed; just close" branch — `CLOSE_POPUP`, no IdP round
trip. The two logout events are visible in the server log as
`Processing logout flow (from_popup=False)` followed by `(from_popup=True)`.

Repro:

1. Start the fake IdP and the demo as in §1, then
   `$SB/envs/driver/bin/python scripts/drive_popup_logout.py 5260 a1 $W/shots/demo_a1`.
2. `curl -s --noproxy '*' http://localhost:9670/_log` → the run shows
   `GET /authorize …` for the login but **no `GET /logout`**, while the *non-iframed* logout in
   `drive_oidc_demo.py` does produce
   `GET /logout {"state": …, "id_token_hint": …, "post_logout_redirect_uri": …}`.

Baseline: reproduced identically with reflex 0.9.10.post2 (`shots/demo_0910/popup_logout_0910.json`,
same absent `/logout` in the IdP log) ⇒ **not a regression of this train**.

## 2. MCP OAuth 2.1 + human consent, driven by the real MCP SDK client

`scripts/mcp_oauth_drive.py` is a real MCP client: `mcp.client.auth.OAuthClientProvider` +
`mcp.client.streamable_http.streamablehttp_client`, with a stdlib HTTP receiver for the OAuth
redirect and Chromium (Playwright) performing the human half.

```bash
uv venv $SB/envs/ent_mcp_drv --python 3.12                       # from a neutral cwd
uv pip install --python $SB/envs/ent_mcp_drv/bin/python 'mcp==1.30.0' httpx 'playwright==1.62.0'
# app + IdP running as in ISSUE A above, then:
NO_PROXY=localhost,127.0.0.1 $SB/envs/ent_mcp_drv/bin/python \
  scripts/mcp_oauth_drive.py 5262 9662 9671 a1 $W/shots/mcp_oauth_a1
```

**All steps pass on 0.9.11a1 (`shots/mcp_oauth_a1/mcp_oauth_a1.json`,
`logs/mcp_oauth_a1_steps.log`) and identically on 0.9.10.post2
(`shots/mcp_oauth_0910/…`, ports 5263/9663, callback 9672):**

* `/.well-known/oauth-protected-resource/_reflex/mcp` (RFC 9728) and
  `/.well-known/oauth-authorization-server` (RFC 8414) both served; registration endpoint
  advertised as `/register-oidc-client`.
* Unauthenticated POST to the MCP mount → `401` + `WWW-Authenticate: Bearer …
  resource_metadata="…"`; a caller-invented bearer → the same 401.
* RFC 7591 dynamic client registration succeeds (client_id + secret issued to the agent).
* Authorization request carries PKCE S256 and the `resource` parameter; the consent page is
  itself auth-guarded, so it bounces to the AuthPlugin `/login`, the fake IdP signs the human
  in, and the browser lands on `/agent-consent?txn=…` showing *"prerelease-test-agent is asking
  to act as you in this app"*, the redirect host (`localhost:9671`) and Approve/Deny
  (`shots/mcp_oauth_a1/a1_31_consent.png`).
* Approve → `code` + `state` to the client's redirect URI → token exchange → opaque Bearer,
  `expires_in 3600`, refresh token present. Upstream IdP tokens never reach the MCP client.
* With that token: `initialize` (generated instructions), `tools/list`
  (`search_events`, `queue_event`), `resources/list` (`reflex://state`, `reflex://event`),
  `resources/templates/list` (`reflex://event/{event_name}`,
  `reflex://state/events/{state_name}`, `reflex://state/vars/{state_name}`,
  `reflex://state/vars/{state_name}/{var_name}`).
* **The agent acts as the signed-in user**: `queue_event` on the `auth=True` handler
  `set_secret` succeeds; the `auth=True` **background** handler `slow_secret` returns the
  post-sleep delta; the protected computed var reads back
  `{"var": "secret_label", "computed": true, "value": "secret=set-by-mcp-agent"}`.
* Control in the same script: an **anonymous** token from `POST /_reflex/auth/token` is refused
  the same handler — *"requires an authenticated session, but this session is anonymous. Re-run
  the OAuth authorization flow …"* — and the protected var read is refused with
  *"it is protected and the session is not authorized for it"*.

Corroborates session 1's FINDING-031 from a second angle: `search_events` returns
`"state": "authapp___authapp____public_state"`, but `reflex://state/vars/<state>` only accepts
the fully-qualified `reflex___state____state.authapp___authapp____public_state` listed by
`reflex://state`; passing the name `search_events` gave you errors with
*"Unknown state … Use a fully-qualified state name"*.

Also corroborates FINDING-030 (delta key ordering) with a fresh pair of runs: the
`slow_secret` delta is byte-identical apart from key order —
`secret_note, note_echo, shared_label, secret_label` on 0.9.11a1 vs
`note_echo, shared_label, secret_label, secret_note` on 0.9.10.post2.

### API-token surface (`reflex_enterprise/plugins/api_tokens.py`)

`scripts/mcp_extra_probe.py` (`logs/mcp_extra_{a1,0910}.json`), identical on both versions:

* `POST /_reflex/auth/token` — 10 grants succeed, the 11th onward returns `429`
  `{"error":"rate_limited"}` with `Retry-After`, exactly the documented per-IP budget.
* A garbage bearer → 401 with the RFC 9728 pointer.
* The legacy **SSE** transport (`mcp.client.sse.sse_client`) against `/_reflex/mcp` **hangs**
  until the client's own timeout — the plugin mounts streamable-HTTP only, and a legacy client
  gets no clean error, just a stall (anomaly, not a defect; same on both versions).
* `/_reflex/cookies/sync` on this AuthPlugin app answers **400 "No client token in request"**
  without a token and **200** with one — i.e. the route *is* registered in the serving worker
  when `rxe.AuthPlugin` is used. Only the deprecated `register_auth_endpoints()` shape the OIDC
  demo uses 404s (see §3).

## 3. 2026-08-27 FINDING-026 (`/_reflex/cookies/sync` 404) — still open with rxe 0.9.5

Clicking "Cookie Sync" in the shipped demo POSTs `http://localhost:<backend>/_reflex/cookies/sync`
and gets **404** on reflex 0.9.11a1 (`shots/demo_a1/results_a1.json` → `http_errors`) *and* on
0.9.10.post2 (`shots/demo_0910/results_0910.json`). The previous campaign's mechanism holds
unchanged on 0.9.5, and I re-proved it:

```bash
curl -s --noproxy '*' -o /dev/null -w '%{http_code}\n' -X POST \
     http://localhost:9660/_reflex/cookies/sync      # 404
touch $W/oidcdemo/oidc/oidc.py                       # force a granian hot reload
sleep 25
curl -s --noproxy '*' -X POST http://localhost:9660/_reflex/cookies/sync
# -> "No client token in request" (400): the reloaded worker compiled the pages itself,
#    so HTTPCookie.sync()'s compile-time route insertion finally landed in the serving process
```

(`logs/demo_a1_cookiesync.log`.) Pre-existing, enterprise-side, **not** a regression of this
train; the `AuthPlugin` shape does not have the problem.

## 4. Verdicts on the previous campaign's enterprise findings

`scripts/probe_prior_findings.py`, run with each venv from a neutral cwd
(`CI=1 $SB/envs/ent_mcp_a1/bin/python scripts/probe_prior_findings.py`):

| 2026-08-27 finding | Status on reflex 0.9.11a1 + reflex-enterprise 0.9.5 |
| --- | --- |
| FINDING-001 `dynamic.bundled_libraries` removed | **FIXED both sides.** reflex ships a deprecation shim (attribute returns a `list`, `DeprecationWarning` naming `RegistrationContext.ensure_context().bundled_libraries`, removal 1.0) and rxe 0.9.5's `vars.py:28 get_bundled_libraries()` reads the RegistrationContext with the old attribute only as a fallback. |
| FINDING-021 ag-grid python-callable renderer/formatter crash | **FIXED** (mechanism gone; the `ent_aggrid` cluster of this campaign confirms it end to end). |
| FINDING-022 non-static LambdaVar prop with imports | **FIXED**: `LiteralLambdaVar.create(lambda p: rx.text(...))` no longer raises `AttributeError`; it now raises only the legitimate `ValueError: Library @radix-ui/themes is not bundled` when no bundling context exists (this campaign's FINDING-022 about module-scope `bundle_library()`). |
| FINDING-023 `reflex.page.DECORATED_PAGES` removed | **FIXED**: importable again as a `defaultdict` behind a `DeprecationWarning`. |
| FINDING-024 AttributeError masked as a bogus `VarAttributeError` | **NOT FIXED**: an `AttributeError` raised inside a cached var computation still surfaces as `VarAttributeError: Attribute _var_value not found.` (this campaign's FINDING-013). |
| FINDING-025 shipped ag_grid demo's stale `$/utils/components` bundle path | **NOT FIXED** — per this campaign's `ent_aggrid/NOTES.md` (not re-tested here). |
| FINDING-026 `/_reflex/cookies/sync` 404 in the OIDC demo | **NOT FIXED** — §3 above; reproduced on both reflex versions with rxe 0.9.5. |
| FINDING-029 rxe error paths emit `console.error` DeprecationWarning | **NOT FIXED**: `reflex run --env prod` still prints `DeprecationWarning: console.error … (reflex_enterprise/utils.py:119)` right before the paid-subscription gate (`logs/demo_a1_prod_gate.log`), and `console.debug` deprecations appear at startup. |

## 5. Benign-but-surprising observations

* **`[react-moment] Invalid date input: undefined`** floods the console (12 warnings per page
  render) on the demo's Databricks card when the IdP's `/userinfo` response has no `iat`/`exp`
  claims — which is the OIDC norm; those claims belong to the ID token. The demo renders
  `rx.moment(auth_cls.userinfo.to(dict)["iat"], unix=True)`. Seen in the 0.9.11a1 run against
  the un-patched mock (`logs/demo_a1_run.log:271+`) and absent once the mock started returning
  `iat`/`exp` (both versions) — so this is demo code + IdP payload, **not** version-dependent
  and not a react-moment 2.0.2 regression.
* **`Warning: Attempting to send delta to disconnected client`** — exactly once per OAuth
  consent login, on both reflex versions (`logs/authapp_a1_oauth.log` 3 warnings / 3 logins,
  `logs/authapp_0910_oauth.log` 1 / 1). It fires right after
  `Auth callback succeeded; user logged in, redirecting to '/agent-consent?…'`: the callback
  page's socket is gone by the time the follow-up delta is emitted. Cosmetic, pre-existing.
* The MCP SDK logs `INFO Terminating session: None` (`streamable_http.py:831`) for every
  request when the app runs at `--loglevel debug`; upstream SDK noise.
* `POST /_reflex/mcp` without a trailing slash 307-redirects before the 401 (Starlette mount
  behaviour; the SDK follows it).
* Enterprise `--env prod` is gated behind a paid subscription, so no enterprise app can be
  prod-tested in this container: *"`reflex run --env prod` requires a paid Reflex subscription
  … You are currently logged out."* (`logs/demo_a1_prod_gate.log`).
* `register_auth_endpoints` (used by the shipped demo) prints its own deprecation on every
  start, pointing at `rxe.AuthPlugin`.

## Files from this session

```
apps/oidcdemo/, apps/oidcdemo_0910/   unmodified copies of reflex-enterprise/demos/oidc
idp/fake_idp2.py                      multi-client OIDC provider (RS256, PKCE, refresh, logout)
scripts/drive_oidc_demo.py            12-step browser drive of the shipped demo
scripts/drive_refresh.py              proactive access-token refresh observation
scripts/drive_popup.py                iframed popup login
scripts/drive_popup_logout.py         iframed popup login + logout
scripts/mcp_oauth_drive.py            real MCP SDK client: OAuth 2.1 + DCR + human consent
scripts/mcp_extra_probe.py            token rate limit, rest_path, SSE transport, bad bearer
scripts/probe_prior_findings.py       status of the 2026-08-27 enterprise findings
shots/demo_a1/, shots/demo_0910/      screenshots + results JSON (a1 and baseline)
shots/mcp_oauth_a1/, .../mcp_oauth_0910/   consent-page screenshots + step JSON
logs/                                 server logs, IdP request log, probe outputs
```

All servers (5260–5264, 9660–9663), the fake IdP (9670), the OAuth callback receivers
(9671/9672) and every Chromium were stopped; `ps` shows no reflex/granian/vite/bun/chromium
process from this session.
