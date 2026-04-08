"""A list of whitelist paths that should be built.
If the list is empty, all pages will be built.

Tips:
- Ensure that the path starts with a forward slash '/'.
- Do not include a trailing slash '/' at the end of the path.

Examples:
- Correct: WHITELISTED_PAGES = ["/blog/enterprise-ready-ai-app-builder"]
- Incorrect: WHITELISTED_PAGES = ["/blog/enterprise-ready-ai-app-builder/"]
"""

WHITELISTED_PAGES = []


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
