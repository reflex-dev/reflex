"""State-related constants."""

from enum import Enum


class StateManagerMode(str, Enum):
    """State manager constants."""

    DISK = "disk"
    MEMORY = "memory"
    REDIS = "redis"


FIELD_MARKER = "_rx_state_"
MEMO_MARKER = "_rx_memo_"
CAMEL_CASE_MEMO_MARKER = "RxMemo"
# Suffix on the JS identifier a ClientStateVar binds its value to, so a user-chosen
# name can never collide with a JS reserved word (`class`, `const`, ...).
CAMEL_CASE_CLIENT_STATE_MARKER = "RxClientState"
