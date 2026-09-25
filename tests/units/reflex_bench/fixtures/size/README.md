# Exported first pages

The `index.html` that `reflex export` prerenders for `examples/playground`,
used by the `size.export` tests to check which files count as the first page's
JavaScript and CSS. Each file keeps the real `<head>` as exported and cuts the
`<body>` down to its inline module script.

HEAD is reflex `0.9.12.post18.dev0` (this workspace, Vite 8.2.2); 0.8.23 comes
from PyPI (rolldown-vite 7.2.10). Both were exported from a copy of the
playground's tracked files, on Linux:

```console
$ mkdir -p /tmp/rb-size
$ git ls-files -z examples/playground | xargs -0 -I{} cp --parents {} /tmp/rb-size/
$ cd /tmp/rb-size/examples/playground
$ $PY -m reflex export --frontend-only --no-zip --env prod
$ cp .web/build/client/index.html head-index.html   # or 0.8.23-index.html
```

with `PY` the workspace interpreter for `head-index.html` and a Python 3.12
venv with `reflex==0.8.23` (its `bin` first on `PATH`) for `0.8.23-index.html`.
