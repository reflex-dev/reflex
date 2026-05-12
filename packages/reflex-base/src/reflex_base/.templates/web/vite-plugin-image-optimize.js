/* vite-plugin-image-optimize.js
 *
 * Generate optimized image format variants (WebP, AVIF) as sidecar files
 * alongside originals during production builds. The server can then use
 * Accept-header content negotiation to serve the best format to each client.
 */

import { dirname, extname } from "node:path";
import { readFile, writeFile } from "node:fs/promises";
import {
  validateFormats,
  outputDirectoryExists,
  walkFiles,
} from "./vite-plugin-utils.js";

const IMAGE_EXTENSIONS = /\.(png|jpe?g|gif|bmp|tiff?)$/i;

// Skip images smaller than this — tiny icons/favicons rarely benefit.
const MIN_SIZE = 1024;

// Limit parallel sharp operations to avoid memory pressure.
const CONCURRENCY = 8;

const FORMAT_CONFIG = {
  webp: { suffix: ".webp", sharpMethod: "webp" },
  avif: { suffix: ".avif", sharpMethod: "avif" },
};

/**
 * Process a single image file, generating optimized format variants.
 * Never throws — errors for individual images are silently skipped.
 */
async function optimizeImage(sharp, filePath, formats, quality) {
  let raw;
  try {
    raw = await readFile(filePath);
  } catch {
    return;
  }
  if (raw.length < MIN_SIZE) return;

  const stem = filePath.replace(/\.[^.]+$/, "");

  await Promise.all(
    formats.map(async (format) => {
      const config = FORMAT_CONFIG[format];
      const outputPath = stem + config.suffix;

      try {
        const result = await sharp(raw)
          [config.sharpMethod]({ quality })
          .toBuffer();

        if (result.length < raw.length) {
          await writeFile(outputPath, result);
        }
      } catch {
        // Skip this format on error (e.g. unsupported input).
      }
    }),
  );
}

/**
 * Process all images in a directory tree, with bounded concurrency.
 */
async function optimizeDirectory(sharp, directory, formats, quality) {
  if (!(await outputDirectoryExists(directory))) return;

  const pending = [];
  for await (const filePath of walkFiles(directory)) {
    if (!IMAGE_EXTENSIONS.test(filePath)) continue;

    // Don't re-encode files that are already in a target format.
    const ext = extname(filePath).toLowerCase();
    if (formats.some((f) => ext === FORMAT_CONFIG[f].suffix)) continue;

    pending.push(filePath);
  }

  // Process in batches to bound concurrency.
  for (let i = 0; i < pending.length; i += CONCURRENCY) {
    await Promise.all(
      pending
        .slice(i, i + CONCURRENCY)
        .map((file) => optimizeImage(sharp, file, formats, quality)),
    );
  }
}

/**
 * Vite plugin that generates optimized image format variants for build assets.
 * @param {{ formats?: string[], quality?: number }} [options]
 * @returns {import('vite').Plugin}
 */
export default function imageOptimizePlugin(options = {}) {
  const formats = options.formats ?? ["webp", "avif"];
  validateFormats(formats, FORMAT_CONFIG, "image optimization format");
  const quality = options.quality ?? 80;

  if (formats.length === 0) {
    return { name: "vite-plugin-image-optimize", apply: "build" };
  }

  return {
    name: "vite-plugin-image-optimize",
    apply: "build",
    enforce: "post",

    async writeBundle(outputOptions) {
      let sharp;
      try {
        sharp = (await import("sharp")).default;
      } catch {
        console.warn(
          "[vite-plugin-image-optimize] sharp is not available — skipping image optimization. " +
            "Install it with: npm install -D sharp",
        );
        return;
      }

      const outputDir =
        outputOptions.dir ??
        (outputOptions.file ? dirname(outputOptions.file) : null);
      if (!outputDir) return;

      await optimizeDirectory(sharp, outputDir, formats, quality);
    },
  };
}
