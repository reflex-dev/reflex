# Reproduce the published a4 authentication lane

The saved app bodies and retained tests match the a3 bundle. Only the focused reload driver adds a second reload. Keep runtime directories separate from the checkout and exclude generated files when copying. These commands use the same package graph, Bun and browser that were tested; provider accounts and OIDC client values below are disposable local fixtures.

```sh
uv_bin=/Users/masenf/.local/bin/uv
qa_python=/private/tmp/reflex-enterprise-a4-20261005-alpha/bin/python
qa_lane=/private/tmp/reflex-enterprise-a4-20261005-auth
qa_artifacts=/Users/masenf/.codex/worktrees/48e6/reflex/prerelease_testing/2026-10-05/enterprise/a4/auth
export UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache

"$uv_bin" --no-config venv --python /private/tmp/reflex-enterprise-a3-20261005-alpha/bin/python /private/tmp/reflex-enterprise-a4-20261005-alpha
"$uv_bin" --no-config pip install --only-binary :all: --refresh-package reflex-enterprise --python "$qa_python" --index-url https://pypi.org/simple -r "$qa_artifacts/requirements-requested.txt"
"$uv_bin" --no-config pip freeze --python "$qa_python"
"$uv_bin" --no-config pip check --python "$qa_python"
mkdir -p "$qa_lane"
rsync -a --include='*/' --include='*.py' --exclude='*' "$qa_artifacts/" "$qa_lane/"
mkdir -p "$qa_lane/logs" "$qa_lane/screenshots"
cd "$qa_lane/apps/auth_min"
env -u PYTHONPATH "$uv_bin" --no-config run --no-project --python "$qa_python" python ../../repro_auth_field.py
env -u PYTHONPATH "$uv_bin" --no-config run --no-project --python "$qa_python" python ../../repro_oidc_scopes.py
env -u PYTHONPATH "$uv_bin" --no-config run --no-project --python "$qa_python" python ../../mock_oidc.py > ../../logs/mock-oidc.log 2>&1
```

Keep that provider process running in a separate terminal while executing the following servers sequentially. The auth CLI used this exact environment on each run. `CI=true` skips real cloud login; it does not substitute identity-provider responses or patch authentication guards.

```sh
auth_server() {
  env -u PYTHONPATH CI=true \
    REFLEX_DIR=/private/tmp/reflex-enterprise-a4-20261005-runtime \
    REFLEX_CHECK_LATEST_VERSION=false NPM_CONFIG_REGISTRY=https://registry.npmjs.org \
    OIDC_ISSUER_URI=http://localhost:9131 OIDC_CLIENT_ID=reflex-integration-test \
    OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1 \
    UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache \
    "$uv_bin" --no-config run --no-project --python "$qa_python" \
    reflex run --frontend-port 3132 --backend-port 8132 --loglevel debug
}
auth_browser() {
  env -u PYTHONPATH PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers \
    UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache \
    "$uv_bin" --no-config run --no-project --python "$qa_python" python "$1"
}
```

Start the full app from `"$qa_lane/apps/auth"` with `auth_server > ../../logs/auth-full-server.log 2>&1`. In another terminal, with the same variables/functions, run from that app directory:

```sh
auth_browser ../../drive_auth.py > ../../logs/auth-full-driver.log 2>&1
auth_browser ../../recheck_reload.py > ../../logs/reload-repeat-driver.log 2>&1
```

Stop that CLI with Ctrl-C. From `"$qa_lane/apps/auth_min"`, unset `AUTH_TEST_EXTRA_SCOPES`, then start `auth_server > ../../logs/auth-min-default-server.log 2>&1`. Run these drivers from the same app directory:

```sh
unset AUTH_TEST_EXTRA_SCOPES
auth_browser ../../drive_auth_min.py > ../../logs/auth-min-default-driver.log 2>&1
auth_browser ../../recheck_iframe.py > ../../logs/iframe-repeat-driver.log 2>&1
auth_browser ../../check_mcp_oauth.py > ../../logs/mcp-oauth-driver.log 2>&1
```

Stop that CLI. Set `AUTH_TEST_EXTRA_SCOPES=1` for both server and driver terminals, start `auth_server > ../../logs/auth-min-extra-server.log 2>&1` from the same app directory, then run:

```sh
export AUTH_TEST_EXTRA_SCOPES=1
auth_browser ../../drive_auth_min.py > ../../logs/auth-min-extra-driver.log 2>&1
```

Stop that CLI. From `"$qa_lane/apps/components"`, launch the backend-only compatibility app:

```sh
env -u PYTHONPATH CI=true \
  REFLEX_DIR=/private/tmp/reflex-enterprise-a4-20261005-runtime \
  REFLEX_CHECK_LATEST_VERSION=false NPM_CONFIG_REGISTRY=https://registry.npmjs.org \
  UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache \
  "$uv_bin" --no-config run --no-project --python "$qa_python" \
  reflex run --backend-only --backend-port 8132 --loglevel debug \
  > ../../logs/mcp-anonymous-server.log 2>&1
```

Run the client from that same app directory in another terminal:

```sh
env -u PYTHONPATH "$uv_bin" --no-config run --no-project --python "$qa_python" \
  python ../../check_mcp.py > ../../logs/mcp-anonymous-driver.log 2>&1
```

Stop the backend and provider with Ctrl-C. Inspect JSON booleans, not merely shell exit status: the two focused observation drivers record failures without a nonzero exit. Files stay in the neutral tree until explicitly copied back; do not copy `.web`, `.states`, environments, or caches into the evidence directory. The retained `repro_logout.py` was not rerun because the enhanced default/extra matrix already provides stronger logout and cross-user assertions.
