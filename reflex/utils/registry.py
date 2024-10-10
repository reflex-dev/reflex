"""Utilities for working with registries."""

import os

import httpx

from reflex.utils import console, net


def latency(registry: str) -> int:
    """Get the latency of a registry.

    Args:
        registry (str): The URL of the registry.

    Returns:
        int: The latency of the registry in microseconds.
    """
    try:
        return net.get(registry).elapsed.microseconds
    except httpx.HTTPError:
        console.info(f"Failed to connect to {registry}.")
        return 10_000_000


def average_latency(registry, attempts: int = 3) -> int:
    """Get the average latency of a registry.

    Args:
        registry (str): The URL of the registry.
        attempts (int): The number of attempts to make. Defaults to 10.

    Returns:
        int: The average latency of the registry in microseconds.
    """
    return sum(latency(registry) for _ in range(attempts)) // attempts


def get_best_registry() -> str:
    """Get the best registry based on latency.

    Returns:
        str: The best registry.
    """
    registries = [
        "https://registry.npmjs.org",
        "https://r.cnpmjs.org",
    ]

    return min(registries, key=average_latency)


def _get_npm_registry() -> str:
    """Get npm registry. If environment variable is set, use it first.

    Returns:
        str:
    """
    if npm_registry := os.environ.get("NPM_CONFIG_REGISTRY", ""):
        return npm_registry
    else:
        return get_best_registry()
