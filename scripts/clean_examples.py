#!/usr/bin/env python3
"""Script to clean up the examples directory.

This script helps developers maintain a clean development environment by removing
the examples directory and its contents. This is useful when switching between
different example apps or when wanting to start fresh.
"""

import shutil
from pathlib import Path


def clean_examples():
    """Remove the examples directory and its contents."""
    examples_dir = Path(__file__).parent.parent / "examples"
    if examples_dir.exists():
        print(f"Removing examples directory at {examples_dir}")
        shutil.rmtree(examples_dir)
        print("Examples directory removed successfully.")
    else:
        print("No examples directory found.")


if __name__ == "__main__":
    clean_examples()
