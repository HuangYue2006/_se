// E2E 測試：用無頭 Chromium 真的打開網頁、輸入、點擊
const { test, expect } = require("@playwright/test");

// 每個測試前把伺服器上的資料清空，讓測試互不影響
test.beforeEach(async ({ page, request }) => {
  const tasks = await (await request.get("/api/tasks")).json();
  for (const t of tasks) await request.delete(`/api/tasks/${t.id}`);
  await page.goto("/");
});

async function addTask(page, title, { course = "", priority = "2" } = {}) {
  await page.fill("#title", title);
  await page.fill("#course", course);
  await page.selectOption("#priority", priority);
  await page.click("#add");
  await expect(page.locator("li.task", { hasText: title })).toBeVisible();
}

test("一開始是空的", async ({ page }) => {
  await expect(page).toHaveTitle(/作業清單/);
  await expect(page.getByTestId("stats")).toHaveText("目前沒有作業 🎉");
  await expect(page.locator("#empty")).toBeVisible();
});

test("新增作業", async ({ page }) => {
  await addTask(page, "第 7 週 網站測試", { course: "軟體工程" });
  await expect(page.getByTestId("task")).toHaveCount(1);
  await expect(page.locator(".course")).toHaveText("軟體工程");
  await expect(page.getByTestId("stats")).toHaveText("完成 0 / 1（0%）");
  await expect(page.locator("#title")).toHaveValue(""); // 送出後清空
});

test("空白名稱會顯示錯誤，不會送出", async ({ page }) => {
  await page.fill("#title", "   ");
  await page.click("#add");
  await expect(page.getByRole("alert")).toHaveText("請輸入作業名稱");
  await expect(page.getByTestId("task")).toHaveCount(0);
});

test("勾選完成、篩選、清除已完成", async ({ page }) => {
  await addTask(page, "作業 A");
  await addTask(page, "作業 B");
  await page.getByLabel("完成 作業 A").check();
  await expect(page.locator("li.task.done")).toHaveText(/作業 A/);
  await expect(page.getByTestId("stats")).toHaveText("完成 1 / 2（50%）");

  await page.click("[data-filter=active]");
  await expect(page.getByTestId("task")).toHaveCount(1);
  await expect(page.getByTestId("task")).toHaveText(/作業 B/);

  await page.click("[data-filter=completed]");
  await expect(page.getByTestId("task")).toHaveText(/作業 A/);

  await page.click("[data-filter=all]");
  await page.click("#clear");
  await expect(page.getByTestId("task")).toHaveCount(1);
  await expect(page.locator("#clear")).toBeHidden();
});

test("高優先度排在前面", async ({ page }) => {
  await addTask(page, "不急", { priority: "1" });
  await addTask(page, "很急", { priority: "3" });
  await expect(page.locator(".task .title").first()).toHaveText("很急");
});

test("刪除作業", async ({ page }) => {
  await addTask(page, "要刪的");
  await page.getByLabel("刪除 要刪的").click();
  await expect(page.getByTestId("task")).toHaveCount(0);
});

test("雙擊修改名稱", async ({ page }) => {
  await addTask(page, "舊名稱");
  page.once("dialog", (d) => d.accept("新名稱"));
  await page.locator(".task .title").dblclick();
  await expect(page.locator(".task .title")).toHaveText("新名稱");
});

test("重新整理後資料還在（存在伺服器）", async ({ page }) => {
  await addTask(page, "持久化測試");
  await page.reload();
  await expect(page.locator("li.task", { hasText: "持久化測試" })).toBeVisible();
});

test("名稱裡的 HTML 不會被執行 (XSS)", async ({ page }) => {
  await addTask(page, "<b>粗體</b>");
  await expect(page.locator(".task .title")).toHaveText("<b>粗體</b>");
  await expect(page.locator(".task .title b")).toHaveCount(0);
});
