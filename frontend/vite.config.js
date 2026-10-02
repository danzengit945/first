import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config: React plugin + proxy /api → FastAPI backend
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // So the browser can call /api/... and Vite forwards to FastAPI
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // /api/upload → http://127.0.0.1:8000/upload
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
