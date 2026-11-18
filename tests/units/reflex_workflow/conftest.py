"""Shared setup for the workflow tests.

reflex-workflow is built on SQLAlchemy, and CI also runs the unit tests with the
database libraries uninstalled to check that reflex works without them, so these
are skipped wholesale where it is missing.
"""

import importlib.util

import pytest

collect_ignore_glob = [] if importlib.util.find_spec("sqlalchemy") else ["*"]


@pytest.fixture(scope="module", autouse=True)
def _forget_the_tables_a_module_declares(request):
    """Leave the workflow registry without this module's own tables in it.

    A workflow class stays registered for the life of the process, and a worker
    told no workflows runs every workflow in the registry, against a database
    that may never have had those tables. This clears away the ones a module
    declared while its own tests ran, such as inside a test function.

    It cannot help with the ones declared at module level: pytest imports every
    test module while it collects, so those are all registered before the first
    test runs. A worker in a test is given the workflows it is meant to run.

    Only the classes declared by the module being torn down are removed, so a
    module keeps the ones it declared itself, and workflows shared between
    modules -- the examples -- stay registered for all of them.

    Args:
        request: The fixture's context, which names the module.

    Yields:
        Nothing; the registry is cleaned up afterwards.
    """
    yield
    from reflex_workflow.model import REGISTRY

    name = request.module.__name__
    for table, cls in list(REGISTRY.items()):
        if cls.__module__ == name:
            del REGISTRY[table]
