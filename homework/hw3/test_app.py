"""DeadlineMate 測試：核心邏輯單元測試 + API 測試

執行：python -m unittest test_app -v
"""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

os.environ["DM_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["DM_QUIET"] = "1"
os.environ["DM_NOW"] = "2026-11-08T10:00"  # 週日
import app  # noqa: E402
import core  # noqa: E402

NOW = datetime(2026, 11, 8, 10, 0)
COURSES = [
    {"id": 1, "name": "軟體工程", "code": "CS201", "day": 2, "start_period": 2, "end_period": 4},
    {"id": 2, "name": "資料結構", "code": "CS203", "day": 1, "start_period": 2, "end_period": 4},
    {"id": 3, "name": "網頁程式設計", "code": "CS204", "day": 4, "start_period": 6, "end_period": 8},
]


class TestCore(unittest.TestCase):
    def test_urgency(self):
        self.assertEqual(core.urgency(NOW - timedelta(minutes=1), NOW), "overdue")
        self.assertEqual(core.urgency(NOW + timedelta(hours=5), NOW), "today")
        self.assertEqual(core.urgency(NOW + timedelta(days=2), NOW), "soon")
        self.assertEqual(core.urgency(NOW + timedelta(days=6), NOW), "week")
        self.assertEqual(core.urgency(NOW + timedelta(days=30), NOW), "later")
        self.assertEqual(core.urgency(NOW - timedelta(days=1), NOW, done=True), "done")

    def test_humanize(self):
        self.assertEqual(core.humanize(NOW + timedelta(days=2, hours=3), NOW), "還剩 2 天 3 小時")
        self.assertEqual(core.humanize(NOW - timedelta(minutes=30), NOW), "已逾期 30 分鐘")

    def test_next_class(self):
        nc = core.next_class(COURSES, NOW)  # 週日 → 下一堂是週一資料結構
        self.assertEqual(nc["name"], "資料結構")
        self.assertEqual(nc["start"], "2026-11-09T09:10")
        ongoing = core.next_class(COURSES, datetime(2026, 11, 10, 10, 30))  # 週二上軟工中
        self.assertTrue(ongoing["ongoing"])
        self.assertIsNone(core.next_class([], NOW))

    def test_conflict(self):
        new = {"day": 2, "start_period": 4, "end_period": 5}
        self.assertEqual([c["name"] for c in core.find_conflicts(COURSES, new)], ["軟體工程"])
        self.assertEqual(core.find_conflicts(COURSES, {"day": 2, "start_period": 5, "end_period": 6}), [])

    def test_quick_basic(self):
        r = core.parse_quick("軟工 HW3 11/15 21:00", COURSES, NOW)
        self.assertEqual(r, {"course_id": 1, "title": "HW3", "due": "2026-11-15T21:00"})

    def test_quick_relative(self):
        self.assertEqual(core.parse_quick("資結 lab5 明天", COURSES, NOW)["due"], "2026-11-09T23:59")
        self.assertEqual(core.parse_quick("CS204 作業2 3天後", COURSES, NOW)["due"], "2026-11-11T23:59")
        # 一週從星期一開始。今天 11/9（一）：「週三」= 11/11，「下週三」= 11/18
        mon = datetime(2026, 11, 9, 9, 0)
        self.assertEqual(core.parse_quick("網頁 作業 週三", COURSES, mon)["due"], "2026-11-11T23:59")
        self.assertEqual(core.parse_quick("網頁 作業 下週三 12:00", COURSES, mon)["due"], "2026-11-18T12:00")
        # 今天 11/8（日）屬於上一週，所以「下週三」是 11/11
        self.assertEqual(core.parse_quick("網頁 作業 下週三", COURSES, NOW)["due"], "2026-11-11T23:59")

    def test_quick_no_course_and_next_year(self):
        r = core.parse_quick("繳學費 1/5", COURSES, datetime(2026, 12, 20))
        self.assertIsNone(r["course_id"])
        self.assertEqual(r["due"], "2027-01-05T23:59")

    def test_quick_errors(self):
        with self.assertRaises(ValueError):
            core.parse_quick("軟工 HW3", COURSES, NOW)
        with self.assertRaises(ValueError):
            core.parse_quick("軟工 明天", COURSES, NOW)

    def test_ics(self):
        hws = [{"id": 9, "course_id": 1, "title": "HW,1", "due": "2026-11-15T23:59", "done": 0},
               {"id": 10, "course_id": 1, "title": "done", "due": "2026-11-15T23:59", "done": 1}]
        ics = core.to_ics(COURSES, hws, date(2026, 9, 14), now=NOW)
        self.assertIn("RRULE:FREQ=WEEKLY;COUNT=18", ics)
        self.assertIn("DTSTART;TZID=Asia/Taipei:20260915T091000", ics)  # 第一個週二
        self.assertIn("SUMMARY:[截止] 軟體工程 HW\\,1", ics)
        self.assertNotIn("done", ics.split("HW\\,1")[1])
        self.assertEqual(ics.count("BEGIN:VALARM"), 2)

    def test_weekly_load(self):
        hws = [{"due": "2026-11-04T10:00"}, {"due": "2026-11-12T10:00"}, {"due": "2026-11-13T10:00", "done": True}]
        self.assertEqual([w["count"] for w in core.weekly_load(hws, date(2026, 11, 8))], [1, 1, 0, 0])


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = app.make_server(0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, method, path, data=None):
        req = urllib.request.Request(self.base + path, method=method, headers={"Content-Type": "application/json"},
                                     data=json.dumps(data).encode() if data is not None else None)
        try:
            with urllib.request.urlopen(req) as r:
                body = r.read()
                return r.status, (json.loads(body) if "json" in r.headers["Content-Type"] else body.decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_dashboard(self):
        s, d = self.call("GET", "/api/dashboard")
        self.assertEqual(s, 200)
        self.assertEqual(d["stats"]["overdue"], 1)
        self.assertEqual(d["next_class"]["name"], "資料結構")

    def test_assignment_crud(self):
        s, r = self.call("POST", "/api/assignments", {"title": "測試作業", "due": "2026-11-20T12:00", "course_id": 1})
        self.assertEqual(s, 201)
        hid = r["id"]
        self.assertEqual(self.call("PUT", f"/api/assignments/{hid}", {"done": True})[0], 200)
        hw = next(a for a in self.call("GET", "/api/assignments")[1] if a["id"] == hid)
        self.assertEqual(hw["urgency"], "done")
        self.assertEqual(self.call("DELETE", f"/api/assignments/{hid}")[0], 200)
        self.assertEqual(self.call("DELETE", f"/api/assignments/{hid}")[0], 404)

    def test_assignment_validation(self):
        self.assertEqual(self.call("POST", "/api/assignments", {"title": "", "due": "2026-11-20T12:00"})[0], 400)
        self.assertEqual(self.call("POST", "/api/assignments", {"title": "x", "due": "明天"})[0], 400)

    def test_quick(self):
        s, r = self.call("POST", "/api/quick", {"text": "計結 報告 後天 18:00"})
        self.assertEqual(s, 201)
        self.assertEqual((r["course_id"], r["due"]), (2, "2026-11-10T18:00"))
        self.assertEqual(self.call("POST", "/api/quick", {"text": "沒有日期"})[0], 400)

    def test_course_conflict(self):
        c = {"name": "衝堂課", "day": 2, "start_period": 3, "end_period": 3}
        s, r = self.call("POST", "/api/courses", c)
        self.assertEqual(s, 409)
        s, r = self.call("POST", "/api/courses?force=1", c)
        self.assertEqual(s, 201)
        self.call("DELETE", f"/api/courses/{r['id']}")
        self.assertEqual(self.call("POST", "/api/courses", {"name": "x", "day": 9, "start_period": 1, "end_period": 2})[0], 400)

    def test_ics_endpoint(self):
        s, body = self.call("GET", "/calendar.ics")
        self.assertEqual(s, 200)
        self.assertTrue(body.startswith("BEGIN:VCALENDAR"))

    def test_static(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn("DeadlineMate", r.read().decode())


if __name__ == "__main__":
    unittest.main()
