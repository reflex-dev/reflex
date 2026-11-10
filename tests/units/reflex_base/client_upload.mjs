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

  finish(status = 200) {
    this.status = status;
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
  const refs = {};
  const uploaded = uploadFiles(
    "state.handle_upload",
    [],
    "upload",
    undefined,
    {},
    {},
    socket,
    refs,
    (url) => url,
    () => "token",
  );
  const request = StreamedRequest.sent.at(-1);
  return { uploaded, request, refs };
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

test("an unparseable chunk is reported at load without Content-Length", async (t) => {
  const log = t.mock.method(console, "log", () => {});
  const handled = [];
  const { uploaded, request, refs } = startUpload((update) =>
    handled.push(update),
  );
  request.receive('{"n":1}\n{"broken":');
  request.receive("oops}\n");
  assert.equal(log.mock.calls.length, 0);
  request.finish();
  assert.equal((await uploaded).status, 200);
  assert.deepEqual(handled, [{ n: 1 }]);
  assert.equal(log.mock.calls.length, 1);
  assert.equal(log.mock.calls[0].arguments[0], "Error parsing chunk");
  assert.equal(log.mock.calls[0].arguments[1], '{"broken":oops}');
  assert.deepEqual(refs, {});
});

test("load handles a final chunk completed after the last progress event", async (t) => {
  const log = t.mock.method(console, "log", () => {});
  const handled = [];
  const { uploaded, request } = startUpload((update) => handled.push(update));
  request.receive('{"n":1}\n{"n":');
  assert.deepEqual(handled, [{ n: 1 }]);
  request.responseText += "2}\n";
  request.finish();
  await uploaded;
  assert.deepEqual(handled, [{ n: 1 }, { n: 2 }]);
  assert.equal(log.mock.calls.length, 0);
});

test("load handles a response with no progress events", async () => {
  const handled = [];
  const { uploaded, request } = startUpload((update) => handled.push(update));
  request.responseText = '{"n":1}\n{"n":2}';
  request.finish();
  await uploaded;
  assert.deepEqual(handled, [{ n: 1 }, { n: 2 }]);
});

test("a computable progress ratio of one is not response completion", async (t) => {
  const log = t.mock.method(console, "log", () => {});
  const handled = [];
  const { uploaded, request } = startUpload((update) => handled.push(update));
  request.receive('{"n":', { done: true });
  assert.equal(log.mock.calls.length, 0);
  request.responseText += "1}";
  request.finish();
  await uploaded;
  assert.deepEqual(handled, [{ n: 1 }]);
  assert.equal(log.mock.calls.length, 0);
});

test("an empty response does not report a parse error", async (t) => {
  const log = t.mock.method(console, "log", () => {});
  const handled = [];
  const { uploaded, request } = startUpload((update) => handled.push(update));
  request.receive(" \n");
  request.finish();
  await uploaded;
  assert.deepEqual(handled, []);
  assert.equal(log.mock.calls.length, 0);
});

test("load does not parse an HTTP error response", async (t) => {
  const log = t.mock.method(console, "log", () => {});
  const handled = [];
  const { uploaded, request, refs } = startUpload((update) =>
    handled.push(update),
  );
  request.responseText = '{"n":1}';
  request.finish(500);
  assert.equal(await uploaded, false);
  assert.deepEqual(handled, []);
  assert.deepEqual(
    log.mock.calls.map((call) => call.arguments),
    [["Upload error:", "HTTP error! status: 500"]],
  );
  assert.deepEqual(refs, {});
});

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
