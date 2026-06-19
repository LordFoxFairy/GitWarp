import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
  },
  build: {
    outDir: "dist/.vite",
    emptyOutDir: true,
    cssCodeSplit: false,
    minify: "esbuild",
    rollupOptions: {
      input: resolve(__dirname, "src/main.tsx"),
      output: {
        entryFileNames: "app.js",
        inlineDynamicImports: true,
        assetFileNames: (assetInfo) => (assetInfo.name?.endsWith(".css") ? "app.css" : "assets/[name]-[hash][extname]"),
      },
    },
  },
});
