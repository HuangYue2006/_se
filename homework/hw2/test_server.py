"""校務系統 API 測試。執行：python -m unittest test_server -v"""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

tmp = tempfile.mkdtemp()
os.environ["ERP_DB"] = os.path.join(tmp, "test.db")
os.environ["ERP_QUIET"] = "1"
import server  # noqa: E402


class Client:
    def __init__(self, base):
        self.base, self.cookie = base, None

    def call(self, method, path, data=None):
        req = urllib.request.Request(self.base + "/api/" + path, method=method,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json"})
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            with urllib.request.urlopen(req) as r:
                if r.headers.get("Set-Cookie"):
                    self.cookie = r.headers["Set-Cookie"].split(";")[0]
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())


class TestERP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = server.make_server(0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def login(self, acc, pw="1234"):
        c = Client(self.base)
        status, _ = c.call("POST", "login", {"account": acc, "password": pw})
        self.assertEqual(status, 200)
        return c

    def course_id(self, c, code):
        return next(x["id"] for x in c.call("GET", "courses")[1] if x["code"] == code)

    def test_letter(self):
        self.assertEqual(server.letter(95), ("A+", 4.3))
        self.assertEqual(server.letter(59), ("F", 0.0))

    def test_login_fail_and_need_login(self):
        c = Client(self.base)
        self.assertEqual(c.call("POST", "login", {"account": "s001", "password": "x"})[0], 401)
        self.assertEqual(c.call("GET", "courses")[0], 401)

    def test_enroll_rules(self):
        s = self.login("s002")
        ai = self.course_id(s, "CS205")       # 週二 3-5
        se = self.course_id(s, "CS201")       # s002 已修，週二 2-4
        status, j = s.call("POST", "enroll", {"course_id": ai})
        self.assertEqual(status, 409)
        self.assertIn("衝堂", j["error"])
        self.assertEqual(s.call("POST", "enroll", {"course_id": se})[0], 409)  # 重複
        db_id = self.course_id(s, "CS206")
        self.assertEqual(s.call("POST", "enroll", {"course_id": db_id})[0], 201)
        self.assertEqual(s.call("DELETE", f"enroll/{db_id}")[0], 200)

    def test_cannot_drop_graded(self):
        s = self.login("s001")
        self.assertEqual(s.call("DELETE", f"enroll/{self.course_id(s, 'CS201')}")[0], 409)

    def test_grades_gpa(self):
        s = self.login("s001")
        status, t = s.call("GET", "grades")
        self.assertEqual(status, 200)
        self.assertEqual(t["earned_credits"], 6)
        self.assertEqual(t["gpa"], round((4.3 * 3 + 4.0 * 3) / 6, 2))

    def test_teacher_score_permissions(self):
        t1 = self.login("t001")
        t2 = self.login("t002")
        cs202 = self.course_id(t1, "CS202")
        s3 = next(r["id"] for r in t1.call("GET", f"roster/{cs202}")[1])
        self.assertEqual(t1.call("PUT", "score", {"course_id": cs202, "student_id": s3, "score": 70})[0], 200)
        self.assertEqual(t2.call("PUT", "score", {"course_id": cs202, "student_id": s3, "score": 99})[0], 403)
        self.assertEqual(t1.call("PUT", "score", {"course_id": cs202, "student_id": s3, "score": 120})[0], 400)

    def test_student_forbidden_admin_api(self):
        s = self.login("s001")
        self.assertEqual(s.call("POST", "courses", {"code": "X"})[0], 403)

    def test_admin_add_course(self):
        a = self.login("admin", "admin")
        data = {"code": "CS999", "name": "測試課", "teacher_id": None, "credits": 2, "day": 5,
                "start_period": 8, "end_period": 9, "room": "A", "capacity": 10}
        self.assertEqual(a.call("POST", "courses", data)[0], 201)
        self.assertEqual(a.call("POST", "courses", data)[0], 409)


if __name__ == "__main__":
    unittest.main()
