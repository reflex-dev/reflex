Reset in the Overkey example restores the configuration controls after a typing round but leaves the shared client-State input populated. This reproduces before and after an unchanged app is upgraded from published Reflex 0.9.12 to 0.10.0a1; it is a **preexisting example defect**, not a demonstrated alpha regression.

### Reproduce

Use the unmodified Overkey app from reflex-examples commit [`ebe19ff00dfee36f9d67a9a584840c6745950b05`](https://github.com/reflex-dev/reflex-examples/tree/ebe19ff00dfee36f9d67a9a584840c6745950b05/overkey). A [retained source copy](https://github.com/reflex-dev/reflex/tree/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/upgrades/source/overkey) and exact dependency graphs are also available below. Copy the app into a neutral directory and use an isolated published-package environment.

1. Start the app with `reflex run` and open it in a browser.
2. Choose **5 seconds** in the time dropdown.
3. Type the first ten characters of the displayed paragraph into the input.
4. Wait for **Time's up!** and the accuracy result; the tested rounds reached **100.00% accuracy**.
5. Click the Reset button.

Expected: the input/client-State text is empty and a fresh round can start.

Actual: the controls return, but the input retains the previous text. The stable run retained `course end`; the alpha run retained `into how b` (the paragraph is generated, so text varies). Browser diagnostics contain no page errors or failed requests.

The source uses `ClientStateVar.create("user_input", default="")` and a reset witness component whose `on_mount` sets it to an empty string. The browser observation above establishes the failure; no fix or cause is claimed.

### Environment and evidence

- macOS, Python 3.13; stable Reflex/base 0.9.12, then an in-place upgrade to the exact alpha graph with Reflex/base 0.10.0a1.
- App Python sources and `rxconfig.py` remained unchanged. Existing `.web` and `reflex.lock` were retained, followed by a successful cold alpha production export and the same browser flow in dev mode.
- [Upgrade report and frozen graphs](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/upgrades/REPORT.md).
- [Stable browser result](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/upgrades/evidence/overkey-stable.json) and [alpha result](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/upgrades/evidence/overkey-alpha.json).
- [Reusable browser flow](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/components/upgrades/browser_flows.py), including the failing empty-input assertion after Reset.
