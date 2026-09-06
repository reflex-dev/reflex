/** Extract the actual queue and handler functions without loading React or sockets. */
export function queueRuntimeSource(source) {
  const names = [
    "isStateful",
    "queueEventIfSocketExists",
    "applyEvent",
    "applyRestEvent",
    "resolveSocket",
    "queueEvents",
    "processEvent",
  ];
  const declarations = names.map((name) => {
    const match = source.match(
      new RegExp(`(?:export )?const ${name} = [\\s\\S]*?\\n\\};`),
    );
    if (!match) throw new Error(`Cannot extract ${name}`);
    return match[0].replace(/^export /, "");
  });
  const urlFrom = source.match(/function urlFrom\(string\) \{[\s\S]*?\n\}/);
  if (!urlFrom) throw new Error("Cannot extract urlFrom");
  return `function createQueueRuntime(options = {}) {
    const event_queue = [];
    let backend_state_mismatch = false;
    const env = {};
    const refs = {};
    const locationRef = {current: null};
    const window = options.window ?? {location: {host: 'localhost', pathname: '/', search: '', hash: ''}};
    const initialEvents = options.initialEvents ?? (() => []);
    const uploadFiles = options.uploadFiles ?? (() => {});
    const getBackendURL = () => new URL('http://localhost');
    const getToken = () => 'test-token';
    const cookies = options.cookies ?? {remove() {}};
    const localStorage = options.localStorage ?? {clear() {}, removeItem() {}};
    const sessionStorage = options.sessionStorage ?? {clear() {}, removeItem() {}};
    ${urlFrom[0]}
    ${declarations.join("\n")}
    return {event_queue, queueEvents, processEvent, isStateful, applyEvent,
      setMismatch(value) {backend_state_mismatch = value;}};
  }`;
}
