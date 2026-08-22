// Registry of app-provided runtime values for the Reflex frontend runtime.
//
// The shipped runtime modules (state.js and friends) must not import per-app
// generated artifacts (env.json, reflex.json, utils/context.js) — that
// coupling is inverted here: the generated `$/utils/context` module calls
// configureReflexRuntime() in its module body, which ESM guarantees runs
// before any importer's code, so the registry is populated before any
// component renders or event dispatches.

const runtimeConfig = {
  // Contents of the generated env.json (endpoint URLs, TRANSPORT, ...).
  env: undefined,
  // Contents of the generated reflex.json ({ version, ... }).
  reflexEnvironment: undefined,
  initialState: {},
  initialEvents: () => [],
  onLoadInternalEvent: () => [],
  // undefined is legitimate for both names: a stateless app has no state.
  state_name: undefined,
  exception_state_name: undefined,
};

/**
 * Register app-specific runtime values.
 * @param options Partial runtime config; only defined keys are applied.
 */
export function configureReflexRuntime(options) {
  for (const key of Object.keys(runtimeConfig)) {
    if (options[key] !== undefined) {
      runtimeConfig[key] = options[key];
    }
  }
}

/**
 * Get the app's env.json contents, throwing a descriptive error when the
 * runtime has not been configured (an absent env otherwise surfaces as a
 * baffling `new URL(undefined)` failure downstream).
 * @returns The env object.
 */
export function getEnv() {
  if (runtimeConfig.env === undefined) {
    throw new Error(
      "Reflex runtime is not configured (env is missing). The generated " +
        "'$/utils/context' module configures it on import; in tests, call " +
        "configureReflexRuntime({ env: {...}, ... }) first.",
    );
  }
  return runtimeConfig.env;
}

export { runtimeConfig };
