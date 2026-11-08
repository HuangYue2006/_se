# 課程：現代軟體工程 -- 學生作業與專案

欄位 | 內容
-----|--------
學期 | 115 學年上學期
教師 | [陳鍾誠](https://www.nqu.edu.tw/educsie/index.php?act=blog&code=list&ids=4)
學校 | [金門大學資訊工程系](https://www.nqu.edu.tw/educsie/index.php)
學生 | 黃品岳
學號 | 33

## 期中作業檢驗表

第幾週 | 習題內容 | 有上課且準時繳交 | 補交且附上請假證明 | 作業連結
-------|----------|-----------------|-------------------|---------
1 | curl | 是 | | [hw1](homework/hw1/)
2 | 校務系統 | 是 | | [hw2](homework/hw2/)
3 | 有價值專案 | 是 | | [hw3](homework/hw3/)
4 | git flow | 是 | | [hw4](homework/hw4/)
5 | (放假) | | |
6 | docker | 是 | | [hw6](homework/hw6/)
7 | 網站測試 | 是 | | [hw7](homework/hw7/)
8 | 有價值專案（實作） | 是 | | [hw3](homework/hw3/)
9 | cloudflare 網站專案 | 是 | | [hw9](homework/hw9/)

## 作業列表

作業 | 題目 | 內容 | 技術
-----|------|------|-----
[hw1](homework/hw1/) | 習題 1：類似 curl 的專案 | pycurl：用 socket 自己實作 HTTP/HTTPS 用戶端，支援 -X -H -d -i -I -L -o -v、chunked、gzip | Python 標準函式庫
[hw2](homework/hw2/) | 習題 2：類似金大校務系統 | 學生選課（衝堂、學分上限、人數）、課表、成績 GPA；教師登錄成績；管理員開課、公告 | Python、SQLite、JavaScript
[hw3](homework/hw3/) | 習題 3 + 第 8 週：有價值的專案 | **DeadlineMate** 課表 + 作業截止提醒：一句話新增作業、緊急度分色、匯出 Google 日曆、瀏覽器通知 | Python、SQLite、JavaScript
[hw4](homework/hw4/) | 第 4 週：git flow | 分支、合併、fork、pull request 的指令與流程說明（Git Flow / GitHub Flow / Forking Flow） | Git、GitHub
[hw6](homework/hw6/) | 第 6 週：Docker | Docker 學習筆記 + nginx / FastAPI / PostgreSQL 微服務作業看板 | Docker Compose
[hw7](homework/hw7/) | 第 7 週：網站三種測試 | 作業清單網站：單元測試、Web API 測試、Playwright E2E 測試 | Rust (axum)、Playwright
[hw9](homework/hw9/) | 第 9 週：Cloudflare 網站 | DeadlineMate Cloud：多人版、跨裝置同步、行事曆訂閱 | Cloudflare Workers、D1

## 快速執行

```bash
# hw1
python homework/hw1/pycurl.py -i https://example.com

# hw2（http://localhost:8000，帳號 s001 / 1234）
python homework/hw2/server.py

# hw3（http://localhost:8080）
python homework/hw3/app.py

# hw6（http://localhost:8080）
cd homework/hw6 && docker compose up -d --build

# hw7（http://127.0.0.1:3000）
cd homework/hw7/server && cargo run

# hw9（http://localhost:8787）
cd homework/hw9 && npm install && npm run db:local && npm run dev
```
