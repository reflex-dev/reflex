"""Sibling module imported by rxconfig.py -- used to test PR #7075."""

import itertools
import logging
import os

_counter = itertools.count()
IMPORT_ID = next(_counter)

logging.getLogger("dsc.settings").warning(
    "SETTINGS_IMPORT module_id=%s pid=%s import_n=%s",
    id(_counter),
    os.getpid(),
    IMPORT_ID,
)


class SettingsMarker:
    """A class defined in the rxconfig-imported module; must not be duplicated."""

    APP_TITLE = "dsc"


MARKER_CLASS_ID = id(SettingsMarker)
