"""#6933: _load_config() must emit a DeprecationWarning naming its replacement."""
import sys
import warnings

import reflex  # noqa: F401
assert "/envs/" in reflex.__file__, reflex.__file__
from reflex_base import config as rxconf  # noqa: E402

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    cfg = rxconf._load_config()
print("app_name:", cfg.app_name)
print("warnings captured:", len(caught))
for w in caught:
    print(f"  {w.category.__name__}: {w.message}")
# console.deprecate may print to the log instead of the warnings module; show both.
