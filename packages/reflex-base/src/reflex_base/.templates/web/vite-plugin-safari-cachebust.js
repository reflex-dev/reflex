/* vite-plugin-safari-cachebust.js
 *
 * Rewrite modulepreload <link> tags and ESM imports to include a cache-busting
 * query parameter for Safari browser.
 *
 * https://github.com/remix-run/react-router/issues/12761
 *
 * The issue seems to be Safari over-aggressive caching of ESM imports (and modulepreload)
 * which does not respect the cache-control headers sent by the server. This approach
 * allows hot reload to work in Safari when adding routes or changing dependencies.
 *
 * No equivalent transformation is needed for production builds, as the
 * output already contains the file hash in the name.
 */

import { StringDecoder } from "node:string_decoder";

/**
 * @typedef {import('vite').Plugin} Plugin
 * @typedef {import('vite').ViteDevServer} ViteDevServer
 * @typedef {import('http').IncomingMessage} IncomingMessage
 * @typedef {import('http').ServerResponse} ServerResponse
 * @typedef {import('connect').NextHandleFunction} NextHandleFunction
 */

const pluginName = "vite-plugin-safari-cachebust";
const tsParam = "__reflex_ts";
const linkTagRe = /<link\s+rel="modulepreload"\s+href="([^"]+)"[^>]*>/g;
const tsUrlRe = new RegExp(`(\\?|&)${tsParam}=\\d+`);

/**
 * Creates a Vite plugin that adds cache-busting for Safari browsers
 * @returns {Plugin} The Vite plugin
 */
export default function safariCacheBustPlugin() {
  return {
    name: pluginName,
    /**
     * Configure the dev server with the Safari middleware
     * @param {ViteDevServer} server - The Vite dev server instance
     */
    configureServer(server) {
      server.middlewares.use(createSafariMiddleware());
    },
  };
}

/**
 * Determines if the user agent is Safari
 * @param {string} ua - The user agent string
 * @returns {boolean} True if the browser is Safari
 */
function isSafari(ua) {
  return /Safari/.test(ua) && !/Chrome/.test(ua);
}

/**
 * Escapes a string for literal use inside a RegExp
 * @param {string} text - The text to escape
 * @returns {string} The escaped text
 */
function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Creates a streaming rewriter for one HTML response.
 *
 * Hrefs are discovered from modulepreload <link> tags and every later
 * occurrence (e.g. the ESM imports in the trailing inline script) is rewritten
 * as well. Text is emitted as soon as it arrives; only a possibly-partial
 * <link> tag or href at the end of a chunk is held back until the next chunk.
 * @param {number} timestamp - The cache-bust value for this response
 * @returns {{push(text: string, flush: boolean): string, count: number}} The rewriter
 */
function createRewriter(timestamp) {
  /** @type {Map<string, {re: RegExp, replacement: string}>} */
  const replacements = new Map();
  let pending = "";

  /**
   * Registers the hrefs of every complete modulepreload tag in the text
   * @param {string} text - The text to scan
   */
  function discover(text) {
    for (const [, href] of text.matchAll(linkTagRe)) {
      if (
        replacements.has(href) ||
        /^(https?:)?\/\//.test(href) ||
        href.includes(`${tsParam}=`)
      ) {
        continue;
      }
      replacements.set(href, {
        // Skip occurrences that already carry the param (held-back text is rescanned).
        re: new RegExp(`${escapeRegExp(href)}(?![?&]${tsParam}=)`, "g"),
        replacement: `${href}${href.includes("?") ? "&" : "?"}${tsParam}=${timestamp}`,
      });
    }
  }

  /**
   * Finds how much of the end of the text must wait for the next chunk
   * @param {string} text - The rewritten text
   * @returns {number} The index at which the held-back tail starts
   */
  function cutIndex(text) {
    let cut = text.length;
    // An unclosed tag that may turn out to be a modulepreload link.
    const lt = text.lastIndexOf("<");
    if (lt !== -1 && text.indexOf(">", lt) === -1) {
      const tail = text.slice(lt, lt + 5);
      if (tail.length < 5 ? "<link".startsWith(tail) : tail === "<link") {
        cut = lt;
      }
    }
    // A proper prefix of a known href, which may continue in the next chunk.
    let keep = 0;
    for (const href of replacements.keys()) {
      for (let k = Math.min(href.length - 1, cut); k > keep; k--) {
        if (text.startsWith(href.slice(0, k), cut - k)) {
          keep = k;
          break;
        }
      }
    }
    return cut - keep;
  }

  return {
    /**
     * Feeds text through the rewriter
     * @param {string} text - The newly decoded text
     * @param {boolean} flush - Whether this is the end of the response
     * @returns {string} The text that may be sent now
     */
    push(text, flush) {
      text = pending + text;
      discover(text);
      for (const { re, replacement } of replacements.values()) {
        // A function replacer keeps "$" in hrefs from being read as a pattern.
        text = text.replace(re, () => replacement);
      }
      const cut = flush ? text.length : cutIndex(text);
      pending = text.slice(cut);
      return text.slice(0, cut);
    },
    get count() {
      return replacements.size;
    },
  };
}

/**
 * Creates a middleware that adds cache-busting for Safari browsers
 * @returns {NextHandleFunction} The middleware function
 */
function createSafariMiddleware() {
  // Set when a log message for rewriting n links has been emitted.
  let _have_logged_n = -1;

  /**
   * Middleware function to handle Safari cache busting
   * @param {IncomingMessage} req - The incoming request
   * @param {ServerResponse} res - The server response
   * @param {(err?: any) => void} next - The next middleware function
   * @returns {void}
   */
  return function safariCacheBustMiddleware(req, res, next) {
    const ua = req.headers["user-agent"] || "";
    // Remove our special cache bust query param to avoid affecting lower middleware layers.
    if (
      req.url &&
      (req.url.includes(`?${tsParam}=`) || req.url.includes(`&${tsParam}=`))
    ) {
      req.url = req.url.replace(tsUrlRe, "");
      return next();
    }

    // Only apply this middleware for Safari browsers.
    if (!isSafari(ua)) return next();

    // Only transform requests that want HTML.
    const header_accept = req.headers["accept"] || "";
    if (
      typeof header_accept !== "string" ||
      !header_accept.includes("text/html")
    ) {
      return next();
    }

    const rewriter = createRewriter(Date.now());
    // Chunks may be Buffer or plain Uint8Array and may split a multibyte character.
    const decoder = new StringDecoder("utf-8");
    const _write = res.write.bind(res);
    const _end = res.end.bind(res);

    /**
     * Decodes a written chunk to text
     * @param {any} chunk - The chunk passed to write/end, if any
     * @returns {string} The decoded text
     */
    const decode = (chunk) =>
      typeof chunk === "string" ? chunk : chunk ? decoder.write(chunk) : "";

    /**
     * Extracts the optional completion callback from write/end arguments
     * @param {any[]} args - The arguments following the chunk
     * @returns {((err?: Error) => void) | undefined} The callback, if given
     */
    const callback = (args) => args.find((arg) => typeof arg === "function");

    res.setHeader("x-modified-by", pluginName);
    /**
     * Overridden write method to rewrite chunks as they stream through
     * @param {any} chunk - The chunk to write
     * @param {...any} args - Additional arguments
     * @returns {boolean} Result of the write operation
     */
    res.write = function (chunk, ...args) {
      const out = rewriter.push(decode(chunk), false);
      const cb = callback(args);
      if (out) return cb ? _write(out, cb) : _write(out);
      // Everything was held back for the next chunk; nothing is queued.
      cb?.();
      return true;
    };

    /**
     * Overridden end method to flush held-back text and finish the response
     * @param {any} chunk - The final chunk to write
     * @param {...any} args - Additional arguments
     * @returns {ServerResponse<IncomingMessage>} The server response
     */
    res.end = function (chunk, ...args) {
      if (typeof chunk === "function") {
        args.unshift(chunk);
        chunk = undefined;
      }
      const out = rewriter.push(decode(chunk) + decoder.end(), true);
      if (rewriter.count && _have_logged_n !== rewriter.count) {
        _have_logged_n = rewriter.count;
        console.debug(
          `[${pluginName}] Rewrote ${rewriter.count} modulepreload links with ${tsParam} param.`,
        );
      }
      const cb = callback(args);
      return cb ? _end(out, cb) : _end(out);
    };
    return next();
  };
}
