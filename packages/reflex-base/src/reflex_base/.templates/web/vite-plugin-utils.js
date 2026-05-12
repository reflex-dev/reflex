/* vite-plugin-utils.js — Shared utilities for Reflex Vite plugins. */

import { join } from "node:path";
import { readdir, stat } from "node:fs/promises";

export async function* walkFiles(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const entryPath = join(directory, entry.name);
    if (entry.isDirectory()) {
      yield* walkFiles(entryPath);
    } else if (entry.isFile()) {
      yield entryPath;
    }
  }
}

export async function outputDirectoryExists(dir) {
  return Boolean(
    await stat(dir).catch((error) =>
      error?.code === "ENOENT" ? null : Promise.reject(error),
    ),
  );
}

/**
 * Validate format names against a registry. Config already normalizes —
 * this just guards against typos in direct callers of exported functions.
 */
export function validateFormats(formats, registry, label) {
  for (const name of formats) {
    if (!(name in registry)) {
      throw new Error(`Unsupported ${label} "${name}".`);
    }
  }
}
