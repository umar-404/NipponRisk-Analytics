import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies /api -> FastAPI backend (default :8000).
const BACKEND_TARGET = process.env.NIPPORISK_API_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: BACKEND_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});