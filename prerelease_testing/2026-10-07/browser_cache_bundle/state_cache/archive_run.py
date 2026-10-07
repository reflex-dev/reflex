"""Retain compressed browser evidence and selected screenshots from a completed run."""

import argparse
import gzip
import shutil
from pathlib import Path


def main():
    """Copy all structured evidence while keeping the campaign artifact bounded."""
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    for path in args.source.iterdir():
        if path.name.endswith(".gz") or path.name == "run.json":
            shutil.copy2(path, args.destination / path.name)
        elif path.name.endswith("-results.json"):
            (args.destination / (path.name + ".gz")).write_bytes(
                gzip.compress(path.read_bytes(), mtime=0)
            )
        elif args.screenshots and (
            path.name.endswith("-a-dict_values.png")
            or path.name.endswith("-mutated.png")
        ):
            shutil.copy2(path, args.destination / path.name)


if __name__ == "__main__":
    main()
