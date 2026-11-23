# CLAUDE.md

## What is this project?

The Reflex documentation site: a Reflex app that lives in the reflex monorepo at
`docs/app/` and is a uv workspace member, so it runs against the workspace's
`reflex` and `packages/*` sources. `rxconfig.py` mounts it at `frontend_path="/docs"`,
so every route is served under `/docs/` (for example `/docs/state/overview/`).
Its Python package is `reflex_docs`.

The repository rules in the root `CLAUDE.md` apply here too. `README.md` in this
directory covers page frontmatter, production checks, redirects, and the
agent-readable exports in more detail.

## Where things live

```
docs/                       # content: every *.md outside docs/app/ and docs/package/ is a page
  app/                      # this app
    rxconfig.py             # app config: frontend_path, plugins, frontend packages
    reflex_docs/
      reflex_docs.py        # app entry point: registers routes, canonical URLs, redirects
      whitelist.py          # dev-only page whitelist (must be empty when committed)
      pages/docs/__init__.py  # discovers docs/**/*.md and integration docs, builds their routes
      pages/docs/           # Python-built pages: API reference, CLI reference, env vars, cloud
      pages/docs_landing/   # the /docs/ home page
      pages/integrations/   # integration pages and gallery
      templates/docpage/    # the docpage decorator, page layout, sidebar (sidebar/sidebar_items/)
      components/, views/   # app components: navbar, search, footer, feedback
      changelogs.py         # changelog pages from each package's CHANGELOG.md
      redirects.py          # middleware serving 301s for legacy URLs
    agent_files/            # AgentFilesPlugin: per-page .md copies, llms.txt, llms-full.txt
    assets/                 # static assets and the docs theme CSS (see design.md)
    data/                   # datasets read by demos
    tests/                  # pytest (some use Playwright) and frontend_quality.test.mjs
    news/                   # changelog fragments for docs changes
  package/                  # reflex-docs-bundle: the Markdown docs packaged as a wheel
packages/reflex-site-shared/  # shared site code: Markdown rendering (docs/markdown.py), demo blocks, styles
packages/reflex-docgen/       # Markdown parser and API-reference generation
packages/integrations-docs/   # integration pages, served under /docs/ai/integrations/
```

A Markdown page's route comes from its path (`doc_route_from_path` in
`reflex_docs/pages/docs/__init__.py`): `docs/state/overview.md` is
`/docs/state/overview/`, and `docs/ai_builder/...` is served under `/docs/ai/...`.
Renaming or moving a page changes its URL, so add a redirect in
`reflex_docs/reflex_docs.py` when you do. Pages are rendered by
`reflex_site_shared.docs.markdown`; fenced blocks such as `python demo exec` and
`md alert info` are handled there.

## Commands

Run these from `docs/app/`.

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Run dev server | `uv run reflex run`, then open http://localhost:3000/docs/ |
| Compile check | `uv run reflex compile` |
| Full production build | `uv run reflex export --no-zip` (slow) |
| Tests | `uv run pytest tests/` |
| Frontend checks (after a production build) | `node --test tests/frontend_quality.test.mjs` |
| Browser checks against a running server | `REFLEX_DOCS_PREVIEW_URL=http://localhost:3000 uv run pytest tests/test_editorial_browser.py tests/test_docs_features_browser.py` |
| Lint / format | `uv run ruff check . && uv run ruff format .` |
| Repository hooks (from the repo root) | `uv run pre-commit run --all-files` |

The app is built on `reflex_enterprise.App`, which exits at startup unless you
are logged in (`reflex login`) or `CI` is set. `reflex run --env prod` is also
restricted to paid tiers; the CI jobs set `APP_HARNESS_FLAG=true` to build it.

## Dev mode: page whitelist

`reflex_docs/whitelist.py` limits which pages are compiled, for faster builds.
Paths are app routes without the `/docs` mount, start with `/`, have no trailing
slash, and match by prefix; an empty list builds every page. CI
(`.github/workflows/docs_whitelist.yml`) fails if the list is not empty, so never
commit entries. A whitelisted build also rewrites `reflex.lock/`; restore it
before committing.

## Tests

- `tests/` holds module-level pytest tests. Browser tests in
  `test_editorial_browser.py` and `test_docs_features_browser.py` skip unless
  `REFLEX_DOCS_PREVIEW_URL` points at a running server.
- `test_doc_links.py` and `test_published_seo.py` read a production build's
  sitemap and exports. Run them with `--runxfail` after `uv run reflex export --no-zip`.
- Code examples are executed by tests such as `test_database_examples.py`; keep
  those tests passing when you edit an example they cover.
- CI: `.github/workflows/docs_tests.yml` runs `pytest tests/`, and the
  `reflex-docs` job in `.github/workflows/integration_tests.yml` builds the
  production site and runs the link, SEO, and frontend checks.

## Conventions

- New app UI uses `rx.el.*` elements with Tailwind classes and the theme tokens
  in `design.md`.
- Imports are absolute from the app root, e.g.
  `from reflex_docs.templates.docpage import docpage`.
- Code examples teach the current APIs: SQLAlchemy models with async sessions
  (see `docs/database/overview.md`), not the deprecated `rx.Model`/`rx.session()`.
- User-facing changes need a fragment in `news/` (see the root `CLAUDE.md`).
  Changes to `packages/reflex-site-shared` need one in that package's `news/`.
- Before committing: `uv run pytest tests/`, `uv run reflex compile`, and
  `uv run pre-commit run --all-files` from the repo root.
