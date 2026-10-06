A production app with 1,500 dormant `rx.State` subclasses builds and serves HTTP 200 on published Reflex 0.10.0a1, but its browser renders only the Reflex badge and raises `RangeError: Maximum call stack size exceeded`. Development mode fails during React mutation-effect traversal as well.

This is a confirmed alpha limitation, **not a proven regression**. Both published 0.9.12 and 0.10.0a1 pass the same browser flow at 500 and 1,000 extra States. At 1,500, the stable frontend exits with SIGILL during build/startup, preventing a valid stable browser comparison. The alpha's SSR succeeds; this is a separate client-rendering limit from the SSR change in #7369.

### Reproduce

Use the unchanged [alpha sample](https://github.com/reflex-dev/reflex/tree/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/enterprise/many_states/alpha) and [exact published dependency graph](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/enterprise/many_states/requirements-alpha-lock.txt). Copy the sample into a neutral directory and install the requirements in an isolated virtual environment, using PyPI packages only.

The sample creates dormant classes with one integer field:

```python
for index in range(int(os.environ.get("QA_EXTRA_STATES", "0"))):
    name = f"WorkspaceState{index}"
    globals()[name] = type(
        name,
        (rx.State,),
        {"__module__": __name__, "__annotations__": {"value": int}, "value": 0},
    )
```

From the copied app directory:

```sh
env -u PYTHONPATH CI=true QA_EXTRA_STATES=1500 uv --no-config run --no-project \
  --python /private/tmp/many-states-alpha/bin/python \
  reflex run --env prod --frontend-port 3133 --backend-port 3133 --loglevel debug
```

1. Open a fresh browser tab at `http://localhost:3133/articles/7?self=1`.
2. Expected: Article 7 appears; Home navigation and Increment work.
3. Actual: badge-only blank page; JavaScript stack overflow. Captured document, JavaScript and CSS responses are HTTP 200.
4. Repeat with 500/1,000: navigation and counter events pass.
5. For a readable stack, repeat in dev mode with backend port 8133. The stack repeatedly traverses `commitMutationEffectsOnFiber` and `recursivelyTraverseMutationEffects`.

### Environment and evidence

- macOS arm64, CPython 3.12.1; Reflex/base/core/Radix 0.10.0a1.
- React 19.3.0, Vite 8.3.2; reproduced with existing Bun 1.4.0 and a fresh isolated Bun 1.4.2 install.
- Reproduced in the Codex in-app browser and independently in native Chrome 154.0.8037.98 via published Playwright 1.63.0.
- [Controlled stable/alpha report and commands](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/enterprise/many_states/REPORT.md).
- [Independent fresh-Bun browser diagnostics](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/lifecycle/evidence/fresh-bun-scale/browser.json) and [screenshot](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/lifecycle/evidence/fresh-bun-scale/blank-page.png).

The generated client still nests `SubstateProvider` for every substate. A client render-depth limit is an inference from generated code and the observed stack; no framework/generated code was modified. No exact failure threshold or universal browser limit is claimed.
