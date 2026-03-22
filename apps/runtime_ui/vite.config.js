import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/ui/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 4173,
    proxy: {
      "/api": {
        target: process.env.LANGBRIDGE_RUNTIME_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    emptyOutDir: true,
    outDir: "../../langbridge/ui/static",
  },
});
