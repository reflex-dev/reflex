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


@pytest.mark.asyncio
async def test_lifespan_task_starlette_app_param_receives_starlette_instance():
    """Lifespan tasks should receive the Starlette app when requested."""

    class DummyApp(LifespanMixin):
        """Minimal test app based on the lifespan mixin."""

    app = DummyApp()
    received: dict[str, object] = {}
    starlette_app = Starlette()

    def lifespan_task(starlette_app):
        """Record the Starlette app argument injected by the lifespan runner.

        Args:
            starlette_app: Starlette app object injected by the lifespan runner.
        """
        received["starlette_app"] = starlette_app

    app.register_lifespan_task(lifespan_task)

    async with app._run_lifespan_tasks(starlette_app):
        await asyncio.sleep(0)

    assert received["starlette_app"] is starlette_app


@pytest.mark.asyncio
async def test_lifespan_task_both_app_and_starlette_app_params_are_injected():
    """Lifespan tasks should receive both app and starlette_app when declared."""

    class DummyApp(LifespanMixin):
        """Minimal test app based on the lifespan mixin."""

    app = DummyApp()
    received: dict[str, object] = {}
    starlette_app = Starlette()

    def lifespan_task(app, starlette_app):
        """Record both injected app objects from the lifespan runner.

        Args:
            app: Reflex app object injected by the lifespan runner.
            starlette_app: Starlette app object injected by the lifespan runner.
        """
        received["app"] = app
        received["starlette_app"] = starlette_app

    app.register_lifespan_task(lifespan_task)

    async with app._run_lifespan_tasks(starlette_app):
        await asyncio.sleep(0)

    assert received["app"] is app
    assert received["starlette_app"] is starlette_app
