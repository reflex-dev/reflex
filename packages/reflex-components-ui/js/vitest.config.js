import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// `src` is copied into an app's `.web/reflex-ui`, and `$/` names `.web` there.
const src = fileURLToPath(new URL("./src/", import.meta.url));

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{js,jsx}"],
  },
  resolve: {
    alias: [{ find: /^\$\/reflex-ui\//, replacement: src }],
  },
});
