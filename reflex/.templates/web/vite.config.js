import { fileURLToPath, URL } from "url";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [reactRouter()],
  server: {
    port: process.env.PORT,
  },
  resolve: {
    alias: [
      { find: "$", replacement: fileURLToPath(new URL("./", import.meta.url)) },
      {
        find: "@",
        replacement: fileURLToPath(new URL("./public", import.meta.url)),
      },
    ],
  },
});
