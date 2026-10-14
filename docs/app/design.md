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

Use Inter for text, Geist for editorial headings, and JetBrains Mono for code. Inter and Geist use pinned Fontsource variable WOFF2 packages with Latin subsets and `font-display: swap`, bundled through `assets/docs-theme.css`. Retain their license notices in `assets/fonts/`. Body and controls use weight 400; page titles use Geist 300. Article body is 15px with a 1.85 line height; retain a comfortable reading width instead of using the marketing site's large display sizing for prose.

Use capsule buttons (`rounded-control`), 12px inputs (`rounded-xl`), 20px cards (`rounded-card`), and 24px panels (`rounded-panel`). Keep primary and ghost actions flat; outlined actions use a solid border. Preserve labels, links, disabled states, and keyboard interaction.

The light palette matches marketing: #fdfcfc canvas, #f5f3f1 quiet surfaces, black foreground, #e5e2de boundaries, and #efeeec separators. Docs use a slightly darker #69645e for small descriptive text and #777169 for metadata. Docs retain a warm dark palette. Use foreground/background pairs so controls remain legible in both modes. Keep status and syntax colors when they convey meaning.

New UI must not use numbered primary/secondary colors. Their CSS aliases remain for internal controls and downstream consumers. Scope editorial rules to `.docs-heading`, `.docs-prose`, and named shell hooks. Never target every heading, paragraph, or button inside an article: live examples must retain their own typography and interactions. Respect reduced-motion preferences and keep focus indicators visible.

The announcement banner reuses the marketing opal artwork in `assets/header/opal.avif`. Docs retain a compact 64px header with a 40px visible announcement. Mobile navigation and article offsets follow `--docs-header-height`; dismissal removes only the announcement contribution.
