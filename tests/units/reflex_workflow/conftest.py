"""Skip the workflow tests where SQLAlchemy is not installed.

reflex-workflow is built on SQLAlchemy, and CI also runs the unit tests with the
database libraries uninstalled to check that reflex works without them.
"""

import importlib.util

collect_ignore_glob = [] if importlib.util.find_spec("sqlalchemy") else ["*"]
