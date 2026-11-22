# reflex-frontend

The javascript a Reflex app runs on: state sync over the websocket, the event
loop, client state, the python-semantics helpers compiled code calls, and the
Vite plugins of the build.

## How it reaches an app

This package is not published to npm. When the `reflex-base` wheel is built, its
build hook (`packages/reflex-base/hatch_build.py`) embeds `src/` as
`reflex_base/.templates/web`. `reflex init` copies that into the project's `.web`
directory, where Vite bundles it with the compiled pages.
Compiled code imports it through the `$/` alias, which names `.web`:
`$/utils/state` is `src/utils/state.js`.

In a checkout of the repository there is no embedded copy: reflex-base reads
`src/` in place, so the next `reflex init` copies an edit without a rebuild.

Everything in `src/` ships to every app, including the build tooling an app
runs (`compress-static.js`, `script-modules.js`, which the compiler runs to read
the JavaScript modules an app imports from Python, `script-signatures.js`, which
reads their types for their Python stubs in development, the PostCSS config,
the Vite plugins). The output of `script-signatures.js`, the contract with
`reflex_base/js/stubs.py`, is `tests/fixtures/signatures/signatures.json`. Tests,
fixtures and this package's own lint and type-check setup stay outside it.

A change under `src/` is a change to reflex-base: its news fragment goes in
`packages/reflex-base/news/`.

## Working on it

```
npm ci            # install
npm run check     # lint, type-check and test: what CI runs
npm run lint      # biome, configured in lint.biome.jsonc
npm run typecheck # tsc over the JSDoc, nothing emitted
npm test          # vitest + jsdom
npm run build     # pack the tarball a release would publish
```

`$/env.json` is compiled per app, so tests read `tests/fixtures/env.json` in its
place.

The source is javascript with JSDoc types. `tsc` checks it in place (`checkJs`),
so there is still no compile step between this directory and an app.

## State that is not in the function signatures

Several of the bugs found in this code came from state a function reads or writes
without it appearing in its arguments. What there is, and where it is pinned:

- **Module-level state in `utils/state.js`**: the event queue, the session
  token, the socket warmed up before React mounts, the record of sent
  localStorage values, the app's JavaScript modules loaded so far. Every
  mounted event loop and every drain shares them. A test that needs a clean
  copy reloads the module (`vi.resetModules()`, as
  `tests/state_connection.test.js` does). Code that awaits must not assume the
  queue or the socket is as it left them.
- **Work done on import**: `utils/state.js` creates the cookie reader, always;
  publishes the client state store on `refs`, when there is a `document`; and
  starts a socket transport and loading the JavaScript modules the app imports
  from Python (`utils/scripts.js`), when there is a `window`. A production
  build evaluates every module in node to prerender pages, so anything added
  here has to load without either. `tests/public_api.test.js` imports each module in
  node to keep it that way.
- **Script scope**: event code sent by the backend (`rx.call_script`, event
  callbacks) runs through `runScript` in `utils/state.js`, which compiles it
  with the Function constructor and passes in every export of that module, the
  late-bound `addEvents`, the `socket`, `navigate` and `params` of the event
  being applied, the session `token`, `env` (the app's `$/env.json`, which
  `rx.get_upload_url` compiles to) and `reflex` (the API in `utils/reflex.js`,
  which `rx.js` compiles to). A direct `eval` would see every module local, but
  it stops the minifier from mangling the chunk that holds it. So a script sees
  those names and the globals, and nothing else. Renaming an export changes
  what compiled callbacks can call.
- **Globals the runtime reads**: hooks other code installs on `window`
  (`__reflex_otel`, `__reflex`, `__reflex_load`) and the per-app `$/env.json`.
  Each is declared in `types/globals.d.ts`; reading one that is not fails the
  type check.
- **Globals the runtime publishes**: `utils/state.js` sets `globalThis.refs`
  on import, so code written against 0.10 that reads `refs[...]` without
  importing it keeps working. TypeScript takes that assignment as declaring a
  global, so the type check accepts a bare `refs` in any module here. The
  linter is what rejects one that was not imported (`noUndeclaredVariables`).
- **Exported names**: compiled pages and separately published component
  packages import them by name. `tests/public_api.test.js` lists them, so a
  rename or removal is a visible edit.
- **Timers keyed by name**: `debounce` and `throttle` keep one timer per event
  name and delay, shared by every component that fires that event.

## Dependencies

`dependencies` pins what the modules under `src/utils` and `src/app` import, at
the versions Reflex installs into an app (`PackageJson.DEPENDENCIES` in
`reflex_base/constants/installer.py`). A python unit test fails when the two
drift, so bump them together.

A few modules import packages that are not declared here yet.
`utils/helpers/dataeditor.js` (`@glideapps/glide-data-grid`) and
`vite-plugin-react-compiler.js` (babel) belong to an optional component or
plugin, which installs the package. `app/routes.js` imports `@react-router/dev`
and `@react-router/fs-routes`, which every app installs as dev dependencies.
`script-modules.js` imports rolldown's parser through `vite`, another of them;
here vitest brings both.

What `script-modules.js` prints is a contract with the compiler, which reads
it with `_read_script_modules` in `reflex/compiler/utils.py` and rejects output
of any other `format` or shape. Change its `format` with its shape, and the
TypedDicts there with both; `test_read_script_modules_contract` runs the real
script through that parser.

## Before this can be published

- A name. `reflex-frontend` is a placeholder and the package is `private`.
- Imports of `$/...` and of the per-app `$/env.json` only resolve inside an app's
  `.web`; a published package needs relative imports and the app's settings
  passed in.
- npm leaves `src/.gitignore` out of the tarball, and `.web` needs it.
