import { defineConfig } from "vite";
export default defineConfig({
  base: "./",
  build: {
    rolldownOptions: { input: { main: "index.html", compact: "compact.html" } },
  },
});
