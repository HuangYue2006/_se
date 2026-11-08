#!/usr/bin/env python3
"""金大校務系統（迷你版）後端

只用 Python 標準函式庫：http.server + sqlite3 + hashlib。
執行：python server.py  →  打開 http://localhost:8000
"""
import hashlib
import json
import os
import secrets
import sqlite3
import sys
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ERP_DB", os.path.join(HERE, "erp.db"))
STATIC = os.path.join(HERE, "public")
MAX_CREDITS = 25
SESSIONS = {}  # token -> user_id（記憶體 session）


# ================================================================ 資料庫
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    account TEXT UNIQUE NOT NULL,
    pw_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
    dept TEXT, grade INTEGER, email TEXT
);
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    teacher_id INTEGER REFERENCES users(id),
    credits INTEGER NOT NULL,
    day INTEGER NOT NULL,        -- 1=週一 ... 5=週五
    start_period INTEGER NOT NULL,
    end_period INTEGER NOT NULL,
    room TEXT, capacity INTEGER NOT NULL DEFAULT 50,
    required INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS enrollments (
    student_id INTEGER REFERENCES users(id),
    course_id INTEGER REFERENCES courses(id),
    score REAL,
    PRIMARY KEY (student_id, course_id)
);
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL, content TEXT NOT NULL,
    author_id INTEGER REFERENCES users(id),
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
"""


def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()


def seed(conn):
    """示範資料（帳號/密碼都是測試用）"""
    users = [
        ("admin", "admin", "教務處管理員", "admin", None, None, "admin@nqu.edu.tw"),
        ("t001", "1234", "陳鍾誠", "teacher", "資訊工程學系", None, "ccc@nqu.edu.tw"),
        ("t002", "1234", "王大明", "teacher", "資訊工程學系", None, "wang@nqu.edu.tw"),
        ("s001", "1234", "黃品岳", "student", "資訊工程學系", 2, "s001@nqu.edu.tw"),
        ("s002", "1234", "林小華", "student", "資訊工程學系", 2, "s002@nqu.edu.tw"),
        ("s003", "1234", "張美玲", "student", "資訊工程學系", 3, "s003@nqu.edu.tw"),
    ]
    for acc, pw, name, role, dept, grade, email in users:
        salt = secrets.token_hex(8)
        conn.execute(
            "INSERT INTO users(account,pw_hash,salt,name,role,dept,grade,email) VALUES (?,?,?,?,?,?,?,?)",
            (acc, hash_pw(pw, salt), salt, name, role, dept, grade, email),
        )
    tid = {r["account"]: r["id"] for r in conn.execute("SELECT id, account FROM users")}
    courses = [
        ("CS201", "軟體工程", "t001", 3, 2, 2, 4, "理工 E321", 60, 1),
        ("CS202", "計算機結構", "t001", 3, 3, 5, 7, "理工 E320", 60, 1),
        ("CS203", "資料結構", "t002", 3, 1, 2, 4, "理工 E318", 50, 1),
        ("CS204", "網頁程式設計", "t002", 3, 4, 6, 8, "電腦教室 B", 40, 0),
        ("CS205", "人工智慧導論", "t001", 3, 2, 3, 5, "理工 E215", 45, 0),  # 與軟工衝堂
        ("CS206", "資料庫系統", "t002", 3, 5, 2, 4, "理工 E318", 50, 0),
        ("GE101", "閩南文化與金門", "t002", 2, 3, 2, 3, "人文 H101", 80, 0),
    ]
    for code, name, t, cr, d, s, e, room, cap, req in courses:
        conn.execute(
            "INSERT INTO courses(code,name,teacher_id,credits,day,start_period,end_period,room,capacity,required)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (code, name, tid[t], cr, d, s, e, room, cap, req),
        )
    cid = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM courses")}
    for stu, code, score in [
        ("s001", "CS201", 92), ("s001", "CS203", 85), ("s001", "GE101", None),
        ("s002", "CS201", 78), ("s002", "CS204", 88), ("s003", "CS202", 66),
    ]:
        conn.execute("INSERT INTO enrollments VALUES (?,?,?)", (tid[stu], cid[code], score))
    conn.execute(
        "INSERT INTO announcements(title,content,author_id) VALUES (?,?,?)",
        ("115 學年度第 1 學期加退選公告", "加退選時間：9/15 ~ 9/26，請同學於期限內完成。", tid["admin"]),
    )
    conn.execute(
        "INSERT INTO announcements(title,content,author_id) VALUES (?,?,?)",
        ("期中考週停課通知", "11/9 ~ 11/13 為期中考週，請注意各科考試時間。", tid["admin"]),
    )


# ================================================================ 商業邏輯
class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


def letter(score):
    """百分制轉等第與 GPA 點數（4.3 制）"""
    if score is None:
        return None, None
    table = [(90, "A+", 4.3), (85, "A", 4.0), (80, "A-", 3.7), (77, "B+", 3.3), (73, "B", 3.0),
             (70, "B-", 2.7), (67, "C+", 2.3), (63, "C", 2.0), (60, "C-", 1.7)]
    for low, g, p in table:
        if score >= low:
            return g, p
    return "F", 0.0


def overlaps(a, b):
    return a["day"] == b["day"] and a["start_period"] <= b["end_period"] and b["start_period"] <= a["end_period"]


def course_rows(conn, where="", args=()):
    sql = f"""SELECT c.*, u.name AS teacher,
                (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id) AS enrolled
              FROM courses c LEFT JOIN users u ON u.id = c.teacher_id {where} ORDER BY c.code"""
    return [dict(r) for r in conn.execute(sql, args)]


def enroll(conn, student_id, course_id):
    course = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    if not course:
        raise ApiError(404, "找不到課程")
    if conn.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?",
                    (student_id, course_id)).fetchone():
        raise ApiError(409, "已經選過這門課")
    count = conn.execute("SELECT COUNT(*) FROM enrollments WHERE course_id=?", (course_id,)).fetchone()[0]
    if count >= course["capacity"]:
        raise ApiError(409, "課程人數已滿")
    mine = course_rows(conn, "WHERE c.id IN (SELECT course_id FROM enrollments WHERE student_id=?)", (student_id,))
    total = sum(c["credits"] for c in mine) + course["credits"]
    if total > MAX_CREDITS:
        raise ApiError(409, f"超過學分上限 {MAX_CREDITS}（選後 {total} 學分）")
    for c in mine:
        if overlaps(c, course):
            raise ApiError(409, f"與「{c['name']}」衝堂")
    conn.execute("INSERT INTO enrollments(student_id, course_id) VALUES (?,?)", (student_id, course_id))


def drop(conn, student_id, course_id):
    row = conn.execute("SELECT score FROM enrollments WHERE student_id=? AND course_id=?",
                       (student_id, course_id)).fetchone()
    if not row:
        raise ApiError(404, "沒有選這門課")
    if row["score"] is not None:
        raise ApiError(409, "已有成績，不能退選")
    conn.execute("DELETE FROM enrollments WHERE student_id=? AND course_id=?", (student_id, course_id))


def transcript(conn, student_id):
    rows = conn.execute(
        """SELECT c.code, c.name, c.credits, e.score FROM enrollments e
           JOIN courses c ON c.id = e.course_id WHERE e.student_id=? ORDER BY c.code""",
        (student_id,),
    ).fetchall()
    items, pts, cr, earned = [], 0.0, 0, 0
    for r in rows:
        g, p = letter(r["score"])
        items.append({**dict(r), "letter": g, "point": p})
        if p is not None:
            pts += p * r["credits"]
            cr += r["credits"]
            if r["score"] >= 60:
                earned += r["credits"]
    return {"items": items, "gpa": round(pts / cr, 2) if cr else None, "earned_credits": earned}


# ================================================================ HTTP
def user_public(u):
    return {k: u[k] for k in ("id", "account", "name", "role", "dept", "grade", "email")}


class Handler(BaseHTTPRequestHandler):
    server_version = "NQU-ERP/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("ERP_QUIET") != "1":
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    # ---------- 工具
    def send_json(self, status, obj, extra_headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            raise ApiError(400, "JSON 格式錯誤")

    def current_user(self, conn):
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        token = c["sid"].value if "sid" in c else None
        uid = SESSIONS.get(token)
        if not uid:
            return None
        return conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    def need(self, conn, *roles):
        u = self.current_user(conn)
        if not u:
            raise ApiError(401, "請先登入")
        if roles and u["role"] not in roles:
            raise ApiError(403, "沒有權限")
        return u

    # ---------- 靜態檔
    def serve_static(self, path):
        if path == "/":
            path = "/index.html"
        full = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not full.startswith(STATIC) or not os.path.isfile(full):
            self.send_error(404)
            return
        ext = os.path.splitext(full)[1]
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------- 路由
    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def dispatch(self, method):
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            if method == "GET":
                return self.serve_static(path)
            return self.send_error(405)
        conn = db()
        try:
            status, obj, headers = self.route(conn, method, path.split("/")[2:])
            conn.commit()
            self.send_json(status, obj, headers)
        except ApiError as e:
            conn.rollback()
            self.send_json(e.status, {"error": e.msg})
        finally:
            conn.close()

    def route(self, conn, method, parts):
        key = (method, parts[0] if parts else "")
        # ---- 認證
        if key == ("POST", "login"):
            b = self.body()
            u = conn.execute("SELECT * FROM users WHERE account=?", (b.get("account", ""),)).fetchone()
            if not u or hash_pw(b.get("password", ""), u["salt"]) != u["pw_hash"]:
                raise ApiError(401, "帳號或密碼錯誤")
            token = secrets.token_urlsafe(24)
            SESSIONS[token] = u["id"]
            return 200, user_public(u), {"Set-Cookie": f"sid={token}; HttpOnly; Path=/; SameSite=Lax"}
        if key == ("POST", "logout"):
            c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            if "sid" in c:
                SESSIONS.pop(c["sid"].value, None)
            return 200, {"ok": True}, {"Set-Cookie": "sid=; Max-Age=0; Path=/"}
        if key == ("GET", "me"):
            return 200, user_public(self.need(conn)), None
        if key == ("PUT", "me"):
            u = self.need(conn)
            b = self.body()
            if "email" in b:
                conn.execute("UPDATE users SET email=? WHERE id=?", (b["email"], u["id"]))
            if b.get("new_password"):
                if hash_pw(b.get("old_password", ""), u["salt"]) != u["pw_hash"]:
                    raise ApiError(400, "舊密碼錯誤")
                if len(b["new_password"]) < 4:
                    raise ApiError(400, "新密碼至少 4 碼")
                salt = secrets.token_hex(8)
                conn.execute("UPDATE users SET pw_hash=?, salt=? WHERE id=?",
                             (hash_pw(b["new_password"], salt), salt, u["id"]))
            return 200, {"ok": True}, None

        # ---- 公告
        if key == ("GET", "announcements"):
            self.need(conn)
            rows = conn.execute("""SELECT a.*, u.name AS author FROM announcements a
                                   LEFT JOIN users u ON u.id=a.author_id ORDER BY a.id DESC""")
            return 200, [dict(r) for r in rows], None
        if key == ("POST", "announcements"):
            u = self.need(conn, "admin", "teacher")
            b = self.body()
            if not b.get("title") or not b.get("content"):
                raise ApiError(400, "標題與內容必填")
            conn.execute("INSERT INTO announcements(title,content,author_id) VALUES (?,?,?)",
                         (b["title"], b["content"], u["id"]))
            return 201, {"ok": True}, None

        # ---- 課程
        if key == ("GET", "courses"):
            self.need(conn)
            return 200, course_rows(conn), None
        if key == ("POST", "courses"):
            self.need(conn, "admin")
            b = self.body()
            try:
                conn.execute(
                    "INSERT INTO courses(code,name,teacher_id,credits,day,start_period,end_period,room,capacity,required)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (b["code"], b["name"], b.get("teacher_id"), int(b["credits"]), int(b["day"]),
                     int(b["start_period"]), int(b["end_period"]), b.get("room", ""),
                     int(b.get("capacity", 50)), int(bool(b.get("required")))),
                )
            except (KeyError, ValueError):
                raise ApiError(400, "欄位不完整")
            except sqlite3.IntegrityError:
                raise ApiError(409, "課號重複")
            return 201, {"ok": True}, None
        if key == ("GET", "teachers"):
            self.need(conn, "admin")
            rows = conn.execute("SELECT id, name FROM users WHERE role='teacher'")
            return 200, [dict(r) for r in rows], None

        # ---- 學生：選課 / 課表 / 成績
        if key == ("GET", "my-courses"):
            u = self.need(conn, "student")
            return 200, course_rows(conn, "WHERE c.id IN (SELECT course_id FROM enrollments WHERE student_id=?)",
                                    (u["id"],)), None
        if key == ("POST", "enroll"):
            u = self.need(conn, "student")
            enroll(conn, u["id"], int(self.body().get("course_id", 0)))
            return 201, {"ok": True}, None
        if method == "DELETE" and parts[0] == "enroll" and len(parts) == 2:
            u = self.need(conn, "student")
            drop(conn, u["id"], int(parts[1]))
            return 200, {"ok": True}, None
        if key == ("GET", "grades"):
            u = self.need(conn, "student")
            return 200, transcript(conn, u["id"]), None

        # ---- 老師：授課 / 名單 / 登錄成績
        if key == ("GET", "teaching"):
            u = self.need(conn, "teacher")
            return 200, course_rows(conn, "WHERE c.teacher_id=?", (u["id"],)), None
        if method == "GET" and parts[0] == "roster" and len(parts) == 2:
            u = self.need(conn, "teacher", "admin")
            c = conn.execute("SELECT teacher_id FROM courses WHERE id=?", (int(parts[1]),)).fetchone()
            if not c:
                raise ApiError(404, "找不到課程")
            if u["role"] == "teacher" and c["teacher_id"] != u["id"]:
                raise ApiError(403, "不是你的課")
            rows = conn.execute("""SELECT u.id, u.account, u.name, u.dept, u.grade, e.score FROM enrollments e
                                   JOIN users u ON u.id=e.student_id WHERE e.course_id=? ORDER BY u.account""",
                                (int(parts[1]),))
            return 200, [dict(r) for r in rows], None
        if key == ("PUT", "score"):
            u = self.need(conn, "teacher")
            b = self.body()
            c = conn.execute("SELECT teacher_id FROM courses WHERE id=?", (b.get("course_id"),)).fetchone()
            if not c or c["teacher_id"] != u["id"]:
                raise ApiError(403, "不是你的課")
            score = b.get("score")
            if score not in (None, ""):
                score = float(score)
                if not 0 <= score <= 100:
                    raise ApiError(400, "成績需介於 0~100")
            else:
                score = None
            cur = conn.execute("UPDATE enrollments SET score=? WHERE course_id=? AND student_id=?",
                               (score, b["course_id"], b.get("student_id")))
            if cur.rowcount == 0:
                raise ApiError(404, "學生沒有修這門課")
            return 200, {"ok": True}, None

        raise ApiError(404, "API 不存在")


def make_server(port=8000):
    init_db()
    return ThreadingHTTPServer(("0.0.0.0", port), Handler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    srv = make_server(port)
    print(f"金大校務系統啟動：http://localhost:{port}")
    print("測試帳號：學生 s001/1234、老師 t001/1234、管理員 admin/admin")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
