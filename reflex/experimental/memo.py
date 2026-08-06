"""Deprecated alias for :mod:`reflex_base.components.memo`."""

import sys

from reflex_base.components import memo

from reflex.experimental import ExperimentalNamespace

ExperimentalNamespace.register_component_warning("memo")

sys.modules[__name__] = memo  # pyright: ignore[reportArgumentType]
