// 共用邏輯的單元測試（Node 內建 test runner）：npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  abbrMatch, fmt, humanize, nextClass, parseNaive, parseQuick, taipeiNow, toIcs, urgency, weeklyLoad, findConflicts,
} from "../public/lib.js";

const NOW = parseNaive("2026-11-08T10:00"); // 週日
const COURSES = [
  { id: 1, name: "軟體工程", code: "CS201", day: 2, start_period: 2, end_period: 4, room: "E321" },
  { id: 2, name: "資料結構", code: "CS203", day: 1, start_period: 2, end_period: 4, room: "E318" },
  { id: 3, name: "網頁程式設計", code: "CS204", day: 4, start_period: 6, end_period: 8, room: "B" },
];
const H = 3600e3;

test("taipeiNow 是 UTC+8", () => {
  assert.equal(fmt(taipeiNow(Date.UTC(2026, 10, 8, 16, 30))), "2026-11-09T00:30");
});

test("parseNaive 擋掉不存在的日期", () => {
  assert.equal(fmt(parseNaive("2026-02-28T08:05")), "2026-02-28T08:05");
  assert.equal(parseNaive("2026-02-30"), null);
  assert.equal(parseNaive("明天"), null);
});

test("urgency 分級", () => {
  assert.equal(urgency(new Date(NOW - 60e3), NOW), "overdue");
  assert.equal(urgency(new Date(+NOW + 5 * H), NOW), "today");
  assert.equal(urgency(new Date(+NOW + 48 * H), NOW), "soon");
  assert.equal(urgency(new Date(+NOW + 144 * H), NOW), "week");
  assert.equal(urgency(new Date(+NOW + 720 * H), NOW), "later");
  assert.equal(urgency(new Date(NOW - H), NOW, true), "done");
});

test("humanize", () => {
  assert.equal(humanize(new Date(+NOW + 51 * H), NOW), "還剩 2 天 3 小時");
  assert.equal(humanize(new Date(NOW - 30 * 60e3), NOW), "已逾期 30 分鐘");
});

test("nextClass：週日的下一堂是週一資料結構", () => {
  const nc = nextClass(COURSES, NOW);
  assert.equal(nc.name, "資料結構");
  assert.equal(nc.start, "2026-11-09T09:10");
  assert.equal(nextClass(COURSES, parseNaive("2026-11-10T10:30")).ongoing, true);
  assert.equal(nextClass([], NOW), null);
});

test("findConflicts", () => {
  assert.deepEqual(findConflicts(COURSES, { day: 2, start_period: 4, end_period: 5 }).map((c) => c.id), [1]);
  assert.deepEqual(findConflicts(COURSES, { id: 1, day: 2, start_period: 2, end_period: 4 }), []);
});

test("abbrMatch 縮寫", () => {
  assert.ok(abbrMatch("軟工", "軟體工程"));
  assert.ok(abbrMatch("資結", "資料結構"));
  assert.ok(!abbrMatch("工軟", "軟體工程"));
  assert.ok(!abbrMatch("軟", "軟體工程"));
});

test("parseQuick 各種日期", () => {
  assert.deepEqual(parseQuick("軟工 HW3 11/15 21:00", COURSES, NOW), { course_id: 1, title: "HW3", due: "2026-11-15T21:00" });
  assert.equal(parseQuick("資結 lab5 明天", COURSES, NOW).due, "2026-11-09T23:59");
  assert.equal(parseQuick("CS204 作業2 3天後", COURSES, NOW).due, "2026-11-11T23:59");
  const mon = parseNaive("2026-11-09T09:00");
  assert.equal(parseQuick("網頁 作業 週三", COURSES, mon).due, "2026-11-11T23:59");
  assert.equal(parseQuick("網頁 作業 下週三 12:00", COURSES, mon).due, "2026-11-18T12:00");
  const r = parseQuick("繳學費 1/5", COURSES, parseNaive("2026-12-20T09:00"));
  assert.equal(r.course_id, null);
  assert.equal(r.due, "2027-01-05T23:59");
});

test("parseQuick 錯誤", () => {
  assert.throws(() => parseQuick("軟工 HW3", COURSES, NOW), /找不到日期/);
  assert.throws(() => parseQuick("軟工 明天", COURSES, NOW), /缺少作業名稱/);
  assert.throws(() => parseQuick("   ", COURSES, NOW), /空的/);
});

test("toIcs", () => {
  const hws = [
    { id: 9, course_id: 1, title: "HW,1", due: "2026-11-15T23:59", done: false },
    { id: 10, course_id: 1, title: "已完成", due: "2026-11-15T23:59", done: true },
  ];
  const ics = toIcs(COURSES, hws, parseNaive("2026-09-14"), NOW);
  assert.match(ics, /RRULE:FREQ=WEEKLY;COUNT=18/);
  assert.match(ics, /DTSTART;TZID=Asia\/Taipei:20260915T091000/); // 學期第一個週二
  assert.match(ics, /SUMMARY:\[截止\] 軟體工程 HW\\,1/);
  assert.doesNotMatch(ics, /已完成/);
  assert.equal(ics.match(/BEGIN:VALARM/g).length, 2);
});

test("weeklyLoad", () => {
  const hws = [{ due: "2026-11-04T10:00" }, { due: "2026-11-12T10:00" }, { due: "2026-11-13T10:00", done: true }];
  assert.deepEqual(weeklyLoad(hws, NOW).map((w) => w.count), [1, 1, 0, 0]);
});
