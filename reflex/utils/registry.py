"""Utilities for working with registries."""

from pathlib import Path

from reflex.environment import environment
from reflex.utils import console, net
from reflex.utils.decorator import cache_result_in_disk, once


def latency(registry: str) -> int:
    """Get the latency of a registry.

    Args:
        registry (str): The URL of the registry.

    Returns:
        int: The latency of the registry in microseconds.
    """
    import httpx

    try:
        time_to_respond = net.get(registry, timeout=2).elapsed.microseconds
    except httpx.HTTPError:
        console.info(f"Failed to connect to {registry}.")
        return 10_000_000
    else:
        console.debug(f"Latency of {registry}: {time_to_respond}")
        return time_to_respond


def average_latency(registry: str, attempts: int = 3) -> int:
    """Get the average latency of a registry.

    Args:
        registry: The URL of the registry.
        attempts: The number of attempts to make. Defaults to 10.

    Returns:
        The average latency of the registry in microseconds.
    """
    registry_latency = sum(latency(registry) for _ in range(attempts)) // attempts
    console.debug(f"Average latency of {registry}: {registry_latency}")
    return registry_latency


def _best_registry_file_path() -> Path:
    """Get the file path for the best registry cache.

    Returns:
        The file path for the best registry cache.
    """
    return environment.REFLEX_DIR.get() / "reflex_best_registry.cached"


@cache_result_in_disk(cache_file_path=_best_registry_file_path)
def _get_best_registry() -> str:
    """Get the best registry based on latency.

    Returns:
        The best registry.
    """
    console.debug("Getting best registry...")
    registries = [
        ("https://registry.npmjs.org", 1),
        ("https://registry.npmmirror.com", 2),
    ]

    best_registry = min(registries, key=lambda x: average_latency(x[0]) * x[1])[0]
    console.debug(f"Best registry: {best_registry}")
    return best_registry


@once
def get_npm_registry() -> str:
    """Get npm registry. If environment variable is set, use it first.

    Returns:
        The npm registry.
    """
    return environment.NPM_CONFIG_REGISTRY.get() or _get_best_registry()
