import sys
from pathlib import Path

import reflex as rx

nba_app_path = Path("../nba").resolve()
if str(nba_app_path) not in sys.path:
    sys.path.insert(0, str(nba_app_path))


config = rx.Config(
    app_name="nba_proxy",
    app_module_import="nba.nba",
    tailwind=None,
)
