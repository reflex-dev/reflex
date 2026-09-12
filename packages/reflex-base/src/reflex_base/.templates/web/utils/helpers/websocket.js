// Plain WebSocket transport speaking the Reflex JSON event protocol: each
// frame is a JSON array `[event_name, payload]`. Mirrors the socket.io-client
// surface that state.js and upload.js rely on: connected, connect(),
// disconnect(), emit(), on(), io.opts.query, and _callbacks.

// Protocol-level message names (must match reflex/event_namespace.py).
const HANDSHAKE_MESSAGE = "_handshake";
const PING_MESSAGE = "_ping";
const PONG_MESSAGE = "_pong";
const OPEN_MESSAGE = "_open";
const OPENED_MESSAGE = "_opened";
const CHANNEL_ERROR_MESSAGE = "_error";

// Backend protocol version that speaks channels. A backend older than this
// closes the connection on a binary frame, so channels stay shut until the
// handshake proves otherwise.
const CHANNEL_PROTOCOL_VERSION = 2;

// Binary frames align every attachment to this boundary, so a handler can
// view one as a Float64Array without copying.
const FRAME_ALIGNMENT = 8;

// Messages a channel buffers while it is not open, oldest dropped first.
const MAX_QUEUED_CHANNEL_MESSAGES = 64;

// Attachments one channel message may carry (must match
// reflex.channels.MAX_MESSAGE_BUFFERS). The backend closes the connection over
// a frame that breaks its limits, so they are enforced here, where the mistake
// is, rather than losing the app's socket for it.
const MAX_MESSAGE_BUFFERS = 64;

// A channel handle reports its own lifecycle under these names, so a message
// may not use them (must match reflex.channels.RESERVED_EVENTS).
const LIFECYCLE_EVENTS = new Set(["connect", "disconnect", "error"]);

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
 * Serialize one channel message: binary when it carries attachments.
 * @param event The message name.
 * @param data The JSON metadata.
 * @param channel The channel name.
 * @param buffers Binary attachments (ArrayBuffers or typed arrays).
 * @returns The serialized frame, text or binary.
 */
const channelFrame = (event, data, channel, buffers) =>
  buffers?.length
    ? encodeChannelFrame(event, data, channel, buffers)
    : stringifyFrame([event, data, channel]);

/**
 * Whether a parsed frame names a channel, which only a channel message does.
 * @param message The parsed frame.
 * @returns Whether it carries a channel name after the event and its payload.
 */
const isChannelMessage = (message) =>
  Array.isArray(message) && message.length > 2;

/**
 * Whether a serialized frame carries a channel message.
 * @param frame The serialized text or binary frame.
 * @returns True for a binary frame, or a text frame naming a channel.
 */
const isChannelFrame = (frame) =>
  // Only channel messages carry attachments, so only they go out binary.
  typeof frame !== "string" ||
  isChannelMessage(parseJsonLenient(frame, undefined));

/**
 * Whether a serialized frame is over the backend's inbound message limit.
 *
 * Mirrors the check the backend applies before closing the connection: the
 * limit counts UTF-8 bytes, and UTF-8 is 1-4 bytes per character, so a text
 * frame is only measured exactly when the cheap bounds cannot settle it.
 * @param frame The serialized text or binary frame.
 * @param limit The limit in bytes.
 * @returns Whether the frame exceeds it.
 */
const exceedsMessageLimit = (frame, limit) => {
  if (typeof frame !== "string") {
    return frame.byteLength > limit;
  }
  if (frame.length > limit) {
    return true;
  }
  if (frame.length * 4 <= limit) {
    return false;
  }
  return new TextEncoder().encode(frame).byteLength > limit;
};

/**
 * The size a serialized frame occupies on the wire, for diagnostics.
 * @param frame The serialized text or binary frame.
 * @returns The size in bytes.
 */
const frameByteLength = (frame) =>
  typeof frame === "string"
    ? new TextEncoder().encode(frame).byteLength
    : frame.byteLength;

/**
 * Serialize an outgoing frame.
 * @param frame The frame array to serialize.
 * @returns The JSON string.
 */
const stringifyFrame = (frame) => JSON.stringify(frame, undefinedToNull);

/**
 * View any binary value as bytes without copying it.
 * @param buffer An ArrayBuffer, typed array or DataView.
 * @returns A Uint8Array over the same memory.
 */
const asBytes = (buffer) =>
  buffer instanceof ArrayBuffer
    ? new Uint8Array(buffer)
    : new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength);

/**
 * Bytes of padding needed to reach the next attachment boundary.
 * @param offset The current offset.
 * @returns The padding length.
 */
const padding = (offset) =>
  (FRAME_ALIGNMENT - (offset % FRAME_ALIGNMENT)) % FRAME_ALIGNMENT;

/**
 * Serialize a channel message carrying binary attachments.
 * @param event The message name.
 * @param data The JSON metadata.
 * @param channel The channel name.
 * @param buffers The binary attachments.
 * @returns The frame as an ArrayBuffer.
 */
export const encodeChannelFrame = (event, data, channel, buffers) => {
  const views = buffers.map(asBytes);
  const header = new TextEncoder().encode(
    stringifyFrame([event, data, channel, views.map((v) => v.byteLength)]),
  );
  let size = 4 + header.byteLength;
  for (const view of views) {
    size += padding(size) + view.byteLength;
  }
  const frame = new ArrayBuffer(size);
  const bytes = new Uint8Array(frame);
  new DataView(frame).setUint32(0, header.byteLength, true);
  bytes.set(header, 4);
  let offset = 4 + header.byteLength;
  for (const view of views) {
    offset += padding(offset);
    bytes.set(view, offset);
    offset += view.byteLength;
  }
  return frame;
};

/**
 * Deserialize a binary channel frame.
 * @param frame The received ArrayBuffer.
 * @returns [event, data, channel, buffers], or undefined if malformed.
 */
export const decodeChannelFrame = (frame) => {
  if (frame.byteLength < 4) {
    return undefined;
  }
  const headerSize = new DataView(frame).getUint32(0, true);
  if (4 + headerSize > frame.byteLength) {
    return undefined;
  }
  const header = parseJsonLenient(
    new TextDecoder().decode(new Uint8Array(frame, 4, headerSize)),
    undefined,
  );
  if (!Array.isArray(header) || !Array.isArray(header[3])) {
    return undefined;
  }
  const [event, data, channel, lengths] = header;
  const buffers = [];
  let offset = 4 + headerSize;
  for (const length of lengths) {
    offset += padding(offset);
    if (offset + length > frame.byteLength) {
      return undefined;
    }
    buffers.push(new Uint8Array(frame, offset, length));
    offset += length;
  }
  return [event, data, channel, buffers];
};

/**
 * Local handler registry shared by the transport and its channels.
 *
 * Handlers are keyed with socket.io's "$"-prefixed convention because
 * upload.js reads `socket._callbacks.$event` directly.
 */
class LocalEmitter {
  /**
   * Create an emitter with no handlers registered.
   */
  constructor() {
    this._callbacks = {};
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
   * Remove a handler, every handler for an event, or all of them.
   * @param event The event name; omit to remove all handlers.
   * @param fn The handler to remove; omit to remove all handlers for event.
   */
  off(event, fn) {
    if (event === undefined) {
      this._callbacks = {};
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
   * Invoke the registered handlers for a local event.
   * @param event The event name.
   * @param args The handler arguments.
   */
  _emitLocal(event, ...args) {
    for (const fn of this._callbacks["$" + event] ?? []) {
      fn(...args);
    }
  }
}

// Channel handles by name, and the transport they currently ride. A handle
// outlives every transport: the event loop recreates the socket on remount and
// hot reload, and a channel must survive that without its consumer
// re-registering handlers.
const channels = new Map();
let activeTransport = null;
let channelsUnsupportedReason = null;

class ReflexChannel extends LocalEmitter {
  /**
   * Create a channel handle. Use getChannel() instead of constructing one.
   *
   * Handlers live on the channel rather than on the transport, whose table
   * the event loop clears wholesale with socket.off() on unmount.
   * @param name The channel name, matching the backend registration.
   */
  constructor(name) {
    super();
    this.name = name;
    this.connected = false;
    this._queue = [];
    this._transport = null;
  }

  /**
   * Send a message to the channel's backend, buffering until it is open.
   * @param event The message name.
   * @param data The JSON metadata.
   * @param buffers Binary attachments (ArrayBuffers or typed arrays).
   */
  emit(event, data, buffers = []) {
    if (buffers?.length > MAX_MESSAGE_BUFFERS) {
      throw new Error(
        `Channel message "${event}" carries ${buffers.length} attachments, ` +
          `over the ${MAX_MESSAGE_BUFFERS} a frame may hold.`,
      );
    }
    // Serialize now, connected or not: a queued frame must carry what was
    // emitted, not whatever the caller's payload and typed arrays hold by the
    // time the channel opens.
    const frame = channelFrame(event, data, this.name, buffers);
    const limit = this._transport?._maxMessageSize;
    if (limit && exceedsMessageLimit(frame, limit)) {
      throw new Error(
        `Channel message "${event}" is ${frameByteLength(frame)} bytes, over ` +
          `the ${limit} the backend accepts ` +
          "(REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE).",
      );
    }
    if (this.connected && this._transport) {
      this._transport._send(frame);
      return;
    }
    if (this._queue.length >= MAX_QUEUED_CHANNEL_MESSAGES) {
      // The backend is unreachable and the producer is not waiting for
      // "connect"; drop the oldest rather than grow without bound.
      this._queue.shift();
    }
    this._queue.push(frame);
  }

  /**
   * Open the channel on a newly connected transport.
   * @param transport The connected transport.
   */
  _attach(transport) {
    this._transport = transport;
    transport.emitChannel(this.name, OPEN_MESSAGE, null, []);
  }

  /**
   * Report the transport going away; queued messages survive for the next one.
   * @param reason The disconnect reason.
   */
  _detach(reason) {
    this._transport = null;
    if (this.connected) {
      this.connected = false;
      this._emitLocal("disconnect", reason);
    }
  }

  /**
   * Report that this deployment cannot carry channels at all.
   * @param reason Why channels are unavailable.
   */
  _unsupported(reason) {
    this._emitLocal("error", { code: "channels_unsupported", message: reason });
  }

  /**
   * Dispatch one message received for this channel.
   * @param event The message name.
   * @param data The JSON metadata.
   * @param buffers Binary attachments, as Uint8Array views.
   */
  _receive(event, data, buffers) {
    if (event === OPENED_MESSAGE) {
      if (this._transport === null) {
        // A straggler from a transport this channel is no longer on; the queue
        // belongs to whichever transport it attaches to next.
        return;
      }
      this.connected = true;
      const queued = this._queue;
      this._queue = [];
      const limit = this._transport._maxMessageSize;
      for (const frame of queued) {
        // A message emitted before the channel opened was queued without a
        // limit to check it against; now there is one, and sending it anyway
        // would cost the app its websocket.
        if (limit && exceedsMessageLimit(frame, limit)) {
          this._emitLocal("error", {
            code: "message_too_large",
            message:
              `A queued channel message is ${frameByteLength(frame)} bytes, ` +
              `over the ${limit} the backend accepts; it was dropped.`,
          });
          continue;
        }
        // The transport re-queues it if its socket closed mid-flush.
        this._transport._send(frame);
      }
      this._emitLocal("connect");
      return;
    }
    if (event === CHANNEL_ERROR_MESSAGE) {
      this._emitLocal("error", data);
      return;
    }
    if (LIFECYCLE_EVENTS.has(event)) {
      // The backend rejects these names; a frame carrying one is not from a
      // Reflex backend and must not be mistaken for the handle's own events.
      console.error(`Ignoring channel message named "${event}" (reserved)`);
      return;
    }
    this._emitLocal(event, data, buffers);
  }
}

/**
 * Get the handle for a named channel, creating it on first use.
 * @param name The channel name, matching the backend registration.
 * @returns The channel handle.
 */
export const getChannel = (name) => {
  let channel = channels.get(name);
  if (channel === undefined) {
    channel = new ReflexChannel(name);
    channels.set(name, channel);
    if (channelsUnsupportedReason !== null) {
      // After this turn: the caller registers its "error" handler on the
      // handle we are still returning.
      const reason = channelsUnsupportedReason;
      queueMicrotask(() => channel._unsupported(reason));
    } else if (activeTransport !== null) {
      channel._attach(activeTransport);
    }
  }
  return channel;
};

/**
 * Declare that channels cannot run against this backend, failing every handle.
 * @param reason Why channels are unavailable.
 */
export const disableChannels = (reason) => {
  if (channelsUnsupportedReason === reason) {
    // Already reported; a remount must not fire "error" at every consumer again.
    return;
  }
  channelsUnsupportedReason = reason;
  activeTransport = null;
  for (const channel of channels.values()) {
    channel._detach(reason);
    channel._unsupported(reason);
  }
};

/**
 * Open every channel on a transport that just finished its handshake.
 * @param transport The connected transport.
 */
const attachChannels = (transport) => {
  channelsUnsupportedReason = null;
  activeTransport = transport;
  for (const channel of channels.values()) {
    channel._attach(transport);
  }
};

/**
 * Detach every channel from a transport that went away.
 * @param transport The transport reporting the disconnect.
 * @param reason The disconnect reason.
 */
const detachChannels = (transport, reason) => {
  if (activeTransport !== transport) {
    return;
  }
  activeTransport = null;
  for (const channel of channels.values()) {
    channel._detach(reason);
  }
};

export class ReflexWebSocket extends LocalEmitter {
  /**
   * Create the transport and start connecting.
   * @param url The http(s) endpoint URL of the backend event route.
   * @param opts Options: `query` (object) and `protocols` (subprotocol list).
   */
  constructor(url, opts) {
    super();
    this._url = new URL(url);
    // Exposed as io.opts for socket.io API compatibility: state.js refreshes
    // io.opts.query before reconnecting.
    this.io = { opts };
    this.connected = false;
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
    // The backend's inbound message limit, learned from the handshake.
    this._maxMessageSize = null;
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
    super.off(event, fn);
    if (event === undefined && this._offlineListener) {
      removeEventListener("offline", this._offlineListener, false);
      this._offlineListener = null;
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
    // Channel attachments arrive as binary frames; take them as ArrayBuffers
    // so handlers can view them as typed arrays without a copy.
    ws.binaryType = "arraybuffer";
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
      detachChannels(this, this._closeReason ?? "transport close");
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
    detachChannels(this, reason);
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
    this._send(stringifyFrame([event, data]));
  }

  /**
   * Send a channel message to the backend, buffering while disconnected.
   * @param channel The channel name.
   * @param event The message name.
   * @param data The JSON metadata.
   * @param buffers Binary attachments (ArrayBuffers or typed arrays).
   */
  emitChannel(channel, event, data, buffers) {
    this._send(channelFrame(event, data, channel, buffers));
  }

  /**
   * Write one serialized frame, buffering while disconnected.
   * @param frame The serialized text or binary frame.
   */
  _send(frame) {
    if (this.connected && this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(frame);
    } else {
      this._sendQueue.push(frame);
    }
  }

  /**
   * Handle one incoming frame.
   * @param data The raw frame: text, or an ArrayBuffer for a channel message.
   */
  _onMessage(data) {
    if (data instanceof ArrayBuffer) {
      const frame = decodeChannelFrame(data);
      if (frame === undefined) {
        console.error("Failed to parse binary websocket message");
        return;
      }
      const [event, payload, channel, buffers] = frame;
      channels.get(channel)?._receive(event, payload, buffers);
      return;
    }
    const text = data;
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
      this._maxMessageSize = payload.max_message_size ?? null;
      // Open the channels first: a frame queued on the transport for one of
      // them has to arrive after its _open, or the backend has no session to
      // dispatch it to and answers channel_not_open.
      if ((payload.protocol ?? 1) >= CHANNEL_PROTOCOL_VERSION) {
        attachChannels(this);
      } else {
        // A backend older than the channel protocol closes the connection on
        // the binary frames channels use, so never open one against it.
        disableChannels(
          "This backend predates channel support; upgrade Reflex to use channels.",
        );
        // A channel frame queued against an earlier connection would reach a
        // backend that closes the socket over it, costing the app its state
        // updates too.
        this._sendQueue = this._sendQueue.filter(
          (frame) => !isChannelFrame(frame),
        );
      }
      const queue = this._sendQueue;
      this._sendQueue = [];
      for (const frame of queue) {
        this._ws.send(frame);
      }
      this._emitLocal("connect");
      return;
    }
    if (isChannelMessage(message)) {
      channels.get(message[2])?._receive(event, payload, []);
      return;
    }
    this._emitLocal(event, payload);
  }

  /**
   * Drop the socket as a transport failure, which the event loop reconnects
   * from -- unlike disconnect(), which reports an intentional close.
   * @param reason The disconnect reason to report.
   */
  _dropConnection(reason) {
    if (this._ws && this.connected) {
      this._closeReason = reason;
      this._ws.close();
    }
  }

  /**
   * (Re)arm the dead-connection watchdog; fires when no message (heartbeat
   * included) arrives within the server's ping interval + timeout.
   */
  _resetWatchdog() {
    this._clearWatchdog();
    this._watchdogTimer = setTimeout(
      () => this._dropConnection("ping timeout"),
      this._watchdogMs,
    );
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
