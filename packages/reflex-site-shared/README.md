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

## App-owned HTTP routing

`HttpRoutingPlugin(redirects={"/old": "/new/"})` exports Caddy fragments from
Reflex's registered pages, including client-only and noindex pages. Paths in the
redirect mapping are public URLs; registered page routes receive the configured
`frontend_path` prefix. Local destinations must be registered pages. Chains are
flattened, cycles and missing destinations fail the build, and queries/fragments
are preserved. External destinations retain their path shape.

The plugin writes `__http_routing__/app-redirects.caddy` and `app-pages.caddy`
inside the frontend export. The frontend Dockerfile must move this directory to
`/etc/caddy/app-routing` **outside the web root**, and fail if either file is
missing. The internal Helm chart imports these optional fragments before slash
normalization and before the HTML/SPA fallback, respectively. Its `querySuffix`
map supplies the original query string. Existing images without fragments retain
their existing behavior; new images require the matching chart to activate rules.

Unknown extensionless page requests return 404 before JavaScript. Exact registered
client routes may still use the SPA shell. Static assets and Markdown negotiation
keep their separate handlers. A sitemap is not a routing inventory: pages can be
valid while intentionally excluded from indexing.

Dynamic parameters are not converted to permissive wildcards. Apps with catalog
routes should register every concrete slug, then explicitly list the replaced
parameter route in `excluded_dynamic_routes`. Other dynamic routes cause a build
error until the app supplies an explicit policy. This plugin is opt-in; it does
not change framework routing or enable itself for other sites.
