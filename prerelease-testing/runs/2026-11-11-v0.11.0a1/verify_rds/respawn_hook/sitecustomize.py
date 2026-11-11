"""Test-only hook: make granian respawn failed workers (granian's own option, default False)."""
try:
    import granian.server.common as _c

    _orig = _c.AbstractServer.__init__

    def _init(self, *a, **kw):
        kw["respawn_failed_workers"] = True
        _orig(self, *a, **kw)

    _c.AbstractServer.__init__ = _init
except Exception:  # noqa: BLE001
    pass
