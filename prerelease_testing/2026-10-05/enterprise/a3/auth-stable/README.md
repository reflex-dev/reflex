# Enterprise 0.9.7a3 with stable Reflex 0.9.12

Published `reflex-enterprise==0.9.7a3` passed all **22 retained auth flows** on published `reflex==reflex-base==0.9.12`, plus **five fresh-context repeats** of the protected async-var public reload case. A separate tiny app narrows the alpha-only async-var hydration failure. The additional combined iframe popup/pending-event case also fails on stable, so that finding is shared across these Reflex versions.

| Probe | Stable Reflex 0.9.12 + enterprise a3 | Alpha Reflex 0.10.0a1 + enterprise a3 |
| --- | --- | --- |
| Four field-wrapper rendering variants | 4/4 pass | Covered by the parallel alpha auth report |
| OIDC extra-scope metadata/setup smoke | Pass | Covered by the parallel alpha auth report |
| Retained full auth browser definitions | 22/22 pass | Covered by the parallel alpha auth report |
| Exact public reload case, fresh-context repeats | 5/5 pass | Covered by the parallel alpha auth report |
| Same tiny core-State public navigation/reload app | 3/3 pass | **0/3 pass**, async value remains placeholder |
| Enhanced auth_min default-scopes browser driver | **3/4 pass** | Parallel report reproduces the same combined iframe failure |

## Isolation and dependency evidence

The fresh stable venv is `/private/tmp/reflex-enterprise-a3-20261005-stable`, and neutral apps/drivers are under `/private/tmp/reflex-enterprise-a3-20261005-auth-stable`. Every Python command used `uv --no-config run --no-project --python <exact-env>/bin/python`, with `PYTHONPATH` unset. Installation used `uv --no-config pip install --python <exact-env>/bin/python --index-url https://pypi.org/simple` and explicit published requirements. No checkout, branch, editable package, `uv sync`, repository framework test execution, or framework patch was used.

[`requirements-input.txt`](requirements-input.txt) starts from the retained `enterprise/many_states/requirements-stable-lock.txt`, changing only enterprise a2 to a3 and adding permitted `pytest==8.4.2` for retained browser-definition imports. [`evidence/provenance.json`](evidence/provenance.json) asserts every original pin is unchanged except enterprise, and records exactly 91 distributions. The only added distributions are pytest 8.4.2, pluggy 1.6.0, and iniconfig 2.3.0. [`requirements-resolved.txt`](requirements-resolved.txt), installation logs, and `pip-check.log` preserve the graph and consistency check.

Provenance asserts stable versions, isolated import paths, absent `PYTHONPATH`, no checkout on `sys.path`, and no distribution `direct_url.json`. It hashes the imported framework/auth/provider/browser modules. The separately verified alpha environment was the parent-authorized `/private/tmp/reflex-enterprise-a3-20261005-free-tier-venv`; it was used read-only. [`evidence/alpha-provenance.json`](evidence/alpha-provenance.json) records its exact 104-distribution graph, published alpha/a3 versions, framework origins and source hashes. These complete graphs differ in additional dependencies, so the comparison does not identify the single package or change causing the alpha-only behavior.

Both app environments used the existing explicit Bun **1.4.2** binary at `/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun`; saved startup logs show the Bun installer was skipped. Browser control used published Playwright **1.55.0** in the stable venv with official private Chromium **140.0.7339.16**, fresh contexts and no user browser tabs. Ports were frontend 3152, backend 8152 and mock OIDC provider 9151. All three ports are released; [`evidence/cleanup.json`](evidence/cleanup.json) records cleanup. This rerun installed no Bun and made no shell configuration changes.

## Stable validation

`repro_auth_field.py` checks enterprise public/protected `rx.Field[int]` wrappers, a core field and an ordinary annotated enterprise field. All four become `NumberCastedVar` objects and render. `repro_oidc_scopes.py` is a metadata/setup smoke using the same scope setup method called by AuthPlugin; the subsequent full CLI compile and real login flows supply the end-to-end evidence.

`apps/auth` is the retained upstream `AuthFlowApp` lifted to module scope. `reference/` preserves the browser test definitions and shared helpers. The driver supplies a frontend URL to those definitions; it does not instantiate the upstream AppHarness or run its framework initialization/reset machinery. Copied fixture changes are only the assigned port constants and explicit `Path`-typed Bun config. New driver changes preserve console, page-error, response, cookie-flag and visible-field evidence without changing upstream test assertions. The 22 cases cover login/redirect, anonymous protection, protected/public fields and vars, sync/async admin checks, pending-event replay, refresh, public reload and client navigation, logout and reset before a different user. Three custom login-builder tests belong to a different fixture configuration and are excluded by the retained public-app driver.

[`evidence/auth-stable-browser.json`](evidence/auth-stable-browser.json) records all 22 outcomes. [`evidence/focused-reload.json`](evidence/focused-reload.json) records five additional fresh sessions: after public-page reload, `secret-view` is `computed:initial-secret`, the async protected var is `async-admin-data`, and the synchronous admin var is valid. Screenshots preserve the five restored pages.

The full 22-case run recorded no console errors, page errors or HTTP responses >=400. It also recorded aborted `/_reflex/cookies/sync` requests during navigation in several passing cases; these are retained separately in [`evidence/audit-results.json`](evidence/audit-results.json), not silently counted as successful requests. The initial configuration attempt used a string Bun path and failed in stable path handling; this fixture authoring error was corrected to `Path`, and its log is retained as `auth-run-config-type-attempt.log`.

## Independently reduced async-var failure

[`narrow-alpha/reload_probe/reload_probe.py`](narrow-alpha/reload_probe/reload_probe.py) uses ordinary core `rx.State` fields, a synchronous protected computed getter, and an asynchronous protected getter with the retained awaited sibling `get_state(OrgState)` authorization pattern. It uses AuthPlugin only: no enterprise field wrappers or MCP plugin are needed. Alpha and stable run the same app/config source in separate clean directories.

Each of three fresh alpha contexts completes OIDC login as Alice. On the protected dashboard, the async getter correctly displays `async-admin-data`. Full navigation to the public `/` page changes it to `async-admin-placeholder`; a subsequent full reload keeps the placeholder through the 15-second observation. The sync getter stays `computed:initial-secret`, the core field stays `initial-secret`, and user identity stays `Alice Admin`. The identical stable app retains the correct async data before and after reload in all three contexts through 15 seconds.

[`narrow-alpha/evidence/reload-alpha.json`](narrow-alpha/evidence/reload-alpha.json) and [`narrow-alpha/evidence/reload-stable.json`](narrow-alpha/evidence/reload-stable.json) include dashboard, public-page and 0/1/5/15-second reload observations, cookies without their values, console and HTTP-error diagnostics. Neither tiny run observed page errors or HTTP responses >=400. The tiny driver did not record request-failure events, so it does not establish that all cookie-sync requests completed. Saved screenshots show the alpha placeholder and stable restored value. Startup logs remain in `evidence/narrow-*-run.log`.

`completed: true` means the diagnostic sequence completed; `async_restored: false` means the product behavior failed. The audit explicitly records **0/3 alpha functional passes** and **3/3 stable functional passes**. The reusable driver now asserts the actual restoration result after saving all observations, making the alpha reproduction exit unsuccessfully. Its executed observation-only predecessor is retained in `executed-source/`; the raw run's zero exit status did not establish a product pass. An earlier attempt navigated public before explicitly asserting the dashboard result; its setup assertion failures are retained as `narrow-alpha-initial-attempt.*` and are not part of the three completed contrast cases.

## Shared combined iframe/pending-event failure

The enhanced retained [`drive_auth_min.py`](drive_auth_min.py) runs four default-scope flows against `apps/auth_min`. Profile/login/reveal/refresh/logout/different-user reset passes; ordinary anonymous pending-event replay passes; direct iframe popup login passes. **Combined iframe pending-event replay fails**: an anonymous Reveal event sends the child to the login page, popup authentication succeeds and the popup closes, but the child remains at `/login?redirect_to=%2F`, `#message` is absent, and `rxe_auth_pending_event` still contains `ProfileState.reveal`.

[`evidence/auth-min-default-browser.json`](evidence/auth-min-default-browser.json), driver/server logs and the failure screenshot preserve the real browser failure. There are no page errors or HTTP responses >=400 in the failed case; two cookie-sync requests are aborted. This reproduces the parallel alpha default-scope failure on stable and must not be reported as a new Reflex 0.10 regression. No enterprise a2 control for this combined case was run here. Extra-scopes auth_min was not rerun in this stable slice.

## Reproduction

The saved apps, reference definitions, mock provider, requirements and drivers are self-contained fixtures. Use the exact recorded paths below, or adapt all path constants together. Python packages must continue to come from PyPI. The existing Bun path is required to avoid invoking the installer.

The final snapshot contains **84 hashed source/evidence files plus `sha256.json`**. Generated `reflex.lock/`, `assets/external/` and app-local `requirements.txt` copies are omitted and excluded by the collector. In particular, the copied generated app requirements named Reflex 0.10.0a1 even for the stable snapshot; they were not used for installation. The saved root `requirements-input.txt` and `requirements-resolved.txt`, together with import provenance, define the tested stable environment. AuthPlugin recreates its generated external assets when compiling the fixture. Runtime originals and browser drivers were left unchanged during this packaging cleanup.

```sh
UV=/Users/masenf/.local/bin/uv
ENV=/private/tmp/reflex-enterprise-a3-20261005-stable
APP_ROOT=/private/tmp/reflex-enterprise-a3-20261005-auth-stable
ARTIFACT=/Users/masenf/.codex/worktrees/48e6/reflex/prerelease_testing/2026-10-05/enterprise/a3/auth-stable
export UV_CACHE_DIR=/private/tmp/reflex-enterprise-a3-20261005-stable-cache
export PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers
unset PYTHONPATH

# For a fresh environment, create it and install only the saved PyPI requirements.
"$UV" --no-config venv --python 3.12 "$ENV"
"$UV" --no-config pip install --python "$ENV/bin/python" --index-url https://pypi.org/simple -r "$ARTIFACT/requirements-resolved.txt"
mkdir -p "$APP_ROOT/logs" "$APP_ROOT/screenshots"
cp -R "$ARTIFACT/apps" "$ARTIFACT/reference" "$APP_ROOT/"
cp "$ARTIFACT/"*.py "$APP_ROOT/"
cd "$APP_ROOT"
"$UV" --no-config run --no-project --python "$ENV/bin/python" python -m playwright install chromium
"$UV" --no-config run --no-project --python "$ENV/bin/python" python repro_auth_field.py
"$UV" --no-config run --no-project --python "$ENV/bin/python" python repro_oidc_scopes.py
"$UV" --no-config run --no-project --python "$ENV/bin/python" python mock_oidc.py
```

Keep the provider running in its own terminal. Start the full app in another terminal with the same UV/cache variables and `PYTHONPATH` unset:

```sh
cd /private/tmp/reflex-enterprise-a3-20261005-auth-stable/apps/auth
env -u PYTHONPATH CI=true REFLEX_USE_SYSTEM_BUN=false REFLEX_DIR=/private/tmp/reflex-enterprise-a3-20261005-runtime-stable OIDC_ISSUER_URI=http://localhost:9151 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1 "$UV" --no-config run --no-project --python "$ENV/bin/python" reflex run --frontend-port 3152 --backend-port 8152 --loglevel debug
```

From the neutral root, run `drive_auth.py` and `focus_reload.py` with the same exact `uv run` prefix. Stop that app before starting `apps/auth_min` with the same app command, unset `AUTH_TEST_EXTRA_SCOPES`, and run `drive_auth_min.py`; its combined case is expected to fail. To reproduce the reduced async case, copy `narrow-alpha/` into a fresh neutral directory and start it with the same app command using either the recorded stable or alpha interpreter, then run `drive_reload.py stable` or `drive_reload.py alpha` with the Playwright/stable interpreter. The backend graph controls the app behavior; the driver interpreter only supplies browser automation.

Only development-mode Chromium with the local mock OIDC provider was exercised here. Production auth, external providers, other browsers, custom login builders and server-side multiworker persistence are outside this slice. No framework changes, commits or external issues/comments were made.
