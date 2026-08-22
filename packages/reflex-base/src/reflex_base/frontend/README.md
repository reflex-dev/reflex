# @reflex-dev/reflex-base

The Reflex frontend runtime: state and event plumbing (`./state`), the runtime
config registry (`./runtime`), theming (`./react-theme`), and helpers imported
by Reflex-compiled apps.

This package is distributed inside the `reflex-base` Python wheel as a packed
tarball (its version is stamped from the wheel's version at build time) and is
installed into each app's `.web` directory by `reflex run`. In editable/dev
installs of reflex-base, this source directory is linked into `.web` directly,
so edits hot-reload without a reinstall.

Manifest contract (consumed by the Python side):

- `dependencies` are the runtime libraries the app graph resolves transitively;
  users override versions via `overrides` in their `reflex.lock/package.json`.
- `devDependencies` declare the app-level build toolchain (vite, react-router
  tooling, postcss, ...). A dependency's devDependencies are never installed by
  package managers, so Reflex installs these into the app's own
  `devDependencies` at setup time. They are not used to build this package —
  it ships plain ESM source and has no build step; the app's vite compiles it.
- optional `peerDependencies` (shiki, glide-data-grid) back the per-component
  modules under `./components` and `./helpers`; the owning Reflex components
  install them only when actually used.

Unit tests live in `tests/` (excluded from the tarball via `files`); run them
with `npm ci && npm test` from that directory.
