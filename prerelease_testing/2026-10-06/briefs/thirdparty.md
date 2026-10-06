# Cluster `thirdparty` — breaking-change surface and third-party package compatibility

Ports: frontend 3100-3119, backend 8100-8119. Work dir: $SB/apps/thirdparty/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/thirdparty/

## Why this cluster exists
0.10.0a1 removes public names and changes how State vars work (descriptors). The previous campaign only
checked reflex-enterprise against these removals. Nobody has checked the third-party ecosystem, and
downstream breakage is the most common release blocker. Changelog lines (verbatim):

- (reflex, Breaking) Remove the `reflex component` CLI (`init`, `build`, `share`, `install`) and the `CustomComponents` constants. Wrap React libraries directly in your app as described in the wrapping React docs, and start reusable component packages from the component template. (#6425)
- (reflex, Breaking) A substate may now declare a var or computed var with the same name as an inherited var ... The internal class maps `backend_vars`, `inherited_vars` and `inherited_backend_vars`, `get_skip_vars()` and the instance `_backend_vars` are removed: use `get_fields()`, whose fields know the state they belong to. (#7312)
- (reflex-base, Breaking) `reflex_base.utils.types.is_backend_base_variable` and `RESERVED_BACKEND_VAR_NAMES` are removed ... `is_mutable_type` moved to `reflex_base.utils.types` (still importable from `reflex.istate.proxy`). (#7312)
- (reflex-base, Breaking) `PageContext.get()` and `CompileContext.get()` now raise `LookupError` instead of `RuntimeError` when no context is active. (#6553)
- (reflex-base, Features) `Field` is now the descriptor holding a state var's value, and `EventHandler` binds to the state that declares it when accessed on a state instance. (#7312)
- (reflex-base, Performance) ... vars, computed vars and event handlers are now descriptors on the state class that declares them, instead of every attribute access going through `BaseState.__getattribute__`. (#7312)
- (reflex-base, Performance) `EventHandler.is_background` and `EventHandler.supersedes` are read once per handler, so mark the function before the handler is first used. (#7370)

A grep of the published wheels of ~23 third-party packages and the stable 0.9.x component packages found
NO textual references to the removed names (only reflex-enterprise 0.9.7a4 references them, behind
hasattr/getattr guards). So the risk is behavioral, not import-time — that is what you must exercise.
Wheels are already downloaded at $SB/downloads/wheels/ if you want to inspect them (unzip -p).

## What to do
1. In your own venv (alpha pins + the package), for EACH of these packages: install against
   `reflex==0.10.0a1`, import it, and build a tiny page that actually uses it; run it (dev) and drive it
   in Chromium. Record install resolution (did it downgrade/upgrade anything? conflicts?), import errors,
   compile errors, console errors, and whether the feature works:
   - `reflex-local-auth` (0.5.0): register, login, logout, a `@reflex_local_auth.require_login` page,
     `LocalAuthState` substates, session expiry; it uses `rx.Model` + `reflex[db]` and State inheritance —
     exactly the surface #7312 changed. Also clone its repo (`git clone --depth 1 https://github.com/masenf/reflex-local-auth`
     into $SB/downloads/, read-only) and run its integration tests (`tests/`) against the PUBLISHED
     reflex-local-auth + alpha reflex using `AppHarness` (install pytest + whatever the tests need; the
     tests may use `reflex.testing.AppHarness`/selenium or playwright — adapt; if they need selenium +
     a chromedriver you don't have, port the key flows to Playwright instead). Compare any failure
     against `reflex==0.9.12` in a second venv.
   - `reflex-global-hotkey` (1.2.3): a page with `global_hotkey_watcher(on_key_down=State.on_key)`; press keys.
   - `reflex-google-auth` (0.2.0): import + render the button with a dummy client id (no real login).
   - `reflex-magic-link-auth` (0.2.2): import, render its form, trigger the "send link" flow against the
     local sqlite db (no email needed; check the State/db interactions).
   - `reflex-intersection-observer`, `reflex-audio-capture`, `reflex-webcam`, `reflex-simpleicons`,
     `reflex-monaco`, `reflex-calendar`, `reflex-pyplot`, `reflex-chakra` (0.8.2.post1),
     `reflex-ag-grid` (community 0.0.11), `reflex-google-recaptcha-v2`, `reflex-clerk`, `reflex-motion`,
     `reflex-type-animation`, `reflex-image-zoom`, `reflex-dynoselect`, `reflex-color-picker`,
     `reflex-qrcode`, `reflex-chat`: import sweep + render each on a page; drive a basic interaction
     where one exists. Some are old (0.4-era); an install failure due to their own old pins is NOT a
     finding, but a runtime error in a package that installs fine IS worth recording with a judgement of
     whether 0.9.12 behaves differently.
   Put several packages on one app with multiple pages to keep server count down; one app per
   incompatible dependency set.
2. `reflex component --help`, `reflex component init` on the alpha: what does a user see now? A clean
   "unknown command" is fine; a traceback is a finding. Check `reflex --help` no longer lists it.
3. Code using the removed names: write a short probe (run from a neutral dir) that does what a
   third-party author would: `from reflex.constants import CustomComponents`, `State.backend_vars`,
   `State.inherited_vars`, `State.get_skip_vars()`, `state_instance._backend_vars`,
   `reflex_base.utils.types.is_backend_base_variable`, `RESERVED_BACKEND_VAR_NAMES`,
   `reflex.istate.proxy.is_mutable_type`, `PageContext.get()` outside a context. Record the exact
   exception type/message for each — judge whether the error points to the replacement
   (`get_fields()`), as a good breaking change should. Same probe on 0.9.12 for contrast.
4. Downstream-style State patterns on the alpha vs 0.9.12 (these are what packages do internally):
   mixin states (`mixin=True`) contributing vars/handlers/computed vars to several substates; a
   package-provided base state that user apps subclass; `get_fields()` iteration to find backend
   vars; `cls.__fields__`-style access; `State.get_value()`/`setvar`; dynamically created substates
   (`type(...)` at import time); `rx.State.get_state(OtherState)` from a package handler; a package's
   handler stored and re-attached (`State.event_handlers`). Record any behavioral difference.

Record EVERY difference between alpha and 0.9.12 as at least an anomaly, with the exact traceback.
