import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { createQueueRuntime } from "./client_event_queue_runtime.mjs";

const source = fs.readFileSync(process.argv[2], "utf8");
const stateful = (id) => ({
  name: "reflex___state.test.event",
  payload: { id },
});
const call = (fn, callback) => ({
  name: "_call_function",
  payload: { function: fn, callback },
});
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};

/** Bind dispatch arguments while keeping the real queue and handlers intact. */
async function createQueue(connected = true) {
  const output = [];
  const runtime = await createQueueRuntime(source, {
    uploadFiles: () => output.push("upload"),
  });
  const socket = {
    connected,
    emit: (_, event) => output.push(event.payload.id),
  };
  const navigate = (path, options) => output.push([path, options]);
  const params = { current: {} };
  return {
    runtime,
    socket,
    output,
    local: (id) => call(() => output.push(id)),
    enqueue: (events, prepend = false, target = socket) =>
      runtime.queueEvents(events, target, prepend, navigate, params),
    drain: () => runtime.processEvent(socket, navigate, params),
  };
}

/** Create the real addEvents callback with lightweight React hook stubs. */
async function createAddEvents() {
  const output = [];
  const actionKeys = [];
  const runtime = await createQueueRuntime(source, {
    throttle: (key) => {
      actionKeys.push(key);
      return true;
    },
  });
  const [addEvents] = runtime.useEventLoop({});
  return {
    actionKeys,
    addEvents,
    output,
    local: (id) => call(() => output.push(id)),
  };
}

for (const ref of [false, true]) {
  test(
    "FIFO filtering with " + (ref ? "reference" : "raw") + " sockets",
    async () => {
      const q = await createQueue();
      await q.enqueue(
        [null, stateful(1), undefined, q.local(2), stateful(3)],
        false,
        ref ? { current: q.socket } : q.socket,
      );
      assert.deepEqual(q.output, [1, 2, 3]);
      assert.equal(q.runtime.event_queue.length, 0);
      assert.equal(q.runtime.isStateful(), false);
    },
  );
}

test("offline stateful events hold the whole queue until reconnect", async () => {
  const q = await createQueue(false);
  await q.enqueue([q.local(1), stateful(2), q.local(3)]);
  assert.deepEqual(q.output, []);
  assert.equal(q.runtime.event_queue.length, 3);
  assert.equal(q.runtime.isStateful(), true);
  q.socket.connected = true;
  await q.drain();
  assert.deepEqual(q.output, [1, 2, 3]);
  assert.equal(q.runtime.event_queue.length, 0);
});

test("empty and local-only queues work with absent or disconnected sockets", async () => {
  for (const socket of [null, { current: null }, { connected: false }]) {
    const q = await createQueue();
    await q.enqueue([], false, socket);
    await q.enqueue([null, undefined], false, socket);
    await q.enqueue([q.local(1), q.local(2)], false, socket);
    assert.deepEqual(q.output, [1, 2]);
    assert.equal(q.runtime.event_queue.length, 0);
  }
});

test("prepend preserves order, queue identity, and input without extra shifts", async (t) => {
  const q = await createQueue(false);
  const pending = q.runtime.event_queue;
  const shift = (pending.shift = t.mock.fn(pending.shift));
  const existing = [stateful(3), q.local(4)];
  await q.enqueue(existing);
  const incoming = Object.freeze([
    Object.freeze([stateful(1), null]),
    Object.freeze([q.local(2), Object.freeze([undefined])]),
  ]);
  await q.enqueue(incoming, true);
  await q.enqueue([[], [null, [undefined]]], true);
  assert.equal(q.runtime.event_queue, pending);
  assert.deepEqual([...pending], [incoming[0][0], incoming[1][0], ...existing]);
  assert.equal(shift.mock.callCount(), 0);
  q.socket.connected = true;
  await q.drain();
  assert.deepEqual(q.output, [1, 2, 3, 4]);
  assert.equal(shift.mock.callCount(), 4);
  assert.equal(pending.length, 0);
});

for (const prepend of [false, true]) {
  test(
    "connected dispatch skips stateful scans, prepend=" + prepend,
    async (t) => {
      const q = await createQueue();
      const pending = q.runtime.event_queue;
      const scan = (pending.some = t.mock.fn(pending.some));
      for (const event of [q.local, stateful]) {
        await q.enqueue([event(1)], prepend);
        await q.drain();
        assert.equal(q.output.pop(), 1);
        assert.equal(q.output.length, 0);
        const ids = Array.from({ length: 32 }, (_, id) => id);
        await q.enqueue(ids.map(event), prepend);
        assert.deepEqual(q.output.splice(0), ids);
      }
      assert.equal(q.runtime.event_queue.length, 0);
      assert.equal(scan.mock.callCount(), 0);
    },
  );
}

test("disconnect during an event pauses remaining stateful events", async () => {
  const q = await createQueue();
  await q.enqueue([
    call(() => {
      q.output.push(1);
      q.socket.connected = false;
    }),
    q.local(2),
    stateful(3),
  ]);
  assert.deepEqual(q.output, [1]);
  assert.equal(q.runtime.event_queue.length, 2);
  q.socket.connected = true;
  await q.drain();
  assert.deepEqual(q.output, [1, 2, 3]);
});

for (const prepend of [false, true]) {
  test("reentrant dispatch preserves order, prepend=" + prepend, async () => {
    const q = await createQueue();
    let nested;
    await q.enqueue([
      call(() => {
        q.output.push(1);
        nested = q.enqueue([q.local(2)], prepend);
      }),
      q.local(3),
    ]);
    await nested;
    assert.deepEqual(q.output, prepend ? [1, 2, 3] : [1, 3, 2]);
    assert.equal(q.runtime.event_queue.length, 0);
  });
}

test("overlapping calls retain async callback and promise settling order", async () => {
  const q = await createQueue();
  const wait = deferred();
  let settled = false;
  const first = q
    .enqueue([
      call(
        () => {
          q.output.push(1);
          return wait.promise;
        },
        () => q.output.push(4),
      ),
      q.local(2),
    ])
    .then(() => {
      settled = true;
    });
  await q.enqueue([q.local(3)]);
  assert.deepEqual(q.output, [1, 2, 3]);
  await new Promise(setImmediate);
  assert.equal(settled, false);
  wait.resolve();
  await first;
  assert.deepEqual(q.output, [1, 2, 3, 4]);
  assert.equal(settled, true);
});

for (const alreadyMismatched of [false, true]) {
  test(
    "mismatch clears pending work after reconnect, already set=" +
      alreadyMismatched,
    async () => {
      const q = await createQueue(false);
      q.runtime.setMismatch(alreadyMismatched);
      await q.enqueue([stateful(1), q.local(2)]);
      q.runtime.setMismatch(true);
      await q.drain();
      assert.equal(q.runtime.event_queue.length, 2);
      q.socket.connected = true;
      await q.drain();
      assert.deepEqual(q.output, []);
      assert.equal(q.runtime.event_queue.length, 0);
      q.socket.connected = false;
      await q.enqueue([q.local(3)]);
      assert.deepEqual(q.output, []);
      assert.equal(q.runtime.event_queue.length, 0);
    },
  );
}

test("redirect and REST events retain ordering", async () => {
  const q = await createQueue();
  await q.enqueue([
    { name: "_redirect", payload: { path: "/next", replace: true } },
    {
      name: "reflex___state.test.upload",
      handler: "uploadFiles",
      payload: { files: [] },
    },
    q.local("last"),
  ]);
  assert.deepEqual(q.output, [["/next", { replace: true }], "upload", "last"]);
  assert.equal(q.runtime.event_queue.length, 0);
});

test("dispatch rejection does not block pending work", async (t) => {
  const q = await createQueue();
  const emit = t.mock.method(q.socket, "emit", () => {
    throw new Error("socket write failed");
  });
  await assert.rejects(
    q.enqueue([stateful(1), q.local(2)]),
    /socket write failed/,
  );
  assert.deepEqual(q.output, [2]);
  assert.equal(q.runtime.event_queue.length, 0);
  emit.mock.restore();
  await q.enqueue([stateful(3)]);
  assert.deepEqual(q.output, [2, 3]);
  assert.equal(q.runtime.event_queue.length, 0);
});

for (const rejection of [0, null]) {
  test(`falsy dispatch rejection ${rejection} is preserved`, async (t) => {
    const q = await createQueue();
    t.mock.method(q.socket, "emit", () => {
      throw rejection;
    });

    await assert.rejects(q.enqueue([stateful(1), q.local(2)]), (error) =>
      Object.is(error, rejection),
    );
    assert.deepEqual(q.output, [2]);
    assert.equal(q.runtime.event_queue.length, 0);
  });
}

test("addEvents flattens nested event lists before applying actions", async () => {
  const q = await createAddEvents();
  const actions = [];
  const browserEvent = {
    preventDefault: () => actions.push("preventDefault"),
    stopPropagation: () => actions.push("stopPropagation"),
  };
  const first = {
    ...q.local(1),
    event_actions: { preventDefault: true },
  };
  const second = {
    ...q.local(2),
    event_actions: { stopPropagation: true, throttle: 1 },
  };

  const generatedHandler = (event) =>
    q.addEvents(
      [[], [first, [null, second, [undefined]]], q.local(3)],
      [event],
      {},
    );
  await generatedHandler(browserEvent);

  assert.deepEqual(actions, ["preventDefault", "stopPropagation"]);
  assert.deepEqual(q.actionKeys, [
    "_call_function+++_call_function+++_call_function",
  ]);
  assert.deepEqual(q.output, [1, 2, 3]);
});

test("a malformed event does not strand later queued events", async () => {
  const q = await createQueue(false);
  q.socket.emit = (_, event) => {
    if (event.payload?.id !== undefined) q.output.push(event.payload.id);
  };

  q.runtime.event_queue.push({ name: 7 }, q.local(1));
  await q.drain();

  assert.deepEqual(q.output, [1]);
  assert.equal(q.runtime.event_queue.length, 0);
});

test("stateful arrival during an offline local await pauses the later drain", async () => {
  const q = await createQueue(false);
  const wait = deferred();
  const first = q.enqueue([
    call(
      () => wait.promise,
      () => q.output.push(1),
    ),
  ]);
  await q.enqueue([q.local(2), stateful(3)]);
  assert.deepEqual(q.output, []);
  wait.resolve();
  await first;
  assert.deepEqual(q.output, [1]);
  assert.equal(q.runtime.event_queue.length, 2);
  q.socket.connected = true;
  await q.drain();
  assert.deepEqual(q.output, [1, 2, 3]);
  assert.equal(q.runtime.event_queue.length, 0);
});
