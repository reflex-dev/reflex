"""Pin AppHarness to this agent's reserved ports (5384-5385 / 9784-9785).

AppHarness normally binds ephemeral ports (uvicorn port=0, frontend PORT=0).
The pre-release testing rules reserve a port range per agent, so both are
redirected here without touching the framework.
"""

import subprocess

try:
    import uvicorn
except ImportError:  # bare install (0.9.10.post2): let the test module report it
    uvicorn = None

RESERVED = iter([9784, 5384, 9785, 5385, 9786, 5386])

_orig_config = uvicorn.Config if uvicorn is not None else object


class _PinnedConfig(_orig_config):  # type: ignore[misc]
    def __init__(self, *args, **kwargs):
        if kwargs.get("port") == 0:
            kwargs["port"] = next(RESERVED)
        super().__init__(*args, **kwargs)


if uvicorn is not None:
    uvicorn.Config = _PinnedConfig

_orig_popen = subprocess.Popen


class _PinnedPopen(_orig_popen):
    def __init__(self, *args, **kwargs):
        env = kwargs.get("env")
        if env is not None and env.get("PORT") == "0":
            env = dict(env)
            env["PORT"] = str(next(RESERVED))
            kwargs["env"] = env
        super().__init__(*args, **kwargs)


subprocess.Popen = _PinnedPopen
