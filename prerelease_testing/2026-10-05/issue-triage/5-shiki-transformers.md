`rx._x.code_block(..., use_transformers=True)` silently produces an empty Shiki transformer configuration, so notation highlighting is missing. This reproduces with stable `reflex-components-code==0.9.6`/Reflex 0.9.12 and alpha code/Reflex 0.10.0a1; it is **preexisting**, not a regression from the Shiki version bump.

### Reproduce

Render this component in a normal app and open it in a browser:

```python
rx._x.code_block(
    "print('x') # [!code highlight]",
    language="python",
    use_transformers=True,
)
```

Expected: the notation transformer highlights the annotated line.

Actual: no `.highlighted` line appears. The constructed transformer is `ShikiJsTransformer(library='', fns=[], style=None)`, imports are empty, and the generated component emits `transformers:[]`.

Explicit configuration works in the alpha browser:

```python
rx._x.code_block(
    "print('x') # [!code highlight]",
    language="python",
    transformers=[
        rx._x.code_block.create_transformer(
            "@shikijs/transformers@4.5.0",
            ["transformerNotationHighlight"],
        ),
    ],
)
```

### Environment and retained repros

macOS, Python 3.13, actual dev/prod browser testing with Chromium 143.0.7499.4. All framework packages came from isolated PyPI installs; no source or generated frontend code was patched.

- [Small construction probe](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/component_probe.py): run with each isolated interpreter, passing an output JSON path.
- [Stable render/config](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/evidence/probe-stable-venv.json) and [alpha render/config](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/evidence/probe-venv.json), under `shiki`.
- [Complete dashboard](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/component_dashboard.py), comparing convenience and explicit configuration side by side.
- [Production failure screenshot](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/evidence/prod-final/failure-shiki-default-transformer.png).
