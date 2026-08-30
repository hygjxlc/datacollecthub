// Playwright E2E 配置（E2E 测试方案第 2 章）：前置条件 = docker compose up 完成
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  timeout: 180000,          // 含上传与容器内验证，放宽超时
  retries: 0,
  workers: 1,               // 用例共享基线数据，串行执行
  reporter: [["list"]],
  // 公网部署下上传/弹窗等网络路径 >5s，全局放宽 expect 超时
  expect: { timeout: 30000 },
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost",
    headless: true,
    trace: "retain-on-failure",
  },
});
