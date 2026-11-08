// 前端純函式測試（Node 內建 test runner，不用安裝套件）：npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { escapeHtml, renderTask, statsText, validateTitle } from "../logic.js";

test("escapeHtml 防止 XSS", () => {
  assert.equal(escapeHtml('<img src=x onerror="alert(1)">'), "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
  assert.equal(escapeHtml(null), "");
});

test("validateTitle", () => {
  assert.equal(validateTitle("   "), "請輸入作業名稱");
  assert.equal(validateTitle("字".repeat(101)), "作業名稱不能超過 100 個字");
  assert.equal(validateTitle("HW7"), null);
});

test("statsText", () => {
  assert.equal(statsText({ total: 0, done: 0, percent: 0 }), "目前沒有作業 🎉");
  assert.equal(statsText({ total: 4, done: 1, percent: 25 }), "完成 1 / 4（25%）");
});

test("renderTask 會跳脫標題並標示完成", () => {
  const html = renderTask({ id: 3, title: "<b>x</b>", course: "", priority: 3, done: true });
  assert.match(html, /class="task done p3"/);
  assert.match(html, /&lt;b&gt;x&lt;\/b&gt;/);
  assert.match(html, /checked/);
  assert.doesNotMatch(html, /class="course"/);
});
