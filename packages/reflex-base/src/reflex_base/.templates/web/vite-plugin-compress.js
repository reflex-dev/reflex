/* vite-plugin-compress.js
 *
 * Generate pre-compressed build assets so they can be served directly by
 * production static file servers and reverse proxies without on-the-fly
 * compression. The default format is gzip, with optional brotli and zstd.
 */

import * as zlib from "node:zlib";
import { dirname, join } from "node:path";
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { promisify } from "node:util";

const gzipAsync = promisify(zlib.gzip);
const brotliAsync =
  typeof zlib.brotliCompress === "function"
    ? promisify(zlib.brotliCompress)
    : null;
const zstdAsync =
  typeof zlib.zstdCompress === "function" ? promisify(zlib.zstdCompress) : null;

const COMPRESSIBLE_EXTENSIONS = /\.(js|css|html|json|svg|xml|txt|map|mjs)$/;

// Only compress files above this size (bytes).  Tiny files don't benefit
// and the overhead of Content-Encoding negotiation can outweigh the saving.
const MIN_SIZE = 256;

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
            zlib.constants.BROTLI_MAX_QUALITY ?? 11,
        },
      }),
  },
  zstd: zstdAsync && {
    extension: ".zst",
    compress: (raw) => zstdAsync(raw),
  },
};

function normalizeFormats(formats = ["gzip"]) {
  const normalized = [];
  const seen = new Set();

  for (const format of formats) {
    const normalizedFormat = String(format).trim().toLowerCase();
    if (!normalizedFormat || seen.has(normalizedFormat)) {
      continue;
    }
    if (!(normalizedFormat in COMPRESSORS)) {
      throw new Error(
        `Unsupported frontend compression format "${format}". ` +
          'Expected one of: "gzip", "brotli", "zstd".',
      );
    }
    normalized.push(normalizedFormat);
    seen.add(normalizedFormat);
  }

  return normalized;
}

async function* walkFiles(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const entryPath = join(directory, entry.name);
    if (entry.isDirectory()) {
      yield* walkFiles(entryPath);
      continue;
    }
    if (entry.isFile()) {
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

async function outputDirectoryExists(outputDir) {
  return Boolean(
    await stat(outputDir).catch((error) =>
      error?.code === "ENOENT" ? null : Promise.reject(error),
    ),
  );
}

async function compressFile(filePath, formats) {
  const raw = await readFile(filePath);
  if (raw.length < MIN_SIZE) return;

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

export async function compressDirectory(directory, formats = ["gzip"]) {
  const normalizedFormats = normalizeFormats(formats);
  ensureFormatsSupported(normalizedFormats);

  if (!(await outputDirectoryExists(directory))) {
    return;
  }

  const jobs = [];
  for await (const filePath of walkFiles(directory)) {
    if (!COMPRESSIBLE_EXTENSIONS.test(filePath)) continue;
    jobs.push(compressFile(filePath, normalizedFormats));
  }

  await Promise.all(jobs);
}

/**
 * Vite plugin that generates pre-compressed files for eligible build assets.
 * @param {{ formats?: string[] }} [options]
 * @returns {import('vite').Plugin}
 */
export default function compressPlugin(options = {}) {
  const formats = normalizeFormats(options.formats);

  return {
    name: "vite-plugin-compress",
    apply: "build",
    enforce: "post",

    async writeBundle(outputOptions) {
      const outputDir =
        outputOptions.dir ??
        (outputOptions.file ? dirname(outputOptions.file) : null);
      if (!outputDir) return;
      await compressDirectory(outputDir, formats);
    },
  };
}
