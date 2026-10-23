# Cluster `cli-build` — init/run/export, .web management, frontend deps, concurrency locks

## Changelog lines (verbatim)
- (reflex #7052) Use atomic writes and OS locks to protect shared JSON metadata from concurrent Reflex processes. When locks are unavailable (for example, with a read-only `REFLEX_DIR`), writes remain atomic but concurrent updates may overwrite each other.
- (reflex #7404) A `stateful_pages.json` marker that is not valid UTF-8 is now treated as corrupt and rebuilt, instead of raising `UnicodeDecodeError` on every backend start.
- (reflex #7453) Production exports, `reflex run --env prod`, and preview startup that share a `.web` directory now wait for one another instead of overwriting each other's compiled frontend and archives.
- (reflex #7450, PERF) Speed up deployment archive creation by reducing filesystem checks for excluded files and avoiding recompression of precompressed frontend assets.
- (reflex #7554) `reflex init` no longer refuses to reinitialize an existing app just because its project directory is named `reflex`; the check now applies to the `app_name` set in `rxconfig.py`.
- (reflex #7566) Add development frontend packages with `-D`, so npm saves them under `devDependencies` and source-only hot reloads no longer reinstall frontend packages.
- (reflex #7639 / reflex-base #7639) Upgrade the default Bun version to 1.4.4. Clarify the warning shown when Bun is below the minimum supported version.
- (reflex-base #7645, MISC) Update generated apps to React 19.3.1, Vite 8.3.4, PostCSS 8.5.30, and postcss-import 17.0.1.
- (reflex-components-code #7645) Update react-syntax-highlighter to 16.1.2. (reflex-components-radix #7645) Update the Radix primitives to the versions bundled with the current `radix-ui` release (accordion 1.3.1, dialog 1.3.1, form 0.3.0, progress 1.2.1, slider 1.6.1), so apps load a single copy of each primitive.
- (reflex #7411) Fix installing Reflex source distributions with uv by excluding references to workspace packages that are not included in the archive.

## What to do
- `reflex init` in a dir named `reflex` (fresh) and re-init over an existing app; `reflex init` with `app_name="reflex"` in rxconfig (should refuse with a clear message).
- Inspect generated `.web/package.json`: dependencies vs devDependencies split; versions of react, vite, postcss, postcss-import, radix primitives (`bun pm ls` or lockfile); confirm exactly one copy of each `@radix-ui/react-*` primitive in `.web/node_modules` (`find .web/node_modules -path '*@radix-ui/react-dialog/package.json' | wc -l`, for each primitive) when the app uses accordion, dialog, form, progress, slider, and `rx.code_block` and `rx.markdown`. Compare with 0.10.0.
- Hot reload: run dev, touch a python source file → log must NOT show a frontend package install; add a new component that needs a new frontend package → it must install.
- Bun: run with a deliberately old bun on PATH if installable (`bun upgrade --version`? or download an older release) — else just read the warning text in the released source and set `REFLEX_BUN_PATH` to a stub that prints an old version, to see the message. Record what you did.
- Concurrency: run `reflex export --frontend-only` twice concurrently in the same app dir, and `reflex run --env prod` while an export is running; both should complete with consistent output (no half-written `.web/build`, zip integrity `unzip -t`). Time `reflex export` for an app with a few MB of static assets including precompressed `.gz`/`.br` files in `assets/`, 0.10.0 vs 0.10.1a1.
- Corrupt `.web/stateful_pages.json` (write invalid UTF-8 bytes) → backend starts and rebuilds it.
- Read-only `REFLEX_DIR`: point `REFLEX_DIR` at a dir made read-only after bun is installed; `reflex run` must still work (writes may be skipped) — record the exact behavior.
- Two different apps running `reflex init`/`run` at the same time with a shared `REFLEX_DIR` (lock correctness).
- Export + preview: `reflex run --env preview` if present in this version's CLI help, else skip.
