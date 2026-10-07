# Component browser campaign: macOS second pass

Completed against published PyPI `reflex==0.10.0a2`, with 0.10.0a1 and 0.9.12 baselines. No new 0.10 regression was established in this slice. Five pre-existing component defects were reproduced; this is not a verdict on the entire release train.

## Evidence map

- [Dataeditor matrix and exact reproduction](NOTES-de.md): five version/mode matrices, typing delays, component isolation, theme/filter/large-grid checks. 170 assertions, 139 pass and 31 fail. Includes pinned bootstrap and launch scripts.
- [Forms, charts and cross-browser matrix](NOTES-forms.md): Chromium 153 and Playwright WebKit 26.6, alpha2 dev/prod, stable/alpha1 form baselines. 438 assertions, 392 pass and 46 fail, with explicit interpretation of expected/pre-existing failures. `forms/summary.json` is generated from saved assertions.
- [Independent minimal verification](NOTES-verification.md): separate foreach/memo, bound/unbound deletion, and form-only/form-plus-grid controls on alpha2 and stable.
- `verification-extra/`: primary-session reproduction of the typing and image-Escape findings against its own alpha2 production server. Ordered console/websocket captures are preserved in gzip sidecars.
- [Wheel comparison](wheel_diff/NOTES.md): Python and other substantive wheel contents identical for dataeditor, react-player, Sonner and Lucide versus their prior versions. Python and sibling dependency floors changed; exact wheel hashes/metadata are saved.
- `final-cleanup.txt`: independent final audit of claimed ports and owned test process commands.

## Confirmed findings

1. **Medium, pre-existing:** dataeditor's generated data callback escapes `rx.foreach` variable scope; memo-wrapped control renders.
2. **Medium, pre-existing:** typing to open a first cell edit loses leading characters, including at 120 ms per character. Enter-opened editing and a delayed first-key control work.
3. **Medium, pre-existing:** binding ordinary `on_delete` delivers selection but prevents deletion and throws; unbound Delete/Backspace controls work.
4. **Low, pre-existing:** Escape immediately after activating a single-image preview leaves it open; text-editor and focused-carousel controls dismiss.
5. **Low, pre-existing:** Radix checkbox/switch/radio synthetic clicks throw in a form containing a dataeditor. Controls still update; the no-grid control is clean.

These are inbox entries `dataeditor-1.md` through `dataeditor-5.md`; the coordinator owns the main FINDINGS/RELEASE_PLAN documents. No framework fix was made.

## Claims refuted or narrowed

- Named selects submit correctly. The old fixture used only `id`; stable submitted `null`, whereas alpha1/alpha2 omit that key. The selected value was already lost on stable. Use `name` for successful submission.
- Dialog submit propagation and closed-dialog keys in outer payloads predate the train. Explicit `stop_propagation` prevents the outer event; these observations are not promoted to new release bugs.
- The Recharts formatter failures came from wrong SVG selectors. Corrected rendered-value checks and reactive currency/background updates pass on alpha2 in both engines and modes. Its new typed formatter API is unavailable on stable, so that fixture is excluded from stable compilation.
- Bool toggles, ComponentState isolation, memo/filter/theme controls and local carousel styles pass with corrected browser actions. No general performance claim is made from this concurrent machine's 5,000-row observations.

## Review and limits

All execution imported isolated published packages, with guards and freezes. Drivers captured server output, warnings/errors, failed HTTP/network requests, websocket activity where relevant, and screenshots. Package environments and generated frontend builds remain in scratch, outside this artifact directory. Complete ordered repetitive captures are gzip-compressed to keep this item below approximately 10 MB.

The adversarial review caught misleading historical collector exit codes and replay output overwriting the source evidence directory. Final harnesses propagate failure and default replay outputs to scratch; the form runner refuses existing app/output directories. Earlier exit codes remain unchanged as historical evidence, and assertion JSON determines every reported count. A fresh browser rerun validated exit 1 for the known id-only failure and refusal of a second run without changing archived evidence; see `forms/harness-review/`.

The saved Python artifacts passed isolated Ruff fatal syntax/undefined-name checks. Formatting was applied to the newly authored parent harnesses. The monorepo unit suite/type check was not run: this campaign prohibits installing the checkout and changes no framework source. Public APIs, news fragments and component stubs are unchanged.

Coverage limits include alpha1 production, installed Safari, Intel/other macOS releases, unmuted autoplay, clipboard/drag-resize/sort, remote carousel loading and broader load/performance claims. A separate [macOS lifecycle item](../macos_lifecycle/NOTES.md) covers npm/bun, HMR, Unicode paths, production and F-007.
