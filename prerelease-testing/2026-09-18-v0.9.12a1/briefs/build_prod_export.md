# Cluster `build_prod_export` — prerender/asset collisions, compression, preload, lazy bundled libraries, sitemap (#7078); `frontend_path` prefix routes (#7153); backend-only bundled-library metadata (#7096); json5 removal (#7165); atomic stateful-page markers (#7142); sentry ASGI wrap (#7139); vite memory + urllib telemetry (#7112)

Changelog lines (verbatim):
- Preserve prerendered pages when asset directories collide with routes under `frontend_path`, and compress the final merged output. (#7078)
- Preload the global stylesheet so browsers can discover render-blocking CSS alongside early resource hints. (#7078)
- Honor `frontend_lazy_bundled_libraries` when compiling the app root so optional dynamic-component namespaces do not force their full exports into every page's initial bundle. (#7078) / (reflex-base) Add the opt-in `frontend_lazy_bundled_libraries` config setting to load optional dynamic-component libraries on first use, reducing JavaScript loaded by ordinary pages. React and the shared runtime remain immediately available. (#7078)
- (reflex-base) Allow unused memoized components to be removed from shared frontend bundles. Render readable code before Shiki loads, and highlight blocks as they approach the viewport. (#7078)
- (reflex-base) Use the standard sitemap XML namespace and include `frontend_path` in default sitemap URLs. (#7078)
- (reflex-base) Load `rxconfig` only from the requested project directory, preventing an installed or editable app from supplying another project's configuration when no local config exists. (#7078)
- Match routes that start with the `frontend_path` text, such as `/apple` under `frontend_path="/app"`, instead of treating them as 404. (#7153)
- Persist bundled-library metadata for backend-only workers so state hydration can serialize values that reference libraries included in the frontend build. (#7096)
- (reflex-base) The upload helper no longer imports `json5`... Exported production bundles no longer embed json5's bundled core-js 2.6.5 runtime, and upload responses are now parsed with the same native JSON path the socket already uses, non-finite float values included. (#7165)
- Fix backend startup crashes from concurrent or truncated stateful-page marker writes. Markers are replaced atomically, remain readable by separate backend users, and are rebuilt when missing or corrupt; dry-run compilation leaves them unchanged. (#7142)
- Apps no longer crash at startup with `AttributeError: 'method' object attribute '__call__' is read-only` when ASGI instrumentation that wraps middleware is active, such as sentry-sdk's Starlette integration. (#7139)
- Reduce `reflex run` and `reflex export` memory: the vite/react-router processes no longer keep their dependency pre-bundling arena resident (`MIMALLOC_ARENA_EAGER_COMMIT=0`, overridable from the environment), and error telemetry is sent through `urllib` so backend workers never import `httpx`. (#7112)

Read #7078 (huge docs-site PR — only the framework parts matter), #7153, #7096 (its issue #7096 came
out of the previous campaign's FINDING-018: a state var referencing a bundled library made the
whole hydrate delta fail in backend-only mode), #7142.

## Build

App with `frontend_path="/app"` and routes `/`, `/apple`, `/app`, `/about`, `/components`,
`/assets`, `/items/[id]`; an `assets/components/logo.svg` and `assets/apple/note.txt` (asset dirs
named like routes); a page using `rx.code_block` (shiki fallback), `rx.markdown`, `rx.upload`
whose handler sets vars to `float("inf")`, `float("nan")` and a normal float; a dynamic component
(`rx.dynamic`/`rx.bundle_library`-registered library, e.g. a lucide icon by name via
`rx.icon(tag=State.icon_name)` or `rx._x.dynamic`) and a State var that holds/refers to such a
component (the #7096 shape — read the previous campaign notes at
`git -C /home/user/reflex show origin/claude/reflex-prerelease-testing-t0sd90:prerelease-testing/2026-09-10-v0.9.11a1/ent_map_dnd_flow/NOTES.md`
for the FINDING-018 repro).

1. `reflex export` (and `--frontend-only`): inspect `.web/build/client/`: prerendered
   `components/index.html`, `apple/index.html`, `about/index.html` exist and contain page text
   (not the SPA shell), `assets/components/logo.svg` still served; `.gz`/`.br` siblings exist for
   the merged html/js/css; `sitemap.xml` uses `http://www.sitemaps.org/schemas/sitemap/0.9` and
   URLs carry `/app`; the HTML head has `<link rel="preload" as="style">` for the global CSS.
   `grep -r "core-js" .web/build` must be empty (#7165). Serve the export statically (e.g.
   `python -m http.server` from the client dir with a backend `reflex run --backend-only`) and load
   every route in Chromium.
2. `reflex run --env prod` (one port): `/apple`, `/app/apple`, `/app`, `/app/`, `/app/about`,
   `/apple/` and `/appx` — record status codes and rendered content for each; baseline 0.9.11.post1
   (the changelog says `/apple` was a 404).
3. `frontend_lazy_bundled_libraries=True` vs default: compare initial JS bytes transferred for a
   plain page (network capture) and confirm the dynamic component still renders on the page that
   uses it (a deferred chunk appears in the network log). Also with the setting on: a
   `rx.dynamic` component whose library FAILS to load once (block it via Playwright `route`) then
   succeeds ("retry after failures").
4. Backend-only prod: `reflex run --env prod --backend-only --backend-port P` plus the static
   export served separately (set `api_url`/`deploy_url` accordingly): hydrate a state whose var
   references a bundled library — no `ValueError`/dropped hydrate (FINDING-018 shape); check
   `.web/` for the persisted bundled-library metadata file and what happens if it is missing.
5. Upload with non-finite floats → the vars show `Infinity`/`NaN` (or whatever the design is) in
   the browser and NO console error; baseline.
6. Markers (#7142): find the stateful-pages marker path in the source (`grep -rn stateful
   /home/user/reflex/reflex/app.py /home/user/reflex/packages/reflex-base/src`), then: prod with
   `granian` workers = 4 starting together (`REFLEX_GRANIAN_WORKERS`? check `reflex run --help`);
   truncate/corrupt the marker and start again (rebuilt, no crash); delete it (rebuilt); run the
   dry-run/compile-only path and confirm the marker is unchanged (mtime/hash).
7. Sentry: own venv with `sentry-sdk`; `sentry_sdk.init(dsn="http://k@localhost:1/1", integrations=[StarletteIntegration(), StarletteIntegration()])`
   in the app module → `reflex run` starts, pages work, no `__call__` AttributeError; baseline.
8. Memory/imports: `ps -o rss` of the vite/react-router node processes during dev with the default
   and with `MIMALLOC_ARENA_EAGER_COMMIT=1` exported; a handler that returns
   `sorted(m for m in sys.modules if m in ("httpx","json5","sqlalchemy","pandas"))` rendered on the
   page, in dev and prod (backend worker must not have `httpx`).
9. rxconfig isolation: from an EMPTY directory (no rxconfig.py) with the app installed as a package
   on `sys.path`/`PYTHONPATH`, `reflex run` must fail with a clear error rather than pick up the
   other project's config.
