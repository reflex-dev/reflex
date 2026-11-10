# reflex-frontend

The javascript a Reflex app runs on: state sync over the websocket, the event
loop, client state, the python-semantics helpers compiled code calls, and the
Vite plugins of the build.

## How it reaches an app

This package is not published to npm. `src/` is embedded in the `reflex-base`
wheel as `reflex_base/.templates/web`, and `reflex init` copies it into the
project's `.web` directory, where Vite bundles it with the compiled pages.
Compiled code imports it through the `$/` alias, which names `.web`:
`$/utils/state` is `src/utils/state.js`.

In a checkout of the repository there is no embedded copy: reflex-base reads
`src/` in place, so the next `reflex init` copies an edit without a rebuild.

Everything in `src/` ships to every app. Tests, fixtures and tooling stay
outside it.

## Working on it

```
npm ci        # install
npm test      # vitest + jsdom
npm run build # pack the tarball a release would publish
```

`$/env.json` is compiled per app, so tests read `tests/fixtures/env.json` in its
place.

## Dependencies

`dependencies` pins what the modules under `src/utils` and `src/app` import, at
the versions Reflex installs into an app (`PackageJson.DEPENDENCIES` in
`reflex_base/constants/installer.py`). A python unit test fails when the two
drift, so bump them together.

A few modules belong to an optional component or plugin and import a package only
that component installs: `utils/helpers/dataeditor.js`
(`@glideapps/glide-data-grid`), `vite-plugin-react-compiler.js` (babel) and
`app/routes.js` (`@react-router/dev`). Those are not declared here yet.

## Before this can be published

- A name. `reflex-frontend` is a placeholder and the package is `private`.
- Imports of `$/...` and of the per-app `$/env.json` only resolve inside an app's
  `.web`; a published package needs relative imports and the app's settings
  passed in.
- npm leaves `src/.gitignore` out of the tarball, and `.web` needs it.
