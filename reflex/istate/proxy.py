"""Re-export from reflex_base."""

import sys

from reflex_base.state import proxy
from reflex_base.state.proxy import *  # pyright: ignore[reportWildcardImportFromLibrary]

sys.modules[__name__] = proxy  # pyright: ignore[reportArgumentType]
