/* vite-plugin-compress.js
 *
 * Generate pre-compressed .gz copies of build assets so that sirv (the
 * production static file server) can serve them directly.  sirv has built-in
 * support for pre-compressed files (--gzip flag, enabled by default) but only
 * looks for existing .gz files on disk -- it does not compress on-the-fly.
 *
 * Without this plugin the browser receives uncompressed assets, which is the
 * single biggest Lighthouse performance bottleneck for Reflex apps.  With gzip
 * the total asset payload typically shrinks by ~75-80%.
 */

import { promisify } from "node:util";
import { gzip } from "node:zlib";

const gzipAsync = promisify(gzip);

const COMPRESSIBLE_EXTENSIONS = /\.(js|css|html|json|svg|xml|txt|map|mjs)$/;

// Only compress files above this size (bytes).  Tiny files don't benefit
// and the overhead of Content-Encoding negotiation can outweigh the saving.
const MIN_SIZE = 256;

/**
 * Vite plugin that generates .gz files for all eligible build assets.
 * @returns {import('vite').Plugin}
 */
export default function compressPlugin() {
  return {
    name: "vite-plugin-compress",
    apply: "build",
    enforce: "post",

    async generateBundle(_options, bundle) {
      const jobs = [];

      for (const [fileName, asset] of Object.entries(bundle)) {
        if (!COMPRESSIBLE_EXTENSIONS.test(fileName)) continue;

        const source = asset.type === "chunk" ? asset.code : asset.source;
        if (source == null) continue;

        const raw = typeof source === "string" ? Buffer.from(source) : source;
        if (raw.length < MIN_SIZE) continue;

        jobs.push(
          gzipAsync(raw, { level: 9 }).then((compressed) => {
            this.emitFile({
              type: "asset",
              fileName: fileName + ".gz",
              source: compressed,
            });
          }),
        );
      }

      await Promise.all(jobs);
    },
  };
}
