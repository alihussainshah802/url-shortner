import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // Everything the backend serves lives under /api, so the browser only talks
    // to Vite and no CORS configuration is needed.
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
