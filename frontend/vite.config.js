import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 开发态代理：/api 转发后端 FastAPI（含 /api/v1/integration 仅本地调试用）
      "/api": { target: "http://localhost:8080", changeOrigin: true },
    },
  },
});
