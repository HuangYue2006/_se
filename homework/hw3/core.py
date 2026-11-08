"""課表 + 作業截止提醒 —— 核心邏輯（不碰 HTTP，方便單元測試）"""
import re
from datetime import date, datetime, time, timedelta

# 金大節次時間（可依學校修改）
PERIODS = {
    1: ("08:10", "09:00"), 2: ("09:10", "10:00"), 3: ("10:10", "11:00"), 4: ("11:10", "12:00"),
    5: ("13:30", "14:20"), 6: ("14:30", "15:20"), 7: ("15:30", "16:20"), 8: ("16:30", "17:20"),
    9: ("17:30", "18:20"), 10: ("18:30", "19:20"),
}
WEEKDAY_ZH = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}


def _t(s):
    h, m = s.split(":")
    return time(int(h), int(m))


def class_start(day_date, start_period):
    return datetime.combine(day_date, _t(PERIODS[start_period][0]))


def class_end(day_date, end_period):
    return datetime.combine(day_date, _t(PERIODS[end_period][1]))


# ---------------------------------------------------------------- 緊急程度
def urgency(due, now, done=False):
    """回傳 done / overdue / today(<24h) / soon(<3天) / week(<7天) / later"""
    if done:
        return "done"
    delta = due - now
    if delta.total_seconds() < 0:
        return "overdue"
    if delta <= timedelta(hours=24):
        return "today"
    if delta <= timedelta(days=3):
        return "soon"
    if delta <= timedelta(days=7):
        return "week"
    return "later"


def humanize(due, now):
    """把剩餘時間轉成「還剩 2 天 3 小時」這類文字"""
    secs = int((due - now).total_seconds())
    past = secs < 0
    secs = abs(secs)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        s = f"{d} 天 {h} 小時"
    elif h:
        s = f"{h} 小時 {m} 分"
    else:
        s = f"{m} 分鐘"
    return f"已逾期 {s}" if past else f"還剩 {s}"


# ---------------------------------------------------------------- 課表
def classes_on(courses, d):
    """某一天的課（依節次排序）"""
    wd = d.isoweekday()
    return sorted([c for c in courses if c["day"] == wd], key=lambda c: c["start_period"])


def next_class(courses, now):
    """找出下一堂（或正在上的）課，最多往後找 7 天"""
    for offset in range(8):
        d = now.date() + timedelta(days=offset)
        for c in classes_on(courses, d):
            start, end = class_start(d, c["start_period"]), class_end(d, c["end_period"])
            if end > now:
                return {**c, "start": start.isoformat(timespec="minutes"),
                        "end": end.isoformat(timespec="minutes"), "ongoing": start <= now}
    return None


def find_conflicts(courses, new):
    return [c for c in courses
            if c.get("id") != new.get("id") and c["day"] == new["day"]
            and c["start_period"] <= new["end_period"] and new["start_period"] <= c["end_period"]]


# ---------------------------------------------------------------- 快速新增
def parse_quick(text, courses, now):
    """解析一句話新增作業，例如：
        「軟工 HW3 11/15 23:59」
        「計結 期中報告 明天」
        「資料結構 lab5 下週三 12:00」
        「網頁 作業2 3天後」
    課名可以是全名、課號或任意子字串/縮寫（每個字依序出現即可）。
    沒寫時間預設 23:59。回傳 {course_id, title, due} 或丟出 ValueError。
    """
    text = text.strip()
    if not text:
        raise ValueError("內容是空的")
    tokens = text.split()

    # 1) 課程：第一個 token 比對課名
    course = None
    if courses:
        first = tokens[0].lower()
        for c in courses:
            if first in (c["name"].lower(), (c.get("code") or "").lower()):
                course = c
                break
        if not course:
            for c in courses:
                if _abbr_match(first, c["name"].lower()):
                    course = c
                    break
    if course:
        tokens = tokens[1:]

    # 2) 時間 hh:mm
    hhmm = time(23, 59)
    for i, tk in enumerate(tokens):
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", tk)
        if m:
            hhmm = time(int(m[1]), int(m[2]))
            tokens.pop(i)
            break

    # 3) 日期
    due_date = None
    for i, tk in enumerate(tokens):
        d = _parse_date(tk, now.date())
        if d:
            due_date = d
            tokens.pop(i)
            break
    if due_date is None:
        raise ValueError("找不到日期，例如 11/15、明天、下週三、3天後")

    title = " ".join(tokens).strip()
    if not title:
        raise ValueError("缺少作業名稱")
    return {"course_id": course["id"] if course else None, "title": title,
            "due": datetime.combine(due_date, hhmm).isoformat(timespec="minutes")}


def _abbr_match(abbr, name):
    """縮寫比對：abbr 的每個字依序出現在 name 中，如「軟工」→「軟體工程」"""
    it = iter(name)
    return len(abbr) >= 2 and all(ch in it for ch in abbr)


def _parse_date(tk, today):
    if tk in ("今天", "today"):
        return today
    if tk in ("明天", "tomorrow"):
        return today + timedelta(days=1)
    if tk == "後天":
        return today + timedelta(days=2)
    m = re.fullmatch(r"(\d+)\s*天後", tk)
    if m:
        return today + timedelta(days=int(m[1]))
    m = re.fullmatch(r"(本|這|下)?(?:週|周|星期|禮拜)([一二三四五六日天])", tk)
    if m:
        target = WEEKDAY_ZH[m[2]]
        cur = today.isoweekday()
        if m[1] == "下":
            monday_next = today + timedelta(days=8 - cur)
            return monday_next + timedelta(days=target - 1)
        diff = (target - cur) % 7
        return today + timedelta(days=diff)
    m = re.fullmatch(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", tk)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})", tk)
    if m:
        d = date(today.year, int(m[1]), int(m[2]))
        if d < today - timedelta(days=60):  # 例如 12 月輸入 1/10，視為明年
            d = date(today.year + 1, d.month, d.day)
        return d
    return None


# ---------------------------------------------------------------- iCalendar 匯出
def _ics_escape(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_dt(dt):
    return dt.strftime("%Y%m%dT%H%M%S")


def to_ics(courses, assignments, semester_start, weeks=18, now=None):
    """產生 .ics，可匯入 Google 日曆 / Apple 行事曆。
    課程用 RRULE 每週重複；作業是截止時間的事件，並在 1 天前、1 小時前提醒。"""
    now = now or datetime.now()
    by_id = {c["id"]: c for c in courses}
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NQU//DeadlineMate//ZH", "CALSCALE:GREGORIAN",
           "X-WR-CALNAME:課表與作業", "X-WR-TIMEZONE:Asia/Taipei"]
    for c in courses:
        first = semester_start + timedelta(days=(c["day"] - semester_start.isoweekday()) % 7)
        out += ["BEGIN:VEVENT", f"UID:course-{c['id']}@deadlinemate",
                f"DTSTAMP:{_ics_dt(now)}",
                f"DTSTART;TZID=Asia/Taipei:{_ics_dt(class_start(first, c['start_period']))}",
                f"DTEND;TZID=Asia/Taipei:{_ics_dt(class_end(first, c['end_period']))}",
                f"RRULE:FREQ=WEEKLY;COUNT={weeks}",
                f"SUMMARY:{_ics_escape(c['name'])}",
                f"LOCATION:{_ics_escape(c.get('room') or '')}", "END:VEVENT"]
    for a in assignments:
        if a.get("done"):
            continue
        due = datetime.fromisoformat(a["due"])
        cname = by_id.get(a.get("course_id"), {}).get("name")
        summary = f"[截止] {cname + ' ' if cname else ''}{a['title']}"
        out += ["BEGIN:VEVENT", f"UID:hw-{a['id']}@deadlinemate", f"DTSTAMP:{_ics_dt(now)}",
                f"DTSTART;TZID=Asia/Taipei:{_ics_dt(due - timedelta(minutes=30))}",
                f"DTEND;TZID=Asia/Taipei:{_ics_dt(due)}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"DESCRIPTION:{_ics_escape(a.get('note') or '')}"]
        for trig, label in (("-P1D", "明天截止"), ("-PT1H", "1 小時後截止")):
            out += ["BEGIN:VALARM", "ACTION:DISPLAY", f"TRIGGER:{trig}",
                    f"DESCRIPTION:{_ics_escape(summary + ' ' + label)}", "END:VALARM"]
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


# ---------------------------------------------------------------- 統計
def weekly_load(assignments, today):
    """未來 4 週每週有幾份作業要交（看哪週最忙）"""
    monday = today - timedelta(days=today.weekday())
    result = []
    for w in range(4):
        start = monday + timedelta(weeks=w)
        end = start + timedelta(days=7)
        n = sum(1 for a in assignments
                if not a.get("done") and start <= datetime.fromisoformat(a["due"]).date() < end)
        result.append({"week_start": start.isoformat(), "count": n})
    return result
