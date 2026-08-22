"""Handle client side state with `useClientState`.

Deprecated location. The implementation moved to
:mod:`reflex_base.client_state` and is exposed as ``rx.client_state``; this
module re-exports it so existing imports keep working.
"""

from __future__ import annotations

from reflex_base.client_state import ClientStateVar as ClientStateVar
from reflex_base.client_state import NoValue as NoValue
from reflex_base.client_state import client_state as client_state

__all__ = ["ClientStateVar", "NoValue", "client_state"]
