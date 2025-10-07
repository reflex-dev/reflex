"""State-related constants."""

from enum import Enum


class StateManagerMode(str, Enum):
    """State manager constants."""

    DISK = "disk"
    MEMORY = "memory"
    REDIS = "redis"


# Used for things like console_log, etc.
FRONTEND_EVENT_STATE = "__reflex_internal_frontend_event_state"

FIELD_MARKER = "_rx_state_"
MEMO_MARKER = "_rx_memo_"
CAMEL_CASE_MEMO_MARKER = "RxMemo"
