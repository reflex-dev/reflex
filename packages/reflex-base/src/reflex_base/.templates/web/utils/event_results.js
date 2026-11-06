/**
 * Results of backend events dispatched from the frontend.
 *
 * Every event sent to the backend carries a request id. The backend answers
 * with result records riding the "event" socket message: a value the handler
 * yielded or returned, the completion of the request, or its failure. Each
 * dispatch returns a `ResultStream` that receives those records.
 *
 * Kept free of npm imports, so it can be unit tested on its own.
 */

/**
 * The values a backend event handler yields or returns, as they arrive.
 *
 * Iterate it with `for await` to receive each value in order, or await it to
 * get the last value (undefined when the handler produced none). It rejects
 * when the handler raised, or when the connection dropped before the handler
 * finished. It is a thenable rather than a Promise, so a dispatch nobody
 * awaits never reports an unhandled rejection.
 */
export class ResultStream {
  constructor() {
    // Every value received so far, so each iterator sees all of them.
    this.values = [];
    // Whether the stream completed or failed; no value arrives after that.
    this.settled = false;
    // Whether the backend cancelled the handler before it finished.
    this.cancelled = false;
    // The error the stream failed with, when it failed.
    this.error = undefined;
    this._failed = false;
    // Wakes iterators waiting for the next value or the end.
    this._waiters = [];
    // Streams receiving this one's values and outcome (merges, deferred streams).
    this._sinks = [];
    // The completion promise, created on the first then().
    this._promise = undefined;
    this._resolve = undefined;
    this._reject = undefined;
  }

  /**
   * A stream that already completed without values.
   * @returns {ResultStream} The completed stream.
   */
  static completed() {
    const stream = new ResultStream();
    stream.close();
    return stream;
  }

  /**
   * A stream merging several in arrival order, completing once all of them have.
   * It fails with the first of them to fail.
   * @param {ResultStream[]} streams The streams to merge.
   * @returns {ResultStream} The merged stream, or the only one given.
   */
  static merge(streams) {
    if (streams.length === 1) {
      return streams[0];
    }
    const merged = new ResultStream();
    let open = streams.length;
    if (open === 0) {
      merged.close();
      return merged;
    }
    const sink = {
      push: (value) => merged.push(value),
      close: () => {
        if (--open === 0) {
          merged.close();
        }
      },
      fail: (error) => merged.fail(error),
    };
    for (const stream of streams) {
      stream.pipe(sink);
    }
    return merged;
  }

  /**
   * Receive a value.
   * @param value The value the handler yielded or returned.
   */
  push(value) {
    if (this.settled) {
      return;
    }
    this.values.push(value);
    for (const sink of this._sinks) {
      sink.push(value);
    }
    this._wake();
  }

  /**
   * Complete the stream.
   * @param {boolean} cancelled Whether the handler was cancelled.
   */
  close(cancelled = false) {
    if (this.settled) {
      return;
    }
    this.settled = true;
    this.cancelled = cancelled;
    for (const sink of this._sinks) {
      sink.close(cancelled);
    }
    this._sinks = [];
    this._resolve?.(this.values.at(-1));
    this._wake();
  }

  /**
   * Fail the stream.
   * @param {Error} error Why it failed.
   */
  fail(error) {
    if (this.settled) {
      return;
    }
    this.settled = true;
    this._failed = true;
    this.error = error;
    for (const sink of this._sinks) {
      sink.fail(error);
    }
    this._sinks = [];
    this._reject?.(error);
    this._wake();
  }

  /**
   * Forward the values received so far and from now on, and the outcome.
   * @param sink An object with push, close and fail, such as another stream.
   */
  pipe(sink) {
    for (const value of this.values) {
      sink.push(value);
    }
    if (!this.settled) {
      this._sinks.push(sink);
    } else if (this._failed) {
      sink.fail(this.error);
    } else {
      sink.close(this.cancelled);
    }
  }

  /**
   * Follow what a dispatch returned: a stream is piped in, anything else
   * (nothing was sent) completes this stream.
   * @param result What the dispatch returned.
   */
  follow(result) {
    if (result instanceof ResultStream) {
      result.pipe(this);
    } else {
      this.close();
    }
  }

  _wake() {
    const waiters = this._waiters;
    this._waiters = [];
    for (const wake of waiters) {
      wake();
    }
  }

  [Symbol.asyncIterator]() {
    let index = 0;
    const next = async () => {
      while (index >= this.values.length && !this.settled) {
        await new Promise((wake) => this._waiters.push(wake));
      }
      if (index < this.values.length) {
        return { value: this.values[index++], done: false };
      }
      if (this._failed) {
        throw this.error;
      }
      return { value: undefined, done: true };
    };
    return {
      next,
      // Leaving a `for await` early stops this iterator, not the handler.
      return: async (value) => {
        index = Infinity;
        return { value, done: true };
      },
      [Symbol.asyncIterator]() {
        return this;
      },
    };
  }

  then(onFulfilled, onRejected) {
    if (this._promise === undefined) {
      this._promise = new Promise((resolve, reject) => {
        if (!this.settled) {
          this._resolve = resolve;
          this._reject = reject;
        } else if (this._failed) {
          reject(this.error);
        } else {
          resolve(this.values.at(-1));
        }
      });
    }
    return this._promise.then(onFulfilled, onRejected);
  }

  catch(onRejected) {
    return this.then(undefined, onRejected);
  }

  finally(onFinally) {
    return this.then().finally(onFinally);
  }
}

// A random prefix per page load: a reload forgets the pending requests, so a
// late result for a request from before it must not match a new id.
const REQUEST_ID_PREFIX = Math.random().toString(36).slice(2, 10);
let requestCounter = 0;

// The streams of requests sent to the backend and not yet completed, by id.
const pending = new Map();

/**
 * Register a stream for a request about to be sent, under a new id.
 * @param {ResultStream} stream The stream receiving the request's results.
 * @returns {string} The request id to send with the event.
 */
export const registerRequest = (stream) => {
  const id = `${REQUEST_ID_PREFIX}:${(requestCounter++).toString(36)}`;
  pending.set(id, stream);
  return id;
};

/**
 * Route result records from the backend to their streams.
 *
 * Records for unknown ids (requests from before a reload, or already failed by
 * a disconnect) are ignored.
 * @param {Array<Object>} records The records of one state update.
 */
export const applyResults = (records) => {
  for (const record of records) {
    const stream = pending.get(record.id);
    if (stream === undefined) {
      continue;
    }
    if ("value" in record) {
      stream.push(record.value);
    }
    if (record.error !== undefined) {
      pending.delete(record.id);
      stream.fail(new Error(record.error));
    } else if (record.done) {
      pending.delete(record.id);
      stream.close(!!record.cancelled);
    }
  }
};

/**
 * Fail every request sent and not completed, e.g. when the connection drops:
 * results emitted while disconnected never arrive.
 * @param {Error} error Why they failed.
 */
export const failPendingRequests = (error) => {
  const streams = [...pending.values()];
  pending.clear();
  for (const stream of streams) {
    stream.fail(error);
  }
};

// Per debounce key, the stream every call in the open window shares.
const debounced = {};

/**
 * The stream shared by the calls in a debounce window, bound to the dispatch
 * that fires when the window closes.
 * @param {string} key The debounce key.
 * @param {Function} schedule Called with the function to run when the window
 *   closes, to (re)start the debounce timer.
 * @param {Function} dispatch Runs the dispatch, returning its stream.
 * @returns {ResultStream} The shared stream.
 */
export const debouncedResult = (key, schedule, dispatch) => {
  const stream = (debounced[key] ??= new ResultStream());
  schedule(() => {
    delete debounced[key];
    stream.follow(dispatch());
  });
  return stream;
};

// Per throttle key, the stream of the last dispatch that went through.
const throttled = {};

/**
 * Remember the stream of a throttled dispatch that went through.
 * @param {string} key The throttle key.
 * @param result What the dispatch returned.
 * @returns What the dispatch returned.
 */
export const recordThrottled = (key, result) => {
  if (result instanceof ResultStream) {
    throttled[key] = result;
  } else {
    delete throttled[key];
  }
  return result;
};

/**
 * The stream for a call the throttle dropped: the last dispatch's while it is
 * still open, otherwise one already completed.
 * @param {string} key The throttle key.
 * @returns {ResultStream} The stream.
 */
export const throttledResult = (key) => {
  const last = throttled[key];
  if (last !== undefined && !last.settled) {
    return last;
  }
  delete throttled[key];
  return ResultStream.completed();
};
