"""The ``[tool.reflex-release]`` configuration of a consumer repository.

Everything the release pipeline needs to know about a repository's shape — where
its packages live, which branches may publish what, which packages must release
in lockstep — is declared in one table in the repo-root ``pyproject.toml``. A
single-package repository needs no more than ``root-package``.
"""

from __future__ import annotations

import dataclasses
import re
import sys
from pathlib import Path

from packaging.version import Version

from .actions import fail

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pyright: ignore[reportMissingImports]

TOOL_TABLE = "reflex-release"

#: The setting naming the workflow to dispatch after each published tag.
POST_RELEASE_WORKFLOW_KEY = "post-release-workflow"

#: The uv release the generated workflows install. It is written verbatim into
#: every workflow, so bumping it here surfaces in each consumer repository as
#: workflow drift the next ``sync --check`` reports — which is the point: the
#: tool and the release path it generates move together. A repository that wants
#: its own cadence sets ``uv-version``.
DEFAULT_UV_VERSION = "0.12.5"

#: The Python the generated workflows run uv with, pinned for the same reason. A
#: repository whose packages cannot build on it sets ``python-version``.
DEFAULT_PYTHON_VERSION = "3.14.7"

#: What ``uv-version`` and ``python-version`` may contain. Both are interpolated
#: into a double-quoted YAML scalar in the generated workflows, so the allowed
#: characters are those of a version or a specifier and nothing that could end
#: the scalar or open a ``${{ }}`` expression.
_VERSION_PIN_RE = re.compile(r"[A-Za-z0-9<>=~!^][A-Za-z0-9._+*,<>=~!^-]*")

#: The ``workflow_dispatch`` inputs that workflow is dispatched with, in the
#: order they are passed. This is the contract a consumer repository writes its
#: post-release workflow against, so the payload built by ``post-release``, the
#: step scaffolded into ``publish.yml`` and the documentation all name it from
#: here rather than repeating the list.
POST_RELEASE_INPUTS = ("tag", "package", "version")

_KNOWN_KEYS = frozenset({
    "allow-self-review",
    "cli-command",
    "custom-build",
    "dispatch-package-inputs",
    "root-package",
    "root-source-dirs",
    "packages-dir",
    "python-version",
    "package-source-subdirs",
    "release-timezone",
    "uv-version",
    "main-branch",
    "never-publish-packages",
    "prerelease-branch-prefix",
    "hotfix-branch-prefix",
    "release-branch-prefix",
    "tag-prefix",
    "latest-release-package",
    "internal-packages",
    "changelog-exempt-packages",
    POST_RELEASE_WORKFLOW_KEY,
    "lockstep",
})

_KNOWN_LOCKSTEP_KEYS = frozenset({"members", "publish-last", "pin-exact"})

_KNOWN_CUSTOM_BUILD_KEYS = frozenset({"packages", "workflow", "expect-artifacts"})

_LOCKSTEP_LABEL = f"[[tool.{TOOL_TABLE}.lockstep]]"
CUSTOM_BUILD_LABEL = f"[[tool.{TOOL_TABLE}.custom-build]]"

#: A custom build workflow's filename, restricted to what is safe to write as a
#: bare YAML scalar in the generated ``uses:``.
_WORKFLOW_FILENAME_RE = re.compile(r"[A-Za-z0-9_.-]+\.ya?ml")


@dataclasses.dataclass(frozen=True)
class CustomBuild:
    """A repository-supplied workflow that builds some packages' artifacts.

    Packages whose artifacts cannot come from a plain ``uv build`` — a matrix of
    platform-specific wheels, say — delegate the build to a workflow the
    repository owns. It runs unprivileged, before the approval gate, like the
    built-in build job; everything it uploads is verified against the release
    before a reviewer ever sees it.

    Attributes:
        packages: The packages built by this workflow.
        workflow: The workflow's filename under ``.github/workflows``.
        expect_artifacts: Filename glob patterns that must each match at least
            one built file, so a matrix leg that quietly produced nothing fails
            the release instead of publishing an incomplete set.
    """

    packages: tuple[str, ...]
    workflow: str
    expect_artifacts: tuple[str, ...] = ()

    @property
    def job_id(self) -> str:
        """The publish-workflow job id that calls this workflow.

        Returns:
            The workflow filename reduced to the characters GitHub allows in a
            job id, behind a fixed prefix.
        """
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", self.workflow.rpartition(".")[0])
        return f"custom-build-{stem}"


@dataclasses.dataclass(frozen=True)
class LockstepGroup:
    """A set of packages that must always release together at the same version.

    Attributes:
        members: The package names in the group (at least two).
        publish_last: Members that publish only after every other member of the
            group has been uploaded and tagged — used when they depend on their
            siblings at an exact version.
        pin_exact: Whether each ``publish_last`` member's requirement on its
            siblings is rewritten to ``== <version>`` before building.
    """

    members: tuple[str, ...]
    publish_last: tuple[str, ...] = ()
    pin_exact: bool = False


@dataclasses.dataclass(frozen=True)
class Config:
    """Resolved release configuration for one repository.

    Attributes:
        root: The repository root (the directory holding ``pyproject.toml``).
        allow_self_review: Whether the release may be approved by the person who
            triggered it. True keeps GitHub's own behavior; False makes the
            publish job assert that the ``pypi`` environment prevents
            self-review, so every upload needs a second person.
        cli_command: How the scaffolded workflows invoke this tool. ``init``
            writes it pinned to the version that generated them.
        dispatch_package_inputs: How the Dispatch release workflow asks which
            packages to release — ``checkboxes``, a free-text ``text`` field, or
            ``auto`` (checkboxes while they fit under the GitHub input limit).
        news_directory: The fragment directory inside each package, taken from
            towncrier's ``directory`` setting.
        changelog_filename: The changelog file inside each package, taken from
            towncrier's ``filename`` setting.
        root_package: Name of the package built from the repo root, or None when
            the root is not itself a package.
        root_source_dirs: Repo-relative directories whose changes require a news
            fragment for the root package.
        packages_dir: Repo-relative directory holding sub-packages, or None.
        package_source_subdirs: Sub-package subdirectories that hold source; a
            package without any of them counts its whole directory as source.
        release_timezone: IANA timezone for changelog dates and branch names.
        main_branch: The branch final versions publish from.
        prerelease_branch_prefix: Prefix of the branches prereleases publish
            from and are pushed to.
        hotfix_branch_prefix: Prefix of the branches that may publish both final
            versions and prereleases.
        release_branch_prefix: Prefix of the branches release pull requests are
            opened from.
        tag_prefix: Version prefix of the git tags. The root package is tagged
            ``<tag-prefix><version>``, a sub-package ``<package>-<tag-prefix><version>``.
        latest_release_package: The package whose final releases are marked
            "Latest" on GitHub, or None to never mark one.
        internal_packages: Packages released by patch-bumping their newest tag
            instead of from a changelog.
        changelog_exempt_packages: Packages excluded from the pull-request news
            fragment requirement.
        post_release_workflow: A workflow dispatched once per published tag,
            after the tag and the GitHub release exist, or None to dispatch
            nothing.
        lockstep: The lockstep groups.
        custom_build: The repository-supplied build workflows.
        uv_version: The uv release the generated workflows install, pinned
            verbatim; empty installs whatever setup-uv defaults to.
        python_version: The Python those workflows run uv with, pinned the same
            way; empty leaves the choice to uv.
        never_publish_packages: Packages this repository builds but never
            releases. They are excluded from every release path rather than
            merely exempt from the changelog.
    """

    root: Path
    allow_self_review: bool = True
    cli_command: str = "uvx reflex-release"
    dispatch_package_inputs: str = "auto"
    news_directory: str = "news"
    changelog_filename: str = "CHANGELOG.md"
    root_package: str | None = None
    root_source_dirs: tuple[str, ...] = ()
    packages_dir: str | None = "packages"
    package_source_subdirs: tuple[str, ...] = ("src",)
    release_timezone: str = "UTC"
    main_branch: str = "main"
    prerelease_branch_prefix: str = "r/pre-"
    hotfix_branch_prefix: str = "r/hotfix/"
    release_branch_prefix: str = "release/"
    tag_prefix: str = "v"
    latest_release_package: str | None = None
    internal_packages: tuple[str, ...] = ()
    changelog_exempt_packages: tuple[str, ...] = ()
    post_release_workflow: str | None = None
    lockstep: tuple[LockstepGroup, ...] = ()
    custom_build: tuple[CustomBuild, ...] = ()
    # Appended rather than grouped with the settings they belong beside:
    # these are positional parameters of a constructor other code calls, so
    # a new field goes at the end.
    uv_version: str = DEFAULT_UV_VERSION
    python_version: str = DEFAULT_PYTHON_VERSION
    never_publish_packages: tuple[str, ...] = ()

    def package_dir(self, package: str) -> str:
        """Return the repo-relative directory of a package.

        Args:
            package: The package name.

        Returns:
            ``"."`` for the root package, ``<packages-dir>/<package>``
            otherwise.
        """
        if package == self.root_package:
            return "."
        return f"{self.packages_dir}/{package}"

    def path_prefix(self, package: str) -> str:
        """Return the repo-relative path prefix of everything inside a package.

        Args:
            package: The package name.

        Returns:
            ``""`` for the root package — whose files are not nested under a
            directory of their own — and ``<packages-dir>/<package>/``
            otherwise.
        """
        directory = self.package_dir(package)
        return "" if directory == "." else f"{directory}/"

    def package_path(self, package: str) -> Path:
        """Return the absolute directory of a package.

        Args:
            package: The package name.

        Returns:
            The package directory.
        """
        return (
            self.root
            if package == self.root_package
            else self.root / self.package_dir(package)
        )

    def distribution_name(self, package: str) -> str:
        """Return the name a package is published under.

        Args:
            package: The package name (its directory).

        Returns:
            The ``[project] name`` from the package's ``pyproject.toml``, which
            is what appears on PyPI and in built artifact metadata.
        """
        pyproject = self.package_path(package) / "pyproject.toml"
        name = load_pyproject(pyproject).get("project", {}).get("name")
        if not isinstance(name, str) or not name:
            fail(f"{pyproject} declares no [project] name")
        return name

    def changelog_path(self, package: str) -> Path:
        """Return a package's changelog path (which may not exist).

        Args:
            package: The package name.

        Returns:
            The changelog path.
        """
        return self.package_path(package) / self.changelog_filename

    def news_dir(self, package: str) -> Path:
        """Return a package's news fragment directory (which may not exist).

        Args:
            package: The package name.

        Returns:
            The fragment directory of the package.
        """
        return self.package_path(package) / self.news_directory

    def package_tag_prefix(self, package: str) -> str:
        """Return the git tag prefix for a package.

        Args:
            package: The package name.

        Returns:
            The configured prefix for the root package (tags like ``v1.2.3``),
            that prefix behind the package name otherwise (``mypkg-v1.2.3``).
        """
        if package == self.root_package:
            return self.tag_prefix
        return f"{package}-{self.tag_prefix}"

    def tag_for(self, package: str, version: str) -> str:
        """Return the git tag name for a package version.

        Args:
            package: The package name.
            version: The version string (no ``v`` prefix).

        Returns:
            The tag name.
        """
        return f"{self.package_tag_prefix(package)}{version}"

    def sub_packages(self) -> list[str]:
        """List the sub-packages of the repository, alphabetically.

        Returns:
            The directory names under ``packages-dir`` that hold a
            ``pyproject.toml``. Empty when the repo has no sub-packages.
        """
        if self.packages_dir is None:
            return []
        return sorted(
            path.parent.name
            for path in (self.root / self.packages_dir).glob("*/pyproject.toml")
        )

    def all_packages(self) -> list[str]:
        """List every package in the repository.

        Returns:
            The root package first (when there is one), then the sub-packages.
        """
        packages = [self.root_package] if self.root_package is not None else []
        return [*packages, *self.sub_packages()]

    def require_known(self, package: str) -> None:
        """Fail unless a package exists in the repository.

        Args:
            package: The package name to validate.
        """
        if package not in self.all_packages():
            fail(
                f"unknown package {package!r}; this repository builds: "
                f"{', '.join(self.all_packages()) or '<none>'}"
            )

    def is_internal(self, package: str) -> bool:
        """Return whether a package releases without a changelog.

        Args:
            package: The package name.

        Returns:
            True when the package is listed in ``internal-packages``.
        """
        return package in self.internal_packages

    def is_never_published(self, package: str) -> bool:
        """Return whether a package is excluded from every release path.

        Args:
            package: The package name.

        Returns:
            True when the package is listed in ``never-publish-packages``: it
            gets no release selection, is not detected from a changelog, and
            publishing it is refused.
        """
        return package in self.never_publish_packages

    def requires_fragments(self, package: str) -> bool:
        """Return whether pull requests touching a package need a news fragment.

        Args:
            package: The package name.

        Returns:
            False for internal, never-published and explicitly exempt packages.
            A package that never ships has no release notes to carry a
            fragment, so the requirement would have nowhere to land.
        """
        return (
            not self.is_internal(package)
            and not self.is_never_published(package)
            and package not in self.changelog_exempt_packages
        )

    def package_source_prefixes(self, package: str) -> list[str]:
        """Return the repo-relative path prefixes that count as a package's source.

        A change under one of these prefixes makes the package "affected" and so
        requires a news fragment.

        Args:
            package: The package name.

        Returns:
            Path prefixes ending in ``/``. For the root package these are the
            configured ``root-source-dirs``; for a sub-package, its configured
            source subdirectories, falling back to the whole package directory
            (minus its fragment directory and changelog) when it has none.
        """
        if package == self.root_package:
            return [f"{directory.rstrip('/')}/" for directory in self.root_source_dirs]
        directory = self.package_dir(package)
        present = [
            f"{directory}/{subdir}/"
            for subdir in self.package_source_subdirs
            if (self.package_path(package) / subdir).is_dir()
        ]
        return present or [f"{directory}/"]

    def is_package_source(self, package: str, path: str) -> bool:
        """Return whether a changed repo-relative path is source of a package.

        Args:
            package: The package name.
            path: A repo-relative, POSIX-style path from a git diff.

        Returns:
            True when the path falls under one of the package's source
            prefixes. A package's own news fragments and changelog never count,
            so release commits do not look like source changes.
        """
        directory = self.package_dir(package)
        own_prefix = "" if directory == "." else f"{directory}/"
        if path.startswith(own_prefix) and path[len(own_prefix) :].split("/", 1)[0] in {
            self.news_directory,
            self.changelog_filename,
        }:
            return False
        return any(
            path.startswith(prefix) for prefix in self.package_source_prefixes(package)
        )

    def lockstep_group(self, package: str) -> LockstepGroup | None:
        """Return the lockstep group a package belongs to.

        Args:
            package: The package name.

        Returns:
            The group, or None when the package releases independently.
        """
        return next(
            (group for group in self.lockstep if package in group.members), None
        )

    def lockstep_partners(self, package: str) -> tuple[str, ...]:
        """Return the packages that must release alongside a package.

        Args:
            package: The package name.

        Returns:
            The other members of the package's lockstep group, or an empty
            tuple.
        """
        group = self.lockstep_group(package)
        if group is None:
            return ()
        return tuple(member for member in group.members if member != package)

    def publishes_last(self, package: str) -> bool:
        """Return whether a package must publish after its lockstep siblings.

        Args:
            package: The package name.

        Returns:
            True when the package is a ``publish-last`` member of its group.
        """
        group = self.lockstep_group(package)
        return group is not None and package in group.publish_last

    def exact_pin_targets(self, package: str) -> tuple[str, ...]:
        """Return the siblings whose requirement must be pinned exactly.

        Args:
            package: The package being built.

        Returns:
            The lockstep siblings to rewrite to ``== <version>`` in the
            package's ``pyproject.toml``, or an empty tuple.
        """
        group = self.lockstep_group(package)
        if group is None or not group.pin_exact or package not in group.publish_last:
            return ()
        return tuple(member for member in group.members if member != package)

    def custom_build_for(self, package: str) -> CustomBuild | None:
        """Return the repository-supplied workflow that builds a package.

        Args:
            package: The package name.

        Returns:
            The entry, or None when the package builds with ``uv build``.
        """
        return next(
            (entry for entry in self.custom_build if package in entry.packages), None
        )

    def custom_build_packages(self) -> tuple[str, ...]:
        """List every package built by a repository-supplied workflow.

        Returns:
            The package names, in configuration order.
        """
        return tuple(
            package for entry in self.custom_build for package in entry.packages
        )

    def expect_artifacts(self, package: str) -> tuple[str, ...]:
        """Return the filename patterns a package's build must produce.

        Args:
            package: The package being released.

        Returns:
            The configured glob patterns, or an empty tuple when the build is
            only required to produce artifacts of the right name and version.
        """
        entry = self.custom_build_for(package)
        return entry.expect_artifacts if entry is not None else ()

    def branch_allows_publish(self, version: Version, ref_name: str) -> bool:
        """Return whether a version may be published from a branch.

        Final (non-prerelease) versions publish only from the main branch or a
        hotfix branch; prereleases only from a prerelease branch or a hotfix
        branch.

        Args:
            version: The version to publish.
            ref_name: The branch name (``github.ref_name``).

        Returns:
            True when the branch may publish the version.
        """
        if is_final(version):
            return ref_name == self.main_branch or ref_name.startswith(
                self.hotfix_branch_prefix
            )
        return ref_name.startswith((
            self.prerelease_branch_prefix,
            self.hotfix_branch_prefix,
        ))

    def allowed_branches(self, version: Version) -> str:
        """Describe the branches a version may be published from.

        Args:
            version: The version to publish.

        Returns:
            A human-readable list for error messages.
        """
        if is_final(version):
            return f"{self.main_branch} or {self.hotfix_branch_prefix}** branches"
        return f"{self.prerelease_branch_prefix}* or {self.hotfix_branch_prefix}** branches"


def is_final(version: Version) -> bool:
    """Return whether a version is a final release (not a pre/dev release).

    Post releases count as final.

    Args:
        version: The parsed version.

    Returns:
        True when the version is neither a prerelease nor a dev release.
    """
    return not version.is_prerelease and not version.is_devrelease


def load_pyproject(path: Path) -> dict:
    """Parse a ``pyproject.toml`` file.

    Args:
        path: Path to the file.

    Returns:
        The parsed TOML document.
    """
    with path.open("rb") as f:
        return tomllib.load(f)


def _string_list(
    table: dict, key: str, label: str = f"[tool.{TOOL_TABLE}]"
) -> tuple[str, ...]:
    """Read a list-of-strings setting.

    Args:
        table: The table to read from.
        key: The setting name.
        label: How to name the table in an error, so a key in a sub-table does
            not send the reader looking for it in the top-level one.

    Returns:
        The values as a tuple (empty when the key is absent).
    """
    value = table.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        fail(f"{label} {key} must be a list of strings")
    return tuple(value)


def _string(
    table: dict, key: str, default: str, label: str = f"[tool.{TOOL_TABLE}]"
) -> str:
    """Read a string setting.

    Args:
        table: The table to read from.
        key: The setting name.
        default: The value to use when the key is absent.
        label: How to name the table in an error, so a key in a sub-table does
            not send the reader looking for it in the top-level one.

    Returns:
        The configured string.
    """
    value = table.get(key, default)
    if not isinstance(value, str):
        fail(f"{label} {key} must be a string")
    return value


def _version_pin(table: dict, key: str, default: str) -> str:
    """Read a version pin destined for a quoted YAML scalar.

    Args:
        table: The table to read from.
        key: The setting name.
        default: The value to use when the key is absent.

    Returns:
        The configured pin, or ``""`` to leave that version unpinned.
    """
    value = _string(table, key, default).strip()
    if value and not _VERSION_PIN_RE.fullmatch(value):
        fail(
            f"[tool.{TOOL_TABLE}] {key} must be a version or specifier such as "
            f'"1.2.3", ">=1.2" or "latest" (got {value!r}); leave it empty to '
            "install whatever the setup action defaults to"
        )
    return value


def _boolean(table: dict, key: str, default: bool) -> bool:
    """Read a boolean setting.

    Args:
        table: The table to read from.
        key: The setting name.
        default: The value to use when the key is absent.

    Returns:
        The configured boolean.
    """
    value = table.get(key, default)
    if not isinstance(value, bool):
        fail(f"[tool.{TOOL_TABLE}] {key} must be true or false")
    return value


def _load_lockstep(table: dict, packages: list[str]) -> tuple[LockstepGroup, ...]:
    """Parse and validate the ``[[tool.reflex-release.lockstep]]`` entries.

    Args:
        table: The ``[tool.reflex-release]`` table.
        packages: Every package name in the repository.

    Returns:
        The validated lockstep groups.
    """
    entries = table.get("lockstep", [])
    if not isinstance(entries, list):
        fail(f"[[tool.{TOOL_TABLE}.lockstep]] must be an array of tables")

    groups: list[LockstepGroup] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            fail(f"[[tool.{TOOL_TABLE}.lockstep]] must be an array of tables")
        if unknown := sorted(set(entry) - _KNOWN_LOCKSTEP_KEYS):
            fail(
                f"unknown key(s) in [[tool.{TOOL_TABLE}.lockstep]]: "
                f"{', '.join(unknown)}"
            )
        members = _string_list(entry, "members", _LOCKSTEP_LABEL)
        publish_last = _string_list(entry, "publish-last", _LOCKSTEP_LABEL)
        if len(members) < 2:
            fail(f"a [[tool.{TOOL_TABLE}.lockstep]] group needs at least two members")
        if len(set(members)) != len(members):
            fail(f"duplicate member in lockstep group {list(members)}")
        for member in members:
            if member not in packages:
                fail(f"lockstep member {member!r} is not a package in this repository")
            if member in seen:
                fail(f"package {member!r} appears in more than one lockstep group")
            seen.add(member)
        if extra := [name for name in publish_last if name not in members]:
            fail(
                f"publish-last entries are not members of the group: {', '.join(extra)}"
            )
        if publish_last and set(publish_last) == set(members):
            fail(
                "publish-last cannot list every member of a lockstep group; at "
                "least one member must publish first"
            )
        pin_exact = entry.get("pin-exact", False)
        if not isinstance(pin_exact, bool):
            fail(f"[[tool.{TOOL_TABLE}.lockstep]] pin-exact must be a boolean")
        if pin_exact and not publish_last:
            fail("pin-exact requires publish-last: the pinning package publishes last")
        groups.append(
            LockstepGroup(
                members=members, publish_last=tuple(publish_last), pin_exact=pin_exact
            )
        )
    return tuple(groups)


def _load_custom_build(table: dict, config: Config) -> tuple[CustomBuild, ...]:
    """Parse and validate the ``[[tool.reflex-release.custom-build]]`` entries.

    Args:
        table: The ``[tool.reflex-release]`` table.
        config: The configuration loaded so far, with its lockstep groups.

    Returns:
        The validated custom build entries.
    """
    entries = table.get("custom-build", [])
    if not isinstance(entries, list):
        fail(f"[[tool.{TOOL_TABLE}.custom-build]] must be an array of tables")

    packages = config.all_packages()
    builds: list[CustomBuild] = []
    seen: set[str] = set()
    workflows: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            fail(f"[[tool.{TOOL_TABLE}.custom-build]] must be an array of tables")
        if unknown := sorted(set(entry) - _KNOWN_CUSTOM_BUILD_KEYS):
            fail(
                f"unknown key(s) in [[tool.{TOOL_TABLE}.custom-build]]: "
                f"{', '.join(unknown)}"
            )
        members = _string_list(entry, "packages", CUSTOM_BUILD_LABEL)
        if not members:
            fail(
                f"a [[tool.{TOOL_TABLE}.custom-build]] entry needs at least one "
                "package in `packages`"
            )
        workflow = _string(entry, "workflow", "", CUSTOM_BUILD_LABEL)
        # The name is interpolated into the generated workflow's `uses:` as a
        # bare scalar, so it has to be a plain filename and nothing that YAML
        # would read as structure.
        if not _WORKFLOW_FILENAME_RE.fullmatch(workflow):
            fail(
                f"{CUSTOM_BUILD_LABEL} workflow must be a bare filename under "
                '.github/workflows made of letters, digits, ".", "_" and "-", '
                f'e.g. "build_wheels.yml" (got {workflow!r})'
            )
        build = CustomBuild(
            packages=members,
            workflow=workflow,
            expect_artifacts=_string_list(
                entry, "expect-artifacts", CUSTOM_BUILD_LABEL
            ),
        )
        # One job per entry in the generated publish workflow, so two entries
        # whose workflows share a job id would silently collapse into one.
        if previous := workflows.get(build.job_id):
            fail(
                f"[[tool.{TOOL_TABLE}.custom-build]] entries for {previous} and "
                f"{workflow} produce the same publish job ({build.job_id}); list "
                "every package one workflow builds in a single entry"
            )
        workflows[build.job_id] = workflow
        for member in members:
            if member not in packages:
                fail(
                    f"custom-build package {member!r} is not a package in this "
                    "repository"
                )
            if member in seen:
                fail(f"package {member!r} appears in more than one custom-build entry")
            seen.add(member)
            # pin-exact rewrites the package's pyproject.toml in the build
            # checkout; a custom build workflow builds from a checkout this
            # pipeline never touches, so the pin would silently not be applied.
            if config.exact_pin_targets(member):
                fail(
                    f"{member} pins its lockstep siblings exactly (pin-exact), "
                    "which rewrites its pyproject.toml in the build checkout — a "
                    "custom build workflow builds from its own checkout, so the "
                    "pin would never be applied. Drop pin-exact or build "
                    f"{member} in-repo."
                )
        builds.append(build)
    return tuple(builds)


def _default_root_source_dirs(root: Path, root_package: str | None) -> tuple[str, ...]:
    """Guess the root package's source directories.

    Args:
        root: The repository root.
        root_package: The root package name, if any.

    Returns:
        ``("src",)`` for a src layout, ``(<import name>,)`` when a directory
        named after the package exists, else an empty tuple.
    """
    if root_package is None:
        return ()
    if (root / "src").is_dir():
        return ("src",)
    module = root_package.replace("-", "_")
    return (module,) if (root / module).is_dir() else ()


def load_config(root: Path) -> Config:
    """Load the release configuration from a repository's ``pyproject.toml``.

    Args:
        root: The repository root.

    Returns:
        The validated configuration.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        fail(f"no pyproject.toml in {root}; run this from the repository root")
    tools = load_pyproject(pyproject).get("tool", {})
    towncrier = tools.get("towncrier", {})
    table = tools.get(TOOL_TABLE)
    if table is None:
        fail(
            f"no [tool.{TOOL_TABLE}] table in {pyproject}; run "
            "`reflex-release init` to set up this repository"
        )
    if unknown := sorted(set(table) - _KNOWN_KEYS):
        fail(f"unknown key(s) in [tool.{TOOL_TABLE}]: {', '.join(unknown)}")

    root_package = table.get("root-package")
    if root_package is not None and not isinstance(root_package, str):
        fail(f"[tool.{TOOL_TABLE}] root-package must be a string")
    latest_release_package = table.get("latest-release-package", root_package)
    if latest_release_package is not None and not isinstance(
        latest_release_package, str
    ):
        fail(f"[tool.{TOOL_TABLE}] latest-release-package must be a string")
    packages_dir = table.get("packages-dir", "packages")
    if packages_dir is not None and not isinstance(packages_dir, str):
        fail(f"[tool.{TOOL_TABLE}] packages-dir must be a string or omitted")
    if packages_dir is not None and not (root / packages_dir).is_dir():
        packages_dir = None

    config = Config(
        root=root,
        allow_self_review=_boolean(table, "allow-self-review", True),
        cli_command=_string(table, "cli-command", "uvx reflex-release"),
        uv_version=_version_pin(table, "uv-version", DEFAULT_UV_VERSION),
        python_version=_version_pin(table, "python-version", DEFAULT_PYTHON_VERSION),
        dispatch_package_inputs=_string(table, "dispatch-package-inputs", "auto"),
        news_directory=towncrier.get("directory") or "news",
        changelog_filename=towncrier.get("filename") or "CHANGELOG.md",
        root_package=root_package,
        # An explicitly empty list means "nothing here", which is not the same
        # as leaving the key out and taking the layout guess.
        root_source_dirs=(
            _string_list(table, "root-source-dirs")
            if "root-source-dirs" in table
            else _default_root_source_dirs(root, root_package)
        ),
        packages_dir=packages_dir,
        package_source_subdirs=(
            _string_list(table, "package-source-subdirs")
            if "package-source-subdirs" in table
            else ("src",)
        ),
        release_timezone=_string(table, "release-timezone", "UTC"),
        main_branch=_string(table, "main-branch", "main"),
        prerelease_branch_prefix=_string(table, "prerelease-branch-prefix", "r/pre-"),
        hotfix_branch_prefix=_string(table, "hotfix-branch-prefix", "r/hotfix/"),
        release_branch_prefix=_string(table, "release-branch-prefix", "release/"),
        tag_prefix=_string(table, "tag-prefix", "v"),
        # The documented opt-out is the empty string; anything else falsy was
        # rejected above rather than silently disabling the Latest marking.
        latest_release_package=latest_release_package or None,
        internal_packages=_string_list(table, "internal-packages"),
        changelog_exempt_packages=_string_list(table, "changelog-exempt-packages"),
        never_publish_packages=_string_list(table, "never-publish-packages"),
        # The documented opt-out is leaving the key out; an empty string is the
        # same thing rather than a workflow named "".
        post_release_workflow=_string(table, POST_RELEASE_WORKFLOW_KEY, "").strip()
        or None,
    )

    if not config.main_branch:
        fail(
            f"[tool.{TOOL_TABLE}] main-branch must not be empty: it is the branch "
            "final versions publish from and release pull requests target"
        )

    # An empty branch prefix makes str.startswith() match everything, which
    # would silently turn "only these branches may publish" into "any branch
    # may publish" — and widen the release workflow's push trigger to "**".
    for key, prefix in (
        ("prerelease-branch-prefix", config.prerelease_branch_prefix),
        ("hotfix-branch-prefix", config.hotfix_branch_prefix),
        ("release-branch-prefix", config.release_branch_prefix),
    ):
        if not prefix:
            fail(
                f"[tool.{TOOL_TABLE}] {key} must not be empty: an empty prefix "
                "matches every branch, so any branch could publish"
            )
        if config.main_branch.startswith(prefix):
            fail(
                f"[tool.{TOOL_TABLE}] {key} ({prefix!r}) matches the main branch "
                f"({config.main_branch!r}), which collapses the branch policy"
            )
        # git stores refs as paths, so refs/heads/main and refs/heads/main/x
        # cannot both exist: branches under such a prefix could never be created.
        if prefix.startswith(f"{config.main_branch}/"):
            fail(
                f"[tool.{TOOL_TABLE}] {key} ({prefix!r}) nests under the main "
                f"branch ({config.main_branch!r}); git cannot create a branch "
                "under an existing ref"
            )

    if config.dispatch_package_inputs not in {"auto", "checkboxes", "text"}:
        fail(
            f"[tool.{TOOL_TABLE}] dispatch-package-inputs must be one of "
            f"auto, checkboxes, text (got {config.dispatch_package_inputs!r})"
        )

    packages = config.all_packages()
    if not packages:
        fail(
            f"[tool.{TOOL_TABLE}] describes no packages: set root-package and/or "
            "create a packages directory"
        )
    for key in (
        "internal-packages",
        "changelog-exempt-packages",
        "never-publish-packages",
    ):
        for name in _string_list(table, key):
            if name not in packages:
                fail(f"[tool.{TOOL_TABLE}] {key} lists unknown package {name!r}")
    latest = config.latest_release_package
    if latest is not None and latest not in packages:
        fail(f"[tool.{TOOL_TABLE}] latest-release-package is unknown: {latest!r}")

    # A package cannot both never publish and publish on every push, and one
    # that never publishes cannot be the release GitHub marks "Latest".
    if both := sorted(
        set(config.never_publish_packages) & set(config.internal_packages)
    ):
        fail(
            f"[tool.{TOOL_TABLE}] {', '.join(both)} is listed in both "
            "never-publish-packages and internal-packages; internal packages "
            "release on every push that touches them"
        )
    if latest is not None and config.is_never_published(latest):
        fail(
            f"[tool.{TOOL_TABLE}] latest-release-package is {latest!r}, which is "
            "listed in never-publish-packages, so it has no release to mark; "
            "name a package that publishes, or leave it empty to never mark one"
        )

    # Custom builds are validated against the lockstep groups, so they load
    # onto a configuration that already carries them.
    config = dataclasses.replace(config, lockstep=_load_lockstep(table, packages))
    config = dataclasses.replace(config, custom_build=_load_custom_build(table, config))

    # Both features exist to get a package published, so naming one that never
    # publishes is a contradiction rather than a harmless no-op.
    for label, named in (
        (
            _LOCKSTEP_LABEL,
            {name for group in config.lockstep for name in group.members},
        ),
        (
            CUSTOM_BUILD_LABEL,
            {name for entry in config.custom_build for name in entry.packages},
        ),
    ):
        if unpublished := sorted(named & set(config.never_publish_packages)):
            fail(
                f"{label} names {', '.join(unpublished)}, which is listed in "
                "never-publish-packages and so never reaches a release"
            )
    return config
