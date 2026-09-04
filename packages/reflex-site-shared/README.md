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
