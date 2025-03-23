import { fileURLToPath, URL } from "url";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

export default defineConfig((config) => ({
  plugins: [reactRouter()],
  server: {
    port: process.env.PORT,
  },
  optimizeDeps: {
    include: [
      "@emotion/react",
      "sonner",
      "axios",
      "socket.io-client",
      "json5",
      "universal-cookie",
      "@radix-ui/themes",
      "react-error-boundary",
      "react-helmet",
    ],
    force: true,
  },
  resolve: {
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
