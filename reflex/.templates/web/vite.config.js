import { fileURLToPath, URL } from "url";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";
import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";

export default defineConfig((config) => ({
  plugins: [reactRouter(), safariCacheBustPlugin()],
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
    ].concat(
      config.command === "build"
        ? [{ find: "react-dom/server", replacement: "react-dom/server.node" }]
        : [],
    ),
  },
}));
