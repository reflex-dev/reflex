# reflex-site-shared

Shared site scaffolding used across Reflex's web properties (pages, templates, views, gallery, styles).

## Markdown documentation sites

The package can discover a directory of Markdown files, derive routes and
navigation, render them with the Reflex documentation component map, and
register the pages on an app.

```python
from pathlib import Path

import reflex as rx
from reflex_site_shared import styles
from reflex_site_shared.docs import DocsLayoutConfig, DocsSiteConfig, register_docs

app = rx.App(style=styles.BASE_STYLE)

register_docs(
    app,
    DocsSiteConfig(
        content_dir=Path(__file__).parent.parent / "content",
        route_prefix="/",
        exclude=("drafts/**",),
        navigation_order=("/", "/getting-started/", "/guide/installation/"),
        sitemap_base_url="https://example.com/docs/product",
    ),
    layout_config=DocsLayoutConfig(site_title="Product Documentation"),
)
```

Enable the shared global CSS in `rxconfig.py` and install the Fontsource
variable fonts referenced by its `fonts.css`:

```python
from pathlib import Path

import reflex as rx
from reflex_site_shared.docs import DocsSiteConfig
from reflex_site_shared.plugins import DocsMarkdownPlugin, SharedSiteStylesPlugin

docs = DocsSiteConfig(
    content_dir=Path(__file__).parent.parent / "content",
    exclude=("drafts/**",),
)

config = rx.Config(
    app_name="docs_site",
    frontend_packages=[
        "@fontsource-variable/instrument-sans@5.2.8",
        "@fontsource-variable/jetbrains-mono@5.2.8",
    ],
    plugins=[
        rx.plugins.TailwindV4Plugin(),
        SharedSiteStylesPlugin(),
        DocsMarkdownPlugin(docs=docs),
        rx.plugins.RadixThemesPlugin(),
    ],
)
```

Existing sites that provide their own font CSS can use
`SharedSiteStylesPlugin(include_fonts=False)`.

`DocsMarkdownPlugin` serves each discovered page as Markdown using the same
URL convention as the official Reflex docs. For example,
`/guide/installation/` is also available at `/guide/installation.md` and
`/guide/installation/.md`. The site's `frontend_path` is prepended
automatically.

The content tree defines the URL tree:

```text
content/
├── index.md                 -> /
├── getting-started.md       -> /getting-started/
└── guide/
    └── installation.md      -> /guide/installation/
```

Use YAML frontmatter to override the page title and description:

```markdown
---
title: Installation
description: Install and configure the product.
---

# Installation
```

Like the official Reflex docs, ordering lives in a centralized Python list.
Use `DocsSiteConfig.navigation_order` to control sidebar and previous/next
ordering without adding presentation metadata to each Markdown file.

`build_docs_routes` returns routes without registering them when the consuming
app needs custom SEO or registration behavior. Both `build_docs_routes` and
`register_docs` accept custom `renderer` and `layout` callables. The defaults
use the shared responsive docs shell and styled Markdown components.

The default renderer uses the same `reflex-docgen` pipeline as Reflex's main
documentation, including executable example fences, directives, tables, and
the shared documentation component map. Generated component API pages can call
the exported `render_docgen_document` helper directly.

### Expensive documentation previews

Add `defer` to a `python demo exec` fence to mount a heavy preview as it approaches the viewport. The example's source code remains in the initial HTML; the preview reserves 450px of height and stays mounted once shown. This is useful for pages containing many Plotly charts.

## Marketing footer

Use the marketing site's responsive five-column directory footer in another
Reflex site:

```python
from reflex_site_shared.views.marketing_footer import marketing_footer

marketing_footer(show_color_mode_toggle=True)
```

Load `SharedSiteStylesPlugin` for its palette, fonts, icons, and button assets.
The footer includes newsletter signup, social links, and service status using
the package's existing signup/status state. Marketing links use absolute URLs
so they work under a docs router basename. The default `appearance="light"`
uses the site's semantic background and follows its color mode;
`appearance="dark"` uses the contrasting primary surface. Theme controls are
optional and hidden by default.

### Marketing navigation

```python
from reflex_site_shared.views.announcement_banner import announcement_banner
from reflex_site_shared.views.marketing_navbar import (
    marketing_mobile_drawer,
    marketing_navbar,
)

marketing_navbar()  # Fixed header, announcement, desktop menus, and mobile drawer.
marketing_navbar(show_banner=False)
marketing_navbar(banner=my_announcement())
marketing_mobile_drawer()  # Reuse the mobile menu inside a site-specific header.
```

`SharedSiteStylesPlugin` includes the announcement persistence and publication-date
assets. Marketing destinations use absolute `https://reflex.dev` links so they
work from independently hosted docs apps. The legacy `hosting_banner()` entry
point renders the same announcement. Docs keep their section links and use the
shared mobile menu; their article sidebar remains separate.
