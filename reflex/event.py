"""Re-export from reflex_core."""

import sys

from reflex_core.event import *  # pyright: ignore[reportWildcardImportFromLibrary]
from reflex_core.event import event

sys.modules[__name__] = event  # pyright: ignore[reportArgumentType]
