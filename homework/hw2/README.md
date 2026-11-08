# 習題 2：類似金門大學校務系統的專案程式

一個迷你版的「金大校務行政系統」，包含**學生、教師、管理員**三種角色。

* 後端：Python 標準函式庫（`http.server` + `sqlite3`），**不用安裝任何套件**
* 前端：單頁 HTML + 原生 JavaScript（`fetch` 呼叫 JSON API）
* 資料庫：SQLite（第一次啟動自動建表並放入示範資料）

## 執行

```bash
python server.py
```

打開 <http://localhost:8000>

角色 | 帳號 | 密碼
-----|------|-----
學生 | s001 | 1234
教師 | t001 | 1234
管理員 | admin | admin

> 想重置資料，刪掉 `erp.db` 再重新啟動即可。

## 功能

角色 | 功能
-----|-----
共同 | 登入 / 登出、查看公告、個人資料（改 Email、改密碼）
學生 | 課程查詢（可搜尋）、**加選 / 退選**、我的課表（週課表格子）、成績查詢（等第、GPA、已得學分）
教師 | 授課課程、學生名單、**登錄成績**、發布公告
管理員 | 開設課程、發布公告、查看全校課程

### 選課規則（寫在後端，不能從前端繞過）

1. 不能重複選同一門課
2. 人數滿了不能選
3. 學分上限 25
4. **衝堂檢查**：同一天且節次重疊就拒絕（例如「人工智慧導論」週二 3-5 節 和「軟體工程」週二 2-4 節）
5. 已有成績的課不能退選

### 權限控管

* 用 HttpOnly cookie 存 session token
* 密碼用 `PBKDF2-SHA256 + salt` 雜湊，不存明碼
* 每個 API 檢查角色：學生不能開課、老師只能改自己課的成績

## API

方法 | 路徑 | 角色 | 說明
-----|------|------|-----
POST | /api/login | 所有人 | 登入
POST | /api/logout | 登入者 | 登出
GET / PUT | /api/me | 登入者 | 個人資料 / 修改
GET / POST | /api/announcements | 登入者 / 教師、管理員 | 公告
GET | /api/courses | 登入者 | 全部課程
POST | /api/courses | 管理員 | 開課
GET | /api/my-courses | 學生 | 已選課程
POST | /api/enroll | 學生 | 加選 `{course_id}`
DELETE | /api/enroll/{id} | 學生 | 退選
GET | /api/grades | 學生 | 成績單 + GPA
GET | /api/teaching | 教師 | 我的授課
GET | /api/roster/{id} | 教師 | 修課名單
PUT | /api/score | 教師 | 登錄成績 `{course_id, student_id, score}`

可以用習題 1 的 pycurl 測：

```bash
python ../hw1/pycurl.py -i -H "Content-Type: application/json" -d '{"account":"s001","password":"1234"}' http://localhost:8000/api/login
```

## 資料表

```
users(id, account, pw_hash, salt, name, role, dept, grade, email)
courses(id, code, name, teacher_id, credits, day, start_period, end_period, room, capacity, required)
enrollments(student_id, course_id, score)
announcements(id, title, content, author_id, created_at)
```

## 測試

```bash
python -m unittest test_server -v
```

測了：登入失敗、未登入擋下、衝堂、重複加選、已評分不能退選、GPA 計算、老師只能改自己課的成績、成績範圍檢查、學生不能呼叫管理員 API、課號重複。

```
Ran 8 tests

OK
```

## 檔案

```
hw2/
├── server.py         後端（路由、權限、選課規則、SQLite）
├── public/index.html 前端單頁應用
└── test_server.py    API 測試
```
