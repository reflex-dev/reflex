"""State-related constants."""

from enum import Enum


class StateManagerMode(str, Enum):
    """State manager constants."""

    DISK = "disk"
    MEMORY = "memory"
    REDIS = "redis"


# Used for things like console_log, etc.
FRONTEND_EVENT_STATE = "__reflex_internal_frontend_event_state"
