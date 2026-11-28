import fs from "node:fs";
import path from "node:path";
import { SourceTextModule, SyntheticModule } from "node:vm";

// The modules next to utils/state.js that make up the runtime of an app with
// state: the connection to the backend, and what the two share.
const SIBLINGS = ["event_loop", "socket"];

/** Evaluate the complete frontend runtime with isolated dependency stubs. */
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
  // Let Node parse the unchanged modules, with the browser globals in scope.
  const browserModule = (text) =>
    new SourceTextModule(
      `import { window, document, localStorage, sessionStorage } from "test:browser";
${text}
`,
    );
  const utils = path.dirname(process.argv[2]);
  const modules = { "$/utils/state": browserModule(source) };
  for (const name of SIBLINGS) {
    modules[`$/utils/${name}`] = browserModule(
      fs.readFileSync(path.join(utils, `${name}.js`), "utf8"),
    );
  }
  const linked = new Map();
  await modules["$/utils/socket"].link((specifier) => {
    if (modules[specifier]) return modules[specifier];
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
  await modules["$/utils/socket"].evaluate();
  // What compiled code imports, and the private queue for the tests to read.
  return {
    ...modules["$/utils/state"].namespace,
    event_queue: modules["$/utils/event_loop"].namespace.event_queue,
  };
}
