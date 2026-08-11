# reflex-release

Changelog-driven release automation for Python repositories — one package or a
whole monorepo. It is the release pipeline Reflex uses, packaged so other
repositories can standardize on it.

**The `CHANGELOG.md` files are the source of truth for publishing.** A package
is published exactly when the newest version heading in its changelog has no
matching git tag. Tags are created only *after* a successful upload, so a failed
build or a rejected approval never leaves a tag or a GitHub release behind — you
fix the problem on top of the changelog bump and the next push retries.

Every upload is gated on a human: the job that holds the PyPI credential targets
a `pypi` GitHub environment whose required reviewers must approve it, and the
workflow refuses to run if those reviewers are not configured.

```
news fragments ──▶ Dispatch release ──▶ CHANGELOG.md bump ──▶ push to main
                   (towncrier)          (PR, or prerelease branch)     │
                                                                       ▼
                          GitHub release ◀── tag ◀── upload ◀── build + human approval
```

## Quick start

```bash
cd your-repo
uvx reflex-release init
```

That adds the `[tool.reflex-release]` and `[tool.towncrier]` tables to your
`pyproject.toml` (leaving either alone if it already exists), creates the
`news/` directories, writes four GitHub Actions workflows, and prints the
repository settings you still have to configure by hand.

Review the diff, work through the [GitHub setup](#github-setup) checklist,
give every package a [tag-derived version](#tag-derived-versions), and commit.

## What you get

| File | Trigger | What it does |
| --- | --- | --- |
| `.github/workflows/dispatch_release.yml` | manual | Materializes news fragments into `CHANGELOG.md` at the next version. Final releases land through a pull request; prereleases go straight to an `r/pre-*` branch. |
| `.github/workflows/release_from_changelog.yml` | push to `main`, `r/pre-**`, `r/hotfix/**` | Publishes any changelog version that has no git tag. |
| `.github/workflows/publish.yml` | called by the two above, or manual | Builds one package, waits for `pypi` environment approval, uploads, then tags and creates the GitHub release. |
| `.github/workflows/changelog.yml` | pull request | Requires a news fragment for every package the PR touches, and rejects hand-written version headings. |
| `.github/workflows/auto_release_internal.yml` | push to `main` | Only for repos with `internal-packages`: patch-releases them whenever they change. |

The workflows are copied into your repository rather than referenced across
repositories. That is deliberate: PyPI trusted publishing validates the OIDC
`job_workflow_ref` claim, which names the repository owning the workflow file,
so a publish workflow living elsewhere cannot be trusted by your project's
publisher. `reflex-release sync` regenerates them and `sync --check` fails CI
when they drift, so upgrading is still a one-line version bump.

## Configuration

Everything lives in one table in the repo-root `pyproject.toml`. A
single-package repository usually needs no more than the first two keys.

```toml
[tool.reflex-release]
# How the generated workflows invoke this tool. `init` pins the version it ran
# from; bump it and re-run `sync` to upgrade.
cli-command = "uvx reflex-release@0.1.0"

# The package built from the repository root. Omit it when the root is not a
# package (a pure monorepo of sub-packages).
root-package = "mypkg"

# Directories whose changes require a news fragment for the root package.
# Defaults to ["src"] for a src layout, else the directory named after the
# package (mypkg -> mypkg/, my-pkg -> my_pkg/), else nothing.
root-source-dirs = ["src"]

# Where sub-packages live; each directory with a pyproject.toml is a package.
# Ignored when the directory does not exist. Default: "packages".
packages-dir = "packages"

# Sub-package subdirectories that hold publishable source. A sub-package with
# none of them counts its whole directory (minus news/ and CHANGELOG.md).
package-source-subdirs = ["src"]

# Changelog dates and prerelease branch names are stamped in this timezone, so
# an evening release is not dated tomorrow by a UTC runner. Default: "UTC".
release-timezone = "America/Los_Angeles"

# Branch policy. Final versions publish only from main-branch or a hotfix
# branch; prereleases only from a prerelease or hotfix branch.
main-branch = "main"
prerelease-branch-prefix = "r/pre-"
hotfix-branch-prefix = "r/hotfix/"
release-branch-prefix = "release/"

# Version prefix of the git tags: the root package is tagged
# "<tag-prefix><version>" (v1.2.3), a sub-package
# "<package>-<tag-prefix><version>" (widget-core-v1.2.3).
tag-prefix = "v"

# The package whose final releases are marked "Latest" on GitHub.
# Default: the root package. Set to nothing to never mark one.
latest-release-package = "mypkg"

# Packages released by patch-bumping their newest tag on every push that
# touches them, with no changelog and no news fragments.
internal-packages = []

# Packages excluded from the pull-request news-fragment requirement.
changelog-exempt-packages = []
```

Package names are **directory names**: `mypkg` for the root package (whatever
you called it) and the directory name under `packages/` for the rest.

### Lockstep packages

Packages that must always release together at the same version — typically
because one pins the other exactly — form a lockstep group:

```toml
[[tool.reflex-release.lockstep]]
members = ["mypkg", "mypkg-base"]
# Members that publish only after every other member is uploaded and tagged.
publish-last = ["mypkg"]
# Rewrite each publish-last member's requirement on its siblings to
# "== <version>" before building.
pin-exact = true
```

This gives you, for free:

- selecting one member in *Dispatch release* selects the whole group, and all
  members are planned at one version (the highest baseline among them);
- `release_from_changelog` publishes `publish-last` members only after the rest
  of the batch succeeded — never shipping a wheel whose exact pin does not
  exist on PyPI yet;
- a member with nothing to report still gets its section, holding towncrier's
  "No significant changes." placeholder — nobody hand-writes a changelog entry
  just to satisfy the invariant, and a member does not even need a `news/`
  directory;
- detection **fails closed** if one member's changelog is bumped without the
  other's (re-dispatching a release fixes it, materializing the whole group).

`pin-exact` rewrites the requirement in the publishing package's
`pyproject.toml` at build time only; it is never committed.

## Adding towncrier

`init` writes this for you if `[tool.towncrier]` is absent. If you configure it
by hand, the important part is that `package`/`name` stay empty: one shared
configuration serves every package, because each invocation passes
`--dir <package path>` to select one package's `news/` directory
([towncrier monorepo docs](https://towncrier.readthedocs.io/en/stable/monorepo.html)).

```toml
[tool.towncrier]
package = ""
name = ""
directory = "news"
filename = "CHANGELOG.md"
title_format = "## {version} ({project_date})"
issue_format = "[#{issue}](https://github.com/OWNER/REPO/issues/{issue})"
start_string = "<!-- towncrier release notes start -->\n"

[[tool.towncrier.type]]
directory = "breaking"
name = "Breaking Changes"
showcontent = true

# ... deprecation, feature, bugfix, performance, docs, misc
```

Version headings are written as `## v1.2.3 (2026-01-01)`. A custom
`title_format` is honored, including when prerelease sections are collapsed.

Then create one `news/` directory per package:

```
news/                          # fragments for the root package
packages/widget-core/news/     # fragments for packages/widget-core
```

A fragment is a markdown file named `<pr-number>.<type>.md` holding one or two
sentences written for someone reading release notes:

```bash
uvx reflex-release create 1234.feature.md                        # root package
uvx reflex-release create --package widget-core 1234.bugfix.md   # sub-package
```

Before you know the PR number, use an orphan fragment (`+something.feature.md`)
and rename it later. CI requires a fragment for every package whose source the
PR touches; the `skip-changelog` label waives that for changes that genuinely
are not user-facing.

## Adding sub-packages

If the repository has no `packages/` directory, everything above still works —
`packages-dir` is ignored when the directory is missing and the root package is
the only one. To grow into a monorepo:

1. Create `packages/<name>/pyproject.toml` with its own `[project]` table.
   `<name>` is the package's identifier everywhere in this tool.
2. Add `packages/<name>/news/`.
3. Give it a [tag-derived version](#tag-derived-versions) with
   `pattern-prefix = "<name>-"`.
4. If it is a uv workspace member, add it under `[tool.uv.workspace] members`
   and `[tool.uv.sources]` as usual.

Nothing else is generated per package: the *Dispatch release* workflow takes a
free-form package list and auto-selects packages with pending fragments, so
adding a package needs no workflow change.

## Tag-derived versions

The publish workflow tags the checkout locally and then builds, so each
package's build backend must derive its version from git tags. With
[uv-dynamic-versioning](https://github.com/ninoseki/uv-dynamic-versioning):

```toml
# repo root — tags are v1.2.3
[build-system]
requires = ["hatchling", "uv-dynamic-versioning"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "uv-dynamic-versioning"

[tool.uv-dynamic-versioning]
fallback-version = "0.0.0dev0"
```

```toml
# packages/widget-core — tags are widget-core-v1.2.3
[tool.uv-dynamic-versioning]
pattern-prefix = "widget-core-"
fallback-version = "0.0.0dev0"
```

Any backend works as long as the tag prefixes match; `hatch-vcs` and
`setuptools-scm` need their `tag_regex`/`git_describe_command` pointed at the
same prefixes. The `verify-dist` step fails the build when the produced
artifacts do not carry the expected version, so a misconfigured prefix is caught
before anything is uploaded rather than shipping `0.0.0dev0` to PyPI.

If your repository already tags releases some other way, set `tag-prefix` to
match — it applies to both the root package (`<tag-prefix>1.2.3`) and
sub-packages (`<name>-<tag-prefix>1.2.3`), so `tag-prefix = ""` gives you bare
`1.2.3` and `widget-core-1.2.3` tags.

## GitHub setup

Once per repository:

1. **`pypi` environment** (Settings → Environments): create it and add
   **required reviewers**. Every upload — alphas and internal packages included
   — waits for that approval, and `publish.yml` fails closed if it starts
   without reviewers configured. If you restrict deployment branches, allow
   `main`, `r/pre-*` and `r/hotfix/*`.
2. **PyPI trusted publishing** for each distribution: owner + repository,
   workflow `publish.yml`, environment `pypi`. No API token is stored anywhere.
3. **Actions settings** → General → enable *Allow GitHub Actions to create and
   approve pull requests*, so release actions can open their PR.
4. **Labels**: create `skip-changelog` and `changelog-version-edit`.
5. **Branch protection / rulesets**: require review on `main`; restrict who can
   create or push `r/pre-**`, `r/hotfix/**` and `release/**` to maintainers plus
   the `github-actions[bot]` app (the workflow pushes as that app via
   `GITHUB_TOKEN`).

## Cutting a release

Run **Dispatch release** from the Actions tab. Leave *packages* empty to
auto-select: packages with pending news fragments, or — for
`release-from-prerelease` — packages whose changelog is topped by an alpha.

| Action | Result |
| --- | --- |
| `new-prerelease-patch` / `-minor` / `-major` | Starts an alpha train: `1.2.4a1`, `1.3.0a1`, `2.0.0a1`. Pushed to `r/pre-<date>`; builds immediately, uploads after approval. |
| `continued-prerelease` | Next alpha (`a2`, `a3`, …). Must be dispatched **on** the train's `r/pre-*` branch. |
| `release-from-prerelease` | Turns the train into its final version and collapses every alpha section into one — alpha headings never ship in a final changelog. Opens a PR. |
| `release-patch` / `-minor` / `-major` | Final version straight from `main`. Opens a PR. |
| `release-post` | `1.2.3.post1`, for packaging-only fixes. Opens a PR. |

Release actions open a pull request; **merging it is what publishes.** The push
to `main` triggers `release_from_changelog`, which builds every untagged
changelog version and waits for the `pypi` approval before uploading. Only then
are the tag and GitHub release created.

To pull new work into a running prerelease train, merge `main` into the
`r/pre-*` branch and dispatch `continued-prerelease` on it.

Hotfixes: branch `r/hotfix/1.2` from the tag, dispatch on that branch, and both
alphas and final versions publish directly from it. A hotfix of an older line is
not marked "Latest" on GitHub.

## Internal packages

Packages listed in `internal-packages` skip the changelog entirely: every push
to `main` that touches them patch-bumps the newest tag and publishes (still
behind the `pypi` approval). They need no `news/` directory and are excluded
from the fragment check. Adding or removing one changes
`auto_release_internal.yml`, so re-run `reflex-release sync`.

## Post-build hook

Create `.github/scripts/publish/post_build.sh` for repository-specific artifact
checks. It runs after a successful build with `PACKAGE`, `VERSION` and
`BUILD_DIR` in the environment, and a non-zero exit fails the release before
anything is uploaded:

```bash
#!/usr/bin/env bash
set -euo pipefail
[[ "$PACKAGE" == "mypkg" ]] || exit 0
unzip -l "$BUILD_DIR"/dist/*.whl | grep -q '\.pyi$' || {
  echo "Error: no .pyi files in the wheel"; exit 1
}
```

## Keeping the workflows current

Bump `cli-command`, run `reflex-release sync`, commit. To catch drift, add this
to an existing CI job:

```yaml
- run: uvx reflex-release@0.1.0 sync --check
```

`sync` refuses to overwrite a workflow file it did not generate unless you pass
`--force`, so a hand-written `publish.yml` is never clobbered silently.

## Commands

Workflow steps pass their inputs as environment variables; every option also has
a flag for running the same command by hand.

| Command | Purpose |
| --- | --- |
| `init` | Configure the repository and write the workflows. |
| `sync [--check]` | Regenerate the workflows, or fail on drift. |
| `create [--package P] NAME` | Create a news fragment. |
| `packages` | List releasable packages. |
| `plan` | Compute the next version of each selected package. |
| `materialize` | Run towncrier and (for `release-from-prerelease`) collapse alphas. |
| `open-release-pr` / `push-prerelease` | Commit the changelogs and deliver them. |
| `detect` | List packages whose newest changelog version has no tag. |
| `prepare-publish` | Validate a package/version and emit build metadata. |
| `pin-lockstep` | Pin lockstep siblings exactly before building. |
| `verify-dist` | Check the built artifacts carry the target version. |
| `check-dev-pins` | Reject `*.dev` dependency pins in published metadata. |
| `extract-notes` | Write a version's changelog section for the release body. |
| `push-tag` / `create-release` | Tag and publish the GitHub release. |
| `check-headings` | Reject hand-written changelog version headings (PR CI). |
| `changelog-check` | Require news fragments for changed packages (PR CI). |
| `detect-internal` | List internal packages touched by a push. |

## Adopting it in a repository that already has releases

- **An existing hand-written `CHANGELOG.md`**: keep it. Only the *newest*
  version heading matters, and existing versions are already tagged, so nothing
  is detected as due. Headings must be parseable as `## v1.2.3 (date)` or
  `## 1.2.3`; anything else is ignored, which is safe but means those versions
  cannot be re-released.
- **Existing tags**: they are the fallback baseline for packages without a
  changelog, and they are what makes an already-published version a no-op. Make
  sure the prefixes match `root-tag-prefix` / `<package>-v`.
- **Publishing with an API token today**: switch to trusted publishing before
  the first run. `publish.yml` requests no secret other than `GITHUB_TOKEN`.
- **First release of a brand-new package**: it needs no `CHANGELOG.md` up
  front — the first *Dispatch release* creates one. With no tags and no
  changelog, `release-minor` produces `0.1.0`.

## Why the pipeline is shaped this way

- **Changelog as the trigger.** The artifact humans review (the changelog bump)
  is the same artifact that authorizes the release, so a version cannot ship
  without its release notes, and release notes cannot be written for a version
  that never ships.
- **Tags after upload.** A tag means "this is on PyPI". Retrying is a normal
  push, never a tag deletion.
- **Approval holds the only credential.** The gated job runs no repository code
  and resolves no dependencies — it verifies a checksum manifest and uploads the
  artifact that was built and validated before the approval.
- **Detection fails closed.** A broken lockstep pair, a version the branch may
  not publish, or a `*.dev` pin stops the batch rather than shipping something
  uninstallable.

## License

Apache-2.0.
