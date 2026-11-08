# 第 7 週：寫一個網站應用，要做三種測試

題目：

1. **單元測試**（server 一定要測，例如 rust；client 可以不測，例如 node.js）
2. **系統測試**（web api 測試）
3. **E2E 測試**（無頭瀏覽器，playwright）

## 作品：作業清單（Rust + axum）

一個可以新增、勾選完成、篩選、修改、刪除作業的網站。

層 | 技術
---|-----
後端 | Rust、[axum](https://github.com/tokio-rs/axum) 0.7、tokio
前端 | 原生 HTML + JavaScript（ES Module），由 Rust 伺服器直接提供
測試 | `cargo test`（單元 + API）、`node --test`（前端純函式）、Playwright（E2E）

## 檔案結構

```
hw7/
├── server/                      Rust 後端
│   ├── Cargo.toml
│   ├── src/
│   │   ├── todo.rs              ① 核心邏輯 + 單元測試 (#[cfg(test)])
│   │   ├── lib.rs               HTTP 路由（把 Store 包成 REST API）
│   │   └── main.rs              啟動伺服器 + 提供靜態檔
│   └── tests/api_test.rs        ② 系統測試（Web API）
├── client/                      前端
│   ├── index.html
│   ├── app.js                   DOM 操作、呼叫 API
│   ├── logic.js                 純函式（跳脫 HTML、驗證、文字格式）
│   └── test/logic.test.js       （加分）前端單元測試
└── e2e/                         ③ E2E 測試
    ├── playwright.config.js     會自動 cargo run 啟動伺服器
    └── tests/todo.spec.js
```

## 執行網站

需要先安裝 [Rust](https://rustup.rs/)。

```bash
cd homework/hw7/server
cargo run
```

打開 <http://127.0.0.1:3000>

## API

方法 | 路徑 | 說明 | 成功 | 失敗
-----|------|------|------|-----
GET | /api/health | 健康檢查 | 200 `ok` |
GET | /api/tasks?filter=all\|active\|completed | 列出作業 | 200 | 400（filter 不合法）
POST | /api/tasks | 新增 `{title, course?, priority?}` | 201 | 400（驗證失敗）/ 422（缺欄位）
PATCH | /api/tasks/{id} | 修改 `{title?, done?, priority?}` | 200 | 400 / 404
DELETE | /api/tasks/{id} | 刪除 | 204 | 404
DELETE | /api/completed | 清除已完成 | 200 `{removed}` |
GET | /api/stats | 統計 | 200 `{total, done, active, percent}` |

---

## ① 單元測試（Rust）

測的是 `src/todo.rs` 裡的純邏輯，**不經過 HTTP**。這也是為什麼要把邏輯跟路由分成兩個檔案：邏輯越純，越好測。

```bash
cd server
cargo test --lib
```

測試 | 驗證內容
-----|--------
`add_assigns_increasing_ids_and_trims` | id 遞增、標題去頭尾空白
`title_validation` | 空白、超過 100 字（用中文字測，確認算的是「字數」不是 byte 數）
`priority_validation` | 優先度只能 1~3
`failed_add_does_not_consume_id` | 新增失敗不會浪費 id
`list_sorts_and_filters` | 未完成在前、優先度高在前、三種篩選
`update_is_atomic` | 一次 PATCH 裡有一個欄位不合法 → 全部不改
`update_and_remove_missing` | 找不到 → NotFound
`remove_and_clear_completed` | 刪除、清除已完成
`stats_percent` | 統計與百分比（含 0 筆時不會除以零）

<!-- 執行後可以把 cargo test 的輸出截圖放在這裡 -->

## ② 系統測試（Web API 測試）

`tests/api_test.rs` 用 `tower::ServiceExt::oneshot` 把一個真正的 HTTP Request 丟進 axum Router，檢查 **狀態碼** 和 **JSON 回應**。
不用真的開 port，所以測試很快、也不會跟其他程式搶 port。

```bash
cd server
cargo test --test api_test
```

測試 | 驗證內容
-----|--------
`health_ok` | `GET /api/health` → 200 `ok`
`create_then_list` | POST 回 201、預設 priority=2；GET 拿得到
`validation_errors` | 空白標題 400 + 中文錯誤訊息；priority=5 → 400；缺 title → 422
`patch_and_filter` | PATCH done；`?filter=active/completed`；非法 filter → 400
`delete_and_not_found` | DELETE 204；再刪一次 404；PATCH 不存在的 id → 404
`stats_and_clear_completed` | 統計正確、清除已完成

也可以用習題 1 的 pycurl 手動測：

```bash
python ../../hw1/pycurl.py -i -H "Content-Type: application/json" -d '{"title":"HW7","course":"軟工"}' http://127.0.0.1:3000/api/tasks
python ../../hw1/pycurl.py http://127.0.0.1:3000/api/stats
```

一次跑全部 Rust 測試：`cargo test`

## ③ E2E 測試（Playwright 無頭瀏覽器）

用無頭 Chromium 真的打開網頁、打字、點按鈕，從**使用者的角度**驗證前端 + 後端整個流程。
`playwright.config.js` 的 `webServer` 會自動用 `cargo run --release` 在 port 3100 啟動伺服器，測完自動關掉。

```bash
cd e2e
npm install
npx playwright install chromium     # 第一次要下載瀏覽器
npm test
npm run report                      # 看 HTML 報告（失敗時會有截圖與 trace）
```

測試 | 使用者情境
-----|----------
一開始是空的 | 標題、空狀態文字
新增作業 | 輸入 → 出現在清單、統計更新、輸入框清空
空白名稱會顯示錯誤 | 前端驗證擋下，不會送出
勾選完成、篩選、清除已完成 | 打勾 → 刪除線、50%；切換三種篩選；清除後按鈕隱藏
高優先度排在前面 | 後端排序反映在畫面上
刪除作業 | 點 ✕
雙擊修改名稱 | 處理 `prompt()` 對話框
重新整理後資料還在 | 資料存在伺服器，不是前端變數
XSS | 標題 `<b>粗體</b>` 以文字顯示，不會變成 HTML

## （加分）前端單元測試

題目說 client 可以不測，不過 `logic.js` 是純函式，用 Node 內建的 test runner 就能測，不用裝任何套件：

```bash
cd client
npm test
```

## 三種測試的比較

&nbsp; | 單元測試 | 系統測試（API） | E2E 測試
------|---------|----------------|---------
測什麼 | 一個函式 / 模組 | 整個後端的 HTTP 介面 | 整個系統（瀏覽器 + 前端 + 後端）
速度 | 毫秒 | 毫秒~秒 | 秒~分鐘
找到錯誤時 | 很清楚是哪個函式 | 知道是哪支 API | 只知道「某個流程壞了」
數量 | 最多 | 中等 | 最少（只測關鍵流程）
本作業 | `cargo test --lib`（9 個） | `cargo test --test api_test`（6 個） | `npx playwright test`（9 個）

這就是**測試金字塔**：底層的單元測試多又快，上層的 E2E 少但最接近真實使用者。
