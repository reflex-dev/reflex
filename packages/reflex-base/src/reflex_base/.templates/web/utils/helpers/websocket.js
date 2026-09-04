// Plain WebSocket transport speaking the Reflex JSON event protocol: each
// frame is a JSON array `[event_name, payload]`. Mirrors the socket.io-client
// surface that state.js and upload.js rely on: connected, connect(),
// disconnect(), emit(), on(), io.opts.query, and _callbacks.

// Protocol-level message names (must match reflex/event_namespace.py).
const HANDSHAKE_MESSAGE = "_handshake";
const PING_MESSAGE = "_ping";
const PONG_MESSAGE = "_pong";

// Python's json.dumps emits bare Infinity/-Infinity/NaN tokens (invalid JSON).
// Rewrite them outside string literals so JSON.parse accepts the payload.
// 1e999 / -1e999 overflow to ±Infinity; NaN has no JSON literal, so it is
// swapped for a sentinel string and revived back to NaN after parsing.
// The alternation matches whole string literals first (passed through unchanged),
// guaranteeing bare-token matches only land in numeric positions.
const NAN_SENTINEL = "__reflex_nan__";
const NON_FINITE_FLOAT_RE = /"(?:[^"\\]|\\.)*"|-?\bInfinity\b|\bNaN\b/g;
const NON_FINITE_REPLACEMENTS = {
  Infinity: "1e999",
  "-Infinity": "-1e999",
  NaN: `"${NAN_SENTINEL}"`,
};
const rewriteBareNonFiniteFloats = (str) =>
  str.replace(NON_FINITE_FLOAT_RE, (match) =>
    match[0] === '"' ? match : NON_FINITE_REPLACEMENTS[match],
  );
const reviveNonFiniteFloats = (_k, v) => (v === NAN_SENTINEL ? NaN : v);

/**
 * JSON.stringify replacer that sends undefined fields as null instead of
 * removing them. Also assigned as the socket.io encoder replacer.
 * @param _k The key being serialized.
 * @param v The value being serialized.
 * @returns The value to serialize.
 */
export const undefinedToNull = (_k, v) => (v === undefined ? null : v);

/**
 * Parse JSON, tolerating bare non-finite float tokens.
 * @param text The text to parse.
 * @param fallback The value to return if the text is unparsable.
 * @returns The parsed value, or the fallback.
 */
export const parseJsonLenient = (text, fallback) => {
  try {
    return JSON.parse(text);
  } catch (e) {
    try {
      return JSON.parse(
        rewriteBareNonFiniteFloats(text),
        reviveNonFiniteFloats,
      );
    } catch (e2) {
      return fallback;
    }
  }
};

/**
 * Serialize an outgoing frame.
 * @param frame The frame array to serialize.
 * @returns The JSON string.
 */
const stringifyFrame = (frame) => JSON.stringify(frame, undefinedToNull);

export class ReflexWebSocket {
  /**
   * Create the transport and start connecting.
   * @param url The http(s) endpoint URL of the backend event route.
   * @param opts Options: `query` (object) and `protocols` (subprotocol list).
   */
  constructor(url, opts) {
    this._url = new URL(url);
    // Exposed as io.opts for socket.io API compatibility: state.js refreshes
    // io.opts.query before reconnecting.
    this.io = { opts };
    this.connected = false;
    // upload.js reads socket._callbacks.$event directly.
    this._callbacks = {};
    this._ws = null;
    // Frames emitted while disconnected, flushed on (re)connect.
    this._sendQueue = [];
    this._watchdogTimer = null;
    // Heartbeat window: 145 seconds (25s ping interval + 120s ping timeout)
    // in ms; refined by the server handshake.
    this._watchdogMs = (25 + 120) * 1000;
    // Give up after 20 seconds on a dial that neither opens nor errors, so
    // a connect_error always fires and retries proceed.
    this._connectTimeoutMs = 20 * 1000;
    this._connectTimer = null;
    this._closeReason = null;
    // Network emulation and OS offline do not interrupt established
    // websockets, so treat the browser's offline event as a disconnect.
    // Localhost connections keep working offline.
    this._offlineListener = null;
    if (
      typeof addEventListener === "function" &&
      this._url.hostname !== "localhost"
    ) {
      this._offlineListener = () => this._onOffline();
      addEventListener("offline", this._offlineListener, false);
    }
    this.connect();
  }

  /**
   * Remove registered handlers. With no arguments, also releases the global
   * offline listener (transport disposal).
   * @param event The event name; omit to remove all handlers.
   * @param fn The handler to remove; omit to remove all handlers for event.
   */
  off(event, fn) {
    if (event === undefined) {
      this._callbacks = {};
      if (this._offlineListener) {
        removeEventListener("offline", this._offlineListener, false);
        this._offlineListener = null;
      }
      return;
    }
    if (fn === undefined) {
      delete this._callbacks["$" + event];
      return;
    }
    const handlers = this._callbacks["$" + event];
    const ix = handlers ? handlers.indexOf(fn) : -1;
    if (ix !== -1) {
      handlers.splice(ix, 1);
    }
  }

  /**
   * Register a handler for an event.
   * @param event The event name.
   * @param fn The handler function.
   */
  on(event, fn) {
    (this._callbacks["$" + event] ??= []).push(fn);
  }

  /**
   * Invoke the registered handlers for a local event.
   * @param event The event name.
   * @param args The handler arguments.
   */
  _emitLocal(event, ...args) {
    for (const fn of this._callbacks["$" + event] ?? []) {
      fn(...args);
    }
  }

  /**
   * Open the websocket connection if not already open or connecting.
   */
  connect() {
    if (this._ws && this._ws.readyState <= WebSocket.OPEN) {
      // CONNECTING (0) or OPEN (1): already dialing or connected.
      return;
    }
    const url = new URL(this._url);
    // Secure endpoints (https or already-wss) stay secure.
    url.protocol =
      url.protocol === "https:" || url.protocol === "wss:" ? "wss:" : "ws:";
    url.search = new URLSearchParams(this.io.opts.query ?? {}).toString();
    this._closeReason = null;
    const ws = new WebSocket(url, this.io.opts.protocols);
    this._ws = ws;
    this._connectTimer = setTimeout(() => {
      if (this._ws === ws && !this.connected) {
        ws.close();
      }
    }, this._connectTimeoutMs);
    ws.onmessage = (msg) => {
      if (this._ws === ws) {
        // Ignore stragglers from a superseded connection.
        this._onMessage(msg.data);
      }
    };
    ws.onclose = (event) => {
      if (this._ws !== ws) {
        // A newer connection or an explicit disconnect() superseded this one.
        return;
      }
      this._clearConnectTimer();
      this._clearWatchdog();
      const wasConnected = this.connected;
      this.connected = false;
      if (!wasConnected) {
        // Never handshaked: this was a failed connection attempt.
        this._emitLocal(
          "connect_error",
          new Error("websocket connection failed"),
        );
      } else {
        this._emitLocal("disconnect", this._closeReason ?? "transport close", {
          code: event.code,
          reason: event.reason,
        });
      }
    };
  }

  /**
   * Close the connection deliberately (reason "io client disconnect").
   */
  disconnect() {
    this._teardown("io client disconnect", undefined);
  }

  /**
   * Report the disconnect immediately when the browser goes offline.
   */
  _onOffline() {
    if (this.connected) {
      this._teardown("transport close", {
        description: "network connection lost",
      });
    }
  }

  /**
   * Tear down the current connection, reporting the disconnect synchronously
   * (onclose may never fire during page unload or while offline).
   * @param reason The disconnect reason to report.
   * @param details The disconnect details to report.
   */
  _teardown(reason, details) {
    this._clearConnectTimer();
    this._clearWatchdog();
    const ws = this._ws;
    if (!ws) {
      return;
    }
    // Detach so the onclose handler does not double-report.
    this._ws = null;
    if (this.connected) {
      this.connected = false;
      this._emitLocal("disconnect", reason, details);
    }
    if (ws.readyState <= WebSocket.OPEN) {
      ws.onclose = null;
      ws.onmessage = null;
      ws.close(1000);
    }
  }

  /**
   * Send an event to the backend, buffering while disconnected.
   * @param event The event name.
   * @param data The event payload.
   */
  emit(event, data) {
    const frame = stringifyFrame([event, data]);
    if (this.connected && this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(frame);
    } else {
      this._sendQueue.push(frame);
    }
  }

  /**
   * Handle one incoming frame.
   * @param text The raw frame text.
   */
  _onMessage(text) {
    const message = parseJsonLenient(text, undefined);
    if (!Array.isArray(message)) {
      console.error("Failed to parse websocket message", text);
      return;
    }
    const [event, payload] = message;
    if (event === PING_MESSAGE) {
      // The server pings every interval regardless of traffic, so resetting
      // the watchdog only here avoids timer churn per data message.
      this._resetWatchdog();
      this._ws?.send(stringifyFrame([PONG_MESSAGE]));
      return;
    }
    if (event === HANDSHAKE_MESSAGE) {
      // Application-level liveness confirmed; adopt the server's heartbeat
      // settings (sent in seconds, converted to ms) for the connection
      // watchdog.
      this._clearConnectTimer();
      this._watchdogMs = (payload.ping_interval + payload.ping_timeout) * 1000;
      this._resetWatchdog();
      this.connected = true;
      const queue = this._sendQueue;
      this._sendQueue = [];
      for (const frame of queue) {
        this._ws.send(frame);
      }
      this._emitLocal("connect");
      return;
    }
    this._emitLocal(event, payload);
  }

  /**
   * (Re)arm the dead-connection watchdog; fires when no message (heartbeat
   * included) arrives within the server's ping interval + timeout.
   */
  _resetWatchdog() {
    this._clearWatchdog();
    this._watchdogTimer = setTimeout(() => {
      if (this._ws && this.connected) {
        this._closeReason = "ping timeout";
        this._ws.close();
      }
    }, this._watchdogMs);
  }

  /**
   * Cancel the dead-connection watchdog.
   */
  _clearWatchdog() {
    if (this._watchdogTimer) {
      clearTimeout(this._watchdogTimer);
      this._watchdogTimer = null;
    }
  }

  /**
   * Cancel the connect timeout.
   */
  _clearConnectTimer() {
    if (this._connectTimer) {
      clearTimeout(this._connectTimer);
      this._connectTimer = null;
    }
  }
}
