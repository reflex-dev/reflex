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
# Key on the frontend `refs` object that the mounted ClientStateProvider
# publishes its store on. This is the one Python-side definition; the frontend's
# is `CLIENT_STATE_REF` in `.templates/web/utils/client_state.js`, which every
# other frontend reader imports. The two are asserted equal by
# `tests/js/client_state.test.js`, so a rename on either side fails loudly.
CLIENT_STATE_REF = "__client_state"
