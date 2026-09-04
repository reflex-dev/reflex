/* Generate pre-compressed sidecars for the exported static frontend so
 * production servers can serve them directly without on-the-fly compression. */

import * as zlib from "node:zlib";
import { join } from "node:path";
import { readdir, readFile, writeFile } from "node:fs/promises";
import { promisify } from "node:util";

const gzipAsync = promisify(zlib.gzip);
const brotliAsync =
  typeof zlib.brotliCompress === "function"
    ? promisify(zlib.brotliCompress)
    : null;
const zstdAsync =
  typeof zlib.zstdCompress === "function" ? promisify(zlib.zstdCompress) : null;

const COMPRESSIBLE_EXTENSIONS = /\.(js|css|html|json|svg|xml|txt|map|mjs)$/;
const MIN_SIZE = 256;
const CONCURRENCY = 16;

const COMPRESSORS = {
  gzip: {
    extension: ".gz",
    compress: (raw) => gzipAsync(raw, { level: 9 }),
  },
  brotli: brotliAsync && {
    extension: ".br",
    compress: (raw) =>
      brotliAsync(raw, {
        params: {
          [zlib.constants.BROTLI_PARAM_QUALITY]:
            zlib.constants.BROTLI_MAX_QUALITY,
        },
      }),
  },
  zstd: zstdAsync && {
    extension: ".zst",
    compress: (raw) => zstdAsync(raw),
  },
};

const SIDECAR_SUFFIXES = Object.values(COMPRESSORS)
  .filter(Boolean)
  .map((c) => c.extension);

async function* walkFiles(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const entryPath = join(directory, entry.name);
    if (entry.isDirectory()) {
      yield* walkFiles(entryPath);
    } else if (entry.isFile()) {
      yield entryPath;
    }
  }
}

function ensureFormatsSupported(formats) {
  const unavailableFormats = formats.filter(
    (format) => !COMPRESSORS[format]?.compress,
  );
  if (unavailableFormats.length > 0) {
    throw new Error(
      `The configured frontend compression formats are not supported by this Node.js runtime: ${unavailableFormats.join(", ")}`,
    );
  }
}

async function compressFile(filePath, formats) {
  const raw = await readFile(filePath);
  // Always compress HTML entrypoints so their negotiated sidecars exist.
  if (raw.length < MIN_SIZE && !filePath.endsWith(".html")) return;

  await Promise.all(
    formats.map((format) => {
      const compressor = COMPRESSORS[format];
      return compressor
        .compress(raw)
        .then((compressed) =>
          writeFile(filePath + compressor.extension, compressed),
        );
    }),
  );
}

async function compressDirectory(directory, formats) {
  ensureFormatsSupported(formats);

  const pending = [];
  for await (const filePath of walkFiles(directory)) {
    if (
      COMPRESSIBLE_EXTENSIONS.test(filePath) &&
      !SIDECAR_SUFFIXES.some((suffix) => filePath.endsWith(suffix))
    ) {
      pending.push(filePath);
    }
  }

  for (let i = 0; i < pending.length; i += CONCURRENCY) {
    await Promise.all(
      pending
        .slice(i, i + CONCURRENCY)
        .map((file) => compressFile(file, formats)),
    );
  }
}

const [directory, ...formats] = process.argv.slice(2);

if (!directory) {
  throw new Error("Missing static output directory for compression.");
}

await compressDirectory(directory, formats);
