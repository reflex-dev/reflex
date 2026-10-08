"""N-004 disk store: one version writes a session through StateManagerDisk, another reads the same directory.

Usage (cwd = this dir, REFLEX_STATES_WORKDIR=<shared dir>):
  <venv>/bin/python -I disk_probe.py <venv> save|load|step <client-token>
save: fresh session -> login, count+=1, history, _visits, child note; load: report what is found; step: load + mutate + save again.
"""
import asyncio
import os
import sys
import warnings

sys.path.insert(0, os.getcwd())
import reflex as rx  # noqa: E402

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

from reflex.istate.manager.disk import StateManagerDisk  # noqa: E402

from diskstate import DiskChild, DiskFleet  # noqa: E402

warnings.simplefilter("ignore")
VER = version("reflex")
mode, client = sys.argv[2], sys.argv[3]


async def main():
    mgr = StateManagerDisk()
    tok = f"{client}_{DiskChild.get_full_name()}"
    async with mgr.modify_state(tok) as root:
        f = await root.get_state(DiskFleet)
        c = await root.get_state(DiskChild)
        found = f"user={f.user!r} count={f.count} history={list(f.history)} _visits={f._visits} child.note={c.note!r}"
        if mode in ("save", "step"):
            f.user = "alice"
            f.count += 1
            f._visits += 1
            f.history.append(f"{VER}:{f.count}:v{f._visits}")
            c.note = f"by {VER}"
    await mgr.close()
    files = sorted(p.name for p in mgr.states_directory.iterdir())
    print(f"reflex {VER} {mode}: found {found} | files={len(files)}")


asyncio.run(main())
