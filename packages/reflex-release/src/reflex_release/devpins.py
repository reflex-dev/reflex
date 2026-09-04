"""The dependency pin gate, and the pin upgrades that clear it.

Development releases (``*.dev``) are not published to PyPI, so a package whose
published metadata pins one cannot be installed by downstream users.
:func:`check_dev_pins` is the gate that keeps such pins out of a release. Only
each package's *own* published dependencies are inspected — siblings are not
followed — so the usual leaf-first release flow (publish the depended-on
package, then drop the dev pin in the dependent) is never deadlocked by a pin in
another package.

Dropping the pin by hand is the step that flow keeps forgetting, so
materialization does it: :func:`upgrade_dev_pins` lifts every lower bound the
release cannot ship to the earliest published version that satisfies it, and
re-locks the repository, landing both in the release commit. A bound that no
published version satisfies has no upgrade, and the package is held back from
the release instead (see :func:`blocking_pins`) rather than materialized into a
version that could never be published.

"Published" means tagged: tags are created only after a successful upload, so
the repository's own tags are the record of what is on PyPI. A dependency
outside the repository has no such record here, which is why only a *dev* bound
on one blocks a release — that pin is unpublishable whoever owns it — while a
prerelease bound on an outside dependency is left alone.
"""

from __future__ import annotations

import dataclasses
import re
import subprocess

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from .actions import ReleaseError, echo, fail
from .config import Config, is_final, load_pyproject
from .gitutil import tag_versions

# PEP 440 operators that establish a version floor the resolved version must meet
# or match. A development release under one of these is an unpublished
# *minimum*; the same release under an upper bound (``<``, ``<=``) or exclusion
# (``!=``) leaves the requirement resolvable from PyPI, so it is not a dev pin.
_LOWER_BOUND_OPERATORS = frozenset({"===", "==", "~=", ">=", ">"})

# Operators that admit exactly one version, so a floor under one of them cannot
# be lifted onto anything: releasing the dependency never helps.
_EXACT_OPERATORS = frozenset({"===", "=="})

#: The lock file re-resolved after a pin upgrade, and the tool that rewrites it.
LOCK_FILE = "uv.lock"

# One version specifier of a PEP 508 requirement, matched so a single bound can
# be lifted in place without disturbing extras, markers or the other
# specifiers. The operator alternation is longest-first: ``>=`` has to win over
# ``>``, and ``===`` over ``==``.
_SPECIFIER_RE = re.compile(
    r"(?P<op>===|==|~=|>=|>)(?P<space>\s*)(?P<version>[^\s,;\]]+)"
)

# A TOML table header at the start of a line, which is what bounds the region a
# requirement rewrite is allowed to touch.
_TABLE_HEADER_RE = re.compile(r"^\[\[?(?P<name>[^\]]+)\]\]?", re.MULTILINE)


def _unshippable_bounds(
    parsed: Requirement, allow_prereleases: bool
) -> tuple[str, ...]:
    """Return the lower bounds of a requirement a release cannot ship as they are.

    Args:
        parsed: The parsed requirement.
        allow_prereleases: Whether a prerelease floor is shippable. Dev releases
            never are; a prerelease floor is fine for a release that is itself a
            prerelease, and unwanted in a final release, whose dependency floors
            should not drag users onto an alpha.

    Returns:
        The offending versions exactly as written in the requirement, so they can
        be found again in the source text.
    """
    bounds: list[str] = []
    for specifier in parsed.specifier:
        if specifier.operator not in _LOWER_BOUND_OPERATORS:
            continue
        try:
            bound = Version(specifier.version)
        except InvalidVersion:
            # A prefix match such as ``==1.2.*`` has no concrete version to inspect.
            continue
        if bound.is_devrelease or (bound.is_prerelease and not allow_prereleases):
            bounds.append(specifier.version)
    return tuple(bounds)


def _is_exact_pin(parsed: Requirement, bounds: tuple[str, ...]) -> bool:
    """Return whether every offending bound of a requirement is an exact pin.

    Args:
        parsed: The parsed requirement.
        bounds: The offending versions, as returned by :func:`_unshippable_bounds`.

    Returns:
        True when each one appears only under ``==`` or ``===``, which no
        published version other than the pinned one can ever satisfy.
    """
    return all(
        specifier.operator in _EXACT_OPERATORS
        for specifier in parsed.specifier
        if specifier.version in bounds
    )


def parse_requirement(requirement: str) -> tuple[str, bool]:
    """Split a PEP 508 requirement into its canonical name and dev-pin status.

    Args:
        requirement: A dependency string such as ``"mypkg-base >= 1.0.dev1"``.

    Returns:
        A ``(canonical_name, is_dev_pinned)`` tuple. ``is_dev_pinned`` is True
        only when a development release appears as a lower bound. An unparsable
        requirement is reported as ``("", False)``.
    """
    try:
        parsed = Requirement(requirement)
    except InvalidRequirement:
        return "", False
    return (
        canonicalize_name(parsed.name),
        bool(_unshippable_bounds(parsed, allow_prereleases=True)),
    )


def published_dependencies(project: dict) -> list[str]:
    """Collect the requirements that become a package's published metadata.

    Args:
        project: The ``[project]`` table of a parsed ``pyproject.toml``.

    Returns:
        The core runtime dependencies plus every optional-dependency group —
        exactly the requirements emitted as ``Requires-Dist``. Dependency groups
        (PEP 735) are excluded: they are development-only and never published.
    """
    deps = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        deps.extend(group)
    return deps


def check_dev_pins(config: Config, packages: list[str]) -> None:
    """Fail if any selected package declares a development-release pin.

    Args:
        config: The repository configuration.
        packages: The packages to inspect; empty inspects every package.
    """
    for package in packages:
        config.require_known(package)
    # A package that never ships cannot publish an unusable pin, and holding
    # it to the gate would fail the sweep over metadata nobody installs.
    targets = packages or [
        package
        for package in config.all_packages()
        if not config.is_never_published(package)
    ]

    offenders: list[tuple[str, str]] = []
    for package in targets:
        project = load_pyproject(config.package_path(package) / "pyproject.toml").get(
            "project", {}
        )
        offenders += [
            (package, dependency)
            for dependency in published_dependencies(project)
            if parse_requirement(dependency)[1]
        ]

    if offenders:
        listing = "\n".join(f"  {name}: {dependency}" for name, dependency in offenders)
        fail(
            "development-release dependency pins must not be published:\n"
            f"{listing}\n\n{len(offenders)} development-release pin(s) found. Release "
            "the depended-on package(s) and re-pin to a published version before "
            "publishing."
        )
    echo(f"No development-release dependency pins found in {len(targets)} package(s).")


@dataclasses.dataclass(frozen=True)
class PinUpgrade:
    """One dependency lower bound a release has to lift before it can publish.

    Attributes:
        package: The package declaring the requirement.
        requirement: The requirement string, verbatim as written in
            ``pyproject.toml``.
        dependency: The canonical distribution name it depends on.
        bounds: The offending lower-bound versions, as written.
        resolved: The earliest published version that satisfies the requirement,
            or None when no published version does — which disqualifies the
            package from the release.
        reason: Why no published version satisfies it (empty when one does).
        exact: Whether the offending bounds are exact pins (``==``/``===``), for
            which no published version can ever qualify — so the advice is to
            re-pin by hand rather than to release the dependency first.
    """

    package: str
    requirement: str
    dependency: str
    bounds: tuple[str, ...]
    resolved: Version | None
    reason: str = ""
    exact: bool = False

    def rewritten(self) -> str:
        """Return the requirement with its offending bounds lifted.

        Returns:
            The requirement string to write back, preserving extras, markers,
            spacing and every other specifier.
        """
        if self.resolved is None:
            fail(f"{self.requirement!r} has no published version to lift it to")
        # Only the specifier part: a marker such as ``; python_version > '3.10'``
        # holds comparisons of its own that are not version specifiers.
        head, separator, marker = self.requirement.partition(";")
        version = self.resolved

        def lift(match: re.Match[str]) -> str:
            if match["version"] not in self.bounds:
                return match[0]
            # ``> 0.2.0.dev1`` admits 0.2.0, so 0.2.0 can be what it resolves
            # to — but ``> 0.2.0`` would then exclude the very release the
            # requirement was lifted onto. A strict floor over an unreleased
            # version becomes an inclusive floor over the release above it.
            operator = ">=" if match["op"] == ">" else match["op"]
            return f"{operator}{match['space']}{version}"

        lifted = _SPECIFIER_RE.sub(lift, head) + separator + marker
        # The point of the rewrite is a requirement the resolved version
        # satisfies; anything else would publish metadata that resolves to
        # something other than what was checked, or to nothing at all.
        if not Requirement(lifted).specifier.contains(version, prereleases=True):
            fail(
                f"lifting {self.requirement!r} produced {lifted!r}, which "
                f"{version} does not satisfy; re-pin it by hand"
            )
        return lifted


def _distribution_index(config: Config) -> dict[str, str]:
    """Map every repository package's distribution name to its package name.

    Args:
        config: The repository configuration.

    Returns:
        Canonical distribution name to package (directory) name, which is what
        turns a requirement into the sibling whose tags record its releases.
    """
    return {
        canonicalize_name(config.distribution_name(package)): package
        for package in config.all_packages()
    }


def _pin_upgrades(
    config: Config, package: str, allow_prereleases: bool, index: dict[str, str]
) -> list[PinUpgrade]:
    """List the dependency lower bounds a package must lift to be releasable.

    Args:
        config: The repository configuration.
        package: The package whose published dependencies to inspect.
        allow_prereleases: Whether published prereleases count as releases —
            true when materializing a prerelease, so an alpha may depend on a
            sibling's alpha, and false for a final version.
        index: The repository's distribution index, built once by the caller
            because every package in the repository has to be read to build it.

    Returns:
        One entry per offending requirement, each carrying either the version to
        lift it to or the reason there is none. An empty list means the package's
        published metadata is releasable as it stands.
    """
    project = load_pyproject(config.package_path(package) / "pyproject.toml").get(
        "project", {}
    )
    # Lockstep siblings pinned exactly are rewritten to the released version at
    # build time by pin-lockstep, so whatever they say here is not shipped.
    exact = {
        canonicalize_name(config.distribution_name(target))
        for target in config.exact_pin_targets(package)
    }

    upgrades: list[PinUpgrade] = []
    for requirement in published_dependencies(project):
        try:
            parsed = Requirement(requirement)
        except InvalidRequirement:
            continue
        name = canonicalize_name(parsed.name)
        if name in exact:
            continue
        sibling = index.get(name)
        # A prerelease floor is lifted only for siblings: the releases of an
        # outside dependency are not recorded here, and pinning one is a
        # deliberate choice this tool has no business overriding. A *dev* floor
        # is unpublishable whoever owns the dependency, so it always counts.
        bounds = _unshippable_bounds(parsed, allow_prereleases or sibling is None)
        if not bounds:
            continue
        # An exact pin on an unshippable version is a dead end, not a wait: no
        # published version equals it, so no release of the dependency will ever
        # make it satisfiable. Say so instead of sending the operator in a
        # circle, and do not bother consulting the tags.
        if _is_exact_pin(parsed, bounds):
            upgrades.append(
                PinUpgrade(
                    package,
                    requirement,
                    name,
                    bounds,
                    None,
                    "an exact pin on an unpublished version can never be "
                    "satisfied by a release; re-pin it by hand",
                    exact=True,
                )
            )
            continue
        if sibling is None:
            upgrades.append(
                PinUpgrade(
                    package,
                    requirement,
                    name,
                    bounds,
                    None,
                    f"{parsed.name} is not a package in this repository, so its "
                    "published versions are not known here; re-pin it by hand",
                )
            )
            continue
        candidates = [
            version
            for version in tag_versions(config, sibling)
            if allow_prereleases or is_final(version)
        ]
        satisfying = [
            version
            for version in candidates
            if parsed.specifier.contains(version, prereleases=True)
        ]
        if satisfying:
            upgrades.append(
                PinUpgrade(package, requirement, name, bounds, min(satisfying))
            )
            continue
        kind = "" if allow_prereleases else "final "
        upgrades.append(
            PinUpgrade(
                package,
                requirement,
                name,
                bounds,
                None,
                f"no {kind}release of {sibling} satisfies it "
                + (
                    f"(newest tagged: {max(candidates)})"
                    if candidates
                    else f"({sibling} has no {kind}releases yet)"
                ),
            )
        )
    return upgrades


def pin_upgrades(
    config: Config, package: str, allow_prereleases: bool
) -> list[PinUpgrade]:
    """List the dependency lower bounds a package must lift to be releasable.

    Args:
        config: The repository configuration.
        package: The package whose published dependencies to inspect.
        allow_prereleases: Whether published prereleases count as releases —
            true when materializing a prerelease, so an alpha may depend on a
            sibling's alpha, and false for a final version.

    Returns:
        One entry per offending requirement, each carrying either the version to
        lift it to or the reason there is none. An empty list means the package's
        published metadata is releasable as it stands.
    """
    return _pin_upgrades(
        config, package, allow_prereleases, _distribution_index(config)
    )


def _upgrades_for(
    config: Config, packages: list[str], allow_prereleases: bool
) -> list[PinUpgrade]:
    """Collect the pin upgrades of a whole release batch.

    Args:
        config: The repository configuration.
        packages: The packages being considered for a release.
        allow_prereleases: Whether published prereleases count as releases.

    Returns:
        Every offending requirement across the batch, in package order.
    """
    index = _distribution_index(config)
    return [
        upgrade
        for package in packages
        for upgrade in _pin_upgrades(config, package, allow_prereleases, index)
    ]


def blocking_pins(
    config: Config, packages: list[str], allow_prereleases: bool
) -> dict[str, list[PinUpgrade]]:
    """Group the pin upgrades that have no published version to lift them to.

    Args:
        config: The repository configuration.
        packages: The packages being considered for a release.
        allow_prereleases: Whether published prereleases count as releases.

    Returns:
        Package name to its unresolvable pins, for the packages that have any.
        Those packages cannot be released until the pins are satisfiable.
    """
    blocked: dict[str, list[PinUpgrade]] = {}
    for upgrade in _upgrades_for(config, packages, allow_prereleases):
        if upgrade.resolved is None:
            blocked.setdefault(upgrade.package, []).append(upgrade)
    return blocked


def describe_blockers(blocked: dict[str, list[PinUpgrade]]) -> list[str]:
    """Render one human-readable line per unresolvable pin.

    Args:
        blocked: The mapping returned by :func:`blocking_pins`.

    Returns:
        The lines, in package order.
    """
    return [
        f"{package}: {upgrade.requirement!r} — {upgrade.reason}"
        for package, upgrades in blocked.items()
        for upgrade in upgrades
    ]


def blocker_advice(blocked: dict[str, list[PinUpgrade]]) -> str:
    """Return what to do about a set of unresolvable pins.

    Args:
        blocked: The mapping returned by :func:`blocking_pins`.

    Returns:
        The closing sentence(s) for the failure message. Waiting for a release
        only helps a pin a future version could satisfy; an exact pin has to be
        rewritten by hand, so saying otherwise sends the operator in a circle.
    """
    upgrades = [upgrade for entries in blocked.values() for upgrade in entries]
    advice: list[str] = []
    if any(not upgrade.exact for upgrade in upgrades):
        advice.append(
            "Release the depended-on package(s) first; the next release lifts "
            "those pins automatically."
        )
    if any(upgrade.exact for upgrade in upgrades):
        advice.append(
            "An exact pin has no published version to move to, whatever is "
            "released: re-pin it by hand."
        )
    return " ".join(advice)


def _toml_basic(value: str) -> str:
    """Render a string as a TOML basic (double-quoted) value.

    Args:
        value: The string as parsed back out of the document.

    Returns:
        The quoted spelling, with the two characters a requirement can plausibly
        carry escaped. A basic string cannot hold a bare ``"``, so this — not
        the parsed value — is what a requirement with a double-quoted marker
        looks like in the file.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _project_regions(text: str) -> list[tuple[int, int]]:
    """Return the spans of the ``[project]`` table and its subtables.

    Args:
        text: A ``pyproject.toml`` document.

    Returns:
        ``(start, end)`` offsets covering the tables that hold published
        requirements. Everything else — ``[dependency-groups]`` above all, which
        :func:`published_dependencies` deliberately ignores — is outside, so a
        copy of a requirement that is never published is neither counted nor
        rewritten.
    """
    headers = list(_TABLE_HEADER_RE.finditer(text))
    regions: list[tuple[int, int]] = []
    for index, header in enumerate(headers):
        name = header["name"].strip()
        if name != "project" and not name.startswith("project."):
            continue
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        regions.append((header.end(), end))
    return regions


def _replace_requirement(
    text: str, original: str, replacement: str, expected: int
) -> str:
    """Rewrite a package's published copies of one requirement string.

    The requirement is matched as the whole quoted TOML value it was read from,
    so nothing else that happens to contain the same substring is touched. Both
    ways TOML can spell it are tried: a basic string, whose quotes and
    backslashes are escaped, and a literal string, which cannot escape anything.

    Args:
        text: The file content.
        original: The requirement as parsed from the file.
        replacement: The requirement to write instead.
        expected: How many published copies the parser found — the same string
            in ``dependencies`` and in an optional-dependency group is two
            requirements, and both are published, so both are rewritten.

    Returns:
        The updated file content.
    """
    spellings = [
        (_toml_basic(original), _toml_basic(replacement)),
        (f"'{original}'", f"'{replacement}'"),
    ]
    pieces: list[str] = []
    cursor = found = 0
    for start, end in _project_regions(text):
        pieces.append(text[cursor:start])
        chunk = text[start:end]
        for needle, substitute in spellings:
            found += chunk.count(needle)
            chunk = chunk.replace(needle, substitute)
        pieces.append(chunk)
        cursor = end
    pieces.append(text[cursor:])
    if found != expected:
        fail(
            f"expected {expected} published copy(ies) of the requirement "
            f"{original!r} to upgrade, found {found}; re-pin it by hand"
        )
    return "".join(pieces)


def apply_pin_upgrades(config: Config, upgrades: list[PinUpgrade]) -> list[str]:
    """Write resolved pin upgrades back into the packages' ``pyproject.toml``.

    Args:
        config: The repository configuration.
        upgrades: The upgrades to apply; every one must be resolved.

    Returns:
        The repo-relative paths that were rewritten.
    """
    # Grouped by requirement as well as by package: the same string declared in
    # both ``dependencies`` and an optional-dependency group is two published
    # requirements and one piece of text to rewrite, so the rewrite is told how
    # many copies to expect rather than insisting on one.
    by_package: dict[str, dict[str, list[PinUpgrade]]] = {}
    for upgrade in upgrades:
        by_package.setdefault(upgrade.package, {}).setdefault(
            upgrade.requirement, []
        ).append(upgrade)

    changed: list[str] = []
    for package, requirements in by_package.items():
        pyproject = config.package_path(package) / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        for requirement, entries in requirements.items():
            rewritten = entries[0].rewritten()
            text = _replace_requirement(text, requirement, rewritten, len(entries))
            echo(f"{package}: {requirement} -> {rewritten}")
        pyproject.write_text(text, encoding="utf-8")
        changed.append(pyproject.relative_to(config.root).as_posix())
    return changed


def refresh_lock_file(config: Config) -> str | None:
    """Re-resolve the repository lock file after a dependency pin changed.

    A uv workspace records its own members with no version specifier at all
    (``{ name = "mypkg-base", editable = "packages/mypkg-base" }``), so lifting
    a *sibling* pin leaves the lock file byte-identical; only a layout where the
    dependency resolves from an index has a specifier for the lock to follow.

    Args:
        config: The repository configuration.

    Returns:
        The repo-relative lock file path when the re-lock changed it, or None
        when the repository has no lock file or the lock did not move.
    """
    lock = config.root / LOCK_FILE
    if not lock.is_file():
        return None
    before = lock.read_bytes()
    echo(f"$ uv lock  # {LOCK_FILE} follows the upgraded pins")
    if subprocess.run(["uv", "lock"], cwd=config.root, check=False).returncode != 0:
        fail(
            f"`uv lock` failed after upgrading dependency pins; {LOCK_FILE} would "
            "be left describing the old pins"
        )
    if lock.read_bytes() == before:
        echo(f"{LOCK_FILE} is unchanged by the lifted pins.")
        return None
    return LOCK_FILE


def upgrade_dev_pins(
    config: Config, packages: list[str], allow_prereleases: bool
) -> list[str]:
    """Lift every unpublishable dependency bound of the packages being released.

    Args:
        config: The repository configuration.
        packages: The packages being released.
        allow_prereleases: Whether published prereleases count as releases.

    Returns:
        The repo-relative paths that changed — the rewritten ``pyproject.toml``
        files, plus the lock file when the re-lock moved it.
    """
    upgrades = _upgrades_for(config, packages, allow_prereleases)
    blocked: dict[str, list[PinUpgrade]] = {}
    for upgrade in upgrades:
        if upgrade.resolved is None:
            blocked.setdefault(upgrade.package, []).append(upgrade)
    if blocked:
        listing = "\n".join(f"  {line}" for line in describe_blockers(blocked))
        fail(
            "dependency pins that no published version satisfies cannot be "
            f"materialized into a release:\n{listing}\n\n{blocker_advice(blocked)}"
        )
    if not upgrades:
        return []

    # Every pin in the batch and the lock file move together or not at all: the
    # rewrites run package by package, so a requirement the second package
    # cannot be given would otherwise strand the first one's — and a lock file
    # left describing the old pins is worse still, because a re-run finds
    # nothing left to lift, does not re-lock, and could commit that pairing.
    snapshot = {
        path: path.read_text(encoding="utf-8")
        for path in {
            config.package_path(upgrade.package) / "pyproject.toml"
            for upgrade in upgrades
        }
    }
    try:
        changed = apply_pin_upgrades(config, upgrades)
        lock = refresh_lock_file(config)
    except ReleaseError:
        for path, text in snapshot.items():
            path.write_text(text, encoding="utf-8")
        echo(f"restored {len(snapshot)} pyproject.toml file(s); no pin was lifted")
        raise
    if lock is not None:
        changed.append(lock)
    return changed
