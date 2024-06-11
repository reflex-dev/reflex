"""Miscellaneous functions for the experimental package."""

import asyncio


async def run_in_thread(func):
    """Run a function in a separate thread.

    Args:
        func (callable): The function to run.
    """
    await asyncio.get_event_loop().run_in_executor(None, func)
