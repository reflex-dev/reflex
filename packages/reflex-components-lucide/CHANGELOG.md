## v1.0.4 (2026-08-28)

### Miscellaneous

- Internal logging migrated from the legacy console helpers to standard python `logging` per-module loggers. ([#6864](https://github.com/reflex-dev/reflex/issues/6864))


## v1.0.3 (2026-08-04)

### Miscellaneous

- Bumped `lucide-react` 1.14.0 → 1.26.0, adding 46 new icons. ([#6678](https://github.com/reflex-dev/reflex/issues/6678))


## v1.0.2 (2026-06-10)

### Bug Fixes

- `rx.icon` with a static name now emits a deep per-icon import (`import LucideWifiOff from "lucide-react/dist/esm/icons/wifi-off.mjs"`) instead of a named import from the `lucide-react` barrel. The barrel import was harmless on its own, but once an app's module graph also contained `lucide-react/dynamic.mjs` (pulled in by dynamic `Var`-tagged icons, and by the connection overlay mounted on every page), esbuild's dev dep-optimizer rewrote the barrel to statically import every icon chunk — making each page load fetch the entire ~1700-icon library. Deep imports load only the icons actually used. The dynamic `Var` path still resolves through `lucide-react/dynamic.mjs` and is unchanged. ([#6628](https://github.com/reflex-dev/reflex/issues/6628))
