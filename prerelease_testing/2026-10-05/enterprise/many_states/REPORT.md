# Many-state browser comparison

The published alpha successfully builds the 1,500-state production sample and
returns HTTP 200, but the actual Codex in-app browser displays a blank page and
reports `RangeError: Maximum call stack size exceeded`. Development mode also
fails in React's mutation-effect traversal. Both the alpha and stable 0.9.12
render, navigate, and execute backend events at 500 and 1,000 dormant states.

This is a confirmed large-state client rendering limitation on the alpha. It is
**not proven to be a regression**: stable 0.9.12 cannot build/start the same
1,500-state frontend here, so its browser behavior at that size is unavailable.
The changelog for [#7369](https://github.com/reflex-dev/reflex/issues/7369) promises
an SSR fix; this client failure is a separate remaining limit and does not
invalidate the narrower SSR change.

## Controlled sample and environment

`alpha/` and `stable/` contain identical source copied from the campaign's
`lifecycle/lifecycle_app/lifecycle_app.py`. `QA_EXTRA_STATES` creates that many
dormant `rx.State` subclasses, each with one integer field. Only the normal
counter and memoized dynamic article page are used in the UI. No framework or
generated frontend code was edited. The identical configs use disk state,
RadixThemesPlugin, disabled telemetry, and localhost ports 3133/8133.

Each run used an isolated CPython 3.12.1 environment containing only published
PyPI distributions; `PYTHONPATH` was unset and `uv run --no-project --no-config`
was invoked from the sample directory. Import origins and exact Python/JS
versions are saved in `logs/{alpha,stable}-environment.json`, with full frozen
graphs in `requirements-{alpha,stable}-lock.txt`.

- Alpha: Reflex/base/core/Radix 0.10.0a1, React 19.3.0, Vite 8.3.2.
- Stable: Reflex/base 0.9.12, stable component graph, React 19.2.8, Vite 8.2.2.
- Both Python graphs: python-socketio 5.17.0, python-engineio 4.14.0, and
  reflex-enterprise 0.9.7a2 (installed but unused by this core sample).
- Default runtime logged by both published CLIs: Bun 1.4.0. A further stable
  diagnostic used the bundled Node 24.19.0.
- UI observations use actual CUA browser tabs; console and accessibility facts
  are saved in `logs/cua-*.json`. The browser was shown inline for visual QA.

## Results

| Extra dormant states | Alpha 0.10.0a1 production | Stable 0.9.12 production |
|---|---|---|
| 500 | PASS: Article 7, Home navigation, counter 0→1; console errors empty | PASS: same route/navigation/event; console errors empty |
| 1,000 | PASS: same route/navigation/event; console errors empty | PASS after clean rebuild and closing prior alpha tabs; console errors empty |
| 1,500 | Build passes; HTTP 200; badge-only blank page; React stack overflow | Build fails with SIGILL during Vite client transform; browser comparison blocked |

Alpha development at 1,500 states also displays a blank page. Its readable
console stack starts with `pushComponentEffectStart`, followed by repeated
`commitMutationEffectsOnFiber` and `recursivelyTraverseMutationEffects` calls
in `react-dom_client.js`. This supports a client render-depth limit, not a
backend exception or a missing dynamic route. The generated alpha
`ClientStateProvider` still creates a nested `SubstateProvider` tree for every
substate; the server now uses bare context providers. This is an inference
from generated code and the observed stack, not a proposed framework fix.

Stable 1,500 development also fails with SIGILL before a usable page is served.
Making Node available on PATH did not avoid it. A diagnostic direct invocation
of the already installed `@react-router/dev` official CLI with Node likewise
exited 132 during startup. Those failures are preserved in
`stable-1500-{server,dev-server,dev-node-server,node-frontend}.log`; no
stable 1,500 browser result is claimed.

The first stable 1,000 run had alpha tabs still connected to the reused port.
Their newer handshake caused `EventNamespace.on_connect()` argument errors on
the stable backend. Closing all previous tabs and rebuilding the stable
`.web`, `reflex.lock`, and `.states` directories removed those errors. The
clean stable run passed route hydration and counter events with the same
Socket.IO versions, so **no dependency incompatibility is claimed**. Its
authoritative log is `stable-1000-clean-server.log`.

## Reproduce

Create fresh isolated environments and install the saved exact published
graphs. These commands deliberately bypass workspace resolution and its
`exclude-newer` setting:

```bash
uv --no-config venv --python 3.12 /private/tmp/many-states-alpha
uv --no-config pip install --python /private/tmp/many-states-alpha/bin/python \
  --index-url https://pypi.org/simple -r requirements-alpha-lock.txt
uv --no-config venv --python 3.12 /private/tmp/many-states-stable
uv --no-config pip install --python /private/tmp/many-states-stable/bin/python \
  --index-url https://pypi.org/simple -r requirements-stable-lock.txt

bash run_variant.sh alpha 1500 prod /private/tmp/many-states-alpha/bin/python
# Stop the server and close that browser tab before each following variant.
bash run_variant.sh alpha 1000 prod /private/tmp/many-states-alpha/bin/python
bash run_variant.sh alpha 500 prod /private/tmp/many-states-alpha/bin/python
bash run_variant.sh stable 1500 prod /private/tmp/many-states-stable/bin/python
bash run_variant.sh stable 1000 prod /private/tmp/many-states-stable/bin/python
bash run_variant.sh stable 500 prod /private/tmp/many-states-stable/bin/python
bash run_variant.sh alpha 1500 dev /private/tmp/many-states-alpha/bin/python
```

For each successful server launch, open a fresh browser tab at
`http://localhost:3133/articles/7?self=1`, verify **Article 7**, click **Home**, and
click **Increment** once. Read browser errors. The alpha 1,500 production page
instead remains blank with only the Reflex badge, and the development page is
blank. No exact failure threshold or universal browser claim is inferred from
these three tested sizes.

All test servers and owned browser tabs were stopped/closed after recording
the results. No fixes or commits were made by this agent.

## Fresh bundled runtime follow-up

The published alpha's `Bun.VERSION` is 1.4.2 and `Bun.MIN_VERSION` is 1.4.0.
`install_bun()` intentionally accepts an existing runtime at or above the
minimum, explaining the original runs' Bun 1.4.0. A fresh neutral
`REFLEX_DIR=/private/tmp/reflex-pre-js-runtime-20261005` with no Bun/Node on PATH
caused the public alpha CLI to download its official installer and successfully
install **Bun 1.4.2**. The 1,500-state production sample compiled and started
under that runtime; `/articles/7?bun=1.4.2` returned HTTP 200 with 5,309 bytes.
The client entry asset was still named `entry.client-qPZbTPY2.js`, the same
asset name recorded in the original in-app browser stack. The root independently
reproduced the blank page in **native Chrome 154.0.8037.98** with published
Playwright 1.63.0 against this fresh Bun 1.4.2 build. The body contained only
`Built with Reflex`, and the page error was `Maximum call stack size exceeded`.
The captured document, JS, and CSS network responses were HTTP 200. The console
also recorded a separate 404 without its resource URL; no claim of an entirely
error-free network is made.

Fresh-runtime browser evidence and reusable driver:

- [Browser JSON](../../lifecycle/evidence/fresh-bun-scale/browser.json)
- [Blank-page screenshot](../../lifecycle/evidence/fresh-bun-scale/blank-page.png)
- [Root browser driver](../../lifecycle/scale_browser.py)

The alpha failure is therefore observed in both the Codex in-app browser and
native Chrome. No universal browser limit or exact threshold is inferred.

Exact command from `alpha/`:

```bash
env -u PYTHONPATH CI=true QA_EXTRA_STATES=1500 \
  REFLEX_DIR=/private/tmp/reflex-pre-js-runtime-20261005 \
  REFLEX_USE_SYSTEM_BUN=false \
  PATH=/Users/masenf/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache \
  uv --no-config run --no-project \
  --python /private/tmp/reflex-enterprise-test-20261005/bin/python \
  reflex run --env prod --frontend-port 3133 --backend-port 3133 --loglevel debug
```

The runtime files were placed in the temporary directory, but the installer
unexpectedly appended a `# bun` / `BUN_INSTALL` / PATH block to `~/.zshrc`.
`revert_neutral_bun_profile.py` removed exactly this newly appended suffix;
a subsequent read verified that the temporary runtime path was absent from
the profile. The original global Bun executable still reports 1.4.0. No prior
user settings or other agents' blocks were removed by this agent. This side
effect appears **preexisting**: stable 0.9.12 calls the same unpinned official
installer URL with the same `BUN_INSTALL` setup, and that script explicitly
appends to writable `.zshrc`. A fresh stable install was not rerun to prove it.

Evidence: `logs/alpha-1500-neutral-bun-server.log`,
`logs/neutral-bun-install.json`, `logs/reflex-bun-install-reference.sh`, and
the root's independent native Chrome collection linked above. The in-app browser
was unavailable during this follow-up; the new browser proof comes from the
root's separate published Playwright environment. The fresh server was stopped
after collection, and ports 3133/8133 have no listeners.
