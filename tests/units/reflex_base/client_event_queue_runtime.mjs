import { SourceTextModule, SyntheticModule } from "node:vm";

/** Evaluate the complete frontend module with isolated dependency stubs. */
export async function createQueueRuntime(
  source,
  { uploadFiles, throttle, dependencies: dependencyOverrides } = {},
) {
  const unused = () => {
    throw new Error("Unexpected frontend dependency in queue test");
  };
  const app = {
    initialEvents: () => [],
    initialState: {},
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
    },
    mergician: { mergician: unused },
    "$/env.json": { default: {} },
    "$/reflex.json": { default: {} },
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
    "$/utils/context-registry": {
      app,
      eventLoop: { addEvents: unused },
    },
    "$/utils/helpers/debounce": { default: unused },
    "$/utils/helpers/json": {
      parseJsonLenient: unused,
      undefinedToNull: unused,
    },
    "$/utils/helpers/throttle": { default: throttle ?? unused },
    "$/utils/helpers/upload": {
      uploadFiles: uploadFiles ?? unused,
    },
    "$/utils/helpers/websocket": {
      ReflexWebSocket: unused,
      disableChannels: unused,
      getChannel: unused,
    },
    ...dependencyOverrides,
  };
  const linked = new Map();
  const link = (specifier) => {
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
  };
  // Let Node parse the unchanged module; only expose private state to tests.
  const module = new SourceTextModule(
    `import { window, document, localStorage, sessionStorage } from "test:browser";
${source}
export { event_queue };
`,
    {
      // The socket.io client is imported on demand.
      async importModuleDynamically(specifier) {
        const imported = link(specifier);
        // Newer Node versions create synthetic modules already linked.
        if (imported.status === "unlinked") {
          await imported.link(link);
        }
        if (imported.status === "linked") {
          await imported.evaluate();
        }
        return imported;
      },
    },
  );
  await module.link(link);
  await module.evaluate();
  return module.namespace;
}
