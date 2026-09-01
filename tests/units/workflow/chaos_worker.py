"""A real worker for the chaos soak: it serves until it is killed.

Usage: ``chaos_worker.py <store-target> <schema>``. The store target is a
Postgres URL or a SQLite path; the schema applies to Postgres only. The
process never exits on its own -- the driver SIGKILLs it at random while it
holds claims, which is the whole point.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from reflex.workflow.runtime import WorkflowRuntime
from tests.units.workflow.chaos_flows import WORKFLOWS, open_store


async def main() -> None:
    """Serve every chaos workflow until killed."""
    target, schema = sys.argv[1], sys.argv[2]
    runtime = WorkflowRuntime(
        open_store(target, schema),
        lease_duration=1.0,
        lease_renew_interval=0.3,
        recovery_interval=0.3,
        poll_interval=0.05,
        max_concurrency=4,
        alerts=None,
    )
    for workflow_cls in WORKFLOWS:
        runtime.register(workflow_cls)
    await runtime.startup(start_worker=True)
    await asyncio.Event().wait()


asyncio.run(main())
