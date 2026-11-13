"""A list of whitelist paths that should be built.
If the list is empty, all pages will be built.

Tips:
- Ensure that the path starts with a forward slash '/'.
- Do not include a trailing slash '/' at the end of the path.

Examples:
- Correct: WHITELISTED_PAGES = ["/getting-started/introduction"]
- Incorrect: WHITELISTED_PAGES = ["/getting-started/introduction/"]

The REFLEX_DOCS_WHITELIST environment variable, a comma-separated list of
paths, replaces the list below, and set empty, builds all pages (the docs demo
tests use it to compile only the pages they visit).
"""

import os

WHITELISTED_PAGES = []

if (_env_pages := os.environ.get("REFLEX_DOCS_WHITELIST")) is not None:
    WHITELISTED_PAGES = _env_pages.split(",") if _env_pages else []


def _check_whitelisted_path(path: str):
    if len(WHITELISTED_PAGES) == 0:
        return True

    # If the path is the root, always build it.
    if path == "/":
        return True

    if len(WHITELISTED_PAGES) == 1 and WHITELISTED_PAGES[0] == "/":
        return False

    for whitelisted_path in WHITELISTED_PAGES:
        if path.startswith(whitelisted_path):
            return True

    return False
