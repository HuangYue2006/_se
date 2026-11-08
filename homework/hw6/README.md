# 第 6 週：Docker 使用

題目：

1. 學會使用 docker 並做記錄，寫一個 README.md
2. 用 docker 建置一個系統，繳交 `Dockerfile` 和 `docker-compose.yml`
   * 最好是微服務：nginx（web server、反向代理）+ PostgreSQL + 開發執行環境（Python）
   * 最後有一個簡易的 web 介面展示

---

# Part 1：Docker 學習紀錄

## 1. Docker 是什麼？

Docker 把「程式 + 執行環境 + 相依套件」打包成 **image（映像檔）**，跑起來就是 **container（容器）**。
解決的是「我電腦可以跑，你電腦不行」的問題。

名詞 | 比喻 | 說明
-----|------|-----
Image | 類別 / 安裝光碟 | 唯讀的檔案系統快照，由一層一層 layer 疊成
Container | 物件 / 執行中的程式 | Image 跑起來的實例，有自己的檔案系統、網路、行程空間
Dockerfile | 食譜 | 描述怎麼一步一步建出 image
Registry | App Store | 放 image 的地方，例如 Docker Hub
Volume | 外接硬碟 | 容器刪掉資料還在
Network | 區域網路 | 同一個 network 的容器可以用名稱互相連線

### 容器 vs 虛擬機

```
  虛擬機 (VM)                       容器 (Container)
┌─────┬─────┬─────┐              ┌─────┬─────┬─────┐
│ App │ App │ App │              │ App │ App │ App │
├─────┼─────┼─────┤              ├─────┴─────┴─────┤
│ OS  │ OS  │ OS  │  ← 每台都有    │  Docker Engine   │
├─────┴─────┴─────┤     完整 OS   ├─────────────────┤
│   Hypervisor    │              │   Host OS 核心   │  ← 共用核心
├─────────────────┤              ├─────────────────┤
│    Hardware     │              │    Hardware     │
└─────────────────┘              └─────────────────┘
 啟動：分鐘級、GB 級                 啟動：秒級、MB 級
```

容器共用主機的 Linux 核心，靠 **namespace**（隔離）和 **cgroup**（限制資源）做到隔離，所以比 VM 輕很多。
（Windows / macOS 上的 Docker Desktop 其實是在一台小 Linux VM 裡跑容器。）

## 2. 安裝

* Windows / macOS：安裝 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows 需開啟 WSL 2）
* Linux：`curl -fsSL https://get.docker.com | sh`

```bash
docker --version
docker compose version
docker run hello-world      # 測試：會下載 hello-world image 並執行
```

## 3. 常用指令

### Image

```bash
docker pull nginx:1.27-alpine        # 下載 image
docker images                        # 列出本機 image
docker build -t myapp:1.0 .          # 用目前目錄的 Dockerfile 建 image
docker rmi myapp:1.0                 # 刪除 image
docker image prune                   # 清掉沒在用的 image
```

### Container

```bash
docker run -d --name web -p 8080:80 nginx:1.27-alpine   # 背景執行，主機 8080 → 容器 80
docker ps                            # 執行中的容器
docker ps -a                         # 全部（含已停止）
docker logs -f web                   # 看 log（-f 持續追蹤）
docker exec -it web sh               # 進入容器開 shell
docker stop web && docker start web  # 停止 / 啟動
docker rm -f web                     # 強制刪除
docker run --rm -it python:3.12 python   # 用完即丟的 Python REPL
```

`docker run` 常用參數：

參數 | 意思
-----|-----
`-d` | 背景執行 (detached)
`-p 主機:容器` | 連接埠對應
`-v 主機路徑:容器路徑` | 掛載目錄（bind mount）
`-v volume名:容器路徑` | 掛載具名 volume
`-e KEY=VALUE` | 環境變數
`--name` | 容器名稱
`--rm` | 停止後自動刪除
`--network` | 加入指定網路

### Volume 與 Network

```bash
docker volume ls
docker volume inspect hw6_pgdata
docker network ls
docker network inspect hw6_backend
```

### Docker Compose

```bash
docker compose up -d --build         # 建置並在背景啟動全部服務
docker compose ps                    # 服務狀態
docker compose logs -f api           # 看某個服務的 log
docker compose exec db psql -U board # 進入資料庫
docker compose restart nginx         # 重啟單一服務
docker compose down                  # 停止並刪除容器（volume 保留）
docker compose down -v               # 連 volume 一起刪（資料會清空！）
```

## 4. Dockerfile 重點

```dockerfile
FROM python:3.12-slim          # 基底 image，選 slim / alpine 比較小
WORKDIR /app                   # 之後指令的工作目錄
COPY requirements.txt .        # ① 先只複製依賴清單
RUN pip install -r requirements.txt   # ② 安裝（這層可以被 cache）
COPY . .                       # ③ 再複製程式碼
EXPOSE 8000                    # 文件用途：說明會聽哪個 port
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]   # 容器啟動時執行
```

學到的幾個重點：

1. **Layer cache**：每個指令是一層。把「不常變的」（安裝套件）放前面、「常變的」（程式碼）放後面，改程式碼時就不用重新 `pip install`。
2. **`--host 0.0.0.0`**：容器內的服務要聽 0.0.0.0，聽 127.0.0.1 的話外面連不進來。
3. **不要用 root 跑**：`RUN useradd -m appuser` + `USER appuser`。
4. **`.dockerignore`**：排除 `__pycache__`、`.env`、`.git`，image 比較小也不會把密碼包進去。
5. **`CMD` vs `RUN`**：`RUN` 是建 image 時執行；`CMD` 是容器啟動時執行。

## 5. 踩到的坑

問題 | 原因 | 解法
-----|------|-----
API 啟動時連不到資料庫 | `depends_on` 只等容器「啟動」，不等 PostgreSQL「可以連線」 | 加 `healthcheck` + `condition: service_healthy`
API 裡寫 `localhost:5432` 連不到 | 容器裡的 localhost 是自己 | 用服務名稱 `db:5432`（compose 內建 DNS）
改了 `init.sql` 沒效果 | 只有 volume 是空的第一次才會執行 | `docker compose down -v` 後重來
時間差 8 小時 | 容器預設 UTC | 設 `TZ=Asia/Taipei`
Windows 換行造成 shell script 錯誤 | CRLF | 編輯器改成 LF

---

# Part 2：用 Docker 建置的微服務系統

一個「作業看板」：可以新增作業、打勾完成、看到逾期與各課程完成度。

## 架構

```
                 ┌──────────────────────────── docker network: backend ───────────────────┐
  Browser        │                                                                        │
 :8080  ───────► │  nginx (hw6-nginx)  ── /api/* ──►  FastAPI (hw6-api)  ──►  PostgreSQL  │
                 │   ├ /       靜態網頁               uvicorn :8000          (hw6-db)    │
                 │   └ /api/   反向代理                                       :5432       │
                 │                                                        volume: pgdata  │
                 └────────────────────────────────────────────────────────────────────────┘
```

服務 | Image | 角色 | 對外 port
-----|-------|------|---------
nginx | `nginx:1.27-alpine` | web server（給靜態網頁）+ reverse proxy（把 `/api/` 轉給 API） | 8080
api | 自己的 Dockerfile（`python:3.12-slim` + FastAPI） | 商業邏輯、REST API | 無（只在內部網路）
db | `postgres:16-alpine` | 資料庫，資料存在 volume `pgdata` | 無

只有 nginx 對外開 port，API 與資料庫都藏在內部網路，這是常見的安全做法。

## 檔案

```
hw6/
├── docker-compose.yml     三個服務、volume、network
├── .env.example           資料庫帳密設定範本
├── nginx/default.conf     靜態檔 + 反向代理設定
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py            FastAPI
├── db/init.sql            建表 + 示範資料
└── web/index.html         前端介面
```

## 執行

```bash
cd homework/hw6
cp .env.example .env            # 可選：改資料庫密碼
docker compose up -d --build
docker compose ps
```

打開 <http://localhost:8080>

```bash
# 也可以直接打 API
curl http://localhost:8080/api/health
curl http://localhost:8080/api/assignments
curl -X POST http://localhost:8080/api/assignments \
     -H "Content-Type: application/json" \
     -d '{"course":"軟體工程","title":"Docker 作業","due":"2026-11-15T23:59"}'

# 進資料庫看看
docker compose exec db psql -U board -d board -c "SELECT * FROM assignments;"

# 關掉（資料會保留在 volume）
docker compose down
```

FastAPI 自動產生的 Swagger API 文件：<http://localhost:8080/docs>（也是經過 nginx 代理）。

## API

方法 | 路徑 | 說明
-----|------|-----
GET | /api/health | 回傳 API 容器名稱、PostgreSQL 版本、資料筆數（證明三個服務串起來了）
GET | /api/assignments | 作業列表（含是否逾期）
POST | /api/assignments | 新增 `{course, title, due}`
PATCH | /api/assignments/{id} | 標記完成 `{done: true}`
DELETE | /api/assignments/{id} | 刪除
GET | /api/stats | 各課程完成度（PostgreSQL `COUNT(*) FILTER`）

## 參考

1. [教材：03-tool/03-docker](https://github.com/ccc115a/se/tree/main/03-tool/03-docker)
2. [參考解答 week6-docker](https://github.com/ccc115a/se/tree/main/_more/homework/week6-docker)
3. [Docker 官方文件](https://docs.docker.com/)
