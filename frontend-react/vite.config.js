import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiMode = process.env.ASCEND_API_MODE || process.env.VITE_API_MODE || "aws-dev";
const devApiUrl = process.env.ASCEND_DEV_API_URL || process.env.VITE_DEV_API_URL || "https://dq5ab404dg57q.cloudfront.net";
const apiTarget = apiMode === "local" ? "http://127.0.0.1:8000" : devApiUrl;

const apiProxy = {
  target: apiTarget,
  changeOrigin: true,
  secure: true,
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 3001,
    proxy: {
      "/api": apiProxy,
      "/ready": apiProxy,
      "/health": apiProxy,
      "/docs": apiProxy,
      "/openapi.json": apiProxy,
    },
  },
});
