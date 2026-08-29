"""Audit that published packages ship their generated .pyi stubs correctly.

For each package it downloads the wheel and the sdist from PyPI and checks:

  * the package ships stubs for its own modules in BOTH artifacts,
  * those stubs are byte-identical between wheel and sdist,
  * no artifact carries stubs belonging to a different package,
  * per-package stub counts match the repo's pyi_hashes.json manifest (optional).

Stub *content* legitimately differs from the committed manifest hashes because the build
hook regenerates stubs at release time, so this compares presence and counts rather than
hashes. A package with no manifest entries is expected to ship no stubs.

It exits 1 when a package's packaging is wrong and 2 when a package could not be audited
at all, so an unreachable PyPI never reads as a defect in a package nobody looked at.

Usage (the script carries PEP 723 metadata and no shebang, so run it through uv):
    uv run --script audit_pyi.py reflex==0.9.9 reflex-base==0.9.9

Chain it to discovery with && rather than a pipe: a pipe reports only this script's exit
status, so a package dropped for a failed lookup would take the audit's PASS with it.

    uv run --script check_release_versions.py --ref origin/main --specs > specs.txt \
      && xargs uv run --script audit_pyi.py --manifest-ref origin/main < specs.txt
"""

# /// script
# requires-python = ">=3.10"
# ///

from __future__ import annotations

import argparse
import collections
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
import zlib
from pathlib import Path


def _exc_name(exc: BaseException) -> str:
    """Name an exception well enough for the reader to act on it.

    Args:
        exc: The exception to name.

    Returns:
        The class name, module-qualified unless it is a builtin. ``zlib.error`` is called
        just ``error``, which says nothing at all on its own in a report.
    """
    cls = type(exc)
    if cls.__module__ == "builtins":
        return cls.__name__
    return f"{cls.__module__}.{cls.__name__}"


def download_artifacts(name: str, version: str, dest: Path) -> dict[str, Path]:
    """Download the wheel and sdist for a package version.

    Args:
        name: The PyPI distribution name.
        version: The version to download.
        dest: Directory to download into.

    Returns:
        A mapping of ``"wheel"``/``"sdist"`` to the downloaded file paths.
    """
    with urllib.request.urlopen(
        f"https://pypi.org/pypi/{name}/{version}/json", timeout=60
    ) as r:
        data = json.load(r)
    out: dict[str, Path] = {}
    for entry in data.get("urls", []):
        kind = entry["packagetype"]
        if kind not in ("bdist_wheel", "sdist") or entry.get("yanked"):
            # A yanked file is not what a user would install, so auditing it would report
            # on the wrong artifact. With every file yanked this leaves nothing, which the
            # caller already reports as a missing artifact kind.
            continue
        path = dest / entry["filename"]
        if not path.exists():
            # urlretrieve honours only the global socket timeout, which is unset, so a
            # stalled transfer would hang the whole audit rather than failing this row.
            partial = path.with_name(path.name + ".part")
            try:
                with (
                    urllib.request.urlopen(entry["url"], timeout=60) as response,
                    partial.open("wb") as handle,
                ):
                    shutil.copyfileobj(response, handle)
                # Only a whole file earns the real name. A partial one left there would be
                # reused by every later run, since --keep skips what already exists, and
                # the re-run this failure tells you to do could never clear it.
                partial.replace(path)
            finally:
                partial.unlink(missing_ok=True)
        out["wheel" if kind == "bdist_wheel" else "sdist"] = path
    return out


def wheel_stubs(path: Path) -> dict[str, bytes]:
    """Read every stub in a wheel.

    Args:
        path: Path to the wheel file.

    Returns:
        A mapping of archive-relative stub path to its contents.
    """
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist() if n.endswith(".pyi")}


def sdist_stubs(path: Path) -> dict[str, bytes]:
    """Read every stub in an sdist, normalized to the wheel's layout.

    The ``<name>-<version>/`` prefix and any ``src/`` layout directory are stripped so the
    keys line up with the wheel's, making the two directly comparable.

    Args:
        path: Path to the sdist tarball.

    Returns:
        A mapping of normalized stub path to its contents.
    """
    out: dict[str, bytes] = {}
    with tarfile.open(path) as t:
        for member in t.getmembers():
            if not member.name.endswith(".pyi"):
                continue
            parts = member.name.split("/")[1:]  # strip the <name>-<version>/ prefix
            if parts and parts[0] == "src":  # src-layout packages
                parts = parts[1:]
            handle = t.extractfile(member)
            if handle is not None:
                out["/".join(parts)] = handle.read()
    return out


def import_root(dist_name: str, roots: dict[str, str]) -> str:
    """Resolve the top-level import package for a distribution.

    The manifest is authoritative when available because it records each stub's real
    source path; the underscore convention is only a fallback. Deriving the root from the
    artifact itself would be circular — foreign stubs would define themselves as native
    and the leak check could never fail.

    Args:
        dist_name: The PyPI distribution name.
        roots: Import roots by distribution name, from the manifest.

    Returns:
        The import package name.
    """
    return roots.get(dist_name, dist_name.replace("-", "_"))


def manifest_roots(ref: str, repo: str) -> dict[str, str]:
    """Read each distribution's real import root from the stub manifest.

    Args:
        ref: The git ref to read ``pyi_hashes.json`` from.
        repo: Path to the reflex checkout.

    Returns:
        A mapping of distribution name to import package name, empty when the manifest is
        unavailable.
    """
    roots: dict[str, str] = {}
    for key in _manifest_keys(ref, repo):
        parts = key.split("/")
        if key.startswith("packages/"):
            # packages/<dist>/<src dir>/<import root>/...
            if len(parts) > 3:
                roots[parts[1]] = parts[3]
        elif parts:
            roots["reflex"] = parts[0]
    return roots


def _manifest_keys(ref: str, repo: str) -> list[str]:
    """Read the stub paths recorded in the manifest.

    Args:
        ref: The git ref to read ``pyi_hashes.json`` from.
        repo: Path to the reflex checkout.

    Returns:
        The manifest's stub paths, empty when it is unavailable at that ref.
    """
    result = subprocess.run(
        ["git", "-C", repo, "show", f"{ref}:pyi_hashes.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return list(json.loads(result.stdout))


def manifest_counts(ref: str, repo: str) -> dict[str, int]:
    """Count the stubs each distribution is expected to ship.

    Args:
        ref: The git ref to read ``pyi_hashes.json`` from.
        repo: Path to the reflex checkout.

    Returns:
        A mapping of distribution name to expected stub count, empty when the manifest is
        unavailable at that ref.
    """
    counts: collections.Counter[str] = collections.Counter()
    for key in _manifest_keys(ref, repo):
        # "packages/<dist>/src/<pkg>/x.pyi" or a root-package path like "reflex/x.pyi"
        counts[key.split("/")[1] if key.startswith("packages/") else "reflex"] += 1
    return dict(counts)


def _record(
    name: str,
    version: str,
    problems: list[str],
    expected: dict[str, int],
    have_manifest: bool,
    own: int = 0,
    unchecked: str | None = None,
) -> dict:
    """Build one package's audit record.

    Args:
        name: The PyPI distribution name.
        version: The audited version.
        problems: Packaging defects found, empty when the package is clean.
        expected: Expected stub counts by distribution name, from the manifest.
        have_manifest: Whether a manifest was loaded.
        own: Number of the package's own stubs found in the wheel.
        unchecked: Why the package could not be audited at all, when it could not be.
            Kept apart from ``problems`` so an unreachable PyPI never reads as a defect
            in a package nobody managed to look at.

    Returns:
        The record ``main`` prints, with every key it reads.
    """
    return {
        "package": name,
        "version": version,
        "own": own,
        "expected": expected.get(name, 0) if have_manifest else None,
        "problems": problems,
        "unchecked": unchecked,
    }


def audit(
    spec: str,
    workdir: Path,
    expected: dict[str, int],
    have_manifest: bool,
    roots: dict[str, str],
) -> dict:
    """Audit the stubs shipped by one package version.

    Args:
        spec: A ``name==version`` spec.
        workdir: Directory to download artifacts into.
        expected: Expected stub counts by distribution name, from the manifest.
        roots: Import roots by distribution name, from the manifest.
        have_manifest: Whether a manifest was loaded. When it was, a package absent from
            it is expected to ship no stubs at all; without one, counts go unchecked.

    Returns:
        A record with the package, version, stub count and any problems found.
    """
    name, _, version = spec.partition("==")
    root = import_root(name, roots)
    problems: list[str] = []

    try:
        artifacts = download_artifacts(name, version, workdir)
    except Exception as exc:
        # One unreachable package should not abort the audit of all the others.
        # Never reached the package, so nothing is known about its packaging.
        reason = f"could not fetch artifacts: {_exc_name(exc)}"
        return _record(
            name, version, problems, expected, have_manifest, unchecked=reason
        )
    if "wheel" not in artifacts or "sdist" not in artifacts:
        problems.append(f"missing artifact kinds: has {sorted(artifacts)}")
        return _record(name, version, problems, expected, have_manifest)

    try:
        wheel = wheel_stubs(artifacts["wheel"])
        sdist = sdist_stubs(artifacts["sdist"])
    except (
        zipfile.BadZipFile,
        tarfile.TarError,
        OSError,
        EOFError,
        zlib.error,
    ) as exc:
        # A truncated download and an artifact PyPI really serves broken look identical
        # from here, so this is unchecked rather than a defect: re-run to tell them apart.
        reason = f"could not read artifacts: {_exc_name(exc)}"
        return _record(
            name, version, problems, expected, have_manifest, unchecked=reason
        )

    def split(stubs: dict[str, bytes]) -> tuple[dict[str, bytes], dict[str, bytes]]:
        own = {k: v for k, v in stubs.items() if k.split("/")[0] == root}
        foreign = {
            k: v
            for k, v in stubs.items()
            if k.split("/")[0] != root and not k.split("/")[0].endswith(".dist-info")
        }
        return own, foreign

    wheel_own, wheel_foreign = split(wheel)
    sdist_own, sdist_foreign = split(sdist)

    if wheel_foreign:
        problems.append(
            f"wheel carries {len(wheel_foreign)} foreign stub(s): {sorted(wheel_foreign)[:3]}"
        )
    if sdist_foreign:
        problems.append(
            f"sdist carries {len(sdist_foreign)} foreign stub(s): {sorted(sdist_foreign)[:3]}"
        )

    only_wheel = sorted(set(wheel_own) - set(sdist_own))
    only_sdist = sorted(set(sdist_own) - set(wheel_own))
    if only_wheel:
        problems.append(
            f"{len(only_wheel)} stub(s) in wheel but not sdist: {only_wheel[:3]}"
        )
    if only_sdist:
        problems.append(
            f"{len(only_sdist)} stub(s) in sdist but not wheel: {only_sdist[:3]}"
        )

    differing = sorted(
        k for k in set(wheel_own) & set(sdist_own) if wheel_own[k] != sdist_own[k]
    )
    if differing:
        problems.append(
            f"{len(differing)} stub(s) differ between wheel and sdist: {differing[:3]}"
        )

    want = expected.get(name, 0) if have_manifest else None
    if want is not None and want != len(wheel_own):
        problems.append(
            f"expected {want} stub(s) from manifest, wheel ships {len(wheel_own)}"
        )

    return _record(name, version, problems, expected, have_manifest, len(wheel_own))


def main() -> int:
    """Audit every requested package and print a summary.

    Returns:
        ``1`` when any package has packaging problems, ``2`` when a package could not be
        audited and the result is indeterminate, otherwise ``0``.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("specs", nargs="+", help="package==version specs")
    parser.add_argument(
        "--manifest-ref", help="git ref to read pyi_hashes.json from for count checks"
    )
    parser.add_argument(
        "--repo", default=".", help="path to the reflex checkout (default: cwd)"
    )
    parser.add_argument("--keep", help="directory to keep downloaded artifacts in")
    args = parser.parse_args()

    expected = (
        manifest_counts(args.manifest_ref, args.repo) if args.manifest_ref else {}
    )
    # An empty result means the manifest was unreadable at that ref, so counts stay
    # unchecked rather than every package being held to a zero-stub expectation.
    have_manifest = bool(expected)
    roots = manifest_roots(args.manifest_ref, args.repo) if args.manifest_ref else {}

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(args.keep) if args.keep else Path(tmp)
        workdir.mkdir(parents=True, exist_ok=True)
        results = [
            audit(spec, workdir, expected, have_manifest, roots) for spec in args.specs
        ]

    failed = [r for r in results if r["problems"]]
    unchecked = [r for r in results if r["unchecked"]]

    width = max(len(r["package"]) for r in results)
    print(f"pyi packaging audit — {len(results)} package(s)\n")
    for r in results:
        mark = "!! " if r["problems"] else "?? " if r["unchecked"] else "OK "
        want = "" if r["expected"] is None else f" (manifest: {r['expected']})"
        print(
            f"  {mark}{r['package']:<{width}}  {r['version']:<12} stubs={r['own']}{want}"
        )
        for problem in r["problems"]:
            print(f"       - {problem}")
        if r["unchecked"]:
            print(f"       - {r['unchecked']}")

    print()
    if failed:
        print(f"FAIL: {len(failed)} package(s) with packaging problems.")
    if unchecked:
        print(f"INDETERMINATE: {len(unchecked)} package(s) could not be audited:")
        for r in unchecked:
            print(f"  - {r['package']}=={r['version']} ({r['unchecked']})")
        print("  Unaudited is not the same as broken — resolve each before releasing.")
    if not failed and not unchecked:
        total = sum(r["own"] for r in results)
        print(
            f"PASS: {total} stubs ship correctly in both wheel and sdist; no foreign stubs."
        )
    if failed:
        return 1
    return 2 if unchecked else 0


if __name__ == "__main__":
    sys.exit(main())
