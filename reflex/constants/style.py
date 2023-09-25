"""Style constants."""

import os
from types import SimpleNamespace

from reflex.constants.base import DIRS

# The directory where styles are located.
STYLES_DIR = os.path.join(DIRS.WEB, "styles")


class TAILWIND(SimpleNamespace):
    """Tailwind constants."""

    # The Tailwindcss version
    VERSION = "tailwindcss@^3.3.2"
    # The Tailwind config.
    CONFIG = os.path.join(DIRS.WEB, "tailwind.config.js")
    # Default Tailwind content paths
    CONTENT = ["./pages/**/*.{js,ts,jsx,tsx}"]
    # Relative tailwind style path to root stylesheet in STYLES_DIR.
    ROOT_STYLE_PATH = "./tailwind.css"
