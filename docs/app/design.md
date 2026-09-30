# Docs design foundations

Adapted from [the marketing design contract](https://github.com/reflex-dev/marketing/blob/main/design.md), `assets/tailwind-theme.css`, and the neutral ramp in `assets/marketing.css`.
The shared source is `packages/reflex-site-shared/src/reflex_site_shared/styles/assets/tailwind-theme.css`; edit it rather than generated `.web` files.

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

Use Instrument Sans for text and JetBrains Mono for code. Marketing typography roles (`text-hero`, `text-page-title`, `text-section`, `text-caption`) are available; retain docs-specific content sizing where appropriate. Body weight is 425, editorial headings 450, and controls 500.

Use capsule buttons (`rounded-control`), 12px inputs (`rounded-xl`), 14px cards (`rounded-card`), and 16px panels (`rounded-panel`). Keep primary and ghost actions flat; outlined actions use a solid border and `shadow-small`. Preserve labels, links, disabled states, and keyboard interaction.

The light palette matches marketing: white surfaces, #181818 foreground, #595959 descriptive text, #767676 metadata, and #e2e2e2 control borders. Docs also retain a neutral dark palette. Use foreground/background pairs so controls remain legible in both modes. Keep status and illustration colors when they convey meaning.

New UI must not use numbered primary/secondary colors. Their CSS aliases remain for internal controls and downstream consumers during migration. This pass changes foundations and colors; existing docs layouts and artwork remain independently maintained.
