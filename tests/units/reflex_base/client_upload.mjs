import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { createContext, SourceTextModule, SyntheticModule } from "node:vm";

const source = fs.readFileSync(
  path.join(path.dirname(process.argv[2]), "helpers/upload.js"),
  "utf8",
);

/** Run the actual upload helper with a held cookie exchange and fake XHR. */
async function pendingUpload() {
  const requests = [];
  const context = createContext({
    AbortController,
    FormData,
    console,
    window: {},
    XMLHttpRequest: class {
      upload = {};
      open() {}
      setRequestHeader() {}
      send() {
        requests.push(this);
      }
      abort() {
        this.onabort();
      }
    },
  });
  const module = new SourceTextModule(source, { context });
  await module.link((specifier) => {
    const exports =
      specifier === "$/env.json"
        ? { default: { UPLOAD: "/upload" } }
        : { parseJson: JSON.parse };
    return new SyntheticModule(
      Object.keys(exports),
      function () {
        for (const [name, value] of Object.entries(exports))
          this.setExport(name, value);
      },
      { context },
    );
  });
  await module.evaluate();
  let finish;
  const readiness = new Promise((resolve) => {
    finish = resolve;
  });
  const refs = {};
  const socket = { connected: true };
  const start = () =>
    module.namespace.uploadFiles(
      "handler",
      [],
      "test",
      null,
      {},
      {},
      socket,
      refs,
      (value) => value,
      () => "token",
      () => readiness,
    );
  return { start, finish, refs, requests, socket };
}

test("queued uploads are cancellable before the cookie exchange finishes", async () => {
  const upload = await pendingUpload();
  const pending = upload.start();
  assert.ok(upload.refs.__upload_controllers_test);
  assert.equal(upload.requests.length, 0);
  upload.refs.__upload_controllers_test.abort();
  assert.equal(await pending, false);
  assert.equal(upload.requests.length, 0);
  assert.equal(upload.refs.__upload_controllers_test, undefined);
});

test("teardown prevents a queued upload from starting later", async () => {
  const upload = await pendingUpload();
  const pending = upload.start();
  assert.equal(upload.requests.length, 0);
  upload.socket.connected = false;
  upload.finish();
  assert.equal(await pending, false);
  assert.equal(upload.requests.length, 0);
  assert.equal(upload.refs.__upload_controllers_test, undefined);
});

test("duplicate queued uploads reserve their controller before readiness", async () => {
  const upload = await pendingUpload();
  const pending = upload.start();
  assert.equal(await upload.start(), false);
  assert.equal(upload.requests.length, 0);
  upload.refs.__upload_controllers_test.abort();
  upload.finish();
  await pending;
});

test("a ready upload starts once and cleans up its controller", async () => {
  const upload = await pendingUpload();
  const pending = upload.start();
  assert.equal(upload.requests.length, 0);
  upload.finish();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(upload.requests.length, 1);
  const request = upload.requests[0];
  assert.equal(request.withCredentials, true);
  request.status = 200;
  request.onload();
  assert.equal((await pending).status, 200);
  assert.equal(upload.refs.__upload_controllers_test, undefined);
});
