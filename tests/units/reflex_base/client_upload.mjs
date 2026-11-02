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
  receive(text, { done = false } = {}) {
    this.responseText += text;
    this.onprogress({
      lengthComputable: done,
      loaded: this.responseText.length,
      total: this.responseText.length,
    });
  }

  finish() {
    this.status = 200;
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

/** Upload with `handler` as the socket's event listener, and stream the updates. */
async function streamUpdates(handler) {
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
  const request = StreamedRequest.sent.at(-1);
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

test("an update a listener fails on is reported, not retried", async (t) => {
  const log = t.mock.method(console, "log", () => {});
  const handled = [];
  await streamUpdates((update) => {
    handled.push(update.delta.state.n);
    if (update.delta.state.n === 1) {
      throw new Error("boom");
    }
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
