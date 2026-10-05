"""Inventory changelog heads and audit distributions downloaded from PyPI."""

import argparse
import concurrent.futures
import hashlib
import io
import json
import re
import subprocess
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


def git_read(repo: Path, *args: str) -> str:
    """Read release source without importing or installing it.

    Args:
        repo: Source repository.
        *args: Git arguments.

    Returns:
        Command output.
    """
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)


def fetch_json(url: str) -> dict:
    """Read a public JSON document.

    Args:
        url: Public metadata URL.

    Returns:
        Decoded document.
    """
    with urllib.request.urlopen(url, timeout=45) as response:
        return json.load(response)


def audit_package(entry: dict) -> dict:
    """Check publication and inspect published wheel and sdist contents.

    Args:
        entry: Changelog package record.

    Returns:
        Publication and archive audit record.
    """
    result = dict(entry)
    try:
        metadata = fetch_json(
            f"https://pypi.org/pypi/{entry['package']}/{entry['version']}/json"
        )
    except urllib.error.HTTPError as error:
        result.update(
            status="missing" if error.code == 404 else "unverified", error=str(error)
        )
        return result
    except Exception as error:
        result.update(status="unverified", error=str(error))
        return result
    result.update(
        status="published",
        requires_python=metadata["info"]["requires_python"],
        requires_dist=metadata["info"]["requires_dist"],
        files=[],
    )
    stub_sets = {}
    for dist in metadata["urls"]:
        record = {
            key: dist[key]
            for key in ("filename", "url", "size", "upload_time_iso_8601", "yanked")
        }
        record["sha256"] = dist["digests"]["sha256"]
        if not entry["alpha"]:
            result["files"].append(record)
            continue
        with urllib.request.urlopen(dist["url"], timeout=90) as response:
            content = response.read()
        record["digest_matches"] = (
            hashlib.sha256(content).hexdigest() == record["sha256"]
        )
        if dist["filename"].endswith(".whl"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = archive.namelist()
                stubs = {
                    name: hashlib.sha256(archive.read(name)).hexdigest()
                    for name in names
                    if name.endswith(".pyi")
                }
                direct_urls = [
                    name for name in names if name.endswith("direct_url.json")
                ]
        elif dist["filename"].endswith(".tar.gz"):
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
                names = archive.getnames()
                stubs = {}
                for name in names:
                    if name.endswith(".pyi"):
                        relative = name.split("/", 1)[1].removeprefix("src/")
                        stubs[relative] = hashlib.sha256(
                            archive.extractfile(name).read()
                        ).hexdigest()
                direct_urls = []
        else:
            result["files"].append(record)
            continue
        record.update(
            stub_count=len(stubs),
            direct_urls=direct_urls,
            generated_artifacts=[
                name
                for name in names
                if any(
                    part in name.split("/")
                    for part in (".web", "node_modules", ".venv", ".states")
                )
            ],
        )
        stub_sets[dist["packagetype"]] = stubs
        result["files"].append(record)
    if "bdist_wheel" in stub_sets and "sdist" in stub_sets:
        wheel, sdist = stub_sets["bdist_wheel"], stub_sets["sdist"]
        result["stub_audit"] = {
            "wheel_only": sorted(wheel.keys() - sdist.keys()),
            "sdist_only": sorted(sdist.keys() - wheel.keys()),
            "content_mismatch": sorted(
                name
                for name in wheel.keys() & sdist.keys()
                if wheel[name] != sdist[name]
            ),
            "wheel_names": sorted(wheel),
        }
    return result


def main() -> None:
    """Write a reproducible release inventory and PyPI audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--primary-ref", default="origin/r/pre-2026.10.05-37378928999")
    parser.add_argument("--tooling-ref", default="origin/r/pre-2026.10.05-37379302664")
    parser.add_argument("--enterprise-version", default="0.9.7a2")
    args = parser.parse_args()
    primary = args.primary_ref
    tooling = args.tooling_ref
    paths = [
        path
        for path in git_read(
            args.repo, "ls-tree", "-r", "--name-only", primary
        ).splitlines()
        if path.endswith("CHANGELOG.md")
    ]
    entries = []
    for path in paths:
        package = "reflex" if path == "CHANGELOG.md" else path.split("/")[-2]
        ref = (
            tooling if package in ("reflex-release", "reflex-hosting-cli") else primary
        )
        text = git_read(args.repo, "show", f"{ref}:{path}")
        start = re.search(r"^## v([^ ]+)", text, re.MULTILINE)
        version = start.group(1)
        head = re.split(r"\n## v", text[start.start() :], maxsplit=1)[0].strip()
        entries.append(
            {
                "package": package,
                "version": version,
                "alpha": "a" in version,
                "ref": ref,
                "source_sha": git_read(args.repo, "rev-parse", ref).strip(),
                "path": path,
                "changelog": head,
                "prs": sorted(set(re.findall(r"https://github.com/[^)\s]+", head))),
            }
        )
    entries.append(
        {
            "package": "reflex-enterprise",
            "version": args.enterprise_version,
            "alpha": True,
            "ref": "r/pre-2026.10.05",
            "path": "CHANGELOG.md",
            "changelog": "User-specified enterprise release; see enterprise report.",
            "prs": [],
        }
    )
    args.output.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        audited = list(pool.map(audit_package, entries))
    manifest = json.loads(git_read(args.repo, "show", f"{primary}:pyi_hashes.json"))
    comparisons = []
    for entry in audited:
        if not entry["alpha"] or entry["package"] == "reflex-enterprise":
            continue
        prefix = (
            "" if entry["package"] == "reflex" else f"packages/{entry['package']}/src/"
        )
        expected = {
            path.removeprefix(prefix)
            for path in manifest
            if path.startswith(prefix or "reflex/")
        }
        actual = set(entry.get("stub_audit", {}).get("wheel_names", []))
        comparisons.append(
            {
                "package": entry["package"],
                "expected_count": len(expected),
                "actual_count": len(actual),
                "missing": sorted(expected - actual),
                "unexpected": sorted(actual - expected),
            }
        )
    (args.output / "manifest-audit.json").write_text(
        json.dumps(comparisons, indent=2) + "\n"
    )
    (args.output / "inventory.json").write_text(json.dumps(audited, indent=2) + "\n")
    (args.output / "alpha-requirements.txt").write_text(
        "".join(
            f"{entry['package']}=={entry['version']}\n"
            for entry in entries
            if entry["alpha"]
        )
    )
    (args.output / "changelog-heads.md").write_text(
        "\n\n".join(
            f"# {entry['package']} ({entry['ref']})\n\n{entry['changelog']}"
            for entry in entries
        )
    )
    for entry in audited:
        print(
            entry["package"],
            entry["version"],
            entry["status"],
            [
                (file["filename"], file.get("stub_count"))
                for file in entry.get("files", [])
            ],
        )


if __name__ == "__main__":
    main()
