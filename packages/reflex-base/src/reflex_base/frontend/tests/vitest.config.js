import { createRequire } from "node:module";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

const require = createRequire(import.meta.url);
// The package source lives one level up; its bare npm imports resolve from
// this directory's node_modules via the explicit pins below (node resolution
// from the parent directory would never reach tests/node_modules).
const packageRoot = fileURLToPath(new URL("../", import.meta.url));

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["**/*.test.js"],
  },
  resolve: {
    alias: [
      {
        find: /^@reflex-dev\/reflex-base\/(.*)$/,
        replacement: `${packageRoot}$1`,
      },
      { find: /^react$/, replacement: require.resolve("react") },
      { find: /^react-dom$/, replacement: require.resolve("react-dom") },
      { find: /^react-router$/, replacement: require.resolve("react-router") },
      {
        find: /^socket\.io-client$/,
        replacement: require.resolve("socket.io-client"),
      },
      {
        find: /^universal-cookie$/,
        replacement: require.resolve("universal-cookie"),
      },
      { find: /^json5$/, replacement: require.resolve("json5") },
    ],
  },
});
