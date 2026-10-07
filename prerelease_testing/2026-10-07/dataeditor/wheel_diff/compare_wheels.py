"""Download published component wheels and compare Python sources without installing."""

import argparse
import difflib
import email
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

assert "/envs/driver/" in sys.executable, sys.executable

PAIRS = {
    "reflex-components-dataeditor": ("0.9.3.post1", "0.10.0a1"),
    "reflex-components-react-player": ("0.9.2", "0.10.0a1"),
    "reflex-components-sonner": ("0.9.4", "0.10.0a1"),
    "reflex-components-lucide": ("1.0.4", "1.1.0a1"),
}


def read_wheel(wheel):
    """Read Python source and package metadata from a wheel without executing it.

    Args:
        wheel: Wheel path.

    Returns:
        Python sources, selected metadata, and substantive member hashes.
    """
    with zipfile.ZipFile(wheel) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
        source = {name: data.decode("utf-8") for name, data in files.items() if name.endswith(".py")}
        metadata = email.message_from_bytes(next(data for name, data in files.items() if name.endswith(".dist-info/METADATA")))
        return source, {
            "filename": wheel.name,
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "version": metadata["Version"],
            "requires_python": metadata["Requires-Python"],
            "requires_dist": metadata.get_all("Requires-Dist", []),
        }, {
            name: hashlib.sha256(data).hexdigest()
            for name, data in files.items()
            if ".dist-info/" not in name
        }


def main():
    """Download each exact version and write deterministic source diffs and metadata."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.downloads.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for package, versions in PAIRS.items():
        wheels = []
        for version in versions:
            directory = args.downloads / package / version
            directory.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, "-m", "pip", "download", "--index-url", "https://pypi.org/simple",
                       "--no-deps", "--only-binary=:all:", "--dest", str(directory), f"{package}=={version}"]
            process = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            (args.out / f"{package}-{version}.download.log").write_text(process.stdout)
            process.check_returncode()
            wheels.append(next(directory.glob("*.whl")))
        before, old_metadata, old_members = read_wheel(wheels[0])
        after, new_metadata, new_members = read_wheel(wheels[1])
        changed = []
        diffs = []
        for name in sorted(before.keys() | after.keys()):
            old, new = before.get(name, ""), after.get(name, "")
            if old != new:
                changed.append(name)
                diffs.extend(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                                fromfile=f"{versions[0]}/{name}", tofile=f"{versions[1]}/{name}"))
        (args.out / f"{package}.py.diff").write_text("".join(diffs))
        summary[package] = {
            "before": old_metadata,
            "after": new_metadata,
            "python_files_before": len(before),
            "python_files_after": len(after),
            "changed_python_files": changed,
            "changed_non_python_members": sorted(name for name in old_members.keys() | new_members.keys()
                                                 if not name.endswith(".py") and old_members.get(name) != new_members.get(name)),
        }
        print(f"{package}: {len(changed)} changed Python files", flush=True)
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
