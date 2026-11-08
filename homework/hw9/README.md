# 第 9 週：寫一個網站應用架到 Cloudflare 上

## 作品：DeadlineMate Cloud

把[習題 3](../hw3/) 的「課表 + 作業截止提醒」搬上 Cloudflare，變成**任何人打開網址就能用**的線上服務。

🌐 網址：`https://deadlinemate.<你的子網域>.workers.dev`（部署後填上）

### 和 hw3 本機版的差別

&nbsp; | hw3 本機版 | hw9 Cloudflare 版
------|-----------|------------------
後端 | Python `http.server` | Cloudflare **Workers**（JavaScript，跑在全球邊緣節點）
資料庫 | SQLite 檔案 | Cloudflare **D1**（也是 SQLite，但由 Cloudflare 代管）
靜態檔 | Python 讀檔回傳 | Workers **Static Assets**（CDN 直接回應，不消耗 Worker 執行次數）
使用者 | 只有自己 | **多人**：每個瀏覽器自動拿到一把隨機金鑰，資料互相隔離
跨裝置 | 無 | 「在其他裝置使用」連結，手機打開就同步
行事曆 | `localhost` 只有自己電腦能訂閱 | 公開的 `/cal/<金鑰>.ics`，Google 日曆可以直接訂閱
時區 | 用電腦時間 | 伺服器在 UTC，統一換算成**台灣時間**

## 架構

```
            ┌──────────────── Cloudflare 邊緣網路 ────────────────┐
  瀏覽器 ──►│  Static Assets (public/)                           │
            │    index.html、lib.js  ← 找得到檔案就直接回應        │
            │                                                     │
            │  Worker (src/index.js)  ← /api/*、/cal/*            │
            │    ├ 驗證使用者金鑰 (X-User-Key header)             │
            │    ├ 驗證輸入、衝堂檢查、一句話解析                   │
            │    └ SQL ──►  D1 資料庫 (users / courses / assignments)
            └─────────────────────────────────────────────────────┘
```

`public/lib.js` 是**前後端共用**的邏輯（一句話解析、緊急度、下一堂課、.ics 產生）：
瀏覽器用 `<script type="module">` 匯入，Worker 用 `import ... from "../public/lib.js"`，wrangler 打包時會一起包進去。同一份程式碼、同一份測試。

## 檔案

```
hw9/
├── wrangler.toml             Worker 名稱、靜態檔目錄、D1 綁定
├── package.json
├── src/index.js              Worker：REST API + iCalendar
├── public/
│   ├── index.html            前端
│   └── lib.js                前後端共用邏輯
├── migrations/0001_init.sql  D1 資料表
└── test/lib.test.js          共用邏輯的單元測試（11 個）
```

## 部署步驟

### 0. 準備

* 安裝 [Node.js](https://nodejs.org/) 18 以上
* 註冊 [Cloudflare](https://dash.cloudflare.com/sign-up) 帳號（免費方案就夠）

```bash
cd homework/hw9
npm install
npx wrangler login          # 會打開瀏覽器授權
```

### 1. 建立 D1 資料庫

```bash
npx wrangler d1 create deadlinemate
```

會印出類似：

```toml
[[d1_databases]]
binding = "DB"
database_name = "deadlinemate"
database_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

把 `database_id` 貼到 `wrangler.toml`。

### 2. 建立資料表

```bash
npm run db:local     # 本機開發用的資料庫
npm run db:remote    # 雲端正式的資料庫
```

### 3. 本機測試

```bash
npm run dev          # http://localhost:8787
```

### 4. 部署

```bash
npm run deploy
```

完成後會印出 `https://deadlinemate.<子網域>.workers.dev`，把它填到本頁最上面。

### 5. 驗證

```bash
curl https://deadlinemate.<子網域>.workers.dev/api/health
# {"ok":true,"now_taipei":"2026-11-08T17:05"}

# 用習題 1 的 pycurl 也可以
python ../hw1/pycurl.py -X POST https://deadlinemate.<子網域>.workers.dev/api/users
```

看 log：`npx wrangler tail`

## API

所有 `/api/*`（除了建立使用者與 health）都要帶 `X-User-Key` header。

方法 | 路徑 | 說明
-----|------|-----
GET | /api/health | 健康檢查（回傳台灣時間）
POST | /api/users | 建立使用者，回傳 `{key}`；`{"demo":true}` 會放範例課表
GET / PUT / DELETE | /api/me | 學期開始日 / 修改 / 刪除自己全部資料
GET / POST | /api/courses | 課程（衝堂回 409，`?force=1` 強制）
PUT / DELETE | /api/courses/{id} | 修改 / 刪除（作業改成未分類）
GET / POST | /api/assignments | 作業
PUT / DELETE | /api/assignments/{id} | 修改（如 `{"done":true}`）/ 刪除
POST | /api/quick | 一句話新增 `{"text":"軟工 HW3 明天"}`
GET | /cal/{key}.ics | 行事曆訂閱（行事曆 App 不能帶 header，所以金鑰放網址）

### 安全性考量

* 金鑰是 `crypto.getRandomValues` 產生的 18 bytes（144 bits）隨機字串，猜不到
* 所有 SQL 都用 `prepare().bind()`，不會被 SQL injection
* 每個查詢都加 `WHERE user_key = ?`，A 使用者改不到 B 的資料（例如用別人的作業 id 也只會得到 404）
* 新增作業時檢查 `course_id` 屬於自己
* 前端輸出都經過 `esc()` 跳脫，防 XSS

## 測試

```bash
npm test
```

測試 `public/lib.js`：台灣時區換算、不存在的日期、緊急度、剩餘時間、下一堂課、衝堂、縮寫比對、一句話解析（各種日期與錯誤）、.ics、每週作業量。

開發時也用 sql.js（瀏覽器版 SQLite）模擬 D1 跑過整個 Worker，驗證了：建立使用者、沒帶金鑰回 401、衝堂 409 / 強制新增、不合法課程 400、新增作業時課程不屬於自己 400、**別的使用者刪不到我的作業**、刪課程後作業變未分類、.ics 產生、刪除自己全部資料。

## 參考

* [ccc-cloudflare/test-apps](https://github.com/ccc-cloudflare/test-apps/)
* [用 Cloudflare 架設網站：從零開發到全球上線](https://github.com/cccbook/cccbook2026/blob/main/%E9%9B%BB%E8%85%A6/%E7%B6%B2%E7%AB%99%E8%A8%AD%E8%A8%88/%E7%94%A8Cloudflare%E6%9E%B6%E8%A8%AD%E7%B6%B2%E7%AB%99/README.md)
* [Cloudflare Workers 文件](https://developers.cloudflare.com/workers/)、[D1 文件](https://developers.cloudflare.com/d1/)
