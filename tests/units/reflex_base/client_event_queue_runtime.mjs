import { SourceTextModule, SyntheticModule } from "node:vm";

/** Evaluate the complete frontend module with isolated dependency stubs. */
export async function createQueueRuntime(source, options = {}) {
  const unused = () => {
    throw new Error("Unexpected frontend dependency in queue test");
  };
  const dependencies = {
    "test:browser": {
      window: options.window ?? {
        location: { host: "localhost", pathname: "/", search: "", hash: "" },
      },
      document: options.document ?? {},
      localStorage: options.localStorage ?? { clear() {}, removeItem() {} },
      sessionStorage: options.sessionStorage ?? { clear() {}, removeItem() {} },
    },
    "socket.io-client": { default: unused },
    "$/env.json": { default: {} },
    "$/reflex.json": { default: {} },
    "universal-cookie": {
      default: class {
        constructor() {
          return options.cookies ?? { remove() {} };
        }
      },
    },
    react: {
      useCallback: unused,
      useEffect: unused,
      useRef: unused,
      useState: unused,
    },
    "react-router": {
      useLocation: unused,
      useNavigate: unused,
      useSearchParams: unused,
      useParams: unused,
    },
    "$/utils/context": {
      initialEvents: options.initialEvents ?? (() => []),
      initialState: {},
      onLoadInternalEvent: unused,
      state_name: "test_state",
      exception_state_name: "test_exception_state",
    },
    "$/utils/helpers/debounce": { default: unused },
    "$/utils/helpers/throttle": { default: unused },
    "$/utils/helpers/upload": {
      uploadFiles: options.uploadFiles ?? unused,
    },
  };
  // Let Node parse the unchanged module; only expose private state to tests.
  const module = new SourceTextModule(
    `import { window, document, localStorage, sessionStorage } from "test:browser";
${source}
export { event_queue };
export function setMismatch(value) { backend_state_mismatch = value; }
`,
  );
  const linked = new Map();
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
