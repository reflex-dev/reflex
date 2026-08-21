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
| `.github/workflows/publish.yml` | called by the two above, or manual | Builds one package — in-repo, or through a [workflow you supply](#custom-builds) — waits for `pypi` environment approval, uploads, then tags and creates the GitHub release. |
| `.github/workflows/changelog.yml` | pull request | Requires a news fragment named after the PR for every package the PR touches, rejects hand-written version headings, and fails if the generated workflows have drifted. |
| `.github/workflows/auto_release_internal.yml` | push to `main` | Only for repos with `internal-packages`: patch-releases them whenever they change. |

### Why the workflows are copied, not referenced

Three constraints rule out `uses: reflex-dev/reflex-release/.github/workflows/...`:

- **Trusted publishing.** PyPI validates the OIDC `job_workflow_ref` claim,
  which names the repository owning the workflow file. A publish workflow
  hosted elsewhere cannot be trusted by your project's publisher.
- **`release_from_changelog` calls `publish.yml`** through a `./` path, and
  `./` resolves against the repository holding the calling file. Hosted here,
  it would call *this* project's publish workflow instead of yours.
- **Triggers belong to the file that declares them.** `on: pull_request`,
  `on: push` and the `workflow_dispatch` inputs must be files in your
  repository regardless of where the job bodies live — so every workflow needs
  a local file anyway.

That leaves the job bodies of two workflows as the only shareable part, which
is not worth a floating cross-repository dependency on the most privileged path
in your release.

Drift is handled instead of avoided: the files are generated, `reflex-release
sync` regenerates them, and the pull-request workflow runs `sync --check`, so a
stale workflow is a red PR rather than a surprise at release time. Upgrading is
a one-line `cli-command` bump plus `sync`.

## Configuration

Everything lives in one table in the repo-root `pyproject.toml`. A
single-package repository usually needs no more than the first two keys.

```toml
[tool.reflex-release]
# How the generated workflows invoke this tool. `init` pins the version it ran
# from; bump it and re-run `sync` to upgrade.
cli-command = "uvx reflex-release@0.1.0"

# Whether the release may be approved by the person who triggered it. True (the
# default) keeps GitHub's own behavior: the environment's reviewer list decides
# who can release, and one of them can carry a release through end to end. Set
# it to false to require a second person, in which case the publish job also
# asserts that the pypi environment has 'Prevent self-review' enabled.
allow-self-review = true

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

# A workflow of your own to run after every published tag. Omit it (or leave it
# empty) to dispatch nothing. See "Post-release workflow".
post-release-workflow = "docs_publish.yml"

# How the Dispatch release form asks which packages to release: one checkbox
# per package ("checkboxes"), a comma-separated field ("text"), or "auto" —
# checkboxes while they fit under GitHub's ten-input workflow_dispatch limit,
# free text beyond it. Default: "auto".
dispatch-package-inputs = "auto"
```

### Custom build workflows

A package whose artifacts cannot come from a plain `uv build` — a matrix of
platform-specific wheels, say — delegates its build to a workflow the
repository owns:

```toml
[[tool.reflex-release.custom-build]]
packages = ["mypkg"]
workflow = "build_wheels.yml"
# Optional: filename globs that must each match at least one built file.
expect-artifacts = ["*.tar.gz", "*-manylinux*_x86_64.whl", "*-macosx_*_arm64.whl"]
```

See [Custom builds](#custom-builds) for the workflow's contract.

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
`title_format` is honored, including when prerelease sections are collapsed —
but the version must lead the heading, because the same parser reads headings
back to decide what to publish. `reflex-release sync` fails on a format it
could not parse back rather than letting releases go undetected.

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
and rename it once the PR exists — CI rejects a fragment the PR adds under any
other name, since a merged orphan renders a changelog entry with no link back to
the change. CI also requires a fragment for every package whose source the PR
touches; the `skip-changelog` label waives both for changes that genuinely are
not user-facing.

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
artifacts do not carry the expected distribution name and version, so a
misconfigured prefix is caught before anything is uploaded rather than shipping
`0.0.0dev0` to PyPI.

If your repository already tags releases some other way, set `tag-prefix` to
match — it applies to both the root package (`<tag-prefix>1.2.3`) and
sub-packages (`<name>-<tag-prefix>1.2.3`), so `tag-prefix = ""` gives you bare
`1.2.3` and `widget-core-1.2.3` tags.

## GitHub setup

Once per repository. **Items 1, 2 and 5 are what make the pipeline safe** — the
rest is ergonomics. See [Security model](#security-model) for why.

1. **`pypi` environment** (Settings → Environments): create it and add
   **required reviewers**. Every upload — alphas and internal packages included
   — waits for one of them to approve it, and `publish.yml` fails closed if it
   starts without reviewers configured. **That list is who can release**, so
   keep it to people you would trust to publish unilaterally; by default one of
   them can trigger and approve the same release (see
   [`allow-self-review`](#configuration)). Optionally restrict deployment
   branches to `main`, `r/pre-*` and `r/hotfix/*`.
2. **PyPI trusted publishing** for each distribution: owner + repository,
   workflow `publish.yml`, **environment `pypi`**. No API token is stored
   anywhere. Naming the environment is not optional bookkeeping — it is what
   binds the upload credential to the reviewer-gated job. Leave it blank and any
   job in `publish.yml` can mint an upload token, approval or not.
3. **Actions settings** → General → enable *Allow GitHub Actions to create and
   approve pull requests*, so release actions can open their PR.
4. **Labels**: create `skip-changelog` and `changelog-version-edit`.
5. **Branch and tag rulesets**: require review on `main`, and **restrict who may
   create or push `r/pre-**`, `r/hotfix/**` and `release/**`** to maintainers
   plus the `github-actions[bot]` app. Those branches publish; a repository that
   skips this lets anyone with write access publish from a branch they create,
   without review. Also protect the tags — `<tag-prefix>*` and
   `<package>-<tag-prefix>*`, so `v*` and `<package>-v*` by default — from
   deletion and force-pushes: a tag is the record that a version was published.
6. **CODEOWNERS on `.github/workflows/` and `pyproject.toml`**, so changes to the
   release path and to `cli-command` need a specific reviewer.

## Security model

The pipeline's guarantee is: **nothing reaches PyPI without a human approving a
specific, already-built artifact.** Everything else exists to make that approval
meaningful. What follows is the reasoning, and the ways an adopting repository
can undermine it.

### Trust boundaries

| Stage | Privileges | Runs |
| --- | --- | --- |
| `prepare` | `contents: read`. No OIDC, no secrets. | Validation only: no build, no repository hooks. |
| `build` / `custom-build-*` | `contents: read`. No OIDC, no secrets. | Your repository's code: the build backend, its hooks, and any [custom build workflow](#custom-builds). |
| `collect` | `contents: read`. No OIDC, no secrets. | Artifact verification and `post_build.sh`. |
| `publish` | `id-token: write` — the only job that can mint a PyPI token. | Nothing from your repository. Downloads the artifact, checks it, runs `uv publish`. |
| `tag-and-release` | `contents: write`, plus `actions: write` when a [post-release workflow](#post-release-workflow) is configured. | `git` and `gh`, after a successful upload. |
| `materialize` (dispatch) | `contents`/`pull-requests`/`actions: write`. | towncrier and `git`/`gh`; writes changelogs, opens the PR. |

The important split is between the build rows and `publish`: **arbitrary
repository code executes only where there is nothing to steal**, and the job
holding the credential runs no repository code at all. A malicious build
backend, custom build workflow or `post_build.sh` can corrupt the artifact — a
reviewer approving it is the control — but it cannot reach the token. Delegating
a build to your own workflow does not move that line: a called workflow inherits
the calling job's `contents: read` and cannot ask for more.

Every checkout uses `persist-credentials: false`, no `${{ }}` expression is
interpolated into a shell script (inputs travel through `env:`), and no workflow
uses `pull_request_target`, so nothing runs privileged against fork code.

### Who can approve, and self-review

The `pypi` environment's reviewer list is the set of people who can release.
By default (`allow-self-review = true`) GitHub lets one of them approve a
release they triggered themselves, so a single reviewer can carry a release end
to end. That is the right posture when the reviewer list is already a small,
trusted group — it is the same trust you place in anyone who can merge to the
main branch — and it keeps a routine release from needing a second person on
call.

What you keep either way: the upload cannot happen without an explicit,
attributed, logged approval by someone on that list; the artifact is built and
inspectable before the approval; the changelog, branch rules and tag ordering
are unchanged.

What you give up: a compromised or malicious account *in the reviewer list* can
publish without anyone else involved. If that is not acceptable — a
widely-scoped reviewer list, or a package where a single bad release is
expensive — set `allow-self-review = false` and enable **Prevent self-review**
on the environment. The publish job then checks the environment on every run and
fails unless it can prove the setting is on. "The API did not report it" (older
GitHub Enterprise Server, or an API change) is indistinguishable from
"self-review is allowed", so it fails there too: strict mode is opt-in, and a
warning nobody reads is not a two-person rule. A deployment that cannot report
the setting has to set `allow-self-review = true` and rely on the reviewer list.

Either way, the reviewer list is the control worth auditing.

### What the approval actually covers

The reviewer approves the `publish` job of a specific run. At that point the
version, the changelog section and the built artifact already exist and are
visible in the run. **Check the version and the package in the run name**, and
that the run was triggered by a merge you recognize. The `collect` job's summary
lists the SHA-256 of every file that will be uploaded, so what you are approving
is named down to the byte before you approve it.

After the build and before the approval, `verify-dist` checks each file's core
metadata against the release: not just the version — which lockstep siblings
share — but the **distribution name**, since every package in a repository
publishes through the same trusted-publishing identity and nothing else would
stop a misconfigured build from uploading one package under another's approval.
For a build spread over a matrix, `expect-artifacts` additionally requires the
set to be complete, so a leg that silently produced nothing stops the release
rather than shipping a version that can never be completed.

The `SHA256SUMS` manifest travels *inside* the same artifact, so it proves the
upload matches the build — it is an integrity check against truncation and
partial downloads, **not** a defense against a compromised build, which could
write both the files and the manifest. The defense there is that the artifact
can only be written by the unprivileged jobs of the same run, and that the run
is triggered by a branch your ruleset controls.

The manifest is attached to the GitHub release as well, so the record of what a
version contains survives the workflow artifact's retention window. It lists the
distribution files by bare filename — exactly the files that went to PyPI — so
`sha256sum -c SHA256SUMS` works in a directory holding the downloaded wheel and
sdist, years later.

For cryptographic provenance rather than a self-attested manifest — a PyPI
[attestation](https://docs.pypi.org/attestations/) tying the artifact to the
workflow that built it — publish with `pypa/gh-action-pypi-publish` in place of
`uv publish`. That is a deliberate omission here, not an oversight: it puts a
third-party action inside the one job holding the OIDC credential, which is the
job this design keeps free of everything but the upload.

### Ways to weaken it

- **No ruleset on the publishing branches.** `r/pre-**` and `r/hotfix/**`
  publish by design, and `r/hotfix/**` publishes *final* versions without a pull
  request. Without a ruleset, "publishing requires review on `main`" is not
  true: anyone with write access can create a hotfix branch and request a
  release. This is the single most common way to deploy this pipeline unsafely.
- **Trusted publisher without the environment.** Covered above; it turns the
  approval into an advisory step.
- **`internal-packages`.** Those release on every push to the main branch with
  no changelog and no fragment — merge access is release access (still behind
  the `pypi` approval). Use it only for packages where that is acceptable.
- **An unpinned `cli-command`.** `init` pins the version it ran from; `--pin
  none` leaves the release path resolving whatever is newest at run time.
- **Weakening `publish.yml` in a pull request.** The generated workflows are
  ordinary files: a merged change can remove the environment or the assertions.
  `sync --check` catches *drift*, but a change that edits the workflow and
  `cli-command` together is self-consistent and passes. CODEOWNERS is the
  control; review those diffs as release-critical.

### Supply chain

The workflows run `uvx reflex-release@<pinned version>`. A published PyPI
version is immutable, so the pinned tool cannot change under you — but its
dependencies (`packaging`, `towncrier`) resolve fresh on every run, and the tool
runs in jobs holding `contents: write`. If you want the release path fully
locked, vendor the tool instead of resolving it:

```toml
# pyproject.toml — a dev dependency, resolved by your lockfile
[tool.reflex-release]
cli-command = "uv run --frozen reflex-release"
```

Note that the pull-request checks (`check-headings`, `changelog-check`,
`sync --check`) execute the tool named by the *pull request's own*
configuration, in a read-only job with no secrets. That is the same exposure as
running a test suite on a contributed branch, but it is why `cli-command` is a
review-sensitive field.

### Assumptions

- **GitHub-hosted runners.** The isolation of the unprivileged build job is the
  runner's. On self-hosted runners, "no secrets in the build job" only holds if
  the runner itself holds none.
- **`gh` and `jq` are on the runner** (they are on GitHub-hosted images).
- **Never store a PyPI API token.** If you must have one, put it in the `pypi`
  environment's secrets, never in repository secrets, where the build job could
  read it.

## Cutting a release

Run **Dispatch release** from the Actions tab. Each package gets its own
checkbox, generated from your configuration; a lockstep group gets a single
checkbox covering all its members, since they only ever release together.
Selecting nothing auto-selects: packages with pending news fragments, or — for
`release-from-prerelease` — packages whose changelog is topped by an alpha.

Because the checkboxes are generated, **adding or removing a package changes
`dispatch_release.yml`** — run `reflex-release sync` and commit it with the new
package. The pull-request drift check catches it if you forget. Past ten
packages (GitHub's `workflow_dispatch` input limit) the form falls back to a
comma-separated text field; see `dispatch-package-inputs`.

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
are the tag and GitHub release created — titled with the tag (`v1.2.3`) for the
root package, and `<package>@<version>` for a sub-package.

Every *Dispatch release* run links what it produced in its job summary and as a
run annotation: the pull request it opened, or the prerelease branch it pushed
and that branch's `release_from_changelog` runs.

To pull new work into a running prerelease train, merge `main` into the
`r/pre-*` branch and dispatch `continued-prerelease` on it.

Hotfixes: branch `r/hotfix/1.2` from the tag, dispatch on that branch, and both
alphas and final versions publish directly from it. A hotfix of an older line is
not marked "Latest" on GitHub.

## Internal packages

Packages listed in `internal-packages` skip the changelog entirely: every push
to `main` that touches them patch-bumps the newest tag and publishes (still
behind the `pypi` approval) — merge access to those paths is release access, so
weigh it against [Ways to weaken it](#ways-to-weaken-it). They need no `news/` directory and are excluded
from the fragment check. Adding or removing one changes
`auto_release_internal.yml`, so re-run `reflex-release sync`.

## Custom builds

Some packages cannot be built by `uv build` on one runner: a project shipping
compiled extensions needs one job per platform, each on its own operating
system. Those packages hand the build to a workflow **your repository owns**,
and the pipeline keeps everything either side of it:

```toml
[[tool.reflex-release.custom-build]]
packages = ["mypkg"]
workflow = "build_wheels.yml"
```

`publish.yml` then calls `.github/workflows/build_wheels.yml` in place of its
own build job for `mypkg`, and nothing else about the release changes — same
changelog detection, same version, same approval gate, same tag-after-upload.
The whole matrix runs **before** the gate: the reviewer approves a set of files
that already exists and has already been checked.

### The contract

Your workflow declares these inputs, and uploads what it builds:

```yaml
name: Build wheels

on:
  workflow_call:
    inputs:
      package:
        description: "Package being built"
        required: true
        type: string
      version:
        description: "Version being released (no v prefix)"
        required: true
        type: string
      tag:
        description: "Tag the checkout with this so the build derives that version"
        required: true
        type: string
      build-dir:
        description: "Repo-relative directory of the package"
        required: true
        type: string
      artifact-prefix:
        description: "Name every uploaded artifact <artifact-prefix><leg>"
        required: true
        type: string

jobs:
  wheels:
    strategy:
      fail-fast: false
      matrix:
        include:
          - { os: ubuntu-latest, target: linux-x86_64 }
          - { os: macos-latest, target: macos-arm64 }
          - { os: windows-latest, target: windows-x64 }
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-tags: true
          fetch-depth: 0
          persist-credentials: false

      # The dynamic-versioning backend reads the version off the newest tag, so
      # tagging the local checkout is what makes the wheels carry `version`.
      - run: git tag "$TAG"
        env:
          TAG: ${{ inputs.tag }}

      - uses: pypa/cibuildwheel@v3
        with:
          package-dir: ${{ inputs.build-dir }}

      - uses: actions/upload-artifact@v7
        with:
          name: ${{ inputs.artifact-prefix }}${{ matrix.target }}
          path: wheelhouse/*.whl
          if-no-files-found: error
          overwrite: true
```

Four rules, all of them load-bearing:

1. **Name every artifact `${{ inputs.artifact-prefix }}<leg>`.** The prefix
   already ends in the separator the publish workflow globs on, so appending
   anything unique per matrix leg is enough. Anything not matching that prefix
   is not collected, and therefore not published.
2. **Upload the distribution files themselves** — wheels and sdists, nothing
   else. Every file that lands in `dist/` is checked and uploaded to PyPI, so a
   build log or a `.zip` of debug symbols fails the release.
3. **Tag the checkout with `tag`** (or otherwise make the build produce
   `version`). If the artifacts carry a different version, `verify-dist` fails
   the release before the gate rather than shipping `0.0.0dev0`.
4. **Let failures fail.** Every job your workflow starts must succeed; a lost
   matrix leg fails the called workflow, which skips the gate and turns the run
   red. Do not paper over a leg with `continue-on-error`.

`fail-fast: false` is a good idea but not required — it only decides whether
the sibling legs are cancelled when one fails, not whether the release stops.

### Requiring the full set

A matrix leg that runs, succeeds and uploads nothing is indistinguishable from
one you never configured — and an incomplete upload cannot be taken back,
because PyPI accepts a version once. Name what the release must contain:

```toml
[[tool.reflex-release.custom-build]]
packages = ["mypkg"]
workflow = "build_wheels.yml"
expect-artifacts = ["*.tar.gz", "*-manylinux*_x86_64.whl", "*-macosx_*_arm64.whl"]
```

Each pattern is matched against the built filenames, and each one must match at
least one file or the release stops before the approval.

### What stays the pipeline's job

Only the build is delegated. Before your workflow runs, `prepare` has validated
the request against the changelog, the branch rules, the lockstep invariant and
the existing tags, and computed the version. After it, `collect` verifies every
file is that package at that version, runs your `post_build.sh` hook, extracts
the release notes and writes the SHA-256 manifest the approver sees.

Two constraints follow from where the build sits:

- **No secrets, no OIDC.** The calling job grants `contents: read`, and a called
  workflow cannot hold more privilege than its caller grants — so a custom build
  is inside the same trust boundary as the built-in one. A build needing a
  credential does not belong here.
- **Not compatible with `pin-exact`.** That rewrites the package's
  `pyproject.toml` in the build checkout, and your workflow builds from a
  checkout this pipeline never touches. Configuring both is rejected at load
  time.

`reflex-release sync` (and so `sync --check` on every pull request) fails if a
configured build workflow is missing, has no `workflow_call` trigger, or does
not declare all five inputs — GitHub rejects a call naming an undeclared input,
so without that check a renamed input would surface as a failed release instead
of a red PR.

## Post-build hook

Create `.github/scripts/publish/post_build.sh` for repository-specific artifact
checks. It runs in the unprivileged `collect` job — after a successful build,
with `PACKAGE`, `VERSION`, `BUILD_DIR` (the package's directory in the checkout)
and `DIST_DIR` (where the built files are) in the environment, no secrets and no
OIDC — and a non-zero exit fails the release before anything is uploaded:

```bash
#!/usr/bin/env bash
set -euo pipefail
[[ "$PACKAGE" == "mypkg" ]] || exit 0
unzip -l "$DIST_DIR"/*.whl | grep -q '\.pyi$' || {
  echo "Error: no .pyi files in the wheel"; exit 1
}
```

It runs for custom builds too, on exactly the files that were collected. The
checkout it runs in has full history and tags, but — unlike the build job — the
release tag is not applied locally, since `collect` builds nothing. Use
`$VERSION` rather than `git describe` to identify the release.

## Post-release workflow

Set `post-release-workflow` to a workflow of your own and `publish.yml`
dispatches it once per published tag, after the upload, the tag and the GitHub
release all exist — the hook for whatever has to follow a release: publishing
docs, refreshing a container image, notifying a downstream repository.

It runs **on the tag**, so it sees exactly the tree that was published, and it
is handed the three facts about the release:

```yaml
# .github/workflows/docs_publish.yml
on:
  workflow_dispatch:
    inputs:
      tag:
        description: "The published tag"
        required: true
        type: string
      package:
        description: "The published package"
        required: true
        type: string
      version:
        description: "The published version"
        required: true
        type: string
```

All three inputs are required: GitHub rejects a dispatch that passes inputs the
workflow does not declare, and a dispatch with *empty* ones is accepted, so
`post-release` refuses to run without all three rather than telling your
workflow nothing.

The workflow must exist on the default branch (GitHub's rule for
`workflow_dispatch`) and be one of yours. `sync` rejects any name a generated
workflow answers to — its file name *or* its display name, since `gh workflow
run` resolves either, and including the ones your repository does not currently
get, like `auto_release_internal.yml`.

Adding or removing the setting changes `publish.yml` (the dispatch step) and the
`actions: write` grant it needs in `publish.yml`, `release_from_changelog.yml`
and `auto_release_internal.yml`, so re-run `reflex-release sync`.

The dispatch is the last thing a release does, so a failure there never leaves a
half-published version — but it does fail the run, loudly, naming the tag whose
follow-up did not start.

## Keeping the workflows current

Bump `cli-command` in `pyproject.toml`, run `reflex-release sync`, commit the
result. The generated `changelog.yml` already runs `sync --check` on every pull
request, so a workflow that no longer matches your configuration — or a package
added without re-syncing — fails CI there rather than at release time.

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
| `verify-dist` | Check the built artifacts are this package at the target version. |
| `check-dev-pins` | Reject `*.dev` dependency pins in published metadata. |
| `extract-notes` | Write a version's changelog section for the release body. |
| `push-tag` / `create-release` | Tag and publish the GitHub release. |
| `post-release` | Dispatch the configured post-release workflow for a tag. |
| `check-headings` | Reject hand-written changelog version headings (PR CI). |
| `changelog-check` | Require news fragments for changed packages, named after the PR (PR CI). |
| `detect-internal` | List internal packages touched by a push. |

## Adopting it in a repository that already has releases

- **An existing hand-written `CHANGELOG.md`**: keep it. Only the *newest*
  version heading matters, and existing versions are already tagged, so nothing
  is detected as due. Headings must be parseable as `## v1.2.3 (date)` or
  `## 1.2.3`; anything else is ignored, which is safe but means those versions
  cannot be re-released.
- **Existing tags**: they are the fallback baseline for packages without a
  changelog, and they are what makes an already-published version a no-op. Make
  sure they match `tag-prefix` — `<tag-prefix>1.2.3` for the root package and
  `<package>-<tag-prefix>1.2.3` for a sub-package.
- **Publishing with an API token today**: switch to trusted publishing before
  the first run. `publish.yml` requests no secret other than `GITHUB_TOKEN`.
- **First release of a brand-new package**: it needs no `CHANGELOG.md` up
  front — the first *Dispatch release* creates one. With no tags and no
  changelog, `release-minor` produces `0.1.0`. Publishing it still needs an
  explicit version: only `internal-packages` may publish without a changelog.

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
