/* vite-plugin-safari-cachebust.ts
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

import { Plugin, ViteDevServer } from "vite";
import { IncomingMessage, ServerResponse } from "http";
import { NextHandleFunction } from "connect";

export default function safariCacheBustPlugin(): Plugin {
  return {
    name: "vite-plugin-safari-cachebust",
    configureServer(server: ViteDevServer) {
      server.middlewares.use(createSafariMiddleware());
    },
  };
}

function isSafari(ua: string): boolean {
  return /Safari/.test(ua) && !/Chrome/.test(ua);
}

function createSafariMiddleware(): NextHandleFunction {
  return function safariCacheBustMiddleware(
    req: IncomingMessage,
    res: ServerResponse,
    next: (err?: any) => void,
  ): void {
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
    res.write = function (chunk: any, ...args: any[]): boolean {
      buffer += chunk instanceof Buffer ? chunk.toString("utf-8") : chunk;
      return true;
    };
    res.end = function (
      chunk: any,
      ...args: any[]
    ): ServerResponse<IncomingMessage> {
      if (chunk) {
        buffer += chunk instanceof Buffer ? chunk.toString("utf-8") : chunk;
      }
      buffer = rewriteModuleImports(buffer);
      return _end(buffer, ...args);
    };
    return next();
  };
}

function rewriteModuleImports(html: string): string {
  const currentTimestamp = new Date().getTime();
  const parts = html.split(/(<link\s+rel="modulepreload"[^>]*>)/g);
  const replacements: Record<string, string> = {};
  const rewritten = parts.map((chunk) => {
    const match = chunk.match(
      /<link\s+rel="modulepreload"\s+href="([^"]+)"(.*?)\/?>/,
    );
    if (!match) return chunk;

    const [fullMatch, href, rest] = match;
    if (/^(https?:)?\/\//.test(href)) return chunk;

    try {
      const newHref = href.includes("?")
        ? `${href}&__reflex_ts=${currentTimestamp}`
        : `${href}?__reflex_ts=${currentTimestamp}`;
      replacements[href] = newHref;
    } catch {
      // no worries;
    }
    return chunk;
  });
  let transformed = rewritten.join("");
  for (const [match, replacement] of Object.entries(replacements)) {
    transformed = transformed.split(match).join(replacement);
  }
  return transformed;
}
