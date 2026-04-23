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
