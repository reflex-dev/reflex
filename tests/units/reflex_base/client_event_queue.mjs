import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { queueRuntimeSource } from "./client_event_queue_runtime.mjs";

const source = fs.readFileSync(process.argv[2], "utf8");
const createRuntime = new Function(
  `${queueRuntimeSource(source)}; return createQueueRuntime;`,
)();
const params = { current: {} };
const stateful = (id) => ({
  name: "reflex___state.test.event",
  payload: { id },
});
const local = (id, output) => ({
  name: "_call_function",
  payload: { function: () => output.push(id) },
});
const socketFor = (output, connected = true) => ({
  connected,
  emit: (_, event) => output.push(event.payload.id),
});
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};

test("FIFO filtering and both raw and reference sockets", async () => {
  for (const ref of [false, true]) {
    const runtime = createRuntime(),
      output = [],
      socket = socketFor(output);
    await runtime.queueEvents(
      [null, stateful(1), undefined, local(2, output), stateful(3)],
      ref ? { current: socket } : socket,
      false,
      () => {},
      params,
    );
    assert.deepEqual(output, [1, 2, 3]);
    assert.equal(runtime.event_queue.length, 0);
    assert.equal(runtime.isStateful(), false);
  }
});

test("offline stateful events hold the entire queue until reconnect", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output, false);
  await runtime.queueEvents(
    [local(1, output), stateful(2), local(3, output)],
    socket,
    false,
    () => {},
    params,
  );
  assert.deepEqual(output, []);
  assert.equal(runtime.event_queue.length, 3);
  assert.equal(runtime.isStateful(), true);
  socket.connected = true;
  await runtime.processEvent(socket, () => {}, params);
  assert.deepEqual(output, [1, 2, 3]);
  assert.equal(runtime.event_queue.length, 0);
});

test("local events run without a socket, including an empty queue", async () => {
  const runtime = createRuntime(),
    output = [];
  await runtime.queueEvents([], null, false, () => {}, params);
  await runtime.queueEvents(
    [local(1, output), local(2, output)],
    null,
    false,
    () => {},
    params,
  );
  assert.deepEqual(output, [1, 2]);
});

test("prepend preserves new and pending order and does not mutate the input", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output, false);
  await runtime.queueEvents(
    [stateful(3), local(4, output)],
    socket,
    false,
    () => {},
    params,
  );
  const front = [stateful(1), null, local(2, output), undefined];
  const original = front.slice();
  await runtime.queueEvents(front, socket, true, () => {}, params);
  assert.deepEqual(front, original);
  socket.connected = true;
  await runtime.processEvent(socket, () => {}, params);
  assert.deepEqual(output, [1, 2, 3, 4]);
  assert.equal(runtime.event_queue.length, 0);
});

test("disconnect during an event pauses remaining stateful events", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output);
  const disconnect = {
    name: "_call_function",
    payload: {
      function: () => {
        output.push(1);
        socket.connected = false;
      },
    },
  };
  await runtime.queueEvents(
    [disconnect, local(2, output), stateful(3)],
    socket,
    false,
    () => {},
    params,
  );
  assert.deepEqual(output, [1]);
  assert.equal(runtime.event_queue.length, 2);
  socket.connected = true;
  await runtime.processEvent(socket, () => {}, params);
  assert.deepEqual(output, [1, 2, 3]);
});

test("reentrant enqueue and prepend retain FIFO semantics", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output);
  let nested;
  const enqueue = {
    name: "_call_function",
    payload: {
      function: () => {
        output.push(1);
        nested = runtime.queueEvents(
          [local(2, output)],
          socket,
          true,
          () => {},
          params,
        );
      },
    },
  };
  await runtime.queueEvents(
    [enqueue, local(3, output)],
    socket,
    false,
    () => {},
    params,
  );
  await nested;
  assert.deepEqual(output, [1, 2, 3]);
  assert.equal(runtime.event_queue.length, 0);
});

test("overlapping calls and promise settling preserve async handler behavior", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output),
    wait = deferred();
  let firstSettled = false;
  const asynchronous = {
    name: "_call_function",
    payload: {
      function: () => {
        output.push(1);
        return wait.promise;
      },
      callback: () => output.push(4),
    },
  };
  const first = runtime
    .queueEvents(
      [asynchronous, local(2, output)],
      socket,
      false,
      () => {},
      params,
    )
    .then(() => {
      firstSettled = true;
    });
  const second = runtime.queueEvents(
    [local(3, output)],
    socket,
    false,
    () => {},
    params,
  );
  await second;
  assert.deepEqual(output, [1, 2, 3]);
  assert.equal(firstSettled, false);
  wait.resolve();
  await first;
  assert.deepEqual(output, [1, 2, 3, 4]);
  assert.equal(firstSettled, true);
});

test("fatal mismatch clears pending events and lets drain promises settle", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output, false);
  await runtime.queueEvents(
    [stateful(1), local(2, output)],
    socket,
    false,
    () => {},
    params,
  );
  runtime.setMismatch(true);
  socket.connected = true;
  await runtime.processEvent(socket, () => {}, params);
  assert.deepEqual(output, []);
  assert.equal(runtime.event_queue.length, 0);
});

test("redirect and REST events retain the ordering of pending work", async () => {
  const output = [];
  const runtime = createRuntime({ uploadFiles: () => output.push("upload") }),
    socket = socketFor(output);
  await runtime.queueEvents(
    [
      { name: "_redirect", payload: { path: "/next", replace: true } },
      {
        name: "reflex___state.test.upload",
        handler: "uploadFiles",
        payload: { files: [] },
      },
      local("last", output),
    ],
    socket,
    false,
    (path, options) => output.push([path, options]),
    params,
  );
  assert.deepEqual(output, [["/next", { replace: true }], "upload", "last"]);
  assert.equal(runtime.event_queue.length, 0);
});

test("prepend shifts pending events only when they are dispatched", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output, false);
  await runtime.queueEvents(
    [stateful(2), local(3, output)],
    socket,
    false,
    () => {},
    params,
  );
  let shifts = 0;
  runtime.event_queue.shift = () => {
    shifts++;
    return Array.prototype.shift.call(runtime.event_queue);
  };
  socket.connected = true;
  await runtime.queueEvents([local(1, output)], socket, true, () => {}, params);
  assert.deepEqual(output, [1, 2, 3]);
  assert.equal(shifts, 3);
});

test("dispatch rejection leaves pending work available to a later drain", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output);
  socket.emit = () => {
    throw new Error("socket write failed");
  };
  await assert.rejects(
    runtime.queueEvents(
      [stateful(1), local(2, output)],
      socket,
      false,
      () => {},
      params,
    ),
    /socket write failed/,
  );
  assert.equal(runtime.event_queue.length, 1);
  socket.emit = (_, event) => output.push(event.payload.id);
  await runtime.queueEvents([stateful(3)], socket, false, () => {}, params);
  assert.deepEqual(output, [2, 3]);
  assert.equal(runtime.event_queue.length, 0);
});

test("stateful arrival during an offline local await pauses the later drain", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output, false),
    wait = deferred();
  const asynchronous = {
    name: "_call_function",
    payload: { function: () => wait.promise, callback: () => output.push(1) },
  };
  const first = runtime.queueEvents(
    [asynchronous],
    socket,
    false,
    () => {},
    params,
  );
  await runtime.queueEvents(
    [local(2, output), stateful(3)],
    socket,
    false,
    () => {},
    params,
  );
  assert.deepEqual(output, []);
  wait.resolve();
  await first;
  assert.deepEqual(output, [1]);
  assert.equal(runtime.event_queue.length, 2);
  socket.connected = true;
  await runtime.processEvent(socket, () => {}, params);
  assert.deepEqual(output, [1, 2, 3]);
});

test("mismatch retains the existing offline stateful guard until reconnect", async () => {
  const runtime = createRuntime(),
    output = [],
    socket = socketFor(output, false);
  runtime.setMismatch(true);
  await runtime.queueEvents([stateful(1)], socket, false, () => {}, params);
  assert.equal(runtime.event_queue.length, 1);
  assert.deepEqual(output, []);
  socket.connected = true;
  await runtime.processEvent(socket, () => {}, params);
  assert.equal(runtime.event_queue.length, 0);
  assert.deepEqual(output, []);
});

test("one-event queues drain exactly once for both local and stateful handlers", async () => {
  for (const makeEvent of [local, (id) => stateful(id)]) {
    const runtime = createRuntime(),
      output = [],
      socket = socketFor(output);
    await runtime.queueEvents(
      [makeEvent(1, output)],
      socket,
      false,
      () => {},
      params,
    );
    await runtime.processEvent(socket, () => {}, params);
    assert.deepEqual(output, [1]);
    assert.equal(runtime.event_queue.length, 0);
  }
});
