# Reflex Docs

## Getting Started

1. Install dependencies:

```bash
uv sync
```

2. Run the dev server:

```bash
uv run reflex run
```

3. Open [http://localhost:3000/docs/](http://localhost:3000/docs/) to see the app running.

## Editing Docs

Markdown docs live in the parent `docs/` directory (one level above `app/`). Edit any `.md` file there and the dev server will pick up the changes so you can preview them live in the app.

## Page Whitelist (Faster Dev Builds)

By default, the dev server compiles **all** pages, which can be slow. To speed things up, you can whitelist only the pages you're working on so only those get compiled.

Edit `reflex_docs/whitelist.py` and add paths to the `WHITELISTED_PAGES` list. Paths are **app routes** (relative to `frontend_path`, which defaults to `/docs` in `rxconfig.py`). Do not repeat the `/docs` mount segment in the whitelist, or nothing will match.

```python
WHITELISTED_PAGES = [
    "/getting-started/introduction",
    "/components/props",
]
```

**Rules:**
- Each path must start with a forward slash `/`.
- Do **not** include a trailing slash (e.g. `/getting-started/introduction`, not `/getting-started/introduction/`).
- An empty list (`[]`) builds all pages (the default).
- Paths are prefix-matched, so `"/components"` will include all pages under that section.

After editing the whitelist, restart the dev server for changes to take effect.

## Production quality checks

Build the complete documentation app before auditing SEO or load performance:

```bash
uv run reflex export --no-zip
node --test tests/frontend_quality.test.mjs
uv run pytest tests
```

If the build uses a custom `REFLEX_WEB_WORKDIR`, pass that environment variable to both test commands. The Python link validator reads that build's sitemap. The frontend tests use the build's installed React and bundler to check server-rendered code, highlight invalidation, and removal of unused components.

The docs app serves permanent HTTP 301 redirects for its legacy URLs when the Reflex backend serves the frontend. If HTML is hosted separately on a CDN, configure those same redirects at the edge using the `redirects` list in `reflex_docs/reflex_docs.py`. Static redirect pages also contain a canonical link, noindex directive, immediate refresh, and a usable destination link.

Docs pages intentionally omit the marketing site's pixels and session recording scripts. Search, examples, newsletter signup, and status information remain available.

The docs config enables `frontend_lazy_bundled_libraries`. Optional libraries registered for dynamic components load on the first dynamic-component evaluation, while React and the shared runtime stay available immediately. This prevents the full Radix namespace from being imported on every page. The framework default remains `False`; custom scripts that read optional libraries from `window.__reflex` directly should retain that default or await `window.__reflex_load()` first.
