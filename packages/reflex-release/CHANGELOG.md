## v0.1.0a4 (2026-08-26)

### Bug Fixes

- A release using a `[[tool.reflex-release.custom-build]]` entry no longer publishes nothing while reporting success. Exactly one of the built-in `build` job and a custom-build job runs for any given package, so the other is always skipped — and GitHub evaluates the implicit `success()` a job gets when its `if` names no status function over the whole transitive dependency closure, not just the direct `needs`. The skipped build therefore reached `publish` straight through the `collect` written to absorb it, and `tag-and-release` behind it: every build succeeded, the artifacts were verified and checksummed, and then the upload silently never happened. Both jobs now carry an explicit `needs.<job>.result == 'success'` guard. `release_from_changelog.yml`'s `report` job, the canonical failure signal for a partial release, was blind to the same shape because it accepted any skipped leg; it now accepts a skipped leg only when detection found nothing for that leg to publish, so a release that publishes nothing — or holds a lockstep package back — is red.


## v0.1.0a3 (2026-08-25)

### Features

- Materializing a changelog now names leftover orphan news fragments (`+something.feature.md`) after the pull request whose commit added them, so their entries get the usual `#`-link instead of shipping unlinked.

### Miscellaneous

- Every `run:` step in the generated release workflows now declares `shell: bash`, so a `defaults.run.shell` added to one of those files — or a runner whose default shell is not bash — cannot change how a release-critical script is interpreted, or silently drop the `-e`/`-o pipefail` a failing step relies on. ([#6926](https://github.com/reflex-dev/reflex/issues/6926))
- Property docstrings are now noun phrases rather than "Get the ..." / "Return the ..." (ruff 0.16's new `D421`).


## v0.1.0a2 (2026-08-17)

### Features

- `reflex-release` can now delegate a package's build to a workflow the consuming repository owns, for packages whose artifacts cannot come from a single `uv build` — a matrix of platform-specific wheels, say. A `[[tool.reflex-release.custom-build]]` entry names the packages and the workflow file, and the generated `publish.yml` calls it in place of its own build job, passing the package, version, tag, build directory and the artifact-name prefix to upload under. Everything either side of the build is unchanged: the whole matrix runs before the approval gate, in the same unprivileged trust boundary (`contents: read`, no secrets, no OIDC — a called workflow cannot hold more than its caller grants), and every file it produces is verified against the release, hashed into the manifest the approver sees, and published only after that approval. A failed leg fails the release rather than uploading a partial set, and `expect-artifacts` can additionally require the built set to match a list of filename patterns so a leg that silently produced nothing is caught too. `reflex-release sync` fails when a configured build workflow is missing or declares no `workflow_call` trigger, so a renamed file is a red pull request instead of a failed release. ([#6891](https://github.com/reflex-dev/reflex/issues/6891))
- Add `post-release-workflow` to `[tool.reflex-release]`: the named workflow is dispatched once per published tag, on the tag itself, after the upload, the tag and the GitHub release exist — with `tag`, `package` and `version` as `workflow_dispatch` inputs. The dispatch step and the `actions: write` grant it needs are only scaffolded into `publish.yml` (and the workflows that call it) when the setting is present, so a repository that runs nothing after a release keeps the narrower permissions.


## v0.1.0a1 (2026-08-13)

### Features

- New package: `reflex-release` extracts Reflex's changelog-driven release pipeline — the towncrier news-fragment workflow, the changelog-as-source-of-truth publish detection, and the human-gated PyPI upload — into a reusable tool other repositories can adopt with `uvx reflex-release init`. It scaffolds the GitHub Actions workflows into the consuming repository (required for PyPI trusted publishing, which validates the workflow's own repository) and keeps them in step with `reflex-release sync --check`. Repository shape lives in a `[tool.reflex-release]` table: single package or monorepo, branch policy, lockstep groups that release together at one version, and internal packages that release without a changelog. Every upload waits on an approval from the `pypi` environment's required reviewers, and the artifacts it covers are named by SHA-256 in the run summary and in a manifest attached to the GitHub release. See `packages/reflex-release/README.md` for setup, configuration and the security model. ([#6868](https://github.com/reflex-dev/reflex/issues/6868))
