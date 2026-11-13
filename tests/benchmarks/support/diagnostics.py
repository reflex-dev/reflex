"""Diagnostic artifacts captured after severe event-loop lag."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import traceback
from pathlib import Path
from typing import Any


def capture_async_diagnostics(
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Capture task and thread stacks in a JSON artifact.

    Args:
        path: Destination path.
        metadata: Scenario-specific queue, stage, or lag metadata.

    Returns:
        Resolved artifact path.
    """
    tasks = []
    for task in asyncio.all_tasks():
        tasks.append({
            "name": task.get_name(),
            "done": task.done(),
            "cancelled": task.cancelled(),
            "stack": traceback.StackSummary.extract(
                (frame, frame.f_lineno) for frame in task.get_stack()
            ).format(),
        })
    frames = sys._current_frames()  # pyright: ignore [reportPrivateUsage]
    threads = []
    for thread in threading.enumerate():
        frame = frames.get(thread.ident) if thread.ident is not None else None
        threads.append({
            "name": thread.name,
            "ident": thread.ident,
            "daemon": thread.daemon,
            "stack": traceback.format_stack(frame) if frame is not None else [],
        })
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {"metadata": metadata or {}, "tasks": tasks, "threads": threads},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination
