"""Scaffolding and drift-checking of the GitHub Actions workflows.

The workflows are copied into the consumer repository rather than referenced as
cross-repository reusable workflows. Three constraints add up to that:

- PyPI trusted publishing validates the OIDC ``job_workflow_ref`` claim, which
  names the repository owning the workflow file, so a publish workflow living
  somewhere else cannot be trusted by the project's own publisher.
- ``release_from_changelog`` calls ``publish.yml`` through a ``./`` path, which
  resolves against the repository holding the *calling* file. Hosted elsewhere,
  it would call this project's publish workflow instead of the consumer's.
- Triggers live in the workflow that declares them: ``on: pull_request``,
  ``on: push`` and the ``workflow_dispatch`` inputs all have to be files in the
  consumer repository no matter where the job bodies live.

What is left to share is the job bodies of two workflows, which is not worth a
floating cross-repository dependency on the most privileged path in the
release. ``sync`` re-renders every template from the repository's
configuration, so an upgrade is a version bump plus one command, and the
generated pull-request workflow runs ``sync --check`` so drift fails CI instead
of surfacing at release time.
"""

from __future__ import annotations

import dataclasses
import difflib
import json
import re
import subprocess
from importlib import metadata
from pathlib import Path

from packaging.version import Version

from .actions import echo, fail
from .changelog import parse_sections, render_heading
from .config import (
    CUSTOM_BUILD_LABEL,
    POST_RELEASE_INPUTS,
    POST_RELEASE_WORKFLOW_KEY,
    TOOL_TABLE,
    Config,
    load_config,
    load_pyproject,
)
from .discovery import releasable_packages, title_format
from .versions import ACTIONS

WORKFLOW_DIR = ".github/workflows"

#: Workflows every consumer repository gets.
CORE_WORKFLOWS = (
    "changelog.yml",
    "dispatch_release.yml",
    "release_from_changelog.yml",
    "publish.yml",
)

#: ``workflow_dispatch`` accepts at most twenty inputs, one of which is the
#: action.
MAX_DISPATCH_CHECKBOXES = 19

#: Workflow scaffolded only for repositories that declare internal packages.
INTERNAL_WORKFLOW = "auto_release_internal.yml"

#: Generated workflows that a repository may stop needing.
OPTIONAL_WORKFLOWS = (INTERNAL_WORKFLOW,)

#: Every workflow this tool can generate, whether or not a given repository
#: currently gets it.
GENERATED_WORKFLOWS = (*CORE_WORKFLOWS, *OPTIONAL_WORKFLOWS)

TEMPLATE_DIR = Path(__file__).parent / "templates" / "workflows"

#: The inputs the generated publish workflow passes to a custom build workflow.
CUSTOM_BUILD_INPUTS = ("package", "version", "tag", "build-dir", "artifact-prefix")

#: The ``workflow_call`` interface a custom build workflow has to declare.
CUSTOM_BUILD_CONTRACT = """\
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
        type: string\
"""

_GITHUB_REMOTE_RE = re.compile(
    r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$"
)

# A workflow's display name: the only top-level `name:` key, at column 0.
_WORKFLOW_NAME_RE = re.compile(r"^name:[ \t]*(?P<name>\S.*?)[ \t]*$", re.MULTILINE)

TOWNCRIER_TYPES = (
    ("breaking", "Breaking Changes"),
    ("deprecation", "Deprecations"),
    ("feature", "Features"),
    ("bugfix", "Bug Fixes"),
    ("performance", "Performance"),
    ("docs", "Documentation"),
    ("misc", "Miscellaneous"),
)


def installed_version() -> str:
    """Return the installed version of this package.

    Returns:
        The distribution version, or ``0.0.0`` when it cannot be determined
        (running from a source tree without an installed distribution).
    """
    try:
        return metadata.version("reflex-release")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def default_cli_command(pin: str | None) -> str:
    """Return the invocation the scaffolded workflows should use.

    Args:
        pin: An explicit version to pin, ``""`` to leave the tool unpinned, or
            None to pin the installed version when it looks published.

    Returns:
        The command, e.g. ``uvx reflex-release@1.2.3``.
    """
    if pin is None:
        version = installed_version()
        pin = "" if version.startswith("0.0.0") else version
    return f"uvx reflex-release@{pin}" if pin else "uvx reflex-release"


def managed_workflows(config: Config) -> tuple[str, ...]:
    """List the workflow files this tool generates for a repository.

    Args:
        config: The repository configuration.

    Returns:
        The workflow filenames.
    """
    if config.internal_packages:
        return (*CORE_WORKFLOWS, INTERNAL_WORKFLOW)
    return CORE_WORKFLOWS


@dataclasses.dataclass(frozen=True)
class DispatchInput:
    """One checkbox on the Dispatch release form.

    Attributes:
        input_id: The ``workflow_dispatch`` input name.
        description: The label GitHub shows next to the checkbox.
        packages: The packages the checkbox selects — more than one for a
            lockstep group, whose members can only be released together.
    """

    input_id: str
    description: str
    packages: tuple[str, ...]


def _input_id(package: str) -> str:
    """Return the ``workflow_dispatch`` input name for a package.

    Args:
        package: The package name.

    Returns:
        The package name reduced to lowercase word characters.
    """
    return re.sub(r"[^a-z0-9_]", "_", package.lower())


def dispatch_inputs(config: Config) -> list[DispatchInput]:
    """List the package checkboxes the Dispatch release workflow offers.

    Lockstep members share one checkbox: they can only be released together, so
    offering them separately would invite a selection the planner has to
    silently widen anyway.

    Args:
        config: The repository configuration.

    Returns:
        One entry per releasable package or lockstep group, in repository order.
    """
    inputs: list[DispatchInput] = []
    covered: set[str] = set()
    for package in releasable_packages(config):
        if package in covered:
            continue
        partners = config.lockstep_partners(package)
        covered.add(package)
        covered.update(partners)
        inputs.append(
            DispatchInput(
                input_id=_input_id(package),
                description=(
                    f"{package} (with {', '.join(partners)})" if partners else package
                ),
                packages=(package, *partners),
            )
        )
    ids = [entry.input_id for entry in inputs]
    if len(set(ids)) != len(ids):
        fail(
            "package names collide as workflow inputs after normalization: "
            f"{sorted(name for name in ids if ids.count(name) > 1)}"
        )
    return inputs


def use_checkboxes(config: Config) -> bool:
    """Return whether the Dispatch release form should render checkboxes.

    Args:
        config: The repository configuration.

    Returns:
        True for checkboxes, False for the free-text package field. ``auto``
        falls back to free text once the checkboxes would exceed the
        ``workflow_dispatch`` input limit.
    """
    if config.dispatch_package_inputs != "auto":
        return config.dispatch_package_inputs == "checkboxes"
    return len(dispatch_inputs(config)) <= MAX_DISPATCH_CHECKBOXES


def _package_input_block(config: Config) -> str:
    """Render the package selection inputs of the Dispatch release workflow.

    Args:
        config: The repository configuration.

    Returns:
        The YAML block, indented under ``inputs:``.
    """
    if not use_checkboxes(config):
        return (
            "      packages:\n"
            '        description: "Packages to release (comma-separated; '
            'empty auto-selects)"\n'
            "        required: false\n"
            "        type: string\n"
            '        default: ""'
        )
    return "\n".join(
        f"      {entry.input_id}:\n"
        f'        description: "{entry.description}"\n'
        "        type: boolean\n"
        "        default: false"
        for entry in dispatch_inputs(config)
    )


def _package_selection_block(config: Config) -> str:
    """Render the expression that turns the inputs into a package selection.

    Args:
        config: The repository configuration.

    Returns:
        The folded-scalar body of the ``PACKAGES`` environment variable,
        indented under its key. Every unchecked box contributes an empty
        string, so leaving them all unchecked keeps the auto-selection
        behavior.
    """
    if not use_checkboxes(config):
        return "            ${{ inputs.packages }}"
    return "\n".join(
        f"            ${{{{ inputs.{entry.input_id} && "
        f"'{','.join(entry.packages)}' || '' }}}}"
        for entry in dispatch_inputs(config)
    )


def _indented_list(items: list[str], indent: int) -> str:
    """Render a YAML sequence of scalars at a fixed indentation.

    Args:
        items: The scalar values.
        indent: The number of leading spaces per line.

    Returns:
        The rendered block, without a trailing newline.
    """
    return "\n".join(f"{' ' * indent}- {item}" for item in items)


def _selects_package(packages: tuple[str, ...]) -> str:
    """Render the workflow expression matching a set of packages.

    Args:
        packages: The package names to match.

    Returns:
        A ``contains(fromJson(...), inputs.package)`` expression.
    """
    listing = json.dumps(list(packages), separators=(",", ":"))
    return f"contains(fromJson('{listing}'), inputs.package)"


def _uv_setup_block(config: Config, *, checkout: bool = True) -> str:
    """Render the ``with:`` block pinning the uv and Python the workflows use.

    Every generated workflow installs uv the same way, so the pins live in one
    rendered block rather than in each template. They are written verbatim, so a
    repository that has not overridden them sees a bumped default as workflow
    drift the next ``sync --check`` reports.

    Args:
        config: The repository configuration.
        checkout: Whether the job installing uv checked the repository out. A
            job that did not runs in an empty working directory, where setup-uv
            has nothing to key a cache on and warns twice per run about it —
            noise on a job that installs no dependencies anyway.

    Returns:
        The block, indented under a ``uses: astral-sh/setup-uv`` step, or an
        empty string when there is nothing to pass.
    """
    settings = [
        ("version", config.uv_version),
        ("python-version", config.python_version),
    ]
    if not checkout:
        settings += [("enable-cache", "false"), ("ignore-empty-workdir", "true")]
    pins = [f'          {key}: "{value}"' for key, value in settings if value]
    return "\n".join(["        with:", *pins]) if pins else ""


def _custom_build_note(config: Config) -> str:
    """Render the header comment describing the custom build stage.

    Args:
        config: The repository configuration.

    Returns:
        The comment lines, or an empty string for a repository that builds
        every package with ``uv build``.
    """
    if not config.custom_build:
        return ""
    return "".join(
        f"{line}\n"
        for line in (
            "#   custom-build-*   unprivileged: packages configured with a custom",
            "#                    build workflow build there instead of in `build`.",
            "#                    The workflow is this repository's own file, and",
            "#                    uploads its distribution files as artifacts named",
            "#                    after the `artifact-prefix` input it is given.",
        )
    )


def _default_build_guard(config: Config) -> str:
    """Render the clause keeping custom-built packages out of the build job.

    Args:
        config: The repository configuration.

    Returns:
        The extra ``if`` condition, or an empty string.
    """
    packages = config.custom_build_packages()
    if not packages:
        return ""
    return f"      && !{_selects_package(packages)}"


def _custom_dev_pin_step(config: Config) -> str:
    """Render the dev-pin gate for packages that skip the built-in build job.

    Args:
        config: The repository configuration.

    Returns:
        The step, indented under the prepare job's ``steps``, or an empty
        string.
    """
    packages = config.custom_build_packages()
    if not packages:
        return ""
    return "\n" + "\n".join([
        "      # Custom-built packages never reach the `build` job, where this gate",
        "      # normally runs after the lockstep pin rewrites their metadata. They",
        "      # cannot be exact-pin lockstep members, so nothing rewrites theirs",
        "      # and the gate belongs here — still before anything is built.",
        "      - name: Reject development-release dependency pins",
        "        if: >-",
        "          steps.prepare.outputs.skipped != 'true' &&",
        f"          {_selects_package(packages)}",
        "        env:",
        "          PACKAGE: ${{ inputs.package }}",
        "        shell: bash",
        f'        run: {config.cli_command} check-dev-pins "$PACKAGE"',
    ])


def _custom_build_jobs(config: Config) -> str:
    """Render one publish-workflow job per custom build workflow.

    Args:
        config: The repository configuration.

    Returns:
        The job blocks, or an empty string.
    """
    if not config.custom_build:
        return ""
    blocks = [
        "\n".join([
            "  # Repository-supplied build, replacing the `build` job for:",
            f"  #   {', '.join(entry.packages)}",
            "  # A called workflow can hold no more privilege than the calling job",
            "  # grants it, so this runs inside the same unprivileged boundary as",
            "  # `build`: no secrets, no OIDC, and everything it produces is verified",
            "  # by `collect` before the approval gate. Every job it starts has to",
            "  # succeed, so a lost matrix leg stops the release.",
            f"  {entry.job_id}:",
            "    needs: prepare",
            "    if: >-",
            "      needs.prepare.outputs.skipped != 'true' &&",
            f"      {_selects_package(entry.packages)}",
            "    permissions:",
            "      contents: read",
            f"    uses: ./{WORKFLOW_DIR}/{entry.workflow}",
            "    with:",
            "      package: ${{ inputs.package }}",
            "      version: ${{ needs.prepare.outputs.version }}",
            "      tag: ${{ needs.prepare.outputs.tag }}",
            "      build-dir: ${{ needs.prepare.outputs.build_dir }}",
            "      artifact-prefix: dist-${{ inputs.package }}--",
        ])
        for entry in config.custom_build
    ]
    return "\n" + "\n\n".join(blocks)


#: The step that hands each published tag to the repository's own workflow.
#: ``@@INPUTS@@`` is the dispatch contract, named from one place.
POST_RELEASE_STEP = """
      # One dispatch per published tag, on the tag itself, after the upload,
      # the tag and the GitHub release: the workflow sees exactly the tree that
      # was published. It must declare workflow_dispatch inputs named
      # @@INPUTS@@.
      - name: Trigger the post-release workflow
        env:
          TAG: ${{ needs.prepare.outputs.tag }}
          PACKAGE: ${{ inputs.package }}
          VERSION: ${{ needs.prepare.outputs.version }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        shell: bash
        run: @@CLI@@ post-release"""


def render(name: str, config: Config) -> str:
    """Render one workflow template for a repository.

    Args:
        name: The workflow filename.
        config: The repository configuration.

    Returns:
        The rendered YAML.
    """
    cli = config.cli_command
    header = "\n".join([
        "# Generated by reflex-release; do not edit by hand.",
        f"# Re-run `{cli} sync` after changing [tool.reflex-release] in",
        f"# pyproject.toml. `{cli} sync --check` fails when this file drifts.",
    ])
    # The trigger fires on exactly the paths detect-internal counts as a
    # package's source, so the workflow cannot run and then find nothing.
    internal_paths: list[str] = []
    for package in config.internal_packages:
        prefixes = config.package_source_prefixes(package)
        if not prefixes:
            fail(
                f"{package} is the repository-root package and is listed in "
                "internal-packages, so its auto-release trigger needs to know "
                "which paths are its source: set root-source-dirs"
            )
        internal_paths.extend(f'"{prefix}**"' for prefix in prefixes)
    substitutions = {
        "@@HEADER@@": header,
        "@@CLI@@": cli,
        "@@UV_SETUP_WITH@@": _uv_setup_block(config),
        "@@UV_SETUP_NO_CHECKOUT@@": _uv_setup_block(config, checkout=False),
        "@@MAIN_BRANCH@@": config.main_branch,
        "@@PRERELEASE_PREFIX@@": config.prerelease_branch_prefix,
        "@@HOTFIX_PREFIX@@": config.hotfix_branch_prefix,
        "@@RELEASE_PREFIX@@": config.release_branch_prefix,
        "@@ALLOW_SELF_REVIEW@@": "true" if config.allow_self_review else "false",
        "@@ACTION_OPTIONS@@": _indented_list(list(ACTIONS), 10),
        "@@PACKAGE_INPUTS@@": _package_input_block(config),
        "@@PACKAGE_SELECTION@@": _package_selection_block(config),
        "@@INTERNAL_PATHS@@": _indented_list(internal_paths, 6),
        "@@CUSTOM_BUILD_NOTE@@": _custom_build_note(config),
        "@@CUSTOM_DEV_PIN_STEP@@": _custom_dev_pin_step(config),
        "@@DEFAULT_BUILD_GUARD@@": _default_build_guard(config),
        "@@CUSTOM_BUILD_JOBS@@": _custom_build_jobs(config),
        "@@CUSTOM_BUILD_NEEDS@@": "".join(
            f", {entry.job_id}" for entry in config.custom_build
        ),
        # Dispatching a workflow is a write on the actions scope, which the
        # publish job never needs and so is not granted by default.
        "@@ACTIONS_PERMISSION@@": ("write" if config.post_release_workflow else "read"),
        "@@POST_RELEASE_STEP@@": (
            POST_RELEASE_STEP.replace("@@CLI@@", cli).replace(
                "@@INPUTS@@", ", ".join(POST_RELEASE_INPUTS)
            )
            if config.post_release_workflow
            else ""
        ),
    }
    text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    for placeholder, value in substitutions.items():
        # A placeholder alone on a line stands for an optional block: an empty
        # value removes the line rather than leaving a blank one behind.
        if not value:
            text = text.replace(f"{placeholder}\n", "")
        text = text.replace(placeholder, value)
    if remaining := re.findall(r"@@[A-Z_]+@@", text):
        fail(
            f"unsubstituted placeholder(s) in {name}: {', '.join(sorted(set(remaining)))}"
        )
    return text


def check_title_format(config: Config) -> None:
    """Fail unless the configured heading format round-trips through the parser.

    The changelog is the source of truth for publishing, so a heading this tool
    writes but cannot read back would strand every release: detection would
    never see the version. Rather than parse arbitrary formats, require the
    version to lead the heading.

    Args:
        config: The repository configuration.
    """
    configured = title_format(config)
    try:
        heading = render_heading(configured, "v9.9.9", "2026-01-01")
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        fail(
            f"[tool.towncrier] title_format {configured!r} is not a usable format "
            f"string ({exc!r}); it may reference only {{name}}, {{version}} and "
            "{project_date}."
        )
    _, sections = parse_sections(f"{heading}\n\nprobe\n")
    if len(sections) != 1 or sections[0].version != Version("9.9.9"):
        fail(
            f"[tool.towncrier] title_format renders {heading!r}, which this tool "
            "cannot parse back. The release pipeline finds versions by reading "
            "changelog headings, so a heading must be '## ' followed by the "
            "version, optionally followed by a parenthesized date. Example: "
            '"## {version} ({project_date})".'
        )


def _indent_of(line: str) -> int:
    """Return a line's leading-whitespace width.

    Args:
        line: The line to measure.

    Returns:
        The number of leading whitespace characters.
    """
    return len(line) - len(line.lstrip())


def _nested_lines(lines: list[str], index: int) -> list[str]:
    """Return the lines nested under the mapping key at an index.

    Args:
        lines: Significant lines of a YAML document (no blanks or comments).
        index: The index of the key whose block to return.

    Returns:
        The following lines indented deeper than that key.
    """
    outer = _indent_of(lines[index])
    end = next(
        (
            offset
            for offset, line in enumerate(lines[index + 1 :])
            if _indent_of(line) <= outer
        ),
        len(lines) - index - 1,
    )
    return lines[index + 1 : index + 1 + end]


def _key_index(lines: list[str], key: str) -> int | None:
    """Return the index of the line declaring a block mapping key.

    Args:
        lines: Significant lines of a YAML document.
        key: The key to find.

    Returns:
        The index, or None when no line declares that key with a nested block.
    """
    pattern = re.compile(rf"\s*{re.escape(key)}:$")
    return next(
        (index for index, line in enumerate(lines) if pattern.fullmatch(line.rstrip())),
        None,
    )


def workflow_call_inputs(text: str) -> set[str]:
    """List the input names a workflow declares under ``on: workflow_call``.

    This reads the block by indentation rather than parsing YAML: the tool runs
    in the jobs holding write access on the release path, so it deliberately
    carries no YAML parser. It is lenient by design — an input it fails to see
    is still caught by GitHub, which rejects a call naming an undeclared input
    before any job in the run starts.

    Args:
        text: The workflow file's contents.

    Returns:
        The declared input names, empty when the block cannot be found.
    """
    lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    call = _key_index(lines, "workflow_call")
    if call is None:
        return set()
    block = _nested_lines(lines, call)
    inputs = _key_index(block, "inputs")
    if inputs is None:
        return set()
    declared = _nested_lines(block, inputs)
    if not declared:
        return set()
    # Only the keys at the shallowest depth are the input names; anything
    # deeper describes one of them.
    depth = min(_indent_of(line) for line in declared)
    return {
        line.strip().partition(":")[0] for line in declared if _indent_of(line) == depth
    }


def check_custom_build_workflows(config: Config) -> None:
    """Fail unless every configured custom build workflow exists and is callable.

    The generated publish workflow calls these files by path, so a missing file
    or a missing ``workflow_call`` trigger is a run that fails at release time.
    Checking here means the pull-request drift check catches it instead.

    Args:
        config: The repository configuration.
    """
    for entry in config.custom_build:
        listing = ", ".join(entry.packages)
        # GENERATED_WORKFLOWS, not managed_workflows: a repository with no
        # internal packages does not get auto_release_internal.yml, but naming
        # it here would still collide the moment one is added.
        if entry.workflow in GENERATED_WORKFLOWS:
            fail(
                f"{CUSTOM_BUILD_LABEL} names {entry.workflow}, which "
                "reflex-release generates; a custom build workflow has to be a "
                "separate file this repository owns"
            )
        target = config.root / WORKFLOW_DIR / entry.workflow
        if not target.is_file():
            fail(
                f"{listing} builds through {WORKFLOW_DIR}/{entry.workflow}, which "
                f"does not exist. Create it with:\n\n{CUSTOM_BUILD_CONTRACT}"
            )
        text = target.read_text(encoding="utf-8")
        if not re.search(r"\bworkflow_call\b", text):
            fail(
                f"{WORKFLOW_DIR}/{entry.workflow} declares no `workflow_call` "
                f"trigger, so publish.yml cannot call it to build {listing}. It "
                f"needs:\n\n{CUSTOM_BUILD_CONTRACT}"
            )
        # GitHub rejects a call naming an undeclared input, which would fail the
        # release itself; catching it here makes it a red pull request instead.
        if missing := [
            name
            for name in CUSTOM_BUILD_INPUTS
            if name not in workflow_call_inputs(text)
        ]:
            fail(
                f"{WORKFLOW_DIR}/{entry.workflow} does not declare the input(s) "
                f"publish.yml passes it: {', '.join(missing)}. Building {listing} "
                f"would fail the release when GitHub validates the call. It "
                f"needs:\n\n{CUSTOM_BUILD_CONTRACT}"
            )


def generated_workflow_names() -> set[str]:
    """Return every name a workflow this tool generates answers to.

    ``gh workflow run`` resolves a workflow by file name *or* by display name,
    so both are the tool's own — and every workflow it can generate counts, not
    just the ones a repository currently gets: a repository that drops its last
    internal package would otherwise be left dispatching a workflow ``sync``
    deletes.

    Returns:
        The file names and the ``name:`` of each generated workflow.
    """
    names: set[str] = set(GENERATED_WORKFLOWS)
    for filename in GENERATED_WORKFLOWS:
        text = (TEMPLATE_DIR / filename).read_text(encoding="utf-8")
        match = _WORKFLOW_NAME_RE.search(text)
        if match is None:
            fail(f"the {filename} template declares no top-level name")
        names.add(match["name"])
    return names


def check_post_release_workflow(config: Config) -> None:
    """Fail when the post-release workflow is one this tool generates.

    Handing a published tag back to the release pipeline itself would either
    re-enter it or fail on inputs it does not declare, so a repository that
    means to run something of its own after a release has to name that.

    Args:
        config: The repository configuration.
    """
    workflow = config.post_release_workflow
    if workflow is not None and workflow in generated_workflow_names():
        fail(
            f"[tool.{TOOL_TABLE}] {POST_RELEASE_WORKFLOW_KEY} is {workflow!r}, which "
            "names a workflow this tool generates (GitHub resolves a workflow by "
            "file name or by display name); name a workflow of your own to run "
            "after each published tag"
        )


def sync(config: Config, check: bool = False, force: bool = False) -> None:
    """Write the scaffolded workflows, or verify they are up to date.

    Args:
        config: The repository configuration.
        check: Report drift and fail instead of writing.
        force: Overwrite files that were not generated by this tool.
    """
    check_title_format(config)
    check_custom_build_workflows(config)
    check_post_release_workflow(config)
    workflow_dir = config.root / WORKFLOW_DIR
    stale: list[str] = []
    for name in managed_workflows(config):
        target = workflow_dir / name
        rendered = render(name, config)
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == rendered:
            continue
        if check:
            stale.append(name)
            echo(f"::group::{WORKFLOW_DIR}/{name} is out of date")
            echo(
                "".join(
                    difflib.unified_diff(
                        (current or "").splitlines(keepends=True),
                        rendered.splitlines(keepends=True),
                        fromfile=f"a/{WORKFLOW_DIR}/{name}",
                        tofile=f"b/{WORKFLOW_DIR}/{name}",
                    )
                )
            )
            echo("::endgroup::")
            continue
        if (
            current is not None
            and "Generated by reflex-release" not in current
            and not force
        ):
            fail(
                f"{WORKFLOW_DIR}/{name} exists and was not generated by "
                "reflex-release; move it aside or re-run with --force"
            )
        workflow_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        echo(f"{'updated' if current else 'wrote'} {WORKFLOW_DIR}/{name}")

    # A workflow this tool generated but no longer manages — auto_release_internal
    # after the last internal package is removed — would keep firing on pushes.
    for name in OPTIONAL_WORKFLOWS:
        target = workflow_dir / name
        if name in managed_workflows(config) or not target.is_file():
            continue
        if "Generated by reflex-release" not in target.read_text(encoding="utf-8"):
            continue
        if check:
            stale.append(name)
            echo(f"{WORKFLOW_DIR}/{name} is obsolete: no package is internal any more")
            continue
        target.unlink()
        echo(f"removed {WORKFLOW_DIR}/{name} (no internal packages)")

    if stale:
        fail(
            f"{len(stale)} scaffolded workflow(s) are out of date: "
            f"{', '.join(stale)}. Run `{config.cli_command} sync` and commit the result."
        )
    if check:
        echo(
            f"All {len(managed_workflows(config))} scaffolded workflows are up to date."
        )


def _github_slug(root: Path) -> str | None:
    """Return the ``owner/repo`` slug of the origin remote, if it is on GitHub.

    Args:
        root: The repository root.

    Returns:
        The slug, or None when it cannot be determined.
    """
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    match = _GITHUB_REMOTE_RE.search(result.stdout.strip())
    return f"{match['owner']}/{match['repo']}" if match else None


def release_config_toml(root: Path, cli_command: str) -> str:
    """Render a starter ``[tool.reflex-release]`` table for a repository.

    Args:
        root: The repository root.
        cli_command: The invocation the workflows should use.

    Returns:
        The TOML text to append to ``pyproject.toml``.
    """
    project = load_pyproject(root / "pyproject.toml").get("project", {})
    lines = [
        "[tool.reflex-release]",
        f'cli-command = "{cli_command}"',
    ]
    if name := project.get("name"):
        lines.append(f'root-package = "{name}"')
    if (root / "packages").is_dir():
        lines.append('packages-dir = "packages"')
    lines.append('release-timezone = "UTC"')
    return "\n".join(lines) + "\n"


def towncrier_config_toml(root: Path) -> str:
    """Render the shared ``[tool.towncrier]`` configuration for a repository.

    The ``package``/``name`` keys are intentionally empty: every invocation
    passes ``--dir <package path>`` to target one package, which is how a single
    configuration serves a whole monorepo.

    Args:
        root: The repository root.

    Returns:
        The TOML text to append to ``pyproject.toml``.
    """
    slug = _github_slug(root) or "OWNER/REPO"
    lines = [
        "[tool.towncrier]",
        "# One shared configuration for every package: each invocation passes",
        "# --dir <package path> to target a specific package's news/ directory.",
        "# https://towncrier.readthedocs.io/en/stable/monorepo.html",
        'package = ""',
        'name = ""',
        'directory = "news"',
        'filename = "CHANGELOG.md"',
        'title_format = "## {version} ({project_date})"',
        f'issue_format = "[#{{issue}}](https://github.com/{slug}/issues/{{issue}})"',
        'start_string = "<!-- towncrier release notes start -->\\n"',
    ]
    for directory, display in TOWNCRIER_TYPES:
        lines += [
            "",
            "[[tool.towncrier.type]]",
            f'directory = "{directory}"',
            f'name = "{display}"',
            "showcontent = true",
        ]
    return "\n".join(lines) + "\n"


def _append_table(pyproject: Path, table: str, text: str) -> bool:
    """Append a configuration table to ``pyproject.toml`` when it is absent.

    Args:
        pyproject: The file to update.
        table: The table name to look for (e.g. ``tool.towncrier``).
        text: The TOML text to append.

    Returns:
        True when the table was appended, False when it already existed.
    """
    current = pyproject.read_text(encoding="utf-8")
    if re.search(rf"^\[+{re.escape(table)}[.\]]", current, re.MULTILINE):
        echo(f"[{table}] already configured; leaving it untouched.")
        return False
    separator = (
        "" if current.endswith("\n\n") else "\n" if current.endswith("\n") else "\n\n"
    )
    pyproject.write_text(current + separator + text, encoding="utf-8")
    echo(f"added [{table}] to pyproject.toml")
    return True


def init(root: Path, pin: str | None, force: bool) -> None:
    """Set up changelog-driven releases in a repository.

    Adds the configuration tables when they are missing, creates the ``news``
    directories and writes the workflows.

    Args:
        root: The repository root.
        pin: Version to pin the workflows to (None auto-detects, ``""`` leaves
            the tool unpinned).
        force: Overwrite workflow files not generated by this tool.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        fail(f"no pyproject.toml in {root}; run this from the repository root")

    cli_command = default_cli_command(pin)
    _append_table(
        pyproject, "tool.reflex-release", release_config_toml(root, cli_command)
    )
    _append_table(pyproject, "tool.towncrier", towncrier_config_toml(root))

    config = load_config(root)
    for package in config.all_packages():
        if config.is_internal(package) or config.is_never_published(package):
            continue
        news = config.news_dir(package)
        news.mkdir(parents=True, exist_ok=True)
        keep = news / ".gitkeep"
        if not any(news.iterdir()):
            keep.touch()
        echo(f"news directory ready: {news.relative_to(root).as_posix()}")

    sync(config, force=force)
    print_checklist(config)


def print_checklist(config: Config) -> None:
    """Print the repository settings that must be configured by hand.

    Args:
        config: The repository configuration.
    """
    if "@" not in config.cli_command:
        echo(
            "\nWarning: the workflows invoke this tool unpinned "
            f"(`{config.cli_command}`), so the release path resolves whatever "
            "version is newest at run time. Pin it: set cli-command to "
            "`uvx reflex-release@<version>` and re-run sync."
        )
    echo(
        "\n".join([
            "",
            "Remaining setup (GitHub settings, once per repository):",
            "  1. Create the `pypi` environment and add required reviewers. Every",
            "     upload waits for one of them to approve it, so that list is who",
            "     can release."
            + (
                ""
                if config.allow_self_review
                else "\n     This repository sets allow-self-review = false, so also turn"
                "\n     on 'Prevent self-review'; the publish job asserts it."
            ),
            "  2. Configure PyPI trusted publishing for each distribution:",
            "     workflow `publish.yml`, environment `pypi`. Naming the",
            "     environment is what makes the approval gate load-bearing: without",
            "     it, any job in publish.yml can mint an upload token.",
            "  3. Enable 'Allow GitHub Actions to create and approve pull requests'",
            "     in Settings -> Actions -> General.",
            "  4. Create the `skip-changelog` and `changelog-version-edit` labels.",
            f"  5. Protect `{config.main_branch}` and restrict who may push",
            (
                f"     `{config.prerelease_branch_prefix}**`, "
                f"`{config.hotfix_branch_prefix}**` and "
                f"`{config.release_branch_prefix}**`"
            ),
            "     to maintainers plus the github-actions[bot] app.",
            "  6. Give every package a version derived from git tags (see the README",
            "     section 'Tag-derived versions').",
            "",
            "Read the README's 'Security model' section before the first release:",
            "branch rules are only enforced if a ruleset restricts who may create",
            "the publishing branches.",
            "",
            "Then cut a release from the Actions tab: Dispatch release.",
        ])
    )
