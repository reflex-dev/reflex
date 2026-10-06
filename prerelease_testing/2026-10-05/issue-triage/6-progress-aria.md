The high-level primitive Progress wrapper forwards `value` and `max` to its Indicator, leaving the Root indeterminate and without `aria-valuenow`. State-driven visual updates work, but assistive technology cannot read the numeric progress.

This reproduces with stable `reflex-components-radix==0.9.10.post1`/Reflex 0.9.12 and alpha Radix/Reflex 0.10.0a1; it is **preexisting**. Themes `rx.progress` exposes the value correctly.

### Reproduce

```python
import reflex as rx
from reflex_components_radix.primitives.progress import progress

class State(rx.State):
    amount: int = 25

# Render in an app, with a State event/slider that changes amount.
progress(value=State.amount, max=100, id="primitive-progress")
```

1. Open the page and inspect `#primitive-progress`.
2. Change `State.amount` from 25 to 100 through the app's slider.
3. Expected: the Root is determinate, exposes the current numeric `aria-valuenow`, and reaches the complete state at 100.
4. Actual: the visual Indicator updates, but the Root remains `data-state="indeterminate"` and omits `aria-valuenow`.

Construction output isolates the prop placement:

```text
RadixProgressRoot: className only; no value/max
  RadixProgressIndicator: value=<State.amount>, max=100
```

### Environment and evidence

macOS, Python 3.13, real dev/prod Chromium 143.0.7499.4 testing. Only published packages were installed in isolated environments; no framework fix was applied.

- [Small construction probe](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/component_probe.py).
- [Stable render](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/evidence/probe-stable-venv.json) and [alpha render](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/evidence/probe-venv.json), under `primitive_progress`.
- [Dashboard with State slider and Themes comparison](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/component_dashboard.py).
- [Browser assertions](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/browser_checks.py) and [production screenshot](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/evidence/prod-final/failure-radix-primitive-progress-accessibility.png).
