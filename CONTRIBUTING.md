# Reflex Contributing Guidelines

## Running a Local Build of Reflex

Here is a quick guide on how to run Reflex repo locally so you can start contributing to the project.

**Prerequisites:**

- uv version >= 0.9.17 and add it to your path (see [UV Docs](https://docs.astral.sh/uv/getting-started/installation/) for more info).

**1. Fork this repository:**
Fork this repository by clicking on the `Fork` button on the top right.

**2. Clone Reflex and navigate into the repo:**

```bash
git clone https://github.com/<YOUR-USERNAME>/reflex.git
cd reflex
```

**3. Install your local Reflex build:**

```bash
uv sync
```

**4. Now create an examples folder so you can test the local Python build in this repository.**

- We have the `examples` folder in the `.gitignore`, so your changes in `reflex/examples` won't be reflected in your commit.

```bash
mkdir examples
cd examples
```

**5. Init and Run**

```bash
uv run reflex init
uv run reflex run
```

All the changes you make to the repository will be reflected in your running app.

- We have the examples folder in the .gitignore, so your changes in reflex/examples won't be reflected in your commit.

## 🧪 Testing and QA

Any feature or significant change added should be accompanied with unit tests.

Within the 'test' directory of Reflex you can add to a test file already there or create a new test python file if it doesn't fit into the existing layout.

#### What to unit test?

- Any feature or significant change that has been added.
- Any edge cases or potential problem areas.
- Any interactions between different parts of the code.

## 📝 Changelog Fragments

Each PR that changes the source of a published package must add a news fragment describing the change. Fragments are assembled into `CHANGELOG.md` at release time by [towncrier](https://towncrier.readthedocs.io/).

**Where: one fragment per affected package, not one per PR.** A PR that touches
two packages needs two fragments, one in each package's own `news/` directory.
CI decides which packages are affected purely from the changed paths:

| Changed path | Fragment belongs in |
| --- | --- |
| `reflex/**` | repo-root `news/` |
| `packages/<name>/src/**` | `packages/<name>/news/` |

So a PR editing both `reflex/state.py` and `packages/reflex-base/src/reflex_base/vars/base.py`
needs a fragment in `news/` **and** one in `packages/reflex-base/news/`. Changes
that touch neither path (tests, `docs/`, CI, `scripts/`) need no fragment on
their own. The `integrations-docs`, `reflex-components-internal` and
`reflex-site-shared` packages are never published, so they are always exempt.

Run the same check CI runs, once per affected package:

```bash
uv run towncrier check --config pyproject.toml --dir . --compare-with origin/main
uv run towncrier check --config pyproject.toml --dir packages/reflex-base --compare-with origin/main
```

**Filename:** `<pr-or-issue-number>.<type>.md`, where `<type>` is one of:

| Type | When to use |
| --- | --- |
| `breaking` | Backwards-incompatible change users need to adapt to |
| `deprecation` | API marked deprecated but still functional |
| `feature` | New user-facing functionality |
| `bugfix` | Fix for an incorrect behavior |
| `performance` | Speed, memory, or startup improvement |
| `docs` | Documentation or docstring changes |
| `misc` | Internal refactor, build, or dependency change that still warrants mention |

**Content:** one or two sentences, written for users reading release notes (not reviewers of the diff).

**Create a fragment from the CLI:**

```bash
uv run reflex-release create --package reflex-components-lucide 1234.feature.md
```

Drop `--package` for a fragment against the main `reflex` package.

If you don't yet know the PR number, use an [orphan fragment](https://towncrier.readthedocs.io/en/stable/cli.html#towncrier-create) (`+.feature.md`). Renaming it after opening the PR is nice, but not required: the release workflow renames any orphan fragment that made it to `main` after the PR that merged it, so the changelog entry still links to it.

**Skipping the fragment check:** for PRs that are genuinely not user-facing (CI-only tweaks, script fixes, test-only changes), apply the `skip-changelog` label on the PR to bypass the changelog CI check.

**Changelog version headings:** PRs to `main` must not add new version headings to any `CHANGELOG.md` — a merged heading without a git tag is a publish trigger, so new headings only come from the *Dispatch release* workflow. CI enforces this with the same parser the release pipeline uses; for deliberate restructuring of already-published sections, apply the `changelog-version-edit` label.

**Releasing (maintainers):** the `CHANGELOG.md` files are the source of truth
for publishing. A release is cut by materializing the news fragments into a
package's `CHANGELOG.md` under a new version heading and landing that change on
a release branch — never by tagging manually. The pieces:

1. **Dispatch release** (`dispatch_release.yml`, run from the Actions tab)
   selects packages and a release action, computes the next version(s), runs
   towncrier, and delivers the changelog bump. Leaving every package
   unchecked auto-selects the packages with pending news fragments (for
   `release-from-prerelease`: the packages whose changelog is topped by an
   alpha). Details:
   - *Prerelease actions* (`new-prerelease-*`, `continued-prerelease`) push
     alpha versions straight to an `r/pre-<date>` branch (continued
     prereleases push back to the `r/pre-*` branch they are dispatched on);
     alphas build immediately and upload once the `pypi` environment
     deployment is approved. To pull new work into a prerelease train, merge
     `main` into its branch and dispatch `continued-prerelease` on it.
   - *Release actions* (`release-*`) open a PR with the changelog changes
     instead; reviewing and merging that PR is how final versions land (the
     upload still waits for the `pypi` environment approval below). The PR
     targets `main`, or the `r/hotfix/...` branch the workflow was dispatched
     on (hotfix branches may publish final versions directly).
     `release-from-prerelease` collapses the accumulated alpha sections into
     one final-version section — alpha headings never ship in a final
     changelog.
   - `reflex` and `reflex-base` are a lockstep pair and share one checkbox:
     selecting it releases both at the same version. The checkboxes are
     generated from the package list, so adding or removing a package means
     re-running `uv run reflex-release sync`.
2. **Release from changelog** (`release_from_changelog.yml`) runs on every push
   to `main`, `r/pre-*`, and `r/hotfix/**`: any package whose newest changelog
   version has no git tag gets built and queued for publishing. Final
   (non-alpha) versions only publish from `main` or `r/hotfix/**`; alphas only
   from `r/pre-*`/`r/hotfix/**`. `reflex` and `reflex-base` are checked as a
   lockstep pair and `reflex` publishes only after the rest of the batch.
3. **Publish to PyPI** (`publish.yml`, also manually dispatchable with a
   package + version) validates and builds without privileges, then **waits
   for a human to approve the `pypi` environment deployment** — every upload,
   alphas and internal packages included, requires that approval. Only after a
   successful upload does it push the tag and create the GitHub release, so a
   failed or rejected publish leaves no tag behind — fix the problem on top of
   the changelog bump and the next push retries automatically.

**The release workflows are generated.** `dispatch_release.yml`,
`release_from_changelog.yml`, `publish.yml`, `changelog.yml` and
`auto_release_internal.yml` are rendered by
[`reflex-release`](packages/reflex-release/README.md) — the copy bundled in this
repository, run straight from `uv.lock` — out of the `[tool.reflex-release]`
table in the repo-root `pyproject.toml`. Do not edit them by hand: change the
configuration (or the templates under
`packages/reflex-release/src/reflex_release/templates/`) and regenerate with

```bash
uv run reflex-release sync
```

Because the workflows and the tool that renders them live in the same commit,
`reflex-release sync --check` — which every pull request runs — catches both a
workflow edited in place and a template change that was never applied.

**Where changelogs are published:** the docs site renders every `CHANGELOG.md`
in the repo (repo root and `packages/*/`) under
[reflex.dev/docs/changelog/](https://reflex.dev/docs/changelog/). The
`reflex-enterprise` changelog is read from the installed `reflex-enterprise`
distribution at docs build time; it appears once the published wheel ships a
`CHANGELOG.md` and the docs app's lockfile picks up that version.

## ✅ Making a PR

Once you solve a current issue or improvement to Reflex, you can make a PR, and we will review the changes.

Before submitting, a pull request, ensure the following steps are taken and test passing.

In your `reflex` directory run make sure all the unit tests are still passing using the following command.
This will fail if code coverage is below 72%.

```bash
uv run pytest tests/units --cov --no-cov-on-fail --cov-report=
```

Next make sure all the following tests pass. This ensures that every new change has proper type checking.

```bash
uv run ruff check .
uv run pyright reflex tests
```

Finally, run `ruff` to format your code.

```bash
uv run ruff format .
```

Consider installing git pre-commit hooks so Ruff, Pyright, and `make_pyi` will run automatically before each commit.

```bash
uv run pre-commit install
```

That's it you can now submit your PR. Thanks for contributing to Reflex!

## 🤖 AI-Assisted PRs

We welcome AI-assisted contributions, but they must meet the same quality bar as any other PR.

- **A human developer must be responsible for the PR contents and review process.** Bot account PRs are subject to prejudicial closure.
- Ensure pre-commit hooks and unit tests pass before submitting.
- Review the patch locally with an "adversarial" prompt before opening the PR.
- Apply fixes for reasonable feedback from Greptile and/or Copilot review bots.
- Resolve or dismiss irrelevant bot feedback with a brief explanation.
- All added/changed lines MUST have unit or integration test coverage with _real_ assertions. No untested code, no bogus test code.
- PRs with merge conflicts or failing tests will not be reviewed or merged. The maintainers do not spend time on PRs that are not in a ready state. If you need attention on a PR that is not ready, mention the maintainers in a comment.

## 📝 Contributing to the Docs

The Reflex documentation lives in this repo under [`docs/`](https://github.com/reflex-dev/reflex/tree/main/docs). All doc pages are plain Markdown files in [`docs/`](https://github.com/reflex-dev/reflex/tree/main/docs), and the docs site itself (a Reflex app that renders them) lives in [`docs/app/`](https://github.com/reflex-dev/reflex/tree/main/docs/app). If you're fixing a typo, clarifying an explanation, or adding a new page, you can do it all in this repo by editing the relevant `.md` file.

**1. Run the docs site locally:**

```bash
cd docs/app
uv sync
uv run reflex run
```

Then open [http://localhost:3000/docs/](http://localhost:3000/docs/). The dev server picks up changes to the `.md` files in `docs/` so you can preview edits live.

**2. Speed up dev builds with the page whitelist (optional):**

By default the dev server compiles every page, which can be slow. To only compile the pages you're working on, edit `docs/app/reflex_docs/whitelist.py` and add paths to `WHITELISTED_PAGES`:

```python
WHITELISTED_PAGES = [
    "/getting-started/introduction",
    "/components/props",
]
```

Paths must start with `/`, have no trailing slash, and are prefix-matched. An empty list builds everything. Restart the dev server after editing.

## Editing Templates

Changes to the basic `blank` template can be done in the `reflex/.templates/apps/blank` directory.

## Other Notes

For some pull requests when adding new components you will have to generate a pyi file for the new component. This is done by running the following command in the `reflex` directory.

(Please check in with the team before adding a new component to Reflex we are cautious about adding new components to Reflex's core.)

```bash
uv run python -m reflex.utils.pyi_generator
```
