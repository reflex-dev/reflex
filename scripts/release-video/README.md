# Reflex 0.9.8 release video

A ~27s [Remotion](https://www.remotion.dev) video covering the 0.9.8 release,
styled to match [reflex.dev](https://reflex.dev).

## Running it

```bash
npm install
npm run studio    # interactive editor at http://localhost:3000
npm run render    # writes out/reflex-0.9.8.mp4
```

Rendering needs a Chromium **headless shell** — Remotion launches with
old-headless flags that a full Chrome binary rejects. `remotion.config.ts`
defaults to the shell shipped with Playwright; point it elsewhere with:

```bash
REMOTION_BROWSER_EXECUTABLE=/path/to/chrome-headless-shell npm run render
```

## Where the design comes from

Nothing here is invented — the look is lifted from the site's own tokens:

| Piece | Source |
| --- | --- |
| Colors (`src/theme.ts`) | `packages/reflex-site-shared/.../styles/assets/custom-colors.css` |
| Shadows | `packages/reflex-site-shared/.../styles/shadows.py` |
| Fonts | Instrument Sans + JetBrains Mono, the pins in `docs/app/rxconfig.py` |
| Wordmark (`src/logo.ts`) | `docs/images/reflex.svg`, decoded to its 25x5 pixel lattice |

Because the mark is stored as cells rather than a path, each block animates
independently — that is the intro and outro assembly.

## Content

Scene copy comes from the changelogs materialized in
[#6845](https://github.com/reflex-dev/reflex/pull/6845): the root `CHANGELOG.md`
plus each `packages/*/CHANGELOG.md`.

## Structure

```
src/
  Root.tsx          composition registration
  Video.tsx         scene timeline + glow drift
  theme.ts          brand tokens
  logo.ts           wordmark pixel lattice
  useFonts.ts       holds rendering until webfonts rasterize
  components/       Backdrop, Chrome, PixelLogo, Scene, ui primitives
  scenes/           Intro, Preview, Deploy, Features, Fixes, Deps, Outro
```

Scene durations live in the `SCENES` table in `src/Video.tsx`; the composition
length is derived from them, so adding or retiming a scene needs no other edit.
