"""State-related constants."""

from enum import Enum


class StateManagerMode(str, Enum):
    """State manager constants."""

    DISK = "disk"
    MEMORY = "memory"
    REDIS = "redis"
