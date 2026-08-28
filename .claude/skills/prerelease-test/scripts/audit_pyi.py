#!/usr/bin/env python3
"""Audit that published packages ship their generated .pyi stubs correctly.

For each package it downloads the wheel and the sdist from PyPI and checks:

  * the package ships stubs for its own modules in BOTH artifacts,
  * those stubs are byte-identical between wheel and sdist,
  * no artifact carries stubs belonging to a different package,
  * per-package stub counts match the repo's pyi_hashes.json manifest (optional).

Stub *content* legitimately differs from the committed manifest hashes because the build
hook regenerates stubs at release time, so this compares presence and counts rather than
hashes. A package with no manifest entries is expected to ship no stubs.

Usage:
    audit_pyi.py reflex==0.9.9 reflex-base==0.9.9
    check_release_versions.py --ref origin/main --specs | xargs audit_pyi.py --manifest-ref origin/main
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path


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
        if kind not in ("bdist_wheel", "sdist"):
            continue
        path = dest / entry["filename"]
        if not path.exists():
            urllib.request.urlretrieve(entry["url"], path)
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


def import_root(dist_name: str) -> str:
    """Guess the top-level import package for a distribution name.

    Args:
        dist_name: The PyPI distribution name.

    Returns:
        The import package name, which differs only by underscores by convention.
    """
    return dist_name.replace("-", "_")


def manifest_counts(ref: str, repo: str) -> dict[str, int]:
    """Count the stubs each distribution is expected to ship.

    Args:
        ref: The git ref to read ``pyi_hashes.json`` from.
        repo: Path to the reflex checkout.

    Returns:
        A mapping of distribution name to expected stub count, empty when the manifest is
        unavailable at that ref.
    """
    result = subprocess.run(
        ["git", "-C", repo, "show", f"{ref}:pyi_hashes.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {}
    counts: collections.Counter[str] = collections.Counter()
    for key in json.loads(result.stdout):
        # "packages/<dist>/src/<pkg>/x.pyi" or a root-package path like "reflex/x.pyi"
        counts[key.split("/")[1] if key.startswith("packages/") else "reflex"] += 1
    return dict(counts)


def audit(spec: str, workdir: Path, expected: dict[str, int]) -> dict:
    """Audit the stubs shipped by one package version.

    Args:
        spec: A ``name==version`` spec.
        workdir: Directory to download artifacts into.
        expected: Expected stub counts by distribution name, from the manifest.

    Returns:
        A record with the package, version, stub count and any problems found.
    """
    name, _, version = spec.partition("==")
    root = import_root(name)
    problems: list[str] = []

    artifacts = download_artifacts(name, version, workdir)
    if "wheel" not in artifacts or "sdist" not in artifacts:
        problems.append(f"missing artifact kinds: has {sorted(artifacts)}")
        return {"package": name, "version": version, "problems": problems, "own": 0}

    wheel = wheel_stubs(artifacts["wheel"])
    sdist = sdist_stubs(artifacts["sdist"])

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

    want = expected.get(name)
    if want is not None and want != len(wheel_own):
        problems.append(
            f"expected {want} stub(s) from manifest, wheel ships {len(wheel_own)}"
        )

    return {
        "package": name,
        "version": version,
        "own": len(wheel_own),
        "expected": want,
        "problems": problems,
    }


def main() -> int:
    """Audit every requested package and print a summary.

    Returns:
        ``1`` when any package has packaging problems, otherwise ``0``.
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

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(args.keep) if args.keep else Path(tmp)
        workdir.mkdir(parents=True, exist_ok=True)
        results = [audit(spec, workdir, expected) for spec in args.specs]

    width = max(len(r["package"]) for r in results)
    print(f"pyi packaging audit — {len(results)} package(s)\n")
    for r in results:
        mark = "OK " if not r["problems"] else "!! "
        want = "" if r["expected"] is None else f" (manifest: {r['expected']})"
        print(
            f"  {mark}{r['package']:<{width}}  {r['version']:<12} stubs={r['own']}{want}"
        )
        for problem in r["problems"]:
            print(f"       - {problem}")

    failed = [r for r in results if r["problems"]]
    print()
    if failed:
        print(f"FAIL: {len(failed)} package(s) with packaging problems.")
    else:
        total = sum(r["own"] for r in results)
        print(
            f"PASS: {total} stubs ship correctly in both wheel and sdist; no foreign stubs."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
