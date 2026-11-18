import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { SourceTextModule, SyntheticModule } from "node:vm";

// Like the other runtime scripts, this one is handed state.js; upload.js is
// the helper next to it.
const source = fs.readFileSync(
  path.join(path.dirname(process.argv[2]), "helpers", "upload.js"),
  "utf8",
);

/** A request the test streams the upload response through. */
class StreamedRequest {
  static sent = [];

  constructor() {
    this.upload = {};
    this.responseText = "";
    StreamedRequest.sent.push(this);
  }

  open() {}
  setRequestHeader() {}
  send() {}
  abort() {}
  getResponseHeader() {
    return null;
  }

  /** Receive more of the response, as one progress event of the browser. */
  receive(text, { done = false, status = 200 } = {}) {
    // The browser knows the status before any of the body arrives.
    this.status = status;
    this.responseText += text;
    this.onprogress({
      lengthComputable: done,
      loaded: this.responseText.length,
      total: this.responseText.length,
    });
  }

  finish() {
    this.onload();
  }
}

globalThis.window = {};
globalThis.XMLHttpRequest = StreamedRequest;

const dependencies = {
  "$/env.json": { default: { UPLOAD: "http://backend/_upload" } },
  "$/utils/helpers/json": { parseJson: JSON.parse },
};
const module = new SourceTextModule(source);
await module.link(
  (specifier) =>
    new SyntheticModule(Object.keys(dependencies[specifier]), function () {
      for (const [name, value] of Object.entries(dependencies[specifier])) {
        this.setExport(name, value);
      }
    }),
);
await module.evaluate();
const { uploadFiles } = module.namespace;

/** Start an upload with `handler` as the socket's event listener. */
function startUpload(handler) {
  const socket = { _callbacks: { $event: [handler] } };
  const uploaded = uploadFiles(
    "state.handle_upload",
    [],
    "upload",
    undefined,
    {},
    {},
    socket,
    {},
    (url) => url,
    () => "token",
  );
  return { uploaded, request: StreamedRequest.sent.at(-1) };
}

/** Upload with `handler` as the socket's event listener, and stream the updates. */
async function streamUpdates(handler) {
  const { uploaded, request } = startUpload(handler);
  // The browser fires each progress event as a task of its own.
  const nextTask = () => new Promise((resolve) => setImmediate(resolve));
  request.receive('{"delta": {"state": {"n": 1}}}\n');
  await nextTask();
  // The third update arrives in two parts.
  request.receive('{"delta": {"state": {"n": 2}}}\n{"delta": {"sta');
  await nextTask();
  request.receive('te": {"n": 3}}}\n', { done: true });
  await nextTask();
  request.finish();
  await uploaded;
}

test("a synchronous listener handles each streamed update once", async () => {
  const handled = [];
  await streamUpdates((update) => {
    handled.push(update.delta.state.n);
  });
  assert.deepEqual(handled, [1, 2, 3]);
});

test("an async listener handles each streamed update once", async () => {
  const handled = [];
  await streamUpdates(async (update) => {
    handled.push(update.delta.state.n);
  });
  assert.deepEqual(handled, [1, 2, 3]);
});

// A listener fails by throwing, or by rejecting the promise it returns.
const failures = {
  throwing: (update) => {
    if (update.delta.state.n === 1) {
      throw new Error("boom");
    }
  },
  rejecting: async (update) => {
    await null;
    if (update.delta.state.n === 1) {
      throw new Error("boom");
    }
  },
};

for (const [kind, fail] of Object.entries(failures)) {
  test(`an update a ${kind} listener fails on is reported, not retried`, async (t) => {
    const log = t.mock.method(console, "log", () => {});
    const handled = [];
    await streamUpdates((update) => {
      handled.push(update.delta.state.n);
      return fail(update);
    });
    assert.deepEqual(handled, [1, 2, 3]);
    assert.deepEqual(
      log.mock.calls.map((call) => [
        call.arguments[0],
        call.arguments[2].message,
      ]),
      [["Error processing chunk", "boom"]],
    );
  });
}

test("an error frame ending the stream fails the upload, not the listener", async (t) => {
  const log = t.mock.method(console, "log", () => {});
  const handled = [];
  const { uploaded, request } = startUpload((update) =>
    handled.push(update.delta.state.n),
  );
  request.receive(
    '{"delta": {"state": {"n": 1}}}\n{"error": "handler failed"}\n',
    {
      done: true,
    },
  );
  request.finish();
  assert.equal(await uploaded, false);
  assert.deepEqual(handled, [1]);
  assert.deepEqual(
    log.mock.calls.map((call) => call.arguments),
    [["Upload error:", "handler failed"]],
  );
});

test("an error response fails the upload by its status, not as a chunk", async (t) => {
  const log = t.mock.method(console, "log", () => {});
  const handled = [];
  const { uploaded, request } = startUpload((update) => handled.push(update));
  request.receive("The upload handler raised an exception.", {
    done: true,
    status: 500,
  });
  request.finish();
  assert.equal(await uploaded, false);
  assert.deepEqual(handled, []);
  assert.deepEqual(
    log.mock.calls.map((call) => call.arguments),
    [["Upload error:", "HTTP error! status: 500"]],
  );
});
