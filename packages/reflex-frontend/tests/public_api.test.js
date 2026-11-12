// @vitest-environment node
/**
 * What each module exports, and that it can be imported at all without a
 * browser.
 *
 * Compiled pages import these names, and so do component packages that are
 * published on their own schedule: an app can pair this frontend with an older
 * `reflex-components-*` that still asks for a name by its old spelling. A
 * rename or a removal therefore breaks apps at build time, and this list makes
 * either one a visible edit. Adding a name is always safe; add it here too.
 *
 * The node environment is deliberate. A production build prerenders pages in
 * node, so every module is evaluated there, with no `window` or `document`.
 * One that touches either while it loads fails the build of every app.
 */
import { expect, test } from "vitest";

const PUBLIC_API = {
  "$/utils/state": [
    "ReflexEvent",
    "applyDelta",
    "applyEvent",
    "applyEventActions",
    "applyRestEvent",
    "connect",
    "encodeFormDataArgs",
    "evalReactComponent",
    "generateUUID",
    "getBackendURL",
    "getFormData",
    "getRefValue",
    "getRefValues",
    "getToken",
    "hydrateClientStorage",
    "isBackendDisabled",
    "isNotNullOrUndefined",
    "isStateful",
    "isTrue",
    "mergeRefs",
    "mergeSlotProps",
    "processEvent",
    "pyAnd",
    "pyFlatMap",
    "pyLstrip",
    "pyOr",
    "pyRstrip",
    "pyStrAt",
    "pyStrChars",
    "pyStrLength",
    "pyStrSlice",
    "pyStrip",
    "queueEventIfSocketExists",
    "queueEvents",
    "refs",
    "spreadArraysOrObjects",
    "useEventLoop",
    "useRegisteredRef",
  ],
  "$/utils/client_state": [
    "CLIENT_STATE_REF",
    "ClientStateProvider",
    "ClientStateScope",
    "ClientStateScopeContext",
    "createClientStateStore",
    "getClientState",
    "getClientStore",
    "setClientState",
    "useClientState",
    "withClientStateScope",
  ],
  "$/utils/context-registry": [
    "ColorModeContext",
    "DispatchContext",
    "EventLoopContext",
    "StateStoreContext",
    "UploadFilesContext",
    "app",
    "eventLoop",
    "registerApp",
    "useStateContext",
  ],
  "$/utils/react-theme": ["ThemeProvider", "useTheme"],
  "$/utils/helpers/datetime": ["default"],
  "$/utils/helpers/debounce": ["default"],
  "$/utils/helpers/json": ["parseJson"],
  "$/utils/helpers/paste": ["default"],
  "$/utils/helpers/range": ["default"],
  "$/utils/helpers/set": [
    "pySetDifference",
    "pySetHas",
    "pySetIntersection",
    "pySetIsDisjoint",
    "pySetIsSubset",
    "pySetKey",
    "pySetSymmetricDifference",
    "pySetUnion",
  ],
  "$/utils/helpers/throttle": ["default"],
  "$/utils/helpers/upload": ["uploadFiles"],
  "$/components/reflex/radix_themes_color_mode_provider": ["default"],
  "$/components/shiki/code": ["Code"],
};

test.each(
  Object.entries(PUBLIC_API),
)("%s loads without a browser and exports what apps import", async (specifier, names) => {
  const module = await import(specifier);
  expect(Object.keys(module).sort()).toEqual(names);
});

test("loading the modules leaves no browser globals behind", () => {
  expect(typeof window).toBe("undefined");
  expect(typeof document).toBe("undefined");
});
