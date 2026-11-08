// @ts-check
const { defineConfig, devices } = require("@playwright/test");

const PORT = 3100;

module.exports = defineConfig({
  testDir: "./tests",
  workers: 1, // 伺服器資料在記憶體，測試依序跑
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    headless: true, // 無頭瀏覽器
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // 自動啟動 Rust 伺服器
  webServer: {
    command: "cargo run --release",
    cwd: "../server",
    env: { PORT: String(PORT), STATIC_DIR: "../client" },
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 300_000, // 第一次編譯 Rust 比較久
  },
});
