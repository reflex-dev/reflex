import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

const resolve = (relative) => fileURLToPath(new URL(relative, import.meta.url));

// `src` is what a Reflex app is built from: `reflex init` copies it into the
// app's `.web`, where `$/` names that directory.
const webRoot = resolve("./src/");

// The Python side of the client-state registry key. Asserted equal to the
// frontend constant, since these are the two definitions that can drift.
const pyConstants = resolve(
  "../reflex-base/src/reflex_base/constants/state.py",
);

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.js"],
  },
  // Under jsdom `import.meta.url` is an http:// URL, so tests that need to read
  // a source file get the location from here instead.
  define: {
    __WEB_ROOT__: JSON.stringify(webRoot),
    __PY_CONSTANTS__: JSON.stringify(pyConstants),
  },
  resolve: {
    alias: [
      // Compiled into `.web` for each app, so there is none in `src`.
      {
        find: "$/env.json",
        replacement: resolve("./tests/fixtures/env.json"),
      },
      { find: /^\$\//, replacement: webRoot },
    ],
  },
});
