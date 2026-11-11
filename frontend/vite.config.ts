import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks to one origin (this server); API, WebSocket and
// uploaded photos are proxied to the FastAPI backend.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: backend },
      "/media": { target: backend },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      "/api": { target: backend },
      "/media": { target: backend },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
