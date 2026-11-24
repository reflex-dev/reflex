# Docs design foundations

Adapted from [the marketing design contract](https://github.com/reflex-dev/marketing/blob/main/design.md), `assets/tailwind-theme.css`, and the neutral ramp in `assets/marketing.css`.
The shared base is `packages/reflex-site-shared/src/reflex_site_shared/styles/assets/tailwind-theme.css`. The docs app's current marketing treatment lives in `assets/docs-theme.css`, followed by `assets/docs-header-theme.css` for navigation and `assets/docs-overlays-theme.css` for search, feedback, and footer controls. All three load after the shared base. Keep these app-specific overrides out of the shared theme so package documentation sites retain their own branding. Never edit generated `.web` files.

| Role | Classes |
| --- | --- |
| Page or control | `bg-background text-foreground` |
| Card | `bg-card text-card-foreground` |
| Quiet surface | `bg-muted` or `bg-accent` |
| Descriptive text | `text-muted-foreground` |
| Short metadata or placeholder | `text-subtle-foreground` |
| Primary action | `bg-primary text-primary-foreground hover:bg-primary-hover` |
| Control boundary | `border-border` |
| Quiet separator | `border-border-subtle` |
| Strong boundary | `border-border-strong` |
| Keyboard focus | `focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring` |

Use Geist 400 for editorial headings and article text, Inter 400 for navigation and embedded UI, and JetBrains Mono for code. Inter and Geist use pinned Fontsource variable WOFF2 packages, metric-matched fallbacks, Latin subsets and `font-display: swap`, bundled through `assets/docs-theme.css`. Actions use Geist 525 without changing weight on selection. Article body stays 15px with a 1.85 line height; retain a comfortable reading width instead of using marketing display sizes for prose. The overview uses marketing's 56/60px title and 32/40px sections, stepping down to 40/44px and 28/34px below 761px.

Use 8px buttons (`--docs-control-radius` in named docs hooks; framework examples may rebind `--radius-control`), 12px inputs with a flush neutral focus halo, 20px cards (`rounded-card`), and 24px panels (`rounded-panel`). Keep primary and ghost actions flat; outlined actions retain their boundary. Preserve labels, links, disabled states, and keyboard interaction. Keep the existing shared primitives and docs shell; do not copy the full marketing navigation or add a duplicate component library.

The light palette follows marketing PR #213 at `8001d418`: #fdfcfc canvas, #f5f5f5 quiet surfaces, #f9f9f9 panels, #0a0a0a ink, #6b6b6b secondary text, #1f1f1f primary actions and #e5e5e5 boundaries. The dark palette uses corresponding neutral grays with #151515 canvas and #f5f5f5 foreground. Use foreground/background pairs so controls remain legible in both modes. Keep status, syntax and live-example colors when they convey meaning.

New UI must not use numbered primary/secondary colors. Their CSS aliases remain for internal controls and downstream consumers. Scope editorial rules to `.docs-heading`, `.docs-prose`, and named shell hooks. Never target every heading, paragraph, or button inside an article: live examples must retain their own typography and interactions. Respect reduced-motion preferences and keep focus indicators visible.

The announcement is a flat black strip with plain white text and one coordinated text/arrow shimmer. Reduced motion and forced colors use static text. The old opal artwork and glass layers are retired. Docs retain a compact 64px header with a 40px announcement. Mobile navigation and article offsets follow `--docs-header-height`; dismissal removes only the announcement contribution. Promote “Announcing our $14M Series A” and link to `https://reflex.dev/blog/series-a-announcement/`. Preserve the existing dismissal state.

The overview action pairs match the marketing homepage at 42px tall, with 16px inline padding, Geist 525 at 15px, and an 8px gap. The overview footer uses the shared marketing directory, its compact newsletter, and the docs theme switcher. Align its content with the overview's gutters and use 72px top spacing, reduced to 56px on phones.
