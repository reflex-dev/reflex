"""Unit tests for lifespan mixin behavior."""

from __future__ import annotations

import asyncio

import pytest
from starlette.applications import Starlette

from reflex.app_mixins.lifespan import LifespanMixin


@pytest.mark.asyncio
async def test_lifespan_task_app_param_receives_reflex_app_instance():
    """Lifespan tasks should receive the Reflex app instance, not Starlette."""

    class DummyApp(LifespanMixin):
        """Minimal test app based on the lifespan mixin."""

    app = DummyApp()
    received: dict[str, object] = {}

    def lifespan_task(app):
        """Record the app argument injected by the lifespan runner.

        Args:
            app: App object injected by the lifespan runner.
        """
        received["app"] = app

    app.register_lifespan_task(lifespan_task)

    async with app._run_lifespan_tasks(Starlette()):
        await asyncio.sleep(0)

    assert received["app"] is app
