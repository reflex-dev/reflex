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

/**
 * @typedef {import('vite').Plugin} Plugin
 * @typedef {import('vite').ViteDevServer} ViteDevServer
 * @typedef {import('http').IncomingMessage} IncomingMessage
 * @typedef {import('http').ServerResponse} ServerResponse
 * @typedef {import('connect').NextHandleFunction} NextHandleFunction
 */

const pluginName = "vite-plugin-safari-cachebust";

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
 * Creates a middleware that adds cache-busting for Safari browsers
 * @returns {NextHandleFunction} The middleware function
 */
function createSafariMiddleware() {
  // Set when a log message for rewriting n links has been emitted.
  let _have_logged_n = -1;

  /**
   * Rewrites module import links in HTML content with cache-busting parameters
   * @param {string} html - The HTML content to process
   * @returns {string} The processed HTML content
   */
  function rewriteModuleImports(html) {
    const currentTimestamp = new Date().getTime();
    const parts = html.split(/(<link\s+rel="modulepreload"[^>]*>)/g);
    /** @type {[string, string][]} */
    const replacements = parts
      .map((chunk) => {
        const match = chunk.match(
          /<link\s+rel="modulepreload"\s+href="([^"]+)"(.*?)\/?>/,
        );
        if (!match) return;

        const [fullMatch, href, rest] = match;
        if (/^(https?:)?\/\//.test(href)) return;

        try {
          const newHref = href.includes("?")
            ? `${href}&__reflex_ts=${currentTimestamp}`
            : `${href}?__reflex_ts=${currentTimestamp}`;
          return [href, newHref];
        } catch {
          // no worries;
        }
      })
      .filter(Boolean);
    if (replacements.length && _have_logged_n !== replacements.length) {
      _have_logged_n = replacements.length;
      console.debug(
        `[${pluginName}] Rewrote ${replacements.length} modulepreload links with __reflex_ts param.`,
      );
    }
    return replacements.reduce((accumulator, [target, replacement]) => {
      return accumulator.split(target).join(replacement);
    }, html);
  }

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
      (req.url.includes("?__reflex_ts=") || req.url.includes("&__reflex_ts="))
    ) {
      req.url = req.url.replace(/(\?|&)__reflex_ts=\d+/, "");
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

    let buffer = "";
    const _end = res.end.bind(res);

    res.setHeader("x-modified-by", "vite-plugin-safari-cachebust");
    /**
     * Overridden write method to collect chunks
     * @param {any} chunk - The chunk to write
     * @param {...any} args - Additional arguments
     * @returns {boolean} Result of the write operation
     */
    res.write = function (chunk, ...args) {
      buffer += chunk instanceof Buffer ? chunk.toString("utf-8") : chunk;
      return true;
    };

    /**
     * Overridden end method to process and send the final response
     * @param {any} chunk - The final chunk to write
     * @param {...any} args - Additional arguments
     * @returns {ServerResponse<IncomingMessage>} The server response
     */
    res.end = function (chunk, ...args) {
      if (chunk) {
        buffer += chunk instanceof Buffer ? chunk.toString("utf-8") : chunk;
      }
      buffer = rewriteModuleImports(buffer);
      return _end(buffer, ...args);
    };
    return next();
  };
}
