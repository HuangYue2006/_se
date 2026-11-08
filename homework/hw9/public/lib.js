// DeadlineMate 共用邏輯：Worker（後端）與瀏覽器（前端）都 import 這個檔案
//
// 時間處理約定：所有時間都是「台灣當地時間」的字串，例如 "2026-11-15T23:59"。
// 在程式裡用 Date 物件表示時，把當地時間放在 UTC 欄位（getUTCHours 等），
// 這樣不管程式跑在 UTC 的 Cloudflare 機房或任何時區的瀏覽器，計算結果都一樣。

export const PERIODS = {
  1: ["08:10", "09:00"], 2: ["09:10", "10:00"], 3: ["10:10", "11:00"], 4: ["11:10", "12:00"],
  5: ["13:30", "14:20"], 6: ["14:30", "15:20"], 7: ["15:30", "16:20"], 8: ["16:30", "17:20"],
  9: ["17:30", "18:20"], 10: ["18:30", "19:20"],
};
const WEEKDAY_ZH = { 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 日: 7, 天: 7 };
const DAY_MS = 86400e3;
const pad = (n) => String(n).padStart(2, "0");

// ---------------------------------------------------------------- 時間工具
export function taipeiNow(ms = Date.now()) {
  const d = new Date(ms + 8 * 3600e3);
  d.setUTCSeconds(0, 0);
  return d;
}
export function fmt(d) {
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}
export function fmtDate(d) {
  return fmt(d).slice(0, 10);
}
export function parseNaive(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(String(s ?? ""));
  if (!m) return null;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] ?? 0), +(m[5] ?? 0)));
  return d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3] ? d : null; // 擋掉 2/30 這種日期
}
export const isoWeekday = (d) => d.getUTCDay() || 7;
export const addDays = (d, n) => new Date(d.getTime() + n * DAY_MS);
export const dayOnly = (d) => new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
function at(day, hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return new Date(dayOnly(day).getTime() + (h * 60 + m) * 60e3);
}

// ---------------------------------------------------------------- 緊急程度
export function urgency(due, now, done = false) {
  if (done) return "done";
  const diff = due - now;
  if (diff < 0) return "overdue";
  if (diff <= DAY_MS) return "today";
  if (diff <= 3 * DAY_MS) return "soon";
  if (diff <= 7 * DAY_MS) return "week";
  return "later";
}

export function humanize(due, now) {
  let secs = Math.round((due - now) / 1000);
  const past = secs < 0;
  secs = Math.abs(secs);
  const d = Math.floor(secs / 86400), h = Math.floor((secs % 86400) / 3600), m = Math.floor((secs % 3600) / 60);
  const s = d ? `${d} 天 ${h} 小時` : h ? `${h} 小時 ${m} 分` : `${m} 分鐘`;
  return past ? `已逾期 ${s}` : `還剩 ${s}`;
}

// ---------------------------------------------------------------- 課表
export function classesOn(courses, day) {
  const wd = isoWeekday(day);
  return courses.filter((c) => c.day === wd).sort((a, b) => a.start_period - b.start_period);
}

export function nextClass(courses, now) {
  for (let off = 0; off < 8; off++) {
    const day = addDays(dayOnly(now), off);
    for (const c of classesOn(courses, day)) {
      const start = at(day, PERIODS[c.start_period][0]);
      const end = at(day, PERIODS[c.end_period][1]);
      if (end > now) return { ...c, start: fmt(start), end: fmt(end), ongoing: start <= now };
    }
  }
  return null;
}

export function findConflicts(courses, n) {
  return courses.filter((c) => c.id !== n.id && c.day === n.day &&
    c.start_period <= n.end_period && n.start_period <= c.end_period);
}

export function weeklyLoad(assignments, today) {
  const monday = addDays(dayOnly(today), -(isoWeekday(today) - 1));
  return [0, 1, 2, 3].map((w) => {
    const start = addDays(monday, 7 * w), end = addDays(start, 7);
    const count = assignments.filter((a) => {
      const d = parseNaive(a.due);
      return !a.done && d && d >= start && d < end;
    }).length;
    return { week_start: fmtDate(start), count };
  });
}

// ---------------------------------------------------------------- 一句話新增
export function abbrMatch(abbr, name) {
  const chars = [...name];
  if ([...abbr].length < 2) return false;
  let i = 0;
  for (const ch of abbr) {
    i = chars.indexOf(ch, i);
    if (i < 0) return false;
    i++;
  }
  return true;
}

function ymd(y, m, d) {
  return parseNaive(`${y}-${pad(m)}-${pad(d)}`);
}

export function parseDate(tk, today) {
  today = dayOnly(today);
  if (tk === "今天" || tk === "today") return today;
  if (tk === "明天" || tk === "tomorrow") return addDays(today, 1);
  if (tk === "後天") return addDays(today, 2);
  let m = /^(\d+)天後$/.exec(tk);
  if (m) return addDays(today, +m[1]);
  m = /^(本|這|下)?(?:週|周|星期|禮拜)([一二三四五六日天])$/.exec(tk);
  if (m) {
    const target = WEEKDAY_ZH[m[2]], cur = isoWeekday(today);
    if (m[1] === "下") return addDays(today, 8 - cur + target - 1);
    return addDays(today, (((target - cur) % 7) + 7) % 7);
  }
  m = /^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/.exec(tk);
  if (m) return ymd(+m[1], +m[2], +m[3]);
  m = /^(\d{1,2})[/-](\d{1,2})$/.exec(tk);
  if (m) {
    let d = ymd(today.getUTCFullYear(), +m[1], +m[2]);
    if (d && d < addDays(today, -60)) d = ymd(today.getUTCFullYear() + 1, +m[1], +m[2]);
    return d;
  }
  return null;
}

/** 「軟工 HW3 11/15 23:59」→ { course_id, title, due } ；失敗丟 Error */
export function parseQuick(text, courses, now) {
  const tokens = String(text ?? "").trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) throw new Error("內容是空的");

  const first = tokens[0].toLowerCase();
  const course =
    courses.find((c) => first === c.name.toLowerCase() || first === (c.code || "").toLowerCase()) ||
    courses.find((c) => abbrMatch(first, c.name.toLowerCase()));
  if (course) tokens.shift();

  let hhmm = "23:59";
  const ti = tokens.findIndex((t) => /^\d{1,2}:\d{2}$/.test(t));
  if (ti >= 0) {
    const [h, mi] = tokens[ti].split(":").map(Number);
    if (h > 23 || mi > 59) throw new Error("時間格式錯誤");
    hhmm = `${pad(h)}:${pad(mi)}`;
    tokens.splice(ti, 1);
  }

  let due = null;
  for (let i = 0; i < tokens.length; i++) {
    const d = parseDate(tokens[i], now);
    if (d) {
      due = d;
      tokens.splice(i, 1);
      break;
    }
  }
  if (!due) throw new Error("找不到日期，例如 11/15、明天、下週三、3天後");
  const title = tokens.join(" ").trim();
  if (!title) throw new Error("缺少作業名稱");
  return { course_id: course ? course.id : null, title, due: `${fmtDate(due)}T${hhmm}` };
}

// ---------------------------------------------------------------- iCalendar
const icsEsc = (s) => String(s ?? "").replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
const icsDt = (d) => fmt(d).replace(/[-:]/g, "") + "00";

export function toIcs(courses, assignments, semesterStart, now, weeks = 18) {
  const byId = Object.fromEntries(courses.map((c) => [c.id, c]));
  const out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NQU//DeadlineMate Cloud//ZH", "CALSCALE:GREGORIAN",
    "X-WR-CALNAME:課表與作業", "X-WR-TIMEZONE:Asia/Taipei"];
  const stamp = icsDt(now);
  for (const c of courses) {
    const first = addDays(dayOnly(semesterStart), (((c.day - isoWeekday(semesterStart)) % 7) + 7) % 7);
    out.push("BEGIN:VEVENT", `UID:course-${c.id}@deadlinemate`, `DTSTAMP:${stamp}`,
      `DTSTART;TZID=Asia/Taipei:${icsDt(at(first, PERIODS[c.start_period][0]))}`,
      `DTEND;TZID=Asia/Taipei:${icsDt(at(first, PERIODS[c.end_period][1]))}`,
      `RRULE:FREQ=WEEKLY;COUNT=${weeks}`, `SUMMARY:${icsEsc(c.name)}`, `LOCATION:${icsEsc(c.room)}`, "END:VEVENT");
  }
  for (const a of assignments) {
    if (a.done) continue;
    const due = parseNaive(a.due);
    if (!due) continue;
    const cname = byId[a.course_id]?.name;
    const summary = `[截止] ${cname ? cname + " " : ""}${a.title}`;
    out.push("BEGIN:VEVENT", `UID:hw-${a.id}@deadlinemate`, `DTSTAMP:${stamp}`,
      `DTSTART;TZID=Asia/Taipei:${icsDt(new Date(due - 30 * 60e3))}`, `DTEND;TZID=Asia/Taipei:${icsDt(due)}`,
      `SUMMARY:${icsEsc(summary)}`, `DESCRIPTION:${icsEsc(a.note)}`);
    for (const [trig, label] of [["-P1D", "明天截止"], ["-PT1H", "1 小時後截止"]]) {
      out.push("BEGIN:VALARM", "ACTION:DISPLAY", `TRIGGER:${trig}`, `DESCRIPTION:${icsEsc(summary + " " + label)}`, "END:VALARM");
    }
    out.push("END:VEVENT");
  }
  out.push("END:VCALENDAR");
  return out.join("\r\n") + "\r\n";
}
