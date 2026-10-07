# Independent inventory verification

## VERIFICATION

**Confirmed, medium severity, pre-existing on0.9.12.** Independently authored the app and Chromium driver from the written behavioral lead; did not reuse the author's fixture. Tested published `reflex==0.9.12` and `reflex==0.10.0a2` on macOS26.6.2, Python3.12.14, Playwright1.63.0/Chromium153.0.8010.12. Both versions produce the identical result through normal public events and a pure cached `@rx.var`.

The warehouse has tea stock10 and coffee stock20; cached total30. “Reserve one each” through `.values()` or `.items()` changes actual backend stock to9/19, verified by a separate audit field and server print. The visible raw stock and cached total remain10/20/30. Reload updates raw stock to9/19 but total remains30. Copying/reassigning current inventory immediately corrects the total to28. The indexed-key mutation control updates raw stock and total to9/19/28 in the same event. This is a realistic inventory workflow, with no computed-var side effects, no backend-only annotation, no external mutable source, and no direct private-framework call.

| Version | values backend/UI after event | values after reload | items backend/UI after event | items after reload | copy/reassign | key-index control |
|---|---|---|---|---|---|---|
|0.9.12|backend9/19; UI10/20/30|UI9/19/30|backend9/19; UI10/20/30|UI9/19/30|9/19/28|9/19/28|
|0.10.0a2|backend9/19; UI10/20/30|UI9/19/30|backend9/19; UI10/20/30|UI9/19/30|9/19/28|9/19/28|

Each version has9 assertions:5 positive controls pass and4 expected-consistency assertions fail. No browser pageerrors, failed requests, HTTP errors or driver exceptions. The server has only implicit Radix deprecation noise. Initial fixture setup accidentally used the reserved event name `reset`; it was renamed to `reset_inventory` before browser runs. That setup error is preserved separately and is not a framework finding.

Probable cause: published alpha2 `reflex/istate/proxy.py:640` wraps return values only for `get`/`setdefault`; `.values()`/`.items()` return native views containing raw nested dictionaries. `__getitem__` at965 does wrap nested mutable values, explaining the working indexed control. Mutations through the native views bypass dirty/dependency tracking. This is a source-supported diagnosis, not a fix; no framework source was changed.

## Reproduction

Actual scratch root: `/private/tmp/reflex-prerelease-macos-pass2/apps/inventory-verifier`. Shared base envs are read-only; exact freezes in `logs/`. Python app imports assert `REFLEX_EXPECT_ENV`. All Python runs use uv from neutral scratch directories.

To reproduce from clean published environments:

```sh
export REFLEX_TEST_SB=/private/tmp/reflex-inventory-independent
ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/browser_cache_bundle/verify_inventory
mkdir -p "$REFLEX_TEST_SB/envs" "$REFLEX_TEST_SB/apps/inventory-verifier"
cd "$REFLEX_TEST_SB"
export UV_CACHE_DIR="$REFLEX_TEST_SB/uv-cache"
for TRAIN in stable alpha2 driver; do
  uv --no-config venv --python 3.12 "$REFLEX_TEST_SB/envs/$TRAIN"
  uv --no-config pip install --python "$REFLEX_TEST_SB/envs/$TRAIN/bin/python" \
    --prerelease=allow --index-url https://pypi.org/simple -r "$ART/logs/$TRAIN-freeze.txt"
done
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" python -m playwright install chromium
cp -R "$ART/source" "$ART/scripts" "$REFLEX_TEST_SB/apps/inventory-verifier/"
mkdir -p "$REFLEX_TEST_SB/apps/inventory-verifier/logs"
cd "$REFLEX_TEST_SB/apps/inventory-verifier"
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
  python scripts/run.py > logs/run.log 2>&1
```

`run.py` starts stable then alpha2 one at a time, always frontend3734/backend8734, using `reflex run --loglevel debug`, runs Chromium, and stops the owned process group. Individual browser invocation against a running server:

```sh
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" \
python scripts/check_inventory.py http://localhost:3734 alpha2 runs/alpha2
```

Manual steps: load page; click “Reserve via values”; observe audit9/19 with screen10/20/30; reload and observe9/19/30; click “Reassign inventory” and observe9/19/28. Reset, repeat using items; reset and use keys as the control.

`runs/{stable,alpha2}/results.json` contains all snapshots/assertions, console/network outcomes; `full.json.gz` retains complete websocket transcripts. Key screenshots show after-event, after-reload and indexed controls. Compressed server logs retain backend audit values. All owned servers and browsers stopped; final listener/process audits are empty. No git/board mutation.
