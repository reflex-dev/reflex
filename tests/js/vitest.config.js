import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// The units under test live outside this directory, so node resolution from
// them never reaches these node_modules. Point `react` at the copy installed
// here, which also guarantees one React instance across test and subject.
const require = createRequire(import.meta.url);

// The files under test live in the template tree that `reflex init` copies into
// a user's `.web`. Tests deliberately sit outside it, since everything in there
// is copied verbatim into generated apps.
const webRoot = fileURLToPath(
  new URL(
    "../../packages/reflex-base/src/reflex_base/.templates/web/",
    import.meta.url,
  ),
);

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["**/*.test.js"],
  },
  // Under jsdom `import.meta.url` is an http:// URL, so tests that need to read
  // a source file get the location from here instead.
  define: { __WEB_ROOT__: JSON.stringify(webRoot) },
  resolve: {
    alias: [
      { find: /^\$\//, replacement: webRoot },
      { find: /^react$/, replacement: require.resolve("react") },
    ],
  },
});
