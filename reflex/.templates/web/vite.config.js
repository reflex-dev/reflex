import { fileURLToPath, URL } from "url";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";
import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";

// Ensure that bun always uses the react-dom/server.node functions.
function alwaysUseReactDomServerNode() {
  return {
    name: "vite-plugin-always-use-react-dom-server-node",
    enforce: "pre",

    resolveId(source, importer) {
      if (
        typeof importer === "string" &&
        importer.endsWith("/entry.server.node.tsx") &&
        source.includes("react-dom/server")
      ) {
        return this.resolve("react-dom/server.node", importer, {
          skipSelf: true,
        });
      }
      return null;
    },
  };
}

export default defineConfig((config) => ({
  plugins: [
    alwaysUseReactDomServerNode(),
    reactRouter(),
    safariCacheBustPlugin(),
  ],
  build: {
    rollupOptions: {
      jsx: {},
    },
  },
  server: {
    port: process.env.PORT,
    watch: {
      ignored: [
        "**/.web/backend/**",
        "**/.web/reflex.install_frontend_packages.cached",
      ],
    },
  },
  resolve: {
    mainFields: ["browser", "module", "jsnext"],
    alias: [
      {
        find: "$",
        replacement: fileURLToPath(new URL("./", import.meta.url)),
      },
      {
        find: "@",
        replacement: fileURLToPath(new URL("./public", import.meta.url)),
      },
    ],
  },
}));
