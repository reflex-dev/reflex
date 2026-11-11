import reflex as rx

# verifier guard: only ever run from one of the verify_cm venvs (PyPI installs)
assert "/envs/vcm-" in rx.__file__, rx.__file__

config = rx.Config(app_name="refsrepro", plugins=[rx.plugins.RadixThemesPlugin()], disable_plugins=[rx.plugins.SitemapPlugin])
