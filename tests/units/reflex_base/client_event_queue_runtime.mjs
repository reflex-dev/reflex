import fs from "node:fs";
import path from "node:path";
import { SourceTextModule, SyntheticModule } from "node:vm";

// Like the other runtime scripts, this one is handed state.js; the modules it
// re-exports are next to it.
const readUtil = (name) =>
  fs.readFileSync(path.join(path.dirname(process.argv[2]), name), "utf8");
const runtimeSource = readUtil("runtime.js");
const transportSource = readUtil("transport.js");

/** Evaluate the complete frontend modules with isolated dependency stubs. */
export async function createQueueRuntime(
  source,
  {
    uploadFiles,
    throttle,
    dependencies: dependencyOverrides,
    io,
    env,
    browser,
    initialState = {},
  } = {},
) {
  const unused = () => {
    throw new Error("Unexpected frontend dependency in queue test");
  };
  const app = {
    initialEvents: (first) => [
      {
        name: "reflex___state.test.hydrate_and_load",
        payload: first ? { hashes: { test_state: "compiled-defaults" } } : {},
      },
    ],
    initialState,
    onLoadInternalEvent: unused,
    state_name: "test_state",
    exception_state_name: "test_exception_state",
  };
  const dependencies = {
    "test:browser": {
      window: {
        location: { host: "localhost", pathname: "/", search: "", hash: "" },
      },
      document: {},
      localStorage: { clear() {}, removeItem() {} },
      sessionStorage: { clear() {}, removeItem() {} },
      ...browser,
    },
    "socket.io-client": { default: io ?? unused },
    mergician: { mergician: unused },
    "$/env.json": { default: env ?? {} },
    "universal-cookie": {
      default: class {
        remove() {}
      },
    },
    react: {
      useCallback: (callback) => callback,
      useEffect: () => {},
      useRef: (value) => ({ current: value }),
      useState: (value) => [value, () => {}],
    },
    "react-router": {
      useLocation: () => ({ pathname: "/", search: "", hash: "" }),
      useNavigate: () => unused,
      useSearchParams: () => [new URLSearchParams()],
      useParams: () => ({}),
    },
    "$/utils/context": app,
    "$/utils/client_state": {
      CLIENT_STATE_REF: "__client_state",
      getClientState: unused,
      // Published on `refs` when the module loads, so it has to answer.
      getClientStore: () => ({}),
      setClientState: unused,
    },
    "$/utils/context-registry": {
      app,
      eventLoop: { addEvents: unused },
    },
    "$/utils/helpers/debounce": { default: unused },
    "$/utils/helpers/json": { parseJson: unused },
    "$/utils/helpers/throttle": { default: throttle ?? unused },
    "$/utils/helpers/upload": {
      uploadFiles: uploadFiles ?? unused,
    },
    ...dependencyOverrides,
  };
  // Let Node parse the unchanged modules; only expose private state to tests.
  const globals =
    'import { window, document, localStorage, sessionStorage } from "test:browser";';
  const module = new SourceTextModule(source);
  const transport = new SourceTextModule(
    `${globals}
${transportSource}
export { event_queue };
`,
  );
  // state.js re-exports runtime.js and transport.js.
  const linked = new Map([
    ["$/utils/state", module],
    ["$/utils/runtime", new SourceTextModule(`${globals}\n${runtimeSource}`)],
    ["$/utils/transport", transport],
  ]);
  await module.link((specifier) => {
    if (!linked.has(specifier)) {
      const exports = dependencies[specifier];
      if (!exports)
        throw new Error(`Unexpected import in queue test: ${specifier}`);
      linked.set(
        specifier,
        new SyntheticModule(Object.keys(exports), function () {
          for (const [name, value] of Object.entries(exports)) {
            this.setExport(name, value);
          }
        }),
      );
    }
    return linked.get(specifier);
  });
  await module.evaluate();
  return module.namespace;
}
