"""Show that HTTPCookie's route only appears when the *serving* process compiles.

Run from an app dir with the app's venv python. Simulates the granian worker's
App.__call__ factory with and without the `.web/nocompile` marker that
`reflex.utils.exec.run_backend` drops before spawning the dev worker.
"""

import pathlib
import sys

import reflex

assert "/envs/verify2_ent_mcp_oidc_0" in reflex.__file__, reflex.__file__
print("reflex:", reflex.__file__)

sys.path.insert(0, ".")
from reflex.utils.prerequisites import get_and_validate_app  # noqa: E402

app, _mod = get_and_validate_app()


def cookie_routes():
    return [
        getattr(r, "path", None)
        for r in app._api.routes
        if "cookies" in str(getattr(r, "path", ""))
    ]


print("1. after import only          :", cookie_routes())

nocompile = pathlib.Path(".web/nocompile")
nocompile.touch()
app()  # what granian's dev worker does on first spawn
print("2. factory call w/ nocompile  :", cookie_routes(), "(nocompile existed)")

app()  # what granian's worker does after a hot reload (and what prod does)
print("3. factory call w/o nocompile :", cookie_routes())
