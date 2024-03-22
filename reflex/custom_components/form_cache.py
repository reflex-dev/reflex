"""Module for managing a cache file for CLI forms."""

from __future__ import annotations

import json
import os

CACHE_FILE = ".form_cache.json"


def load_cache() -> dict[str, str]:
    """Load the cache from the cache file."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            return json.load(file)
    return {}


def save_cache(cache: dict[str, str]) -> None:
    """Save the cache to the cache file."""
    with open(CACHE_FILE, "w") as file:
        json.dump(cache, file)


def clear_cache() -> None:
    """Clear the cache file."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


class FormCacheContext:
    """Context manager for loading and saving data meant to enter on CLI with a cache."""

    def __enter__(self):
        """Load the cache and return it."""
        self.cache = load_cache()
        return self.cache

    def __exit__(self, exc_type, _exc_val, _exc_tb):
        """Save the cache if exit normally."""
        save_cache(self.cache)
        if exc_type != KeyboardInterrupt:
            clear_cache()
        return False
