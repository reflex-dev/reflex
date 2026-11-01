Ship a `py.typed` marker so type checkers such as mypy read the package's bundled `.pyi` stubs instead of treating it as untyped, and mark the names the package root imports as re-exported.
