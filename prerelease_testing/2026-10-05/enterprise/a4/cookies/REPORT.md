# Published a4 cookie validation

The identical cookie app passes all six production-browser scenario groups on
Reflex 0.10.0a1 and stable 0.9.12, each with enterprise 0.9.7a4. These are fresh
104/91-package PyPI-only environments, copied neutral apps, Bun 1.4.2 and
Playwright 1.55/Chromium 140. No package code was changed.

Both runs verify paired HTTP-only writes hidden from `document.cookie`, inherited
cached values inside `rx.memo`, five repeated updates ending at generation six,
reload persistence, browser-to-backend synchronization/invalidation and deletion.
They retain 15 HTTP 200 sync responses and 15 `net::ERR_ABORTED` notifications
each, with zero page/HTTP errors and zero error-level console messages. The abort
cause remains unestablished; the same category appears in the prior stable/a3
runs. This is not a demonstrated new regression, critical impact or weak security
issue. These sequential clicks do not establish overlapping requests.

The first invocation was rejected because the copied development config has
split frontend/backend ports. Its exact output/source remains in
[alpha-rejected-split-port](alpha-rejected-split-port/result.json). The valid
full-stack production runs explicitly use `--frontend-port 3145 --backend-port
3145`, so all traffic is served on the same origin. This was a fixture invocation
correction, not a framework fix. CI is true here; cloud account/tier guards are
evaluated independently in the Free-tier lane.

[Alpha results](alpha/result.json), [stable results](stable/result.json),
[alpha provenance](alpha-provenance.json), [stable provenance](stable-provenance.json),
screenshots, response headers and full server logs are preserved. Stable also
emits HTTPCookie string-assignment warnings; both log the published `fix_events`
deprecation. No relevant backend traceback occurred. The retained cookie driver
still has the previously reviewed screenshot-before-JSON and recorded-but-not-
gated request-failure limitations; raw evidence was inspected.

To repeat, install either [alpha](../requirements-alpha-lock.txt) or
[stable](../requirements-stable-lock.txt) frozen graph into a fresh UV environment.
Copy [root_runs.py](../root_runs.py) to a neutral directory and run there:

```sh
env -u PYTHONPATH PLAYWRIGHT_BROWSERS_PATH=/private/tmp/reflex-enterprise-browsers uv --no-config run --no-project --python /private/tmp/your-a4-env/bin/python python root_runs.py cookies --graph alpha --campaign /absolute/path/to/prerelease_testing/2026-10-05 --output /private/tmp/cookie-results
```

The controller copies only fixture source from the read-only campaign path and
owns/cleans its temporary production process group. Reset State, HTTPS/partitioned
cookies, ComponentState, and multi-worker persistence remain outside this run.
