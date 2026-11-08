#!/usr/bin/env python3
"""DeadlineMate 課表 + 作業截止提醒 —— Web 伺服器

只用 Python 標準函式庫。執行：python app.py → http://localhost:8080
"""
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import core

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DM_DB", os.path.join(HERE, "deadline.db"))
STATIC = os.path.join(HERE, "public")

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, code TEXT, teacher TEXT, room TEXT,
    day INTEGER NOT NULL CHECK(day BETWEEN 1 AND 7),
    start_period INTEGER NOT NULL CHECK(start_period BETWEEN 1 AND 10),
    end_period INTEGER NOT NULL CHECK(end_period BETWEEN 1 AND 10),
    color TEXT DEFAULT '#4f7cff'
);
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY, course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    title TEXT NOT NULL, due TEXT NOT NULL, note TEXT DEFAULT '',
    priority INTEGER DEFAULT 2, done INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

COURSE_FIELDS = ("name", "code", "teacher", "room", "day", "start_period", "end_period", "color")
HW_FIELDS = ("course_id", "title", "due", "note", "priority", "done")


def now():
    """可用環境變數 DM_NOW 固定「現在時間」，方便測試與展示"""
    fixed = os.environ.get("DM_NOW")
    return datetime.fromisoformat(fixed) if fixed else datetime.now().replace(second=0, microsecond=0)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed=True):
    conn = db()
    conn.executescript(SCHEMA)
    if seed and conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
        n = now()
        courses = [
            ("軟體工程", "CS201", "陳鍾誠", "E321", 2, 2, 4, "#4f7cff"),
            ("計算機結構", "CS202", "陳鍾誠", "E320", 3, 5, 7, "#f08c00"),
            ("資料結構", "CS203", "王大明", "E318", 1, 2, 4, "#2b8a3e"),
            ("網頁程式設計", "CS204", "王大明", "電腦教室B", 4, 6, 8, "#ae3ec9"),
            ("資料庫系統", "CS206", "李小美", "E318", 5, 2, 4, "#e03131"),
        ]
        conn.executemany(f"INSERT INTO courses({','.join(COURSE_FIELDS)}) VALUES (?,?,?,?,?,?,?,?)", courses)
        hws = [
            (1, "第 9 週：Cloudflare 網站", n + timedelta(hours=20), "記得附上網址", 3),
            (2, "Verilog 期中實作", n + timedelta(days=2, hours=3), "", 3),
            (3, "Lab5 二元搜尋樹", n + timedelta(days=5), "要寫測試", 2),
            (4, "期末專題提案", n + timedelta(days=12), "", 1),
            (5, "ER Diagram 作業", n - timedelta(hours=5), "", 2),
        ]
        for cid, title, due, note, pr in hws:
            conn.execute("INSERT INTO assignments(course_id,title,due,note,priority) VALUES (?,?,?,?,?)",
                         (cid, title, due.isoformat(timespec="minutes"), note, pr))
        # 學期開始日預設為本學期 9 月第 2 個星期一
        sep = date(n.year if n.month >= 8 else n.year - 1, 9, 8)
        sep += timedelta(days=(7 - sep.weekday()) % 7)
        conn.execute("INSERT OR REPLACE INTO settings VALUES ('semester_start', ?)", (sep.isoformat(),))
    conn.commit()
    conn.close()


class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


# ---------------------------------------------------------------- 資料存取
def list_courses(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM courses ORDER BY day, start_period")]


def list_assignments(conn, n):
    rows = [dict(r) for r in conn.execute(
        """SELECT a.*, c.name AS course_name, c.color FROM assignments a
           LEFT JOIN courses c ON c.id=a.course_id ORDER BY a.done, a.due""")]
    for a in rows:
        due = datetime.fromisoformat(a["due"])
        a["done"] = bool(a["done"])
        a["urgency"] = core.urgency(due, n, a["done"])
        a["remaining"] = core.humanize(due, n)
    return rows


def validate_course(b):
    try:
        c = {k: b.get(k) for k in COURSE_FIELDS}
        c["name"] = (c["name"] or "").strip()
        for k in ("day", "start_period", "end_period"):
            c[k] = int(c[k])
    except (TypeError, ValueError):
        raise ApiError(400, "星期與節次必須是數字")
    if not c["name"]:
        raise ApiError(400, "課名必填")
    if not (1 <= c["day"] <= 7 and 1 <= c["start_period"] <= c["end_period"] <= 10):
        raise ApiError(400, "星期需 1~7，節次需 1~10 且開始 ≤ 結束")
    c["color"] = c["color"] or "#4f7cff"
    return c


def validate_hw(b, partial=False):
    out = {}
    for k in HW_FIELDS:
        if k in b:
            out[k] = b[k]
    if not partial or "title" in out:
        if not str(out.get("title", "")).strip():
            raise ApiError(400, "作業名稱必填")
    if not partial or "due" in out:
        try:
            out["due"] = datetime.fromisoformat(out.get("due", "")).isoformat(timespec="minutes")
        except (TypeError, ValueError):
            raise ApiError(400, "截止時間格式錯誤，例如 2026-11-15T23:59")
    if "done" in out:
        out["done"] = int(bool(out["done"]))
    if "priority" in out:
        out["priority"] = max(1, min(3, int(out["priority"])))
    if out.get("course_id") in ("", None):
        out["course_id"] = None
    return out


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "DeadlineMate/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("DM_QUIET") != "1":
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send(self, status, body, ctype="application/json; charset=utf-8", extra=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n)) if n else {}
        except json.JSONDecodeError:
            raise ApiError(400, "JSON 格式錯誤")

    def do_GET(self):
        self.handle_req("GET")

    def do_POST(self):
        self.handle_req("POST")

    def do_PUT(self):
        self.handle_req("PUT")

    def do_DELETE(self):
        self.handle_req("DELETE")

    def handle_req(self, method):
        u = urlsplit(self.path)
        path, query = u.path, parse_qs(u.query)
        conn = db()
        try:
            if path == "/calendar.ics" and method == "GET":
                start = conn.execute("SELECT value FROM settings WHERE key='semester_start'").fetchone()
                ics = core.to_ics(list_courses(conn), [dict(r) for r in conn.execute("SELECT * FROM assignments")],
                                  date.fromisoformat(start[0]) if start else now().date(), now=now())
                return self.send(200, ics.encode(), "text/calendar; charset=utf-8",
                                 {"Content-Disposition": 'inline; filename="deadlinemate.ics"'})
            if path.startswith("/api/"):
                status, obj = self.api(conn, method, path[5:].strip("/").split("/"), query)
                conn.commit()
                return self.send(status, obj)
            if method != "GET":
                return self.send(405, {"error": "method not allowed"})
            return self.static(path)
        except ApiError as e:
            conn.rollback()
            self.send(e.status, {"error": e.msg})
        finally:
            conn.close()

    def static(self, path):
        full = os.path.normpath(os.path.join(STATIC, (path if path != "/" else "/index.html").lstrip("/")))
        if not full.startswith(STATIC) or not os.path.isfile(full):
            return self.send(404, {"error": "not found"})
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".json": "application/json",
                 ".svg": "image/svg+xml"}.get(os.path.splitext(full)[1], "application/octet-stream")
        with open(full, "rb") as f:
            self.send(200, f.read(), ctype)

    def api(self, conn, method, parts, query):
        res = parts[0]
        rid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        n = now()

        if res == "dashboard" and method == "GET":
            courses = list_courses(conn)
            hws = list_assignments(conn, n)
            pending = [a for a in hws if not a["done"]]
            return 200, {
                "now": n.isoformat(timespec="minutes"),
                "today": core.classes_on(courses, n.date()),
                "next_class": core.next_class(courses, n),
                "upcoming": [a for a in pending if a["urgency"] in ("overdue", "today", "soon", "week")][:8],
                "stats": {
                    "pending": len(pending),
                    "overdue": sum(a["urgency"] == "overdue" for a in pending),
                    "due_24h": sum(a["urgency"] == "today" for a in pending),
                    "done": len(hws) - len(pending),
                },
                "weekly_load": core.weekly_load(hws, n.date()),
                "periods": core.PERIODS,
            }

        if res == "courses":
            if method == "GET":
                return 200, list_courses(conn)
            if method in ("POST", "PUT"):
                c = validate_course(self.body())
                c["id"] = rid
                conflicts = core.find_conflicts(list_courses(conn), c)
                if conflicts and not query.get("force"):
                    raise ApiError(409, f"與「{conflicts[0]['name']}」衝堂")
                vals = [c[k] for k in COURSE_FIELDS]
                if method == "POST":
                    cur = conn.execute(f"INSERT INTO courses({','.join(COURSE_FIELDS)}) VALUES (?,?,?,?,?,?,?,?)", vals)
                    return 201, {"id": cur.lastrowid}
                cur = conn.execute(f"UPDATE courses SET {','.join(k + '=?' for k in COURSE_FIELDS)} WHERE id=?",
                                   vals + [rid])
                if not cur.rowcount:
                    raise ApiError(404, "找不到課程")
                return 200, {"ok": True}
            if method == "DELETE" and rid:
                if not conn.execute("DELETE FROM courses WHERE id=?", (rid,)).rowcount:
                    raise ApiError(404, "找不到課程")
                return 200, {"ok": True}

        if res == "assignments":
            if method == "GET":
                return 200, list_assignments(conn, n)
            if method == "POST":
                h = validate_hw(self.body())
                cols = list(h)
                cur = conn.execute(f"INSERT INTO assignments({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                                   [h[k] for k in cols])
                return 201, {"id": cur.lastrowid}
            if method == "PUT" and rid:
                h = validate_hw(self.body(), partial=True)
                if not h:
                    raise ApiError(400, "沒有要更新的欄位")
                cur = conn.execute(f"UPDATE assignments SET {','.join(k + '=?' for k in h)} WHERE id=?",
                                   list(h.values()) + [rid])
                if not cur.rowcount:
                    raise ApiError(404, "找不到作業")
                return 200, {"ok": True}
            if method == "DELETE" and rid:
                if not conn.execute("DELETE FROM assignments WHERE id=?", (rid,)).rowcount:
                    raise ApiError(404, "找不到作業")
                return 200, {"ok": True}

        if res == "quick" and method == "POST":
            try:
                h = core.parse_quick(self.body().get("text", ""), list_courses(conn), n)
            except ValueError as e:
                raise ApiError(400, str(e))
            cur = conn.execute("INSERT INTO assignments(course_id,title,due) VALUES (?,?,?)",
                               (h["course_id"], h["title"], h["due"]))
            return 201, {"id": cur.lastrowid, **h}

        if res == "settings":
            if method == "GET":
                return 200, {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}
            if method == "PUT":
                b = self.body()
                if "semester_start" in b:
                    try:
                        date.fromisoformat(b["semester_start"])
                    except ValueError:
                        raise ApiError(400, "日期格式錯誤")
                    conn.execute("INSERT OR REPLACE INTO settings VALUES ('semester_start', ?)", (b["semester_start"],))
                return 200, {"ok": True}

        raise ApiError(404, "API 不存在")


def make_server(port=8080, seed=True):
    init_db(seed)
    return ThreadingHTTPServer(("0.0.0.0", port), Handler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    srv = make_server(port)
    print(f"DeadlineMate 啟動：http://localhost:{port}")
    print(f"行事曆訂閱網址：http://localhost:{port}/calendar.ics")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
