The compiled app root assigns `window.__reflex` when the module loads instead of in a `ReflexProviders` effect, so components can read it during their first render.
