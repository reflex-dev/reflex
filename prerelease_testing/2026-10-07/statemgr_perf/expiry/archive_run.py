"""Copy complete compact evidence without generated apps or state files."""

import argparse
import gzip
import shutil
from pathlib import Path


def main():
    """Archive one completed run into a fresh directory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if not (args.source / "run.json").exists():
        raise RuntimeError("Source is not a completed browser run")
    args.destination.mkdir(parents=True, exist_ok=False)
    for path in args.source.iterdir():
        if path.suffix in {".gz", ".png"} or path.name == "run.json":
            shutil.copy2(path, args.destination / path.name)
        elif path.suffix == ".json":
            (args.destination / (path.name + ".gz")).write_bytes(
                gzip.compress(path.read_bytes(), mtime=0)
            )


if __name__ == "__main__":
    main()
